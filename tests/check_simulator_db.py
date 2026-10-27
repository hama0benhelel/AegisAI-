from datetime import timedelta

import psycopg

from producer import connect, generate_once


with connect() as conn:
    user = conn.execute("SELECT current_user").fetchone()[0]
    if user != "aegisai_simulator":
        raise SystemExit("FAIL : identité DB incorrecte")
    print("PASS : rôle DB dédié au simulateur")
    permissions = conn.execute("""
        SELECT
            has_any_column_privilege(current_user, 'bws_ai.readings', 'UPDATE'),
            has_table_privilege(current_user, 'bws_ai.readings', 'DELETE'),
            has_table_privilege(current_user, 'bws_ai.users', 'SELECT'),
            has_table_privilege(current_user, 'bws_ai.audit_events', 'SELECT')
    """).fetchone()
    if any(permissions):
        raise SystemExit("FAIL : permissions excessives")
    print("PASS : pas de modification/suppression des mesures ni lecture users/audit")

    outside = conn.execute("SELECT count(*) FROM bws_ai.readings WHERE data_source <> 'synthetic_live_v1'").fetchone()[0]
    if outside != 0:
        raise SystemExit("FAIL : anciennes sources visibles au simulateur")
    print("PASS : sources historiques invisibles au simulateur")

    bad_future = conn.execute("""
        SELECT count(*) FROM bws_ai.readings
        WHERE measured_at + interval '1 hour' > clock_timestamp()
    """).fetchone()[0]
    if bad_future:
        raise SystemExit("FAIL : intervalle non terminé")
    print("PASS : uniquement des heures terminées")

    duplicate = conn.execute("""
        SELECT count(*) FROM (
            SELECT tenant_id, sensor_id, resource, measured_at
            FROM bws_ai.readings
            GROUP BY tenant_id, sensor_id, resource, measured_at
            HAVING count(*) > 1
        ) AS duplicated
    """).fetchone()[0]
    if duplicate:
        raise SystemExit("FAIL : doublons")
    print("PASS : aucun doublon de mesures simulées")

    probe = conn.execute("SELECT date_trunc('hour', clock_timestamp()) - interval '1 hour'").fetchone()[0]
    for tenant, sensor, source in (
        ("22222222-2222-4222-8222-222222222222", "A-SIM-WATER-01", "synthetic_live_v1"),
        ("11111111-1111-4111-8111-111111111111", "A-WATER-01", "synthetic_hourly_v1"),
    ):
        try:
            with conn.transaction():
                conn.execute("""
                    INSERT INTO bws_ai.readings
                    (tenant_id, sensor_id, resource, value, unit, measured_at, data_source, interval_seconds)
                    VALUES (%s, %s, 'water', 0.02, 'm3', %s, %s, 3600)
                """, (tenant, sensor, probe, source))
                raise RuntimeError("FAIL : insertion hors périmètre acceptée")
        except psycopg.errors.InsufficientPrivilege:
            print("PASS : insertion hors périmètre refusée par RLS")

    summary = conn.execute("""
        SELECT sensor_id, count(*), min(measured_at), max(measured_at)
        FROM bws_ai.readings GROUP BY sensor_id ORDER BY sensor_id
    """).fetchall()
    if len(summary) != 4 or any(row[1] < 48 for row in summary):
        raise SystemExit("FAIL : historique initial incomplet")
    for sensor, count, first, last in summary:
        print(f"PASS : {sensor} : {count} mesures, de {first} à {last}")

print("Contrôles DB du simulateur réussis.")
