from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from psycopg.types.json import Jsonb

from app.agents import analyze
from app.db import connect, set_tenant
from app.permissions import require_roles
from app.workflow import record_event

router = APIRouter(tags=["Chat confirmations"])


class ConfirmationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["confirm", "cancel"]


def prepare_analysis(resource, sensor_id, request, user):
    # This function is also called directly from the chat route.
    if user["role"] not in {"operator", "tenant_admin"}:
        raise HTTPException(403, "Permissions insuffisantes")

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
            (user["tenant_id"], sensor_id, resource),
        ).fetchall()

        if not rows:
            raise HTTPException(404, "Aucune série horaire accessible")

        # Freeze the result and its sources. No analysis is inserted here.
        snapshot = analyze(resource, list(reversed(rows)))

        pending = conn.execute(
            """
            INSERT INTO bws_ai.chat_confirmations (
                tenant_id, requested_by, resource, sensor_id, snapshot
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, status, created_at, expires_at
            """,
            (
                user["tenant_id"], user["id"], resource,
                sensor_id, Jsonb(snapshot),
            ),
        ).fetchone()

        record_event(
            conn, request, user, "chat_confirmation_requested", pending["id"]
        )

    return {
        **pending,
        "operation": "save_consumption_analysis",
        "resource": resource,
        "sensor_id": sensor_id,
        "preview": snapshot,
    }


@router.post("/chat/confirmations/{confirmation_id}/decision")
def decide_confirmation(
    confirmation_id: UUID,
    body: ConfirmationDecision,
    request: Request,
    user=Depends(require_roles("operator", "tenant_admin")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])

        pending = conn.execute(
            """
            SELECT *
            FROM bws_ai.chat_confirmations
            WHERE id = %s AND tenant_id = %s AND requested_by = %s
            FOR UPDATE
            """,
            (confirmation_id, user["tenant_id"], user["id"]),
        ).fetchone()

        if pending is None:
            raise HTTPException(404, "Demande de confirmation introuvable")

        if pending["status"] == "confirmed":
            if body.decision != "confirm":
                raise HTTPException(409, "La demande a déjà été confirmée")
            return {
                "confirmation_id": pending["id"],
                "status": "confirmed",
                "analysis_id": pending["analysis_id"],
                "already_processed": True,
            }

        if pending["status"] == "cancelled":
            if body.decision != "cancel":
                raise HTTPException(409, "La demande a été annulée")
            return {
                "confirmation_id": pending["id"],
                "status": "cancelled",
                "analysis_id": None,
                "already_processed": True,
            }

        expired = conn.execute(
            "SELECT clock_timestamp() >= %s AS expired",
            (pending["expires_at"],),
        ).fetchone()["expired"]

        if expired:
            raise HTTPException(409, "Demande expirée : envoyez une nouvelle demande")

        if body.decision == "cancel":
            conn.execute(
                """
                UPDATE bws_ai.chat_confirmations
                SET status = 'cancelled', decided_at = clock_timestamp()
                WHERE id = %s AND tenant_id = %s AND requested_by = %s
                """,
                (confirmation_id, user["tenant_id"], user["id"]),
            )
            record_event(
                conn, request, user, "chat_confirmation_cancelled", confirmation_id
            )
            return {
                "confirmation_id": confirmation_id,
                "status": "cancelled",
                "analysis_id": None,
                "already_processed": False,
            }

        snapshot = pending["snapshot"]
        saved = conn.execute(
            """
            INSERT INTO bws_ai.analyses (
                tenant_id, requested_by, agent, sensor_id, rule_version, result
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user["tenant_id"], user["id"],
                pending["resource"], pending["sensor_id"],
                snapshot["rule_version"], Jsonb(snapshot),
            ),
        ).fetchone()

        conn.execute(
            """
            UPDATE bws_ai.chat_confirmations
            SET status = 'confirmed', decided_at = clock_timestamp(),
                analysis_id = %s
            WHERE id = %s AND tenant_id = %s AND requested_by = %s
            """,
            (saved["id"], confirmation_id, user["tenant_id"], user["id"]),
        )

        record_event(
            conn, request, user, "analysis_created", saved["id"]
        )
        record_event(
            conn, request, user, "chat_confirmation_confirmed", confirmation_id
        )

        return {
            "confirmation_id": confirmation_id,
            "status": "confirmed",
            "analysis_id": saved["id"],
            "already_processed": False,
        }
