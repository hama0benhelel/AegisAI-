from app.gas_client import analyze_gas
from app.energy_client import analyze_energy
from app.water_client import analyze_water
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


from app.consumption_rules import analyze


@router.post("/agents/{resource}/analyze", status_code=201)
def run_analysis(
    resource: Literal["water", "energy", "gas"],
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

        ordered_rows = list(reversed(rows))
        analyzers = {"water": analyze_water, "energy": analyze_energy, "gas": analyze_gas}
        if resource not in analyzers:
            raise HTTPException(422, "Ressource non prise en charge")
        result = analyzers[resource](ordered_rows, user, request)

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
