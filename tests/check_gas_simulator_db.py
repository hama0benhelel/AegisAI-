from datetime import timedelta
import psycopg
from producer import connect

with connect() as conn:
    stamp = conn.execute("SELECT date_trunc('hour', clock_timestamp()) - interval '1 hour'").fetchone()[0]
    visible = conn.execute("SELECT DISTINCT tenant_id::text, sensor_id FROM bws_ai.readings WHERE resource = 'gas' ORDER BY sensor_id").fetchall()
    expected = [("11111111-1111-4111-8111-111111111111", "A-SIM-GAS-01"), ("22222222-2222-4222-8222-222222222222", "B-SIM-GAS-01")]
    if visible != expected:
        raise SystemExit("FAIL : les deux compteurs gaz attendus ne sont pas présents")
    print("PASS : uniquement les deux compteurs gaz autorisés visibles")
    for label, tenant, sensor, source, timestamp, unit in (
        ("tenant incorrect", expected[1][0], expected[0][1], "synthetic_live_v1", stamp, "m3"),
        ("capteur arbitraire", expected[0][0], "A-GAS-OTHER", "synthetic_live_v1", stamp, "m3"),
        ("source historique", expected[0][0], expected[0][1], "manual_demo", stamp, "m3"),
        ("heure non terminée", expected[0][0], expected[0][1], "synthetic_live_v1", stamp + timedelta(hours=2), "m3"),
        ("heure non alignée", expected[0][0], expected[0][1], "synthetic_live_v1", stamp + timedelta(minutes=1), "m3"),
        ("unité énergie", expected[0][0], expected[0][1], "synthetic_live_v1", stamp, "kWh"),
    ):
        try:
            with conn.transaction():
                conn.execute("""INSERT INTO bws_ai.readings
                    (tenant_id, sensor_id, resource, value, unit, measured_at, data_source, interval_seconds)
                    VALUES (%s, %s, 'gas', 0.1, %s, %s, %s, 3600)""",
                    (tenant, sensor, unit, timestamp, source))
                raise RuntimeError("FAIL : insertion acceptée : " + label)
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation):
            print("PASS : refus " + label)
print("Contrôles DB gaz réussis.")
