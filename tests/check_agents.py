import getpass
import json
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
        BASE + path, method=method, headers=headers,
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
for name in ("operator.a", "viewer.a", "admin.b"):
    password = getpass.getpass(f"Password {name}@example.test: ")
    body = check(
        f"login {name}",
        call("POST", "/auth/login", data={
            "email": f"{name}@example.test", "password": password,
        }), 200,
    )
    del password
    tokens[name] = body["access_token"]

operator = tokens["operator.a"]
viewer = tokens["viewer.a"]
admin_b = tokens["admin.b"]

check("viewer ne lance pas une analyse",
      call("POST", "/agents/water/analyze", viewer,
           {"sensor_id": "A-WATER-01"}), 403)

check("operator A ne lit pas un capteur B",
      call("POST", "/agents/water/analyze", operator,
           {"sensor_id": "B-WATER-01"}), 404)

analyses_a = []
for resource, sensor, latest, baseline in [
    ("water", "A-WATER-01", 35, 10),
    ("energy", "A-ENERGY-01", 240, 80),
]:
    analysis = check(
        f"analyse {resource} A",
        call("POST", f"/agents/{resource}/analyze", operator,
             {"sensor_id": sensor}), 201,
    )
    result = analysis["result"]
    assert result["classification"] == "high_consumption"
    assert result["latest_value"] == latest
    assert result["baseline_mean"] == baseline
    assert result["sample_count"] == 24
    assert len(result["sources"]) == 24
    assert result["confidence_probability"] is None
    assert all(
        source["data_source"] == "synthetic_hourly_v1"
        for source in result["sources"]
    )
    print("PASS: calcul, sources synthétiques et résultat vérifiés")
    analyses_a.append(analysis)

    check("B ne lit pas l'analyse A",
          call("GET", f'/analyses/{analysis["id"]}', admin_b), 404)

for resource, sensor in [
    ("water", "B-WATER-01"), ("energy", "B-ENERGY-01")
]:
    analysis = check(
        f"analyse {resource} B",
        call("POST", f"/agents/{resource}/analyze", admin_b,
             {"sensor_id": sensor}), 201,
    )
    assert analysis["result"]["classification"] == "normal"
    assert analysis["result"]["suggested_proposal"] is None
    print("PASS: absence de dépassement pour B")

first = analyses_a[0]
stored = check("viewer lit une analyse de son tenant",
               call("GET", f'/analyses/{first["id"]}', viewer), 200)
assert stored["result"] == first["result"]
print("PASS: résultat et sources persistés")

proposal = check(
    "suggestion convertie en proposition",
    call("POST", "/proposals", operator,
         first["result"]["suggested_proposal"]), 201,
)
assert proposal["status"] == "pending"

check("suggestion non exécutable sans approbation",
      call("POST", f'/proposals/{proposal["id"]}/execute', operator), 409)

print("Tous les tests de ce scénario agents ont réussi.")
print("Analyse eau A:", first["id"])
