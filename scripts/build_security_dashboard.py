import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
datasource = {"type": "loki", "uid": "aegisai-loki"}
panels = []


def target(expression, instant=False, legend=""):
    return {
        "refId": "A",
        "datasource": datasource,
        "expr": expression,
        "queryType": "instant" if instant else "range",
        "legendFormat": legend,
        "editorMode": "code",
    }


def stat(panel_id, title, event_pattern, x, description):
    expression = (
        'sum(count_over_time('
        '{job="aegisai",service="backend",'
        f'event_type=~"{event_pattern}"'
        '}[$__range]))'
    )
    panels.append({
        "id": panel_id,
        "type": "stat",
        "title": title,
        "description": description,
        "datasource": datasource,
        "gridPos": {"x": x, "y": 0, "w": 6, "h": 5},
        "targets": [target(expression, instant=True)],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "decimals": 0,
                "noValue": "Aucun résultat",
                "color": {"mode": "fixed", "fixedColor": "orange"},
            },
            "overrides": [],
        },
        "options": {
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False,
            },
            "orientation": "auto",
            "textMode": "value",
            "colorMode": "value",
            "graphMode": "none",
        },
    })


stat(
    1, "Échecs d’authentification",
    "login_failure|authentication_rejected", 0,
    "Nombre d’événements backend dans la période sélectionnée. "
    "Inclut les tokens absents ou invalides et les logins refusés.",
)
stat(
    2, "Refus d’autorisation",
    "authorization_denied", 6,
    "Événements authorization_denied. "
    "Les réponses 404 masquant une ressource d’un autre tenant "
    "ne sont pas automatiquement classées dans cette catégorie.",
)
stat(
    3, "Instructions suspectes",
    "prompt_injection_suspected", 12,
    "Messages marqués suspects par les règles du gate. "
    "Ce compteur ne représente pas toutes les attaques possibles.",
)
stat(
    4, "Autres rejets du gate",
    "intent_gate_rejected", 18,
    "Inclut les intentions désactivées et les formulations "
    "hors périmètre ou non reconnues, y compris des faux rejets possibles.",
)

panels.append({
    "id": 5,
    "type": "timeseries",
    "title": "Requêtes API via Nginx — par résultat HTTP",
    "description": "Nombre de requêtes dans des fenêtres de 5 minutes. "
                   "Les healthchecks /healthz sont exclus.",
    "datasource": datasource,
    "gridPos": {"x": 0, "y": 5, "w": 12, "h": 8},
    "targets": [target(
        'sum by (status_code) (count_over_time('
        '{job="aegisai",service="frontend",event_type="nginx_access"}'
        ' | json | path =~ "^/api/.*" | __error__="" [5m]))',
        legend="HTTP {{status_code}}",
    )],
    "fieldConfig": {
        "defaults": {"unit": "short", "decimals": 0},
        "overrides": [],
    },
    "options": {
        "legend": {"displayMode": "list", "placement": "bottom"},
        "tooltip": {"mode": "multi"},
    },
})

panels.append({
    "id": 6,
    "type": "timeseries",
    "title": "Événements de sécurité — fenêtres de 5 minutes",
    "description": "Chaque série compte un type d’événement backend. "
                   "Les événements métier et HTTP restent distincts.",
    "datasource": datasource,
    "gridPos": {"x": 12, "y": 5, "w": 12, "h": 8},
    "targets": [target(
        'sum by (event_type) (count_over_time('
        '{job="aegisai",service="backend",'
        'event_type=~"login_failure|authentication_rejected|'
        'authorization_denied|prompt_injection_suspected|'
        'intent_gate_rejected|rate_limited"}[5m]))',
        legend="{{event_type}}",
    )],
    "fieldConfig": {
        "defaults": {"unit": "short", "decimals": 0},
        "overrides": [],
    },
    "options": {
        "legend": {"displayMode": "list", "placement": "bottom"},
        "tooltip": {"mode": "multi"},
    },
})

panels.append({
    "id": 7,
    "type": "logs",
    "title": "Événements backend récents",
    "description": "Dépliez une ligne pour consulter son Trace ID. "
                   "Les identités non vérifiées peuvent rester nulles.",
    "datasource": datasource,
    "gridPos": {"x": 0, "y": 13, "w": 24, "h": 10},
    "targets": [{
        **target('{job="aegisai",service="backend",event_type=~".+"}'),
        "maxLines": 200,
    }],
    "options": {
        "showTime": True,
        "showLabels": False,
        "showCommonLabels": False,
        "wrapLogMessage": True,
        "prettifyLogMessage": True,
        "sortOrder": "Descending",
        "enableLogDetails": True,
        "dedupStrategy": "none",
    },
})

dashboard = {
    "uid": "aegisai-security",
    "title": "AegisAI — Security Overview",
    "description": (
        "Console SOC centrale, réservée aux administrateurs de supervision. "
        "Les compteurs portent sur les logs reçus dans la période sélectionnée. "
        "L’absence de résultat ne prouve pas que la collecte fonctionne."
    ),
    "tags": ["AegisAI", "security", "SOC"],
    "schemaVersion": 39,
    "version": 1,
    "editable": False,
    "timezone": "browser",
    "refresh": "30s",
    "time": {"from": "now-1h", "to": "now"},
    "templating": {"list": []},
    "annotations": {"list": []},
    "panels": panels,
}

output = (
    root / "infra/monitoring/grafana/provisioning"
    / "dashboards/definitions/aegisai-security.json"
)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2))
print(f"Dashboard générée : {output}")
