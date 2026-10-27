from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException

from app.db import connect, set_tenant

TIMEZONE = "Africa/Tunis"


def summarize_rows(rows, starts_at):
    if len(rows) > 24 or len({row["measured_at"] for row in rows}) != len(rows):
        raise HTTPException(422, "Série journalière incohérente : heures dupliquées ou trop nombreuses")
    units = {row["unit"] for row in rows}
    if len(units) > 1:
        raise HTTPException(422, "Unités incohérentes")
    values = [Decimal(str(row["value"])) for row in rows]
    if any(not value.is_finite() or value < 0 for value in values):
        raise HTTPException(422, "Valeurs non valides")
    expected = {starts_at + timedelta(hours=index) for index in range(24)}
    complete = len(rows) == 24 and {row["measured_at"] for row in rows} == expected
    return sum(values, Decimal(0)), complete


def daily_readings(user, sensor_id, resource, period):
    if period not in {"today", "yesterday"}:
        raise ValueError("Unsupported daily period")
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        bounds = conn.execute(
            """
            WITH reference AS (
                SELECT clock_timestamp() AS now
            ), day AS (
                SELECT (now AT TIME ZONE 'Africa/Tunis')::date - %s AS day, now
                FROM reference
            )
            SELECT day, now,
                   day::timestamp AT TIME ZONE 'Africa/Tunis' AS starts_at,
                   (day + 1)::timestamp AT TIME ZONE 'Africa/Tunis' AS ends_at
            FROM day
            """, (1 if period == "yesterday" else 0,),
        ).fetchone()
        rows = conn.execute(
            """
            SELECT id, sensor_id, value, unit, measured_at,
                   data_source, interval_seconds
            FROM bws_ai.readings
            WHERE tenant_id = %s AND sensor_id = %s AND resource = %s
              AND interval_seconds = 3600
              AND measured_at >= %s AND measured_at < %s AND measured_at <= %s
            ORDER BY measured_at, id LIMIT 25
            """,
            (user["tenant_id"], sensor_id, resource, bounds["starts_at"], bounds["ends_at"], bounds["now"]),
        ).fetchall()
        latest = conn.execute(
            """
            SELECT measured_at FROM bws_ai.readings
            WHERE tenant_id = %s AND sensor_id = %s AND resource = %s
              AND interval_seconds = 3600 AND measured_at <= %s
            ORDER BY measured_at DESC, id DESC LIMIT 1
            """, (user["tenant_id"], sensor_id, resource, bounds["now"]),
        ).fetchone()

    metadata = {
        "period": {"kind": period, "date": bounds["day"].isoformat(), "timezone": TIMEZONE},
        "sensor_id": sensor_id, "resource": resource, "data_available": bool(rows),
        "data_as_of": rows[-1]["measured_at"].isoformat() if rows else None,
    }
    if not rows:
        text = f"Aucune mesure horaire disponible pour {sensor_id} le {bounds['day'].isoformat()} ({TIMEZONE})."
        if latest:
            text += f" La dernière mesure enregistrée date du {latest['measured_at'].isoformat()}. Elle ne correspond pas à la journée demandée."
        return {**metadata, "answer": text, "sources": [], "coverage_complete": False, "sample_count": 0}

    unit = "m3" if resource == "water" else "kWh"
    if any(row["unit"] != unit for row in rows):
        raise HTTPException(422, "Unité incohérente pour la ressource")
    total, complete = summarize_rows(rows, bounds["starts_at"])
    amount = format(total, "f").replace(".", ",")
    text = (
        f"La somme des {len(rows)} mesures horaires horodatées le "
        f"{bounds['day'].isoformat()} ({TIMEZONE}) pour {sensor_id} est de {amount} {unit}. "
    )
    text += (
        "Les 24 horodatages horaires de la journée sont présents."
        if complete else
        "Les données de cette journée sont partielles : cette somme ne représente pas un total journalier complet."
    )
    return {
        **metadata, "answer": text, "sample_count": len(rows),
        "coverage_complete": complete, "sum_available": float(total),
        "sources": [{
            "reading_id": str(row["id"]), "sensor_id": row["sensor_id"],
            "value": float(row["value"]), "unit": row["unit"],
            "measured_at": row["measured_at"].isoformat(),
            "data_source": row["data_source"], "interval_seconds": row["interval_seconds"],
        } for row in rows],
    }
