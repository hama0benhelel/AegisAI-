from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.auth import current_user
from app.db import connect, set_tenant
from app.permissions import require_roles

router = APIRouter(tags=["Approval workflow"])


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action_type: Literal["create_inspection_task"] = "create_inspection_task"
    sensor_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=5, max_length=200)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["approve", "reject"]
    comment: str | None = Field(default=None, max_length=500)


def record_event(conn, request, user, event_type, proposal_id, status_code=200):
    # Same transaction as the business operation: failure rolls everything back.
    conn.execute(
        """
        INSERT INTO bws_ai.audit_events (
            trace_id, occurred_at, event_type, user_id, tenant_id,
            method, route, status_code, duration_ms, object_id
        )
        VALUES (%s, clock_timestamp(), %s, %s, %s, %s, %s, %s, 0, %s)
        """,
        (
            UUID(request.state.trace_id),
            event_type,
            user["id"],
            user["tenant_id"],
            request.method,
            request.scope["route"].path,
            status_code,
            proposal_id,
        ),
    )


def locked_proposal(conn, proposal_id, tenant_id):
    row = conn.execute(
        """
        SELECT * FROM bws_ai.proposals
        WHERE id = %s AND tenant_id = %s
        FOR UPDATE
        """,
        (proposal_id, tenant_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Proposition introuvable")
    return row


@router.post("/proposals", status_code=201)
def create_proposal(
    body: ProposalInput,
    request: Request,
    user=Depends(require_roles("operator", "tenant_admin", "client")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])

        sensor = conn.execute(
            """
            SELECT sensor_id FROM bws_ai.readings
            WHERE tenant_id = %s AND sensor_id = %s
            LIMIT 1
            """,
            (user["tenant_id"], body.sensor_id),
        ).fetchone()
        if sensor is None:
            raise HTTPException(404, "Capteur introuvable")

        proposal = conn.execute(
            """
            INSERT INTO bws_ai.proposals
                (tenant_id, action_type, sensor_id, title, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                user["tenant_id"], body.action_type,
                body.sensor_id, body.title, user["id"],
            ),
        ).fetchone()

        record_event(
            conn, request, user, "proposal_created", proposal["id"], 201
        )

    return proposal


@router.get("/proposals")
def list_proposals(user=Depends(current_user)):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        rows = conn.execute(
            """
            SELECT * FROM bws_ai.proposals
            WHERE tenant_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 100
            """,
            (user["tenant_id"],),
        ).fetchall()
    return {"items": rows}


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: UUID, user=Depends(current_user)):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        row = conn.execute(
            """
            SELECT * FROM bws_ai.proposals
            WHERE id = %s AND tenant_id = %s
            """,
            (proposal_id, user["tenant_id"]),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Proposition introuvable")
    return row


@router.post("/proposals/{proposal_id}/decision")
def decide(
    proposal_id: UUID,
    body: DecisionInput,
    request: Request,
    user=Depends(require_roles("tenant_admin", "client")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        proposal = locked_proposal(conn, proposal_id, user["tenant_id"])

        if user["role"] == "client" and proposal["created_by"] != user["id"]:
            raise HTTPException(404, "Proposition introuvable")

        if proposal["status"] != "pending":
            raise HTTPException(409, "La proposition a déjà été décidée")

        status = "approved" if body.decision == "approve" else "rejected"
        proposal = conn.execute(
            """
            UPDATE bws_ai.proposals
            SET status = %s, decided_by = %s, decided_at = now(),
                decision_comment = %s
            WHERE id = %s AND tenant_id = %s
            RETURNING *
            """,
            (status, user["id"], body.comment, proposal_id, user["tenant_id"]),
        ).fetchone()

        record_event(conn, request, user, f"proposal_{status}", proposal_id)

    return proposal


@router.post("/proposals/{proposal_id}/execute")
def execute(
    proposal_id: UUID,
    request: Request,
    user=Depends(require_roles("operator", "tenant_admin", "client")),
):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        proposal = locked_proposal(conn, proposal_id, user["tenant_id"])

        if user["role"] == "client" and proposal["created_by"] != user["id"]:
            raise HTTPException(404, "Proposition introuvable")

        if proposal["status"] == "executed":
            task = conn.execute(
                """
                SELECT * FROM bws_ai.tasks
                WHERE proposal_id = %s AND tenant_id = %s
                """,
                (proposal_id, user["tenant_id"]),
            ).fetchone()
            if task is None:
                raise HTTPException(500, "État du workflow incohérent")
            return {"task": task, "already_executed": True}

        if proposal["status"] != "approved":
            raise HTTPException(409, "Approbation requise avant exécution")

        if user["role"] == "client" and proposal["decided_by"] != user["id"]:
            raise HTTPException(409, "Votre confirmation personnelle est requise")

        if proposal["action_type"] != "create_inspection_task":
            raise HTTPException(409, "Action non prise en charge")

        task = conn.execute(
            """
            INSERT INTO bws_ai.tasks
                (tenant_id, proposal_id, sensor_id, title, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                user["tenant_id"], proposal_id,
                proposal["sensor_id"], proposal["title"], user["id"],
            ),
        ).fetchone()

        conn.execute(
            """
            UPDATE bws_ai.proposals
            SET status = 'executed', executed_by = %s, executed_at = now()
            WHERE id = %s AND tenant_id = %s
            """,
            (user["id"], proposal_id, user["tenant_id"]),
        )

        record_event(conn, request, user, "proposal_executed", proposal_id)

    return {"task": task, "already_executed": False}


@router.get("/tasks")
def list_tasks(user=Depends(current_user)):
    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        rows = conn.execute(
            """
            SELECT * FROM bws_ai.tasks
            WHERE tenant_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 100
            """,
            (user["tenant_id"],),
        ).fetchall()
    return {"items": rows}
