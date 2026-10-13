from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import connect, set_tenant
from app.permissions import require_roles

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/audit")
def read_audit(
    tenant_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(require_roles("tenant_admin")),
):
    if tenant_id is not None and tenant_id != user["tenant_id"]:
        raise HTTPException(403, "Accès à un autre tenant interdit")

    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        events = conn.execute(
            """
            SELECT id, trace_id, occurred_at, event_type,
                   user_id, tenant_id, method, route,
                   status_code, duration_ms
            FROM bws_ai.audit_events
            WHERE tenant_id = %s
            ORDER BY occurred_at DESC, id DESC
            LIMIT %s
            """,
            (user["tenant_id"], limit),
        ).fetchall()

    return {"items": events}


@router.get("/llm-calls")
def read_llm_calls(
    tenant_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    user=Depends(require_roles("tenant_admin")),
):
    if tenant_id is not None and tenant_id != user["tenant_id"]:
        raise HTTPException(403, "Accès à un autre tenant interdit")

    with connect() as conn:
        set_tenant(conn, user["tenant_id"])
        rows = conn.execute(
            """
            SELECT id, tenant_id, user_id, trace_id,
                   created_at, completed_at, provider, model,
                   operation, prompt_version, status, reason,
                   prompt_tokens, completion_tokens, total_tokens,
                   duration_ms
            FROM bws_ai.llm_calls
            WHERE tenant_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (user["tenant_id"], limit),
        ).fetchall()

    return {"items": rows}
