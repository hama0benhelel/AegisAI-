"""Deterministic laboratory readings. No physical IoT device is contacted."""
from decimal import Decimal
import hashlib
import json
import os
import signal
import threading

import psycopg

SOURCE = "synthetic_live_v1"
SENSORS = (
    ("11111111-1111-4111-8111-111111111111", "A-SIM-GAS-01", "gas", "m3"),
    ("22222222-2222-4222-8222-222222222222", "B-SIM-GAS-01", "gas", "m3"),
    ("11111111-1111-4111-8111-111111111111", "A-SIM-WATER-01", "water", "m3"),
    ("11111111-1111-4111-8111-111111111111", "A-SIM-ENERGY-01", "energy", "kWh"),
    ("22222222-2222-4222-8222-222222222222", "B-SIM-WATER-01", "water", "m3"),
    ("22222222-2222-4222-8222-222222222222", "B-SIM-ENERGY-01", "energy", "kWh"),
)

INSERT = """
    INSERT INTO bws_ai.readings (
        tenant_id, sensor_id, resource, value, unit,
        measured_at, data_source, interval_seconds
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (tenant_id, sensor_id, resource, measured_at)
    WHERE data_source = 'synthetic_live_v1'
    DO NOTHING
"""


def connect():
    return psycopg.connect(
        host="db", dbname="aegisai", user="aegisai_simulator",
        password=os.environ["SIMULATOR_DB_PASSWORD"],
        connect_timeout=3,
        options="-c statement_timeout=5000 -c timezone=UTC",
    )


def value_for(sensor_id, resource, measured_at, local_hour):
    if resource not in {"water", "energy", "gas"}:
        raise ValueError("Unsupported simulation resource")
    if not 0 <= local_hour <= 23:
        raise ValueError("Invalid hour")
    if measured_at.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    digest = hashlib.sha256(f"{SOURCE}|{sensor_id}|{measured_at.isoformat()}".encode()).digest()
    fraction = Decimal(int.from_bytes(digest[:2], "big")) / Decimal(65535)
    peak = local_hour in {7, 8, 18, 19, 20}
    quiet = local_hour < 6
    if resource == "water":
        value = Decimal("0.012" if quiet else "0.065" if peak else "0.028")
        value += fraction * Decimal("0.008")
    elif resource == "gas":
        value = Decimal("0.006" if quiet else "0.080" if peak else "0.020")
        value += fraction * Decimal("0.006")
    else:
        value = Decimal("0.12" if quiet else "0.95" if peak else "0.45")
        value += fraction * Decimal("0.12")
    if sensor_id.startswith("B-"):
        value *= Decimal("0.80")
    # Deliberate laboratory spikes at fixed local hours, not a moving anomaly.
    if sensor_id == "A-SIM-WATER-01" and local_hour == 18:
        value *= 6
    if sensor_id == "A-SIM-ENERGY-01" and local_hour == 19:
        value *= 5
    if sensor_id == "A-SIM-GAS-01" and local_hour == 20:
        value *= 5
    return value.quantize(Decimal("0.001"))


def generate_once():
    with connect() as conn:
        # The database clock defines completed hours and Tunis calendar days.
        hours = conn.execute("""
            WITH reference AS (
                SELECT clock_timestamp() AS now
            ), bounds AS (
                SELECT
                    (date_trunc('day', now AT TIME ZONE 'Africa/Tunis')
                     - interval '2 days') AT TIME ZONE 'Africa/Tunis' AS starts_at,
                    date_trunc('hour', now) - interval '1 hour' AS ends_at
                FROM reference
            )
            SELECT stamp, extract(hour FROM stamp AT TIME ZONE 'Africa/Tunis')::int
            FROM bounds, LATERAL generate_series(starts_at, ends_at, interval '1 hour') AS stamp
            ORDER BY stamp
        """).fetchall()
        records = [
            (tenant, sensor, resource, value_for(sensor, resource, stamp, hour),
             unit, stamp, SOURCE, 3600)
            for stamp, hour in hours
            for tenant, sensor, resource, unit in SENSORS
        ]
        with conn.cursor() as cursor:
            cursor.executemany(INSERT, records)
            inserted = cursor.rowcount
    print(json.dumps({
        "event_type": "simulation_batch_completed", "data_source": SOURCE,
        "candidate_rows": len(records), "inserted_rows": inserted,
    }), flush=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        generate_once()
        return
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        try:
            generate_once()
        except psycopg.Error as error:
            print(json.dumps({"event_type": "simulation_batch_failed", "sqlstate": error.sqlstate}), flush=True)
        except Exception:
            print(json.dumps({"event_type": "simulation_batch_failed", "reason": "unexpected_error"}), flush=True)
        stop.wait(60)


if __name__ == "__main__":
    main()
