import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def rule(uid, title, query, condition, description, severity):
    return {
        "uid": uid,
        "title": title,
        "condition": "B",
        "for": "30s",
        "noDataState": "NoData",
        "execErrState": "Error",
        "isPaused": False,
        "labels": {
            "project": "aegisai",
            "severity": severity,
        },
        "annotations": {
            "summary": title,
            "description": description,
        },
        "data": [
            {
                "refId": "A",
                "relativeTimeRange": {"from": 300, "to": 0},
                "datasourceUid": "aegisai-loki",
                "model": {
                    "refId": "A",
                    "datasource": {
                        "type": "loki",
                        "uid": "aegisai-loki",
                    },
                    "expr": query,
                    "queryType": "instant",
                    "instant": True,
                    "range": False,
                    "editorMode": "code",
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                },
            },
            {
                "refId": "B",
                "relativeTimeRange": {"from": 0, "to": 0},
                "datasourceUid": "__expr__",
                "model": {
                    "refId": "B",
                    "datasource": {
                        "type": "__expr__",
                        "uid": "__expr__",
                    },
                    "type": "math",
                    "expression": condition,
                    "intervalMs": 1000,
                    "maxDataPoints": 43200,
                },
            },
        ],
    }


rules = [
    rule(
        "aegisai-auth-failures",
        "AegisAI — Refus d’authentification répétés",
        'sum(count_over_time('
        '{job="aegisai",service="backend",'
        'event_type=~"login_failure|authentication_rejected"}[5m]))'
        ' or vector(0)',
        "$A >= 5",
        "Au moins 5 refus dans une fenêtre de 5 minutes. "
        "Examiner les routes et Trace IDs avant de conclure à une attaque.",
        "warning",
    ),
    rule(
        "aegisai-nginx-log-gap",
        "AegisAI — Healthchecks absents des logs",
        'sum(absent_over_time('
        '{job="aegisai",service="frontend",event_type="nginx_access"}'
        ' | json | path="/healthz" | __error__="" [2m]))'
        ' or vector(0)',
        "$A > 0",
        "Aucun healthcheck Nginx reçu depuis 2 minutes. "
        "Vérifier frontend, Alloy, chemins des logs et Loki. "
        "Cette alerte ne localise pas à elle seule la panne.",
        "warning",
    ),
]

document = {
    "apiVersion": 1,
    "groups": [{
        "orgId": 1,
        "name": "aegisai-security",
        "folder": "AegisAI SOC",
        "interval": "30s",
        "rules": rules,
    }],
}

output = (
    root / "infra/monitoring/grafana/provisioning"
    / "alerting/aegisai-security.json"
)
output.write_text(json.dumps(document, ensure_ascii=False, indent=2))
print(f"Deux alertes générées : {output}")
