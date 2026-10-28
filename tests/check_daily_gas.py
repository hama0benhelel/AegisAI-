import getpass
import json
import math
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

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
        with urlopen(request, timeout=40) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def check(label, result, expected=200):
    status, body = result
    if status != expected:
        raise SystemExit(f"FAIL : {label}: attendu {expected}, reçu {status}")
    print(f"PASS : {label} -> {status}")
    return body


def verify(condition, label):
    if not condition:
        raise SystemExit("FAIL : " + label)
    print("PASS : " + label)


def reference(tenant, sensor, resource, yesterday):
    tenant = str(UUID(tenant))
    # Sensor and resource are supplied only by the fixed test cases below.
    query = f"""
        WITH target AS (
            SELECT
                (clock_timestamp() AT TIME ZONE 'Africa/Tunis')::date
                - {1 if yesterday else 0} AS day
        )
        SELECT json_build_object(
            'day', target.day,
            'count', count(r.id),
            'sum', coalesce(sum(r.value), 0),
            'ids', coalesce(
                json_agg(r.id ORDER BY r.measured_at, r.id)
                    FILTER (WHERE r.id IS NOT NULL),
                '[]'::json
            )
        )
        FROM target
        LEFT JOIN bws_ai.readings r
          ON r.tenant_id = '{tenant}'
         AND r.sensor_id = '{sensor}'
         AND r.resource = '{resource}'
         AND r.interval_seconds = 3600
         AND (r.measured_at AT TIME ZONE 'Africa/Tunis')::date = target.day
         AND r.measured_at <= clock_timestamp()
        GROUP BY target.day;
    """
    result = subprocess.run(
        [
            "sudo", "docker", "compose", "exec", "-T", "db",
            "psql", "-X", "-q", "-A", "-t",
            "-U", "postgres", "-d", "aegisai",
            "-v", "ON_ERROR_STOP=1",
        ],
        input=query, text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("FAIL : lecture SQL de référence.")
    return json.loads(result.stdout)


for name in ("a", "b"):
    email = f"client.{name}@example.test"
    password = getpass.getpass(f"Password {email}: ")
    auth = check("login " + name, call("/auth/login", body={
        "email": email, "password": password,
    }))
    del password
    token = auth["access_token"]
    user = check("identité " + name, call("/auth/me", token))
    conversation = check(
        "conversation " + name,
        call("/chat/conversations", token, {}), 201,
    )
    path = f"/chat/conversations/{conversation['id']}/messages"

    for resource, suffix, wording, yesterday in (
        ("gas", "GAS", "Quelle est ma consommation de gaz hier ?", True),
    ):
        sensor = f"{name.upper()}-SIM-{suffix}-01"
        before = reference(user["tenant_id"], sensor, resource, yesterday)
        reply = check(
            sensor + (" hier" if yesterday else " aujourd’hui"),
            call(path, token, {
                "message": wording,
                "sensor_id": sensor,
                "resource": resource,
            }),
        )

        if reply.get("needs_clarification"):
            raise SystemExit(
                "Routeur en clarification : vérifiez son journal et le quota. "
                "Si le motif est local_quota, attendez une minute avant de relancer."
            )

        expected = reference(user["tenant_id"], sensor, resource, yesterday)
        if before != expected:
            raise SystemExit(
                "Les données ont changé pendant la requête "
                "(changement d’heure ou de journée). Relancez le test."
            )

        verify(expected["count"] > 0, "données de simulation présentes")
        verify(
            reply.get("period", {}).get("date") == expected["day"]
            and reply["period"]["kind"] == ("yesterday" if yesterday else "today")
            and reply["period"]["timezone"] == "Africa/Tunis",
            "journée et fuseau corrects",
        )
        verify(reply.get("sensor_id") == sensor, "bon compteur")
        verify(
            reply.get("sample_count") == expected["count"],
            "nombre de mesures identique au SQL",
        )
        verify(
            math.isclose(
                float(reply.get("sum_available", -1)),
                float(expected["sum"]),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ),
            "somme identique au SQL",
        )
        verify(
            [source["reading_id"] for source in reply["sources"]]
            == expected["ids"],
            "sources exactement identiques aux lignes SQL",
        )
        verify(
            all(
                source["sensor_id"] == sensor
                and source["data_source"] == "synthetic_live_v1"
                for source in reply["sources"]
            ),
            "sources du compteur simulé demandé uniquement",
        )
        verify(
            reply.get("coverage_complete") is (expected["count"] == 24),
            "journée complète ou partielle correctement signalée",
        )
        print("Réponse :", reply["answer"])
        print()

print("Comparaison chatbot / SQL réussie pour les deux scénarios gaz.")
