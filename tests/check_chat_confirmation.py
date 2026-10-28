import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from getpass import getpass
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

BASE = "http://127.0.0.1:8080/api"


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS: {label}")


def api(path, token=None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"

    request = Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())


def expect(status, expected, label):
    check(status == expected, f"{label} -> {expected} (reçu {status})")


def sql(statement):
    result = subprocess.run(
        [
            "sudo", "docker", "compose", "exec", "-T", "db",
            "psql", "-U", "postgres", "-d", "aegisai",
            "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1",
            "-c", statement,
        ],
        check=True, text=True, capture_output=True,
    )
    return result.stdout.strip()


def login(email):
    status, data = api("/auth/login", body={
        "email": email,
        "password": getpass(f"Password {email}: "),
    })
    expect(status, 200, f"login {email}")
    return data["access_token"]


def prepare(token):
    status, data = api("/chat", token, {
        "message": "Analyse la consommation",
        "resource": "water",
        "sensor_id": "A-WATER-01",
    })
    expect(status, 200, "préparation")
    check(data.get("needs_confirmation") is True, "confirmation requise")
    check(not data.get("analysis_id"), "aucun ID analyse retourné")
    pending = data["confirmation"]
    check(pending["status"] == "pending", "demande pending")
    return str(UUID(pending["id"])), pending["preview"]


def decision(pending_id, token, value="confirm", **extra):
    return api(
        f"/chat/confirmations/{pending_id}/decision",
        token,
        {"decision": value, **extra},
    )


def state(pending_id):
    pending_id = str(UUID(pending_id))
    return json.loads(sql(f"""
        SELECT json_build_object(
            'status', status,
            'analysis_id', analysis_id
        )
        FROM bws_ai.chat_confirmations
        WHERE id = '{pending_id}'::uuid;
    """))


def main():
    operator = login("operator.a@example.test")
    viewer = login("viewer.a@example.test")
    admin_a = login("admin.a@example.test")
    admin_b = login("admin.b@example.test")

    status, identity = api("/auth/me", operator)
    expect(status, 200, "identité operator")
    user_id = str(UUID(identity["id"]))

    def analysis_count():
        return int(sql(f"""
            SELECT count(*) FROM bws_ai.analyses
            WHERE requested_by = '{user_id}'::uuid;
        """))

    before = analysis_count()
    pending_id, preview = prepare(operator)
    check(analysis_count() == before, "préparation sans création d’analyse")
    check(state(pending_id)["analysis_id"] is None, "pending sans analyse liée")

    status, _ = decision(pending_id, None)
    expect(status, 401, "confirmation sans authentification")

    status, _ = decision(pending_id, viewer)
    expect(status, 403, "viewer interdit")

    status, _ = decision(pending_id, admin_a)
    expect(status, 404, "autre utilisateur du même tenant interdit")

    status, _ = decision(pending_id, admin_b)
    expect(status, 404, "autre tenant interdit")

    status, _ = decision(pending_id, operator, sensor_id="B-WATER-01")
    expect(status, 422, "modification du contenu refusée")

    check(state(pending_id)["status"] == "pending", "demande toujours pending")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(decision, pending_id, operator)
            for _ in range(2)
        ]
        responses = [future.result() for future in futures]

    for status, _ in responses:
        expect(status, 200, "confirmation concurrente")

    results = [data for _, data in responses]
    ids = {data["analysis_id"] for data in results}
    check(len(ids) == 1, "même analyse pour les deux confirmations")
    check(
        sorted(data["already_processed"] for data in results) == [False, True],
        "une création et une répétition",
    )
    check(analysis_count() == before + 1, "une seule analyse créée")

    analysis_id = str(UUID(results[0]["analysis_id"]))
    status, analysis = api(f"/analyses/{analysis_id}", operator)
    expect(status, 200, "lecture analyse confirmée")
    check(analysis["result"] == preview, "résultat identique à la prévisualisation")

    status, repeated = decision(pending_id, operator)
    expect(status, 200, "nouvelle répétition")
    check(
        repeated["analysis_id"] == analysis_id and repeated["already_processed"],
        "répétition sans nouvelle analyse",
    )

    status, _ = decision(pending_id, operator, "cancel")
    expect(status, 409, "annulation après confirmation refusée")

    cancelled_id, _ = prepare(operator)
    status, _ = decision(cancelled_id, operator, "cancel")
    expect(status, 200, "annulation")

    status, _ = decision(cancelled_id, operator)
    expect(status, 409, "confirmation après annulation refusée")
    check(
        state(cancelled_id) == {"status": "cancelled", "analysis_id": None},
        "annulation sans analyse",
    )

    expired_id, _ = prepare(operator)
    # Only this test-created request is modified, using the DB admin.
    # Keep expires_at > created_at to respect the table constraint.
    sql(f"""
        UPDATE bws_ai.chat_confirmations
        SET created_at = clock_timestamp() - interval '20 minutes',
            expires_at = clock_timestamp() - interval '10 minutes'
        WHERE id = '{expired_id}'::uuid
          AND requested_by = '{user_id}'::uuid
          AND status = 'pending';
    """)

    status, _ = decision(expired_id, operator)
    expect(status, 409, "confirmation expirée refusée")
    check(state(expired_id)["analysis_id"] is None, "expiration sans analyse")

    check(analysis_count() == before + 1, "aucune création supplémentaire")

    counts = json.loads(sql(f"""
        SELECT json_build_object(
            'confirmed', (
                SELECT count(*) FROM bws_ai.audit_events
                WHERE object_id = '{pending_id}'::uuid
                  AND event_type = 'chat_confirmation_confirmed'
            ),
            'analysis_created', (
                SELECT count(*) FROM bws_ai.audit_events
                WHERE object_id = '{analysis_id}'::uuid
                  AND event_type = 'analysis_created'
            ),
            'cancelled', (
                SELECT count(*) FROM bws_ai.audit_events
                WHERE object_id = '{cancelled_id}'::uuid
                  AND event_type = 'chat_confirmation_cancelled'
            )
        );
    """))

    check(
        counts == {"confirmed": 1, "analysis_created": 1, "cancelled": 1},
        "événements métier uniques pour confirmation, création et annulation",
    )
    print("\nTous les tests de confirmation ont réussi.")
    print(f"Analyse créée : {analysis_id}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit(f"FAIL: {error}")
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"FAIL PostgreSQL: {error.stderr}")
