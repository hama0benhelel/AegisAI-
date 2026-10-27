from app.semantic_router import resolve_message
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from psycopg.errors import LockNotAvailable

from app.chat import ChatInput, answer, chat, clarify
from app.db import connect, set_tenant
from app.intent_gate import classify, normalize
from app.permissions import require_roles
from app.workflow import record_event

router = APIRouter(prefix="/chat/conversations", tags=["Conversations"])

conversation_user = require_roles(
    "client", "viewer", "operator", "tenant_admin"
)

FOLLOW_UPS = {
    "analyse-la": ("recommendation_request", "Analyse la consommation"),
    "analyse ce compteur": ("recommendation_request", "Analyse la consommation"),
    "analyze it": ("recommendation_request", "Analyse la consommation"),
    "explique-la": ("anomaly_follow_up", "Explique cette analyse"),
    "explique-moi cette analyse": ("anomaly_follow_up", "Explique cette analyse"),
    "explique davantage": ("anomaly_follow_up", "Explique cette analyse"),
    "explain it": ("anomaly_follow_up", "Explique cette analyse"),
}


def owner_context(conn, user):
    set_tenant(conn, user["tenant_id"])
    conn.execute(
        "SELECT set_config('app.user_id', %s, true)",
        (str(user["id"]),),
    )


