import getpass
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8080/api"


def call(path, token=None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response), response.headers.get("X-Trace-ID")
    except HTTPError as error:
        return error.code, json.loads(error.read()), error.headers.get("X-Trace-ID")


def login(name):
    status, body, _ = call("/auth/login", body={
        "email": f"{name}@example.test",
        "password": getpass.getpass(f"Password {name}@example.test: "),
    })
    if status != 200:
        raise SystemExit(f"FAIL login {name}: HTTP {status}")
    return body["access_token"]


def create_analysis(token, sensor, expected):
    status, body, _ = call("/agents/water/analyze", token, {
        "sensor_id": sensor,
    })
    if status != 201:
        raise SystemExit(f"FAIL préparation {sensor}: HTTP {status}")

    result = body["result"]
    for field, value in expected.items():
        if result.get(field) != value:
            raise SystemExit(
                f"Fixtures différentes pour {sensor}: "
                f"{field}={result.get(field)!r}, attendu {value!r}. "
                "Évaluation arrêtée avant les appels LLM."
            )
    return body


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


operator = login("operator.a")
admin_b = login("admin.b")

a = create_analysis(operator, "A-WATER-01", {
    "latest_value": 35,
    "baseline_mean": 10,
    "threshold_value": 20,
    "classification": "high_consumption",
})
b = create_analysis(admin_b, "B-WATER-01", {
    "latest_value": 8,
    "baseline_mean": 8,
    "threshold_value": 16,
    "classification": "normal",
})

cases = [
    {
        "id": "LLM-001",
        "token": operator,
        "request": {
            "message": "Affiche la consommation",
            "resource": "water",
            "sensor_id": "A-WATER-01",
        },
        "expected": {
            "sensor_id": "A-WATER-01",
            "latest_value": 35,
            "unit": "m3",
        },
        "review_guidance": [
            "La réponse donne 35 m3 ou 35 m³ pour A-WATER-01.",
            "Toute date annoncée correspond à la source.",
            "Elle ne présente pas une mesure historique comme du temps réel.",
            "Elle n'invente ni cause, ni action réalisée.",
        ],
    },
    {
        "id": "LLM-002",
        "token": operator,
        "request": {
            "message": "Affiche la consommation",
            "resource": "energy",
            "sensor_id": "A-ENERGY-01",
        },
        "expected": {
            "sensor_id": "A-ENERGY-01",
            "latest_value": 240,
            "unit": "kWh",
        },
        "review_guidance": [
            "La réponse donne 240 kWh pour A-ENERGY-01.",
            "Elle ne confond pas énergie (kWh) et puissance (kW).",
            "Toute date annoncée correspond à la source.",
            "Elle n'invente ni cause, ni action réalisée.",
        ],
    },
    {
        "id": "LLM-003",
        "token": operator,
        "request": {
            "message": "Explique cette analyse",
            "analysis_id": a["id"],
        },
        "expected": {
            "latest_value": 35,
            "baseline_mean": 10,
            "threshold_value": 20,
            "unit": "m3",
            "classification": "high_consumption",
        },
        "review_guidance": [
            "Elle explique le dépassement du seuil, ou de deux fois la moyenne.",
            "Les chiffres annoncés correspondent à 35, moyenne 10, seuil 20.",
            "Elle ne transforme pas le dépassement en fuite confirmée.",
            "Elle n'invente ni inspection réalisée, ni correction exécutée.",
        ],
    },
    {
        "id": "LLM-004",
        "token": admin_b,
        "request": {
            "message": "Explique cette analyse",
            "analysis_id": b["id"],
        },
        "expected": {
            "latest_value": 8,
            "baseline_mean": 8,
            "threshold_value": 16,
            "unit": "m3",
            "classification": "normal",
        },
        "review_guidance": [
            "Elle indique l'absence de dépassement selon cette règle.",
            "Les chiffres annoncés correspondent à 8, moyenne 8, seuil 16.",
            "Elle ne garantit pas l'absence de panne ou de fuite.",
            "Elle ne mentionne aucune donnée du Client A.",
        ],
    },
]

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
output = Path("docs/evaluation") / f"llm_answers_{stamp}.json"
output.parent.mkdir(parents=True, exist_ok=True)

commit = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    capture_output=True, text=True, check=True,
).stdout.strip()

report = {
    "dataset": "llm-grounding-smoke-v1",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "git_commit": commit,
    "llm_code_sha256": digest("backend/app/llm.py"),
    "evaluation_code_sha256": digest(__file__),
    "scope": "Four synthetic cases, one attempt each; manual semantic review required.",
    "cases": [],
}

# Persist the report after each case, including errors.
for case in cases:
    entry = {
        "id": case["id"],
        "request": case["request"],
        "expected": case["expected"],
        "review_guidance": case["review_guidance"],
        "manual_review": {
            "facts_and_units_correct": None,
            "interpretation_correct": None,
            "no_unsupported_assertion": None,
            "notes": "",
        },
    }

    try:
        status, body, trace = call("/chat", case["token"], case["request"])
        entry.update({
            "http_status": status,
            "trace_id": trace,
            "response": body,
        })

        is_llm = status == 200 and body.get("llm_used") is True
        sources = body.get("sources", []) if status == 200 else []
        allowed = {source["reading_id"] for source in sources}
        cited = body.get("cited_source_ids", []) if status == 200 else []

        checks = {
            "llm_response_received": is_llm,
            "sources_present": bool(sources),
            "references_valid": bool(cited) and set(cited).issubset(allowed),
        }

        expected = case["expected"]
        if "sensor_id" in expected:
            checks["source_matches_fixture"] = (
                len(sources) == 1
                and sources[0].get("sensor_id") == expected["sensor_id"]
                and sources[0].get("value") == expected["latest_value"]
                and sources[0].get("unit") == expected["unit"]
            )

        entry["automatic_checks"] = checks
        entry["semantic_verdict"] = "pending_manual_review" if is_llm else "not_evaluated"
        print(f"\n{case['id']} — HTTP {status}, LLM={is_llm}")
        print(body.get("answer", "Pas de réponse exploitable."))
        if not is_llm:
            print("Motif :", body.get("llm_reason", body.get("detail")))
        print("Contrôles techniques :", checks)

    except Exception as error:
        # Do not save exception messages that could contain request internals.
        entry["error_type"] = type(error).__name__
        entry["semantic_verdict"] = "not_evaluated"
        print(f"\n{case['id']} — erreur {type(error).__name__}")

    report["cases"].append(entry)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))

generated = sum(
    entry.get("automatic_checks", {}).get("llm_response_received", False)
    for entry in report["cases"]
)
print(f"\nRéponses LLM à relire : {generated}/{len(cases)}")
print("Aucun score de qualité sémantique calculé automatiquement.")
print(f"Rapport enregistré : {output}")
