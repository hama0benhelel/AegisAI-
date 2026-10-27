from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents import get_analysis
from app.chat_confirmations import prepare_analysis
from app.auth import current_user
from app.db import connect, set_tenant
from app.intent_gate import GATE_VERSION, classify
from app.llm import render_with_llm

router = APIRouter(tags=["Chatbot"])


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=1000)
    resource: Literal["water", "energy"] | None = None
    sensor_id: str | None = Field(default=None, min_length=1, max_length=100)
    analysis_id: UUID | None = None


def answer(intent, text, sources=None, **extra):
    return {
        "mode": "grounded_template",
        "llm_used": False,
        "gate_version": GATE_VERSION,
        "intent": intent,
        "answer": text,
        "sources": sources or [],
        **extra,
    }


def clarify(request, intent, text):
    request.state.audit_event_type = "chat_clarification_required"
    return answer(intent, text, needs_clarification=True)


@router.post("/chat")
def chat(
    body: ChatInput,
    request: Request,
    user=Depends(current_user),
):
    gate = classify(body.message)
    intent = gate["intent"]

    if gate["decision"] == "reject":
        request.state.audit_event_type = (
            "prompt_injection_suspected"
            if gate["reason"] == "suspicious_instruction"
            else "intent_gate_rejected"
        )
        raise HTTPException(
            400,
            detail={
                "reason": gate["reason"],
                "intent": intent,
                "gate_version": GATE_VERSION,
            },
        )

    if intent == "anomaly_follow_up":
        if body.analysis_id is None:
            return clarify(
                request, intent,
                "Sélectionnez une analyse existante avec analysis_id.",
            )

        stored = get_analysis(analysis_id=body.analysis_id, user=user)
        result = stored["result"]

        payload = answer(
            intent,
            result["interpretation"],
            sources=result["sources"],
            analysis_id=str(stored["id"]),
            classification=result["classification"],
            baseline_mean=result["baseline_mean"],
            threshold_value=result["threshold_value"],
            latest_value=result["latest_value"],
            data_as_of=result["data_as_of"],
            limitations=result["limitations"],
        )
        return render_with_llm(request, user, payload)

    if intent == "recommendation_request":
        # Direct Python calls don't execute FastAPI dependencies.
        # Explicit authorization is required before invoking the agent.
        if user["role"] not in {"operator", "tenant_admin", "client"}:
            raise HTTPException(403, "Permissions insuffisantes")

    if body.sensor_id is None or body.resource is None:
        return clarify(
            request, intent,
            "Sélectionnez sensor_id et resource (water ou energy).",
        )

    if intent == "q_and_a":
        with connect() as conn:
            set_tenant(conn, user["tenant_id"])
            reading = conn.execute(
                """
                SELECT id, sensor_id, resource, value, unit,
                       measured_at, data_source, interval_seconds
                FROM bws_ai.readings
                WHERE tenant_id = %s AND sensor_id = %s AND resource = %s
                  AND interval_seconds = 3600
                  AND measured_at <= now()
                ORDER BY measured_at DESC, id DESC
                LIMIT 1
                """,
                (user["tenant_id"], body.sensor_id, body.resource),
            ).fetchone()

        if reading is None:
            raise HTTPException(404, "Aucune mesure horaire accessible")

        source = {
            "reading_id": str(reading["id"]),
            "sensor_id": reading["sensor_id"],
            "value": float(reading["value"]),
            "unit": reading["unit"],
            "measured_at": reading["measured_at"].isoformat(),
            "data_source": reading["data_source"],
            "interval_seconds": reading["interval_seconds"],
        }

        text = (
            f"La dernière mesure horaire disponible pour "
            f"{reading['sensor_id']} est de {reading['value']} "
            f"{reading['unit']}, à {reading['measured_at'].isoformat()}. "
            f"Source: {reading['data_source']}."
        )
        payload = answer(intent, text, sources=[source])
        return render_with_llm(request, user, payload)

    if intent == "recommendation_request":
        confirmation = prepare_analysis(
            resource=body.resource,
            sensor_id=body.sensor_id,
            request=request,
            user=user,
        )
        return answer(
            intent,
            "Vérifiez la prévisualisation, puis confirmez ou annulez "
            "l’enregistrement de cette analyse.",
            sources=confirmation["preview"]["sources"],
            needs_confirmation=True,
            confirmation=confirmation,
            proposal_created=False,
        )

    raise HTTPException(400, "Intent non pris en charge")
