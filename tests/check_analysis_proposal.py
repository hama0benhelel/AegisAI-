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
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
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
for name in ("operator.a", "viewer.a", "admin.a", "admin.b"):
    password = getpass.getpass(f"Password {name}@example.test: ")
    result = check(
        f"login {name}",
        call("POST", "/auth/login", data={
            "email": f"{name}@example.test",
            "password": password,
        }), 200,
    )
    del password
    tokens[name] = result["access_token"]

operator = tokens["operator.a"]
viewer = tokens["viewer.a"]
admin = tokens["admin.a"]
admin_b = tokens["admin.b"]

analysis = check(
    "nouvelle analyse A",
    call("POST", "/agents/water/analyze", operator,
         {"sensor_id": "A-WATER-01"}), 201,
)
aid = analysis["id"]
path = f"/analyses/{aid}/proposal"

check("sans token", call("POST", path), 401)
check("viewer interdit", call("POST", path, viewer), 403)
check("autre tenant interdit", call("POST", path, admin_b), 404)

with ThreadPoolExecutor(max_workers=2) as pool:
    futures = [
        pool.submit(call, "POST", path, operator)
        for _ in range(2)
    ]
    results = [future.result() for future in futures]

statuses = sorted(status for status, _ in results)
assert statuses == [200, 201], statuses

first = results[0][1]["proposal"]
second = results[1][1]["proposal"]
assert first["id"] == second["id"]
assert first["analysis_id"] == aid
assert second["analysis_id"] == aid
assert first["status"] == second["status"] == "pending"
assert sorted(body["already_exists"] for _, body in results) == [False, True]
print("PASS: deux requêtes simultanées, un seul nouveau pending")

suggestion = analysis["result"]["suggested_proposal"]
for field in ("action_type", "sensor_id", "title"):
    assert first[field] == suggestion[field]
print("PASS: contenu issu de l'analyse sauvegardée")

pid = first["id"]
proposal_path = f"/proposals/{pid}"

check("approbation toujours requise",
      call("POST", proposal_path + "/execute", operator), 409)

check("admin approuve",
      call("POST", proposal_path + "/decision", admin,
           {"decision": "approve"}), 200)

execution = check("operator exécute",
                  call("POST", proposal_path + "/execute", operator), 200)
assert execution["task"]["proposal_id"] == pid

replayed = check("répétition après exécution",
                 call("POST", path, operator), 200)
assert replayed["already_exists"] is True
assert replayed["proposal"]["id"] == pid
assert replayed["proposal"]["status"] == "executed"
assert replayed["proposal"]["analysis_id"] == aid
print("PASS: aucune nouvelle proposition ni remise en pending")

normal = check(
    "analyse normale B",
    call("POST", "/agents/water/analyze", admin_b,
         {"sensor_id": "B-WATER-01"}), 201,
)
check("analyse sans suggestion",
      call("POST", f'/analyses/{normal["id"]}/proposal', admin_b), 409)

print("Tous les tests analyse-vers-proposition ont réussi.")
print("Analysis ID:", aid)
print("Proposal ID:", pid)
print("Task ID:", execution["task"]["id"])