@router.post("", status_code=201)
def create_conversation(
    request: Request,
    response: Response,
    user=Depends(conversation_user),
):
    with connect() as conn:
        owner_context(conn, user)
        row = conn.execute(
            """
            INSERT INTO bws_ai.chat_conversations (tenant_id, user_id)
            VALUES (%s, %s)
            RETURNING id, created_at, expires_at
            """,
            (user["tenant_id"], user["id"]),
        ).fetchone()
        record_event(
            conn, request, user, "conversation_created", row["id"], 201
        )

    response.headers["Cache-Control"] = "no-store"
    return row


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    body: ChatInput,
    request: Request,
    response: Response,
    user=Depends(conversation_user),
):
    response.headers["Cache-Control"] = "no-store"

    with connect() as conn:
        owner_context(conn, user)

        # One request at a time per conversation; do not wait behind an LLM call.
        try:
            context = conn.execute(
                """
                SELECT *,
                       clock_timestamp() >= expires_at AS expired
                FROM bws_ai.chat_conversations
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                FOR UPDATE NOWAIT
                """,
                (conversation_id, user["tenant_id"], user["id"]),
            ).fetchone()
        except LockNotAvailable:
            raise HTTPException(
                409, "Une demande est déjà en cours dans cette conversation"
            ) from None

        if context is None:
            raise HTTPException(404, "Conversation introuvable")
        if context["expired"]:
            raise HTTPException(409, "Conversation expirée : créez-en une nouvelle")

        gate = classify(body.message)
        text = normalize(body.message).rstrip(" .?!")
        follow_up = None
        local_follow_up = (
            gate["decision"] == "reject"
            and gate["reason"] == "out_of_scope_or_unrecognized"
            and text in FOLLOW_UPS
        )
        if not local_follow_up and text not in {"oui", "yes", "confirme", "je confirme"}:
            gate = resolve_message(body.message, request, user)

        # Only exact follow-ups can reuse context.
        # Security rejections are never overridden.
        if (
            gate["decision"] == "reject"
            and gate["reason"] == "out_of_scope_or_unrecognized"
        ):
            follow_up = FOLLOW_UPS.get(text)

        if text in {"oui", "yes", "confirme", "je confirme"}:
            return {
                **answer(
                    "action_plan_update",
                    "Pour confirmer une opération, utilisez son bouton "
                    "de confirmation après avoir vérifié la prévisualisation. "
                    "Ce message n’exécute aucune action.",
                    needs_clarification=True,
                ),
                "conversation_id": str(conversation_id),
            }

        resource = body.resource or gate.get("resource_hint")
        sensor_id = body.sensor_id or gate.get("sensor_hint")
        analysis_id = body.analysis_id
        confirmation_id = context["confirmation_id"]

        # A newly selected resource or sensor invalidates the old context.
        changed = (
            (resource is not None and resource != context["resource"])
            or (sensor_id is not None and sensor_id != context["sensor_id"])
        )

        if not changed:
            resource = resource or context["resource"]
            sensor_id = sensor_id or context["sensor_id"]

        period_changed = (
            gate["decision"] == "allow"
            and not gate.get("dialogue_act")
            and gate.get("period", "latest") != context["period"]
        )
        if changed or period_changed:
            confirmation_id = None
        else:
            analysis_id = analysis_id or context["analysis_id"]

        # Resolve only a confirmation owned by this user and tenant.
        if confirmation_id and not analysis_id:
            confirmed = conn.execute(
                """
                SELECT analysis_id
                FROM bws_ai.chat_confirmations
                WHERE id = %s AND tenant_id = %s AND requested_by = %s
                  AND status = 'confirmed'
                """,
                (confirmation_id, user["tenant_id"], user["id"]),
            ).fetchone()
            if confirmed:
                analysis_id = confirmed["analysis_id"]

        if follow_up:
            intent, canonical_message = follow_up
            if intent == "recommendation_request" and context["period"] != "latest":
                return {
                    **clarify(
                        request, intent,
                        "La dernière demande concernait une journée précise. "
                        "L’analyse d’anomalie de cette journée n’est pas disponible. "
                        "Demandez explicitement une analyse des dernières mesures.",
                    ),
                    "conversation_id": str(conversation_id),
                }
            if intent == "recommendation_request" and not sensor_id:
                return {
                    **clarify(
                        request, intent,
                        "De quel compteur parlez-vous ? "
                        "Consultez ou sélectionnez d’abord un compteur.",
                    ),
                    "conversation_id": str(conversation_id),
                }
            if intent == "anomaly_follow_up" and not analysis_id:
                return {
                    **clarify(
                        request, intent,
                        "Aucune analyse enregistrée n’est sélectionnée. "
                        "Confirmez d’abord son enregistrement "
                        "ou sélectionnez une analyse existante.",
                    ),
                    "conversation_id": str(conversation_id),
                }
            message = canonical_message
        else:
            message = body.message

        effective = body.model_copy(update={
            "message": message,
            "resource": resource,
            "sensor_id": sensor_id,
            "analysis_id": analysis_id,
        })

        # Existing chat performs its own gate, authorization and DB checks.
        payload = chat(body=effective, request=request, user=user)

        if not payload.get("dialogue_act") and not payload.get("needs_clarification"):
            new_sensor = payload.get("sensor_id") or sensor_id
            new_resource = payload.get("resource") or resource
            new_analysis = analysis_id
            new_confirmation = confirmation_id

            if payload.get("intent") == "q_and_a" and payload.get("sources"):
                source = payload["sources"][0]
                new_sensor = source.get("sensor_id")
                new_resource = {
                    "m3": "water", "kWh": "energy"
                }.get(source.get("unit"))

            pending = payload.get("confirmation")
            if pending:
                new_sensor = pending["sensor_id"]
                new_resource = pending["resource"]
                new_confirmation = pending["id"]
                new_analysis = None

            if payload.get("analysis_id"):
                new_analysis = payload["analysis_id"]
                # Read back an authorized reference, never trust client metadata.
                stored = conn.execute(
                    """
                    SELECT sensor_id, agent
                    FROM bws_ai.analyses
                    WHERE id = %s AND tenant_id = %s
                    """,
                    (new_analysis, user["tenant_id"]),
                ).fetchone()
                if stored is None:
                    raise HTTPException(404, "Analyse introuvable")
                new_sensor = stored["sensor_id"]
                new_resource = stored["agent"]

            conn.execute(
                """
                UPDATE bws_ai.chat_conversations
                SET resource = %s, sensor_id = %s,
                    analysis_id = %s, confirmation_id = %s, period = %s,
                    updated_at = clock_timestamp(),
                    expires_at = clock_timestamp() + interval '30 minutes'
                WHERE id = %s AND tenant_id = %s AND user_id = %s
                """,
                (
                    new_resource, new_sensor, new_analysis, new_confirmation,
                    payload.get("period", {}).get("kind", "latest"),
                    conversation_id, user["tenant_id"], user["id"],
                ),
            )

        return {**payload, "conversation_id": str(conversation_id)}
