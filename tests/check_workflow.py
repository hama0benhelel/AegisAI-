import getpass
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"


def call(method, path, token=None, data=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


def check(label, result, expected):
    status, body = result
    if status != expected:
        raise SystemExit(f"FAIL {label}: attendu {expected}, reçu {status}")
    print(f"PASS: {label} -> {expected}")
    return body


tokens = {}
for name in ("viewer.a", "operator.a", "admin.a", "admin.b"):
    password = getpass.getpass(f"Password {name}@example.test: ")
    body = check(
        f"login {name}",
        call("POST", "/auth/login", data={
            "email": f"{name}@example.test",
            "password": password,
        }),
        200,
    )
    del password
    tokens[name] = body["access_token"]

viewer = tokens["viewer.a"]
operator = tokens["operator.a"]
admin = tokens["admin.a"]
other_admin = tokens["admin.b"]

payload = {
    "sensor_id": "A-WATER-01",
    "title": "Inspection du compteur eau - test workflow",
}

check("viewer ne crée pas",
      call("POST", "/proposals", viewer, payload), 403)

check("création avec statut forcé refusée",
      call("POST", "/proposals", operator,
           {**payload, "status": "approved"}), 422)

proposal = check("operator crée un pending",
                 call("POST", "/proposals", operator, payload), 201)
assert proposal["status"] == "pending"
pid = proposal["id"]
path = f"/proposals/{pid}"

check("exécution avant approbation",
      call("POST", path + "/execute", operator), 409)

check("operator ne peut pas approuver",
      call("POST", path + "/decision", operator,
           {"decision": "approve"}), 403)

check("autre tenant ne voit pas la proposition",
      call("GET", path, other_admin), 404)

check("autre tenant ne peut pas approuver",
      call("POST", path + "/decision", other_admin,
           {"decision": "approve"}), 404)

check("admin approuve",
      call("POST", path + "/decision", admin,
           {"decision": "approve", "comment": "Validation de démonstration"}),
      200)

check("contenu non modifiable",
      call("PATCH", path, operator, {"title": "Titre modifié"}), 405)

check("viewer ne peut pas exécuter",
      call("POST", path + "/execute", viewer), 403)

# Two execution requests at the same time.
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [
        pool.submit(call, "POST", path + "/execute", operator)
        for _ in range(2)
    ]
    results = [
        check("exécution concurrente", future.result(), 200)
        for future in futures
    ]

assert results[0]["task"]["id"] == results[1]["task"]["id"]
assert sorted(r["already_executed"] for r in results) == [False, True]
print("PASS: les deux requêtes retournent la même tâche")

tasks = check("lecture tâches", call("GET", "/tasks", admin), 200)
assert sum(t["proposal_id"] == pid for t in tasks["items"]) == 1
print("PASS: une seule tâche pour la proposition")

rejected = check("nouvelle proposition",
                 call("POST", "/proposals", operator, payload), 201)
rejected_path = f'/proposals/{rejected["id"]}'

check("admin rejette",
      call("POST", rejected_path + "/decision", admin,
           {"decision": "reject", "comment": "Test de rejet"}), 200)

check("proposition rejetée non exécutable",
      call("POST", rejected_path + "/execute", operator), 409)

print("Tous les tests workflow ont réussi.")
print(f"Proposition exécutée: {pid}")
