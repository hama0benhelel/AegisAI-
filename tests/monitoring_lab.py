"""Shared local-lab helpers. Credentials remain in memory, never in reports or argv."""
import base64
from datetime import datetime, timezone
import getpass
import json
import math
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['sudo','docker','compose','-f','compose.yaml','-f','compose.monitoring.yaml','-f','compose.agents.yaml','-f','compose.simulation.yaml']
CASES = json.loads((ROOT / 'tests/monitoring_alert_cases.json').read_text())

def utc():
    return datetime.now(timezone.utc).isoformat()

def api(path, token=None, body=None):
    headers = {'Content-Type':'application/json'} if body is not None else {}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request('http://127.0.0.1:8000'+path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urlopen(req,timeout=25) as response:
            return response.status,json.load(response),response.headers.get('X-Trace-ID')
    except HTTPError as error:
        return error.code,json.load(error),error.headers.get('X-Trace-ID')

def check_http(label, response, expected):
    status,data,trace = response
    if status != expected or not trace:
        raise RuntimeError(f'{label}: attendu {expected} avec Trace ID, reçu {status}')
    UUID(trace)
    print(f'PASS : {label} -> {status} | trace={trace}',flush=True)
    return data,trace

def login_client():
    password = getpass.getpass('Password client.a@example.test: ')
    auth,_ = check_http('login client A',api('/auth/login',body={'email':'client.a@example.test','password':password}),200)
    del password
    token = auth['access_token']
    user,_ = check_http('identité client A',api('/auth/me',token),200)
    if user['role'] != 'client':
        raise RuntimeError('Compte client attendu')
    return token,user

def compose(*args, input=None, quiet=False):
    result = subprocess.run(COMPOSE+list(args),cwd=ROOT,input=input,text=True,capture_output=quiet)
    if result.returncode:
        raise RuntimeError('Commande Compose échouée : '+ ' '.join(args[:3]))
    return result.stdout if quiet else None

def sql(query):
    result = compose('exec','-T','db','psql','-X','-q','-A','-t','-U','postgres','-d','aegisai','-v','ON_ERROR_STOP=1',input=query,quiet=True)
    return json.loads(result)

def counts(user):
    tenant = str(UUID(user['tenant_id']))
    fields = ','.join(f"'{name}',(SELECT count(*) FROM bws_ai.{name} WHERE tenant_id='{tenant}'::uuid)" for name in ('analyses','chat_confirmations','proposals','tasks','llm_calls'))
    return sql('SELECT json_build_object('+fields+');')

def loki(query, logs=False):
    endpoint = '/loki/api/v1/query_range' if logs else '/loki/api/v1/query'
    params = {'query':query}
    if logs:
        params.update(since='10m',limit='100',direction='backward')
    with urlopen('http://127.0.0.1:3100'+endpoint+'?'+urlencode(params),timeout=12) as response:
        data = json.load(response)
    if data.get('status') != 'success':
        raise RuntimeError('Loki ne retourne pas de succès')
    return data['data']['result']

def metric(kind,labels):
    values = []
    for row in loki(CASES[kind]['query']):
        if all(row['metric'].get(k)==v for k,v in labels.items()):
            value = float(row['value'][1])
            if not math.isfinite(value):
                raise RuntimeError('Métrique non finie')
            values.append(value)
    return sum(values)

def wait_log(event_type,trace,timeout=60):
    trace = str(UUID(trace))
    query = '{job="aegisai",service="backend",event_type="'+event_type+'"} | json trace_id="trace_id" | __error__="" | trace_id="'+trace+'"'
    deadline = time.monotonic()+timeout
    while time.monotonic()<deadline:
        rows = loki(query,logs=True)
        events = [json.loads(line) for stream in rows for _,line in stream['values']]
        if events:
            return events
        time.sleep(2)
    raise RuntimeError('Événement non reçu dans Loki pour la trace '+trace)

class Grafana:
    def __init__(self):
        password = getpass.getpass('Password Grafana soc_admin: ')
        self.authorization = 'Basic '+base64.b64encode(('soc_admin:'+password).encode()).decode()
        del password
    def get(self,path):
        try:
            with urlopen(Request('http://127.0.0.1:3000'+path,headers={'Authorization':self.authorization}),timeout=12) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Grafana HTTP {error.code} sur son API de lecture') from None
    def definition(self,kind):
        expected = CASES[kind]
        rule = self.get('/api/v1/provisioning/alert-rules/'+expected['uid'])
        expressions = {item['refId']:item['model'] for item in rule['data']}
        if expressions['A'].get('expr') != expected['query'] or expressions['B'].get('expression') != '$A >= '+str(expected['threshold']):
            raise RuntimeError('Définition de règle différente du scénario de test')
        if rule.get('isPaused'):
            raise RuntimeError('Règle en pause')
    def state(self,kind,labels):
        data = self.get('/api/prometheus/grafana/api/v1/rules')
        if data.get('status') != 'success':
            raise RuntimeError('API d’état Grafana invalide')
        rules = [rule for group in data.get('data',{}).get('groups',[]) for rule in group.get('rules',[])]
        rule = next((rule for rule in rules if rule.get('name') in {CASES[kind]['title'], CASES[kind]['uid']} or rule.get('uid')==CASES[kind]['uid']),None)
        if not rule:
            return 'initializing'
        health = str(rule.get('health','')).lower()
        if health in {'unknown',''}:
            return 'initializing'
        if health != 'ok' or rule.get('lastError'):
            raise RuntimeError('Erreur d’évaluation de la règle Grafana, examiner son health/lastError')
        active = [alert for alert in rule.get('alerts',[]) if all(alert.get('labels',{}).get(k)==v for k,v in labels.items())]
        states = {str(alert.get('state','')).lower() for alert in active}
        if 'firing' in states or 'alerting' in states:
            return 'firing'
        if 'pending' in states:
            return 'pending'
        if states - {'inactive','normal','resolved',''}:
            raise RuntimeError('État d’instance non reconnu')
        return 'normal'

def wait_state(grafana,kind,labels,desired,timeout,record):
    deadline = time.monotonic()+timeout
    last = None
    last_progress = 0
    while time.monotonic()<deadline:
        state = grafana.state(kind,labels)
        value = metric(kind,labels)
        if state != last:
            row = {'at':utc(),'state':state,'metric':value,'labels':labels}
            record.append(row)
            print('État Grafana : '+state+' | compteur='+str(value),flush=True)
            last = state
            last_progress = time.monotonic()
        elif time.monotonic()-last_progress >= 30:
            remaining = max(0, int(deadline-time.monotonic()))
            print(f'Attente de {desired} : état={state}, compteur={value}, délai restant={remaining}s',flush=True)
            last_progress = time.monotonic()
        threshold = CASES[kind]['threshold']
        if state == desired and ((desired=='firing' and value>=threshold) or (desired=='normal' and value<threshold)):
            return
        time.sleep(10)
    raise RuntimeError('Délai dépassé pour état '+desired+' ; vérifier les évaluations et les autres demandes du même compte/service')

def save(kind,report):
    folder = ROOT/'docs/evaluation';folder.mkdir(parents=True,exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = folder/f'monitoring_{kind}_{stamp}.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Rapport :',path,flush=True)
