import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

URL = "http://127.0.0.1:8000/auth/login"

for attempt in range(1, 12):
    request = Request(
        URL,
        data=json.dumps({
            "email": "rate-limit-test@example.test",
            "password": "invalid-demo-password",
        }).encode(),
        headers={
            "Content-Type": "application/json",
            # Changing this header must not bypass the limit.
            "X-Forwarded-For": f"192.0.2.{attempt}",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            status = response.status
            headers = response.headers
    except HTTPError as error:
        status = error.code
        headers = error.headers

    expected = 401 if attempt <= 10 else 429
    if status != expected:
        raise SystemExit(
            f"FAIL tentative {attempt}: attendu {expected}, reçu {status}. "
            "Si d'autres logins ont eu lieu, attendez 60 secondes "
            "sans tentative avant de relancer."
        )

    print(f"PASS tentative {attempt}: HTTP {status}")

    if status == 429:
        retry_after = headers.get("Retry-After")
        if not retry_after or not 1 <= int(retry_after) <= 60:
            raise SystemExit("FAIL: Retry-After invalide.")
        if not headers.get("X-Trace-ID"):
            raise SystemExit("FAIL: X-Trace-ID absent.")
        print(f"PASS: Retry-After={retry_after}s et X-Trace-ID présent")

print("Rate limiting validé pour ce scénario.")
