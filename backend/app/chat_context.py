from fastapi import HTTPException

from app.db import connect, set_tenant


def resolve_sensor(user, sensor_id=None, resource=None):
    conditions = [
        "tenant_id = %s",
        "interval_seconds = 3600",
        "measured_at <= now()",
    ]
    parameters = [user["tenant_id"]]

    if sensor_id is not None:
        conditions.append("sensor_id = %s")
        parameters.append(sensor_id)

    if resource is not None:
        conditions.append("resource = %s")
        parameters.append(resource)

    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        rows = conn.execute(
            """
            SELECT DISTINCT sensor_id, resource
            FROM bws_ai.readings
            WHERE """
            + " AND ".join(conditions)
            + " ORDER BY resource, sensor_id LIMIT 20",
            tuple(parameters),
        ).fetchall()

    if not rows:
        raise HTTPException(404, "Aucun compteur accessible pour cette demande")

    if len(rows) == 1:
        return rows[0], []

    return None, rows
