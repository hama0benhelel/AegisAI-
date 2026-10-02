from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from app.auth import current_user
from app.db import connect, set_tenant
from app.permissions import require_roles
from app.workflow import record_event

router = APIRouter(tags=["Agents"])
RULE_VERSION = "hourly-baseline-v1"
MULTIPLIER = Decimal("2")


class AnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sensor_id: str = Field(min_length=1, max_length=100)


def analyze(resource, rows):
    if len(rows) != 24:
        raise HTTPException(422, "24 mesures horaires sont nécessaires")

    expected_unit = "m3" if resource == "water" else "kWh"
    if any(row["unit"] != expected_unit for row in rows):
        raise HTTPException(422, "Unités incohérentes")

    for previous, current in zip(rows, rows[1:]):
        if current["measured_at"] - previous["measured_at"] != timedelta(hours=1):
            raise HTTPException(422, "La série doit contenir 24 heures consécutives")

    baseline = sum(row["value"] for row in rows[:-1]) / Decimal(23)
    if baseline <= 0:
        raise HTTPException(422, "Référence nulle: règle non applicable")

    latest = rows[-1]
    threshold = baseline * MULTIPLIER
    anomalous = latest["value"] > threshold

    suggestion = None
    if anomalous:
        suggestion = {
            "action_type": "create_inspection_task",
            "sensor_id": latest["sensor_id"],
            "title": f"Vérifier la consommation du capteur {latest['sensor_id']}",
        }

    return {
        "agent": resource,
        "rule_version": RULE_VERSION,
        "sensor_id": latest["sensor_id"],
        "data_as_of": latest["measured_at"].isoformat(),
        "measurement_kind": "consumption_per_hour",
        "unit": expected_unit,
        "sample_count": len(rows),
        "baseline_mean": float(baseline),
        "latest_value": float(latest["value"]),
        "threshold_multiplier": float(MULTIPLIER),
        "threshold_value": float(threshold),
        "ratio_to_baseline": float(latest["value"] / baseline),
        "classification": "high_consumption" if anomalous else "normal",
        "confidence_probability": None,
        "interpretation": (
            "La dernière heure dépasse deux fois la moyenne des 23 précédentes."
            if anomalous else
            "La dernière heure ne dépasse pas le seuil de cette règle."
        ),
        "limitations": [
            "Règle non calibrée sur des données industrielles.",
            "Aucune cause racine confirmée.",
            "Résultat valable à la date des données, pas une mesure en temps réel.",
        ],
        "sources": [
            {
                "reading_id": str(row["id"]),
                "measured_at": row["measured_at"].isoformat(),
                "value": float(row["value"]),
                "unit": row["unit"],
                "interval_seconds": row["interval_seconds"],
                "data_source": row["data_source"],
            }
            for row in rows
        ],
        "suggested_proposal": suggestion,
    }


@router.post("/agents/{resource}/analyze", status_code=201)
def run_analysis(
    resource: Literal["water", "energy"],
    body: AnalysisInput,
    request: Request,
    user=Depends(require_roles("operator", "tenant_admin")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])

        rows = conn.execute(
            """
            SELECT id, sensor_id, value, unit, measured_at,
                   data_source, interval_seconds
            FROM bws_ai.readings
            WHERE tenant_id = %s AND sensor_id = %s AND resource = %s
              AND interval_seconds = 3600
              AND measured_at <= now()
            ORDER BY measured_at DESC, id DESC
            LIMIT 24
            """,
            (user["tenant_id"], body.sensor_id, resource),
        ).fetchall()

        if not rows:
            raise HTTPException(404, "Aucune série horaire accessible")

        result = analyze(resource, list(reversed(rows)))

        saved = conn.execute(
            """
            INSERT INTO bws_ai.analyses (
                tenant_id, requested_by, agent, sensor_id, rule_version, result
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, tenant_id, requested_by, created_at
            """,
            (
                user["tenant_id"], user["id"], resource,
                body.sensor_id, RULE_VERSION, Jsonb(result),
            ),
        ).fetchone()

        record_event(
            conn, request, user, "analysis_created", saved["id"], 201
        )

    return {**saved, "result": result}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: UUID, user=Depends(current_user)):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        row = conn.execute(
            """
            SELECT * FROM bws_ai.analyses
            WHERE id = %s AND tenant_id = %s
            """,
            (analysis_id, user["tenant_id"]),
        ).fetchone()

    if row is None:
        raise HTTPException(404, "Analyse introuvable")
    return row
