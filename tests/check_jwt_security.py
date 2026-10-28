import base64
import getpass
import json
import secrets
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
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


def expect(label, actual, expected):
    if actual != expected:
        raise SystemExit(
            f"FAIL: {label}: expected {expected}, got {actual}"
        )
    print(f"PASS: {label} -> {expected}")


def login(email):
    password = getpass.getpass(f"Password {email}: ")
    status, body = call("/auth/login", {
        "email": email,
        "password": password,
    })
    expect(f"login {email}", status, 200)
    return body["access_token"]


def read_test_claims(token):
    # Test utility only: production validates signatures before using claims.
    payload = token.split(".")[1]
    return json.loads(
        base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    )


def sign_test_token(claims):
    # Privileged test fixture: signing happens inside the backend container.
    # The JWT secret is never exported or printed.
    result = subprocess.run(
        [
            "sudo", "-n", "docker", "compose",
            "exec", "-T", "backend", "python", "-c",
            "import os, sys, json, jwt; "
            "print(jwt.encode(json.load(sys.stdin), "
            "os.environ['JWT_SECRET'], algorithm='HS256'))",
        ],
        cwd=ROOT,
        input=json.dumps(claims),
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SystemExit("Fixture JWT échouée. Vérifiez sudo et Docker.")
    return result.stdout.strip()


token_a = login("client.a@example.test")
claims = read_test_claims(token_a)

status, _ = call("/auth/login", {
    "email": "client.a@example.test",
    "password": secrets.token_urlsafe(32),
})
expect("password incorrecte", status, 401)

# Change the tenant but keep the original signature.
header, payload, signature = token_a.split(".")
forged_claims = {
    **claims,
    "tenant_id": "22222222-2222-4222-8222-222222222222",
}
forged_payload = base64.urlsafe_b64encode(
    json.dumps(forged_claims).encode()
).rstrip(b"=").decode()
forged_token = f"{header}.{forged_payload}.{signature}"

status, _ = call("/auth/me", token=forged_token)
expect("tenant modifié, signature non valide", status, 401)

now = int(time.time())

expired = sign_test_token({
    **claims,
    "iat": now - 120,
    "exp": now - 60,
})
status, _ = call("/auth/me", token=expired)
expect("token signé mais expiré", status, 401)

wrong_audience = sign_test_token({
    **claims,
    "aud": "another-api",
})
status, _ = call("/auth/me", token=wrong_audience)
expect("audience incorrecte", status, 401)

without_exp = dict(claims)
without_exp.pop("exp")
missing_exp = sign_test_token(without_exp)
status, _ = call("/auth/me", token=missing_exp)
expect("expiration absente", status, 401)

token_b = login("client.b@example.test")
status, result = call("/readings", token=token_b)
expect("lecture Client B", status, 200)

sensors = {item["sensor_id"] for item in result["items"]}
if not sensors or not all(s.startswith("B-") for s in sensors):
    raise SystemExit("FAIL: mesures inattendues pour Client B")
print("PASS: Client B voit uniquement ses mesures")

status, _ = call(
    "/readings?tenant_id=11111111-1111-4111-8111-111111111111",
    token=token_b,
)
expect("Client B demande les données de A", status, 403)

print("Tous les tests de ce fichier ont réussi.")
