"""Controlled gas-agent stop, one API request, unconditional service restoration."""
import json
import signal
import time
from monitoring_lab import Grafana, api, check_http, compose, counts, login_client, metric, save, utc, wait_log, wait_state

HEALTH_PROBE = '''import json, os, ssl
from urllib.request import HTTPSHandler, ProxyHandler, build_opener
from app.gas_client import NoRedirect
assert os.environ['GAS_AGENT_URL'] == 'https://gas-agent:8443'
context = ssl.create_default_context(cafile=os.environ['AGENT_CA_FILE'])
context.load_cert_chain(os.environ['AGENT_CERT_FILE'], os.environ['AGENT_KEY_FILE'])
opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), NoRedirect())
with opener.open('https://gas-agent:8443/health/live', timeout=3) as response:
    data = json.load(response)
    assert response.status == 200 and data.get('service') == 'gas-agent'
print('gas-agent TLS health OK')
'''

def health():
    deadline = time.monotonic()+35
    while time.monotonic()<deadline:
        try:
            compose('exec','-T','backend','python','-',input=HEALTH_PROBE,quiet=True)
            return
        except RuntimeError:
            time.sleep(2)
    raise RuntimeError('Probe mTLS de gas-agent non réussie ; examiner le service et ses certificats')

def interrupted(signum,frame):
    raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,interrupted)
report={'scenario':'gas-agent-failure-alert-v1','started_at':utc(),'result':'failed','transitions':[],'restored':False}
restore_needed=False
try:
    token,user = login_client()
    grafana = Grafana()
    grafana.definition('agent')
    labels={'target_service':'gas-agent'}
    report['labels']=labels
    health()
    if metric('agent',labels)!=0:
        raise RuntimeError('Des erreurs gas-agent existent déjà dans les 2 dernières minutes. Attendre une fenêtre calme.')
    wait_state(grafana,'agent',labels,'normal',90,report['transitions'])
    before=counts(user);report['counts_before']=before
    try:
        restore_needed=True
        compose('stop','gas-agent')
        data,trace=check_http('analyse avec agent gaz arrêté',api('/chat',token,{
            'message':'Analyse la consommation','resource':'gas','sensor_id':'A-SIM-GAS-01',
        }),503)
        report['trace_id']=trace
        after=counts(user);report['counts_after']=after
        if before!=after:
            raise RuntimeError('Une analyse, confirmation, tâche, proposition ou réservation LLM a été créée malgré l’échec')
        print('PASS : aucune création métier pendant la panne',flush=True)
    finally:
        if restore_needed:
            compose('up','-d','--no-deps','--pull','never','gas-agent')
            restore_needed=False
            health()
            report['restored']=True
            print('PASS : gas-agent redémarré et probe mTLS réussie',flush=True)
    events=wait_log('agent_call_failed',trace)
    if len(events)!=1 or events[0].get('target_service')!='gas-agent' or events[0].get('tenant_id')!=user['tenant_id'] or events[0].get('user_id')!=user['id']:
        raise RuntimeError('Attribution ou unicité incorrecte pour agent_call_failed')
    http_events=wait_log('server_error',trace)
    if len(http_events)!=1 or http_events[0].get('status_code')!=503:
        raise RuntimeError('Erreur HTTP 503 non corrélée dans Loki')
    print('PASS : événement agent et erreur HTTP corrélés par le même Trace ID',flush=True)
    wait_state(grafana,'agent',labels,'firing',120,report['transitions'])
    print('PASS : Grafana Firing ; l’agent est déjà rétabli, la fenêtre de 2 minutes doit expirer.',flush=True)
    wait_state(grafana,'agent',labels,'normal',300,report['transitions'])
    report['result']='passed'
    print('PASS : Normal → Firing → Normal pour les erreurs d’appel gas-agent.',flush=True)
except (Exception,KeyboardInterrupt) as error:
    report['error']='interrupted' if isinstance(error,KeyboardInterrupt) else str(error)
    print('FAIL : '+report['error'],flush=True)
finally:
    if restore_needed:
        try:
            compose('up','-d','--no-deps','--pull','never','gas-agent')
            health();report['restored']=True
        except Exception:
            report['restored']=False
            print('IMPORTANT : redémarrer gas-agent manuellement avec aegis up -d --no-deps gas-agent.',flush=True)
    report['completed_at']=utc()
    save('agent',report)
if report['result']!='passed':
    raise SystemExit(1)
