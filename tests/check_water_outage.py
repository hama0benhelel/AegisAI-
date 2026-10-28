import getpass
import json
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

BASE = "http://127.0.0.1:8000"
COMPOSE = [
    "sudo", "docker", "compose",
    "-f", "compose.yaml",
    "-f", "compose.monitoring.yaml",
    "-f", "compose.agents.yaml",
]


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
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response), response.headers.get("X-Trace-ID")
    except HTTPError as error:
        return error.code, json.load(error), error.headers.get("X-Trace-ID")


def counts(user_id):
    user_id = str(UUID(user_id))
    sql = f"""
        SELECT json_build_object(
            'analyses', (
                SELECT count(*) FROM bws_ai.analyses
                WHERE requested_by = '{user_id}'
            ),
            'confirmations', (
                SELECT count(*) FROM bws_ai.chat_confirmations
                WHERE requested_by = '{user_id}'
            )
        );
    """
    result = subprocess.run(
        COMPOSE + [
            "exec", "-T", "db", "psql", "-X", "-q", "-A", "-t",
            "-U", "postgres", "-d", "aegisai",
            "-v", "ON_ERROR_STOP=1",
        ],
        input=sql, text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("FAIL: lecture des compteurs de contrôle.")
    return json.loads(result.stdout)


password = getpass.getpass("Password client.a@example.test: ")
status, auth, _ = call("/auth/login", body={
    "email": "client.a@example.test", "password": password,
})
del password
if status != 200:
    raise SystemExit(f"FAIL: login -> {status}")

token = auth["access_token"]
status, user, _ = call("/auth/me", token)
if status != 200 or user["role"] != "client":
    raise SystemExit("FAIL: identité client.")

before = counts(user["id"])
restore_needed = False

try:
    restore_needed = True
    subprocess.run(COMPOSE + ["stop", "water-agent"], check=True)

    status, body, trace = call("/chat", token, {
        "message": "Analyse la consommation",
        "resource": "water",
        "sensor_id": "A-WATER-01",
    })

    if status != 503:
        raise SystemExit(f"FAIL: attendu 503, reçu {status}")
    print("PASS: agent indisponible -> HTTP 503")

    if not trace:
        raise SystemExit("FAIL: Trace ID absent")
    print("PASS: échec traçable, Trace ID =", trace)

    if body.get("confirmation") or body.get("analysis_id"):
        raise SystemExit("FAIL: résultat métier retourné malgré l’indisponibilité")

    if counts(user["id"]) != before:
        raise SystemExit("FAIL: analyse ou confirmation créée pendant l’échec")

    print("PASS: aucune analyse ni confirmation supplémentaire")
    print("PASS: aucun résultat local de secours retourné")

finally:
    if restore_needed:
        result = subprocess.run(
            COMPOSE + ["up", "-d", "--no-deps", "water-agent"]
        )
        if result.returncode:
            raise SystemExit("FAIL: redémarrage du water-agent à vérifier.")
        print("Agent eau redémarré.")

print("Test d’indisponibilité réussi.")
