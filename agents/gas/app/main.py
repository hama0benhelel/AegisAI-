import json
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.consumption_rules import analyze

app = FastAPI(
    title="AegisAI Gas Agent",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    sensor_id: str = Field(min_length=1, max_length=100)
    value: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    unit: Literal["m3"]
    measured_at: AwareDatetime
    data_source: str = Field(min_length=1, max_length=200)
    interval_seconds: Literal[3600]


class GasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["analyze_consumption"]
    resource: Literal["gas"]
    tenant_id: UUID
    requested_by: UUID
    trace_id: UUID
    sensor_id: str = Field(min_length=1, max_length=100)
    rows: list[Reading] = Field(min_length=24, max_length=24)


@app.get("/health/live")
def live():
    return {"status": "ok", "service": "gas-agent"}


@app.post("/internal/analyze")
def run(body: GasRequest):
    if any(row.sensor_id != body.sensor_id for row in body.rows):
        raise HTTPException(422, "Capteurs incohérents")

    if len({row.id for row in body.rows}) != len(body.rows):
        raise HTTPException(422, "Identifiants de mesures dupliqués")

    rows = [row.model_dump() for row in body.rows]
    result = analyze("gas", rows)

    print(json.dumps({
        "event_type": "agent_analysis_completed",
        "service": "gas-agent",
        "tenant_id": str(body.tenant_id),
        "user_id": str(body.requested_by),
        "trace_id": str(body.trace_id),
        "rule_version": result["rule_version"],
    }), flush=True)

    return {
        "tenant_id": body.tenant_id,
        "trace_id": body.trace_id,
        "result": result,
    }
