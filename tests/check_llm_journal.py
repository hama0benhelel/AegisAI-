import json
from getpass import getpass
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "http://127.0.0.1:8080/api"
A = "11111111-1111-4111-8111-111111111111"
B = "22222222-2222-4222-8222-222222222222"


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
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())


def expect(label, result, expected):
    status, data = result
    if status != expected:
        raise SystemExit(f"FAIL {label}: attendu {expected}, reçu {status}")
    print(f"PASS: {label} -> {status}")
    return data


expect("sans token", call("/security/llm-calls"), 401)

for name, allowed, tenant, other in [
    ("viewer.a", False, A, B),
    ("operator.a", False, A, B),
    ("admin.a", True, A, B),
    ("admin.b", True, B, A),
]:
    email = name + "@example.test"
    auth = expect("login " + name, call("/auth/login", body={
        "email": email,
        "password": getpass(f"Password {email}: "),
    }), 200)
    token = auth["access_token"]

    data = expect(
        "journal " + name,
        call("/security/llm-calls", token),
        200 if allowed else 403,
    )

    if allowed:
        items = data["items"]
        assert all(row["tenant_id"] == tenant for row in items)
        assert all(
            "input_context" not in row and "output_text" not in row
            for row in items
        )
        print(f"PASS: {len(items)} ligne(s), tenant correct, contenu exclu")
        expect(
            "autre tenant interdit",
            call(f"/security/llm-calls?tenant_id={other}", token),
            403,
        )
        expect(
            "limite excessive refusée",
            call("/security/llm-calls?limit=101", token),
            422,
        )

print("Tous les tests du journal LLM ont réussi.")
