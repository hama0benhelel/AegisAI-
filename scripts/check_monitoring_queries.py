"""Ask the deployed Loki parser to validate every new alert/dashboard query."""
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
files = [
    root / 'infra/monitoring/grafana/provisioning/alerting/aegisai-agent-security.json',
    root / 'infra/monitoring/grafana/provisioning/dashboards/definitions/aegisai-agent-security.json',
]
for path in files:
    document = json.loads(path.read_text())
    items = [rule for group in document.get('groups', []) for rule in group['rules']] or document['panels']
    for item in items:
        queries = item.get('data', []) if 'groups' in document else item.get('targets', [])
        for query in queries:
            model = query.get('model', query)
            expression = model.get('expr')
            if not expression:
                continue
            params = {'query': expression}
            if model.get('queryType') == 'instant':
                endpoint = '/loki/api/v1/query'
            else:
                endpoint = '/loki/api/v1/query_range'
                params.update(limit='1', since='5m', step='30s')
            try:
                with urlopen('http://127.0.0.1:3100' + endpoint + '?' + urlencode(params), timeout=20) as response:
                    result = json.load(response)
                if result.get('status') != 'success':
                    raise ValueError('Query failed')
            except HTTPError as error:
                detail = error.read(400).decode(errors='replace')
                raise SystemExit(f"FAIL : {item.get('title')} HTTP {error.code}: {detail}") from None
            except (URLError, TimeoutError, ValueError):
                raise SystemExit(f"FAIL : Loki indisponible ou réponse invalide pour {item.get('title')}") from None
            print('PASS : Loki accepte — ' + item['title'])
print('Toutes les nouvelles requêtes ont été acceptées par Loki.')
