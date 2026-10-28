from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.permissions import require_roles
from app.security_db import connect_security

router = APIRouter(prefix="/bws/security", tags=["BWS security"])


@router.get("/audit")
def read_security_events(
    response: Response,
    tenant_id: UUID | None = None,
    user_id: UUID | None = None,
    trace_id: UUID | None = None,
    event_type: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(require_roles("security_admin")),
):
    filters = []
    parameters = []

    for column, value in (
        ("tenant_id", tenant_id),
        ("user_id", user_id),
        ("trace_id", trace_id),
        ("event_type", event_type),
    ):
        if value is not None:
            filters.append(f"{column} = %s")
            parameters.append(value)

    where = " WHERE " + " AND ".join(filters) if filters else ""
    parameters.append(limit)

    with connect_security() as conn:
        rows = conn.execute(
            """
            SELECT id, trace_id, occurred_at, event_type,
                   user_id, tenant_id, method, route,
                   status_code, duration_ms, object_id
            FROM bws_ai.audit_events
            """
            + where
            + " ORDER BY occurred_at DESC, id DESC LIMIT %s",
            tuple(parameters),
        ).fetchall()

    response.headers["Cache-Control"] = "no-store"
    return {"items": rows}


@router.get("/llm-calls")
def read_security_llm_calls(
    response: Response,
    tenant_id: UUID | None = None,
    trace_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(require_roles("security_admin")),
):
    filters = []
    parameters = []

    for column, value in (
        ("tenant_id", tenant_id),
        ("trace_id", trace_id),
    ):
        if value is not None:
            filters.append(f"{column} = %s")
            parameters.append(value)

    where = " WHERE " + " AND ".join(filters) if filters else ""
    parameters.append(limit)

    with connect_security() as conn:
        rows = conn.execute(
            """
            SELECT id, tenant_id, user_id, trace_id,
                   created_at, completed_at, provider, model,
                   operation, prompt_version, status, reason,
                   prompt_tokens, completion_tokens, total_tokens,
                   duration_ms
            FROM bws_ai.llm_calls
            """
            + where
            + " ORDER BY created_at DESC, id DESC LIMIT %s",
            tuple(parameters),
        ).fetchall()

    response.headers["Cache-Control"] = "no-store"
    return {"items": rows}
