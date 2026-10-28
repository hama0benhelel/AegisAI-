import getpass
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"


def call(path, data=None, token=None):
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )

    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


status, _ = call("/auth/me")
assert status == 401, f"Without token: expected 401, got {status}"
print("PASS: sans token -> 401")

password = getpass.getpass("Password client.a@example.test: ")
status, result = call("/auth/login", {
    "email": "client.a@example.test",
    "password": password,
})
del password
assert status == 200, f"Login: expected 200, got {status}"
token = result["access_token"]
print("PASS: login -> 200")

status, user = call("/auth/me", token=token)
assert status == 200
assert user["email"] == "client.a@example.test"
assert user["tenant_id"] == "11111111-1111-4111-8111-111111111111"
assert "password_hash" not in user
print("PASS: identité Client A correcte, aucun hash exposé")

status, result = call("/readings", token=token)
assert status == 200
sensors = {item["sensor_id"] for item in result["items"]}
assert sensors and all(s.startswith("A-") for s in sensors), "Compteur inattendu dans les mesures du client A"
print("PASS: seules les mesures de A sont visibles")

status, _ = call(
    "/readings?tenant_id=22222222-2222-4222-8222-222222222222",
    token=token,
)
assert status == 403, f"Cross-tenant: expected 403, got {status}"
print("PASS: demande du tenant B -> 403")

status, _ = call("/auth/me", token="invalid-token")
assert status == 401
print("PASS: token invalide -> 401")
