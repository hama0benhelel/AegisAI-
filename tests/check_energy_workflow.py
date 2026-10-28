import getpass
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"


def call(path, token=None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = Request(
        BASE + path,
        headers=headers,
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urlopen(request, timeout=25) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def check(label, result, expected):
    status, body = result
    if status != expected:
        raise SystemExit(
            f"FAIL: {label}: attendu {expected}, reçu {status}"
        )
    print(f"PASS: {label} -> {status}")
    return body


def verify(condition, label):
    if not condition:
        raise SystemExit(f"FAIL: {label}")
    print(f"PASS: {label}")


tokens = {}
identities = {}

for name in ("a", "b"):
    email = f"client.{name}@example.test"
    password = getpass.getpass(f"Password {email}: ")
    auth = check(
        f"login client {name}",
        call("/auth/login", body={"email": email, "password": password}),
        200,
    )
    del password
    tokens[name] = auth["access_token"]
    identities[name] = check(
        f"identité client {name}",
        call("/auth/me", tokens[name]),
        200,
    )
    verify(identities[name]["role"] == "client", f"rôle client {name}")

a, b = tokens["a"], tokens["b"]
verify(
    identities["a"]["tenant_id"] != identities["b"]["tenant_id"],
    "les comptes appartiennent à deux tenants différents",
)

check("sans authentification", call("/readings"), 401)

for name in ("a", "b"):
    readings = check(
        f"lecture client {name}", call("/readings", tokens[name]), 200
    )
    verify(bool(readings["items"]), f"mesures disponibles pour {name}")
    verify(
        all(row["sensor_id"].startswith(f"{name.upper()}-")
            for row in readings["items"]),
        f"mesures synthétiques limitées au client {name}",
    )
    for route in ("/security/audit", "/security/llm-calls"):
        check(
            f"journal technique interdit au client {name}: {route}",
            call(route, tokens[name]),
            403,
        )

check(
    "tenant B demandé explicitement par A",
    call(f"/readings?tenant_id={identities['b']['tenant_id']}", a),
    403,
)

analysis_request = {
    "message": "Analyse la consommation",
    "resource": "energy",
    "sensor_id": "A-ENERGY-01",
}

check(
    "client B demande une analyse du compteur A",
    call("/chat", b, analysis_request),
    404,
)

prepared = check(
    "client A prépare son analyse",
    call("/chat", a, analysis_request),
    200,
)
verify(prepared.get("needs_confirmation") is True, "confirmation requise")
verify(not prepared.get("analysis_id"), "aucune analyse déjà enregistrée")
pending = prepared["confirmation"]
verify(pending["status"] == "pending", "demande en attente")
decision_path = f"/chat/confirmations/{pending['id']}/decision"

check(
    "confirmation par B interdite",
    call(decision_path, b, {"decision": "confirm"}),
    404,
)
check(
    "modification du contenu refusée",
    call(decision_path, a, {
        "decision": "confirm", "sensor_id": "B-ENERGY-01",
    }),
    422,
)
confirmed = check(
    "A confirme personnellement",
    call(decision_path, a, {"decision": "confirm"}),
    200,
)
verify(confirmed["status"] == "confirmed", "analyse confirmée")
saved = check(
    "A consulte son analyse",
    call(f"/analyses/{confirmed['analysis_id']}", a),
    200,
)
verify(
    saved["result"] == pending["preview"],
    "analyse enregistrée identique à la prévisualisation",
)
check(
    "B ne lit pas l’analyse A",
    call(f"/analyses/{confirmed['analysis_id']}", b),
    404,
)
repeated = check(
    "répétition de confirmation",
    call(decision_path, a, {"decision": "confirm"}),
    200,
)
verify(
    repeated["analysis_id"] == confirmed["analysis_id"]
    and repeated["already_processed"] is True,
    "répétition sans nouvelle analyse",
)

proposal_body = {
    "sensor_id": "A-ENERGY-01",
    "title": "Inspection de démonstration du compte client A",
}
check(
    "statut forcé refusé",
    call("/proposals", a, {**proposal_body, "status": "approved"}),
    422,
)
proposal = check(
    "A prépare une proposition",
    call("/proposals", a, proposal_body),
    201,
)
verify(proposal["status"] == "pending", "proposition en attente")
path = f"/proposals/{proposal['id']}"

check("B ne lit pas la proposition A", call(path, b), 404)
check(
    "B ne peut pas approuver la proposition A",
    call(path + "/decision", b, {"decision": "approve"}),
    404,
)
check(
    "exécution sans confirmation refusée",
    call(path + "/execute", a, {}),
    409,
)
check(
    "A approuve personnellement",
    call(path + "/decision", a, {
        "decision": "approve",
        "comment": "Confirmation manuelle du client pendant le test.",
    }),
    200,
)

with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(
        lambda _: call(path + "/execute", a, {}), range(2)
    ))

executions = [
    check("exécution concurrente", result, 200) for result in results
]
task_id = executions[0]["task"]["id"]
verify(
    all(item["task"]["id"] == task_id for item in executions),
    "les deux exécutions retournent la même tâche",
)
tasks = check("lecture des tâches A", call("/tasks", a), 200)
verify(
    sum(item["proposal_id"] == proposal["id"] for item in tasks["items"]) == 1,
    "une seule tâche créée pour la proposition",
)
other_tasks = check("lecture des tâches B", call("/tasks", b), 200)
verify(
    all(item["id"] != task_id for item in other_tasks["items"]),
    "la tâche A est absente des résultats de B",
)

rejected = check(
    "nouvelle proposition pour refus",
    call("/proposals", a, proposal_body),
    201,
)
rejected_path = f"/proposals/{rejected['id']}"
check(
    "A refuse sa proposition",
    call(rejected_path + "/decision", a, {"decision": "reject"}),
    200,
)
check(
    "proposition refusée non exécutable",
    call(rejected_path + "/execute", a, {}),
    409,
)

print("\nTous les tests de ce scénario client ont réussi.")
print("Analyse :", confirmed["analysis_id"])
print("Proposition exécutée :", proposal["id"])
print("Tâche :", task_id)
