from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError

from app.db import connect, set_tenant
from app.permissions import require_roles
from app.workflow import ProposalInput, record_event

router = APIRouter(tags=["Analysis proposals"])


@router.post("/analyses/{analysis_id}/proposal", status_code=201)
def proposal_from_analysis(
    analysis_id: UUID,
    request: Request,
    response: Response,
    user=Depends(require_roles("operator", "tenant_admin")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])

        analysis = conn.execute(
            """
            SELECT id, sensor_id, result
            FROM bws_ai.analyses
            WHERE id = %s AND tenant_id = %s
            """,
            (analysis_id, user["tenant_id"]),
        ).fetchone()

        if analysis is None:
            raise HTTPException(404, "Analyse introuvable")

        suggestion = analysis["result"].get("suggested_proposal")
        if suggestion is None:
            raise HTTPException(409, "Cette analyse ne propose aucune action")

        try:
            validated = ProposalInput.model_validate(suggestion)
        except ValidationError:
            raise HTTPException(409, "Suggestion enregistrée invalide") from None

        if validated.sensor_id != analysis["sensor_id"]:
            raise HTTPException(409, "Capteur de la suggestion incohérent")

        proposal = conn.execute(
            """
            INSERT INTO bws_ai.proposals (
                tenant_id, analysis_id, action_type,
                sensor_id, title, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (analysis_id) DO NOTHING
            RETURNING *
            """,
            (
                user["tenant_id"],
                analysis_id,
                validated.action_type,
                validated.sensor_id,
                validated.title,
                user["id"],
            ),
        ).fetchone()

        if proposal is not None:
            record_event(
                conn, request, user, "proposal_created", proposal["id"], 201
            )
            already_exists = False
        else:
            # Separate statement: sees the committed concurrent insertion
            # under PostgreSQL's default READ COMMITTED isolation.
            proposal = conn.execute(
                """
                SELECT * FROM bws_ai.proposals
                WHERE analysis_id = %s AND tenant_id = %s
                """,
                (analysis_id, user["tenant_id"]),
            ).fetchone()

            if proposal is None:
                raise HTTPException(409, "Conflit de création, réessayez")

            already_exists = True
            response.status_code = 200

    return {
        "proposal": proposal,
        "already_exists": already_exists,
    }
