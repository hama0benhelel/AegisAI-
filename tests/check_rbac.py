import getpass
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


def call(path, data=None, token=None, extra_headers=None):
    headers = dict(extra_headers or {})
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, None


def expect(label, actual, expected):
    if actual != expected:
        raise SystemExit(f"FAIL {label}: attendu {expected}, reçu {actual}")
    print(f"PASS: {label} -> {expected}")


status, _ = call("/security/audit")
expect("audit sans token", status, 401)

accounts = [
    ("viewer.a@example.test", "viewer", A),
    ("operator.a@example.test", "operator", A),
    ("admin.a@example.test", "tenant_admin", A),
    ("admin.b@example.test", "tenant_admin", B),
]

for email, role, tenant in accounts:
    password = getpass.getpass(f"Password {email}: ")
    status, body = call("/auth/login", {
        "email": email,
        "password": password,
    })
    del password
    expect(f"login {email}", status, 200)
    token = body["access_token"]

    status, me = call("/auth/me", token=token)
    expect("identité", status, 200)
    if me["role"] != role or me["tenant_id"] != tenant:
        raise SystemExit("FAIL: rôle ou tenant inattendu.")

    status, _ = call("/readings", token=token)
    expect(f"lecture mesures par {role}", status, 200)

    status, audit = call("/security/audit", token=token)
    expected = 200 if role == "tenant_admin" else 403
    expect(f"lecture audit par {email}", status, expected)

    if role != "tenant_admin":
        status, _ = call(
            "/security/audit",
            token=token,
            extra_headers={"X-Role": "tenant_admin"},
        )
        expect("faux header X-Role ignoré", status, 403)
        continue

    events = audit["items"]
    if not events or any(event["tenant_id"] != tenant for event in events):
        raise SystemExit("FAIL: audit vide ou événement d'un autre tenant.")
    print("PASS: audit limité au tenant de l'administrateur")

    other_tenant = B if tenant == A else A
    status, _ = call(
        f"/security/audit?tenant_id={other_tenant}",
        token=token,
    )
    expect("audit d'un autre tenant interdit", status, 403)

print("Tous les tests RBAC de ce fichier ont réussi.")
