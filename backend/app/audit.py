import json
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import psycopg
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.db import connect


def persist_event(event):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO bws_ai.audit_events (
                trace_id, occurred_at, event_type,
                user_id, tenant_id, method, route,
                status_code, duration_ms
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event["trace_id"],
                event["occurred_at"],
                event["event_type"],
                event["user_id"],
                event["tenant_id"],
                event["method"],
                event["route"],
                event["status_code"],
                event["duration_ms"],
            ),
        )


def classify_event(route, method, status):
    if status >= 500:
        return "server_error"
    if status == 429:
        return "rate_limited"
    if route == "/auth/login" and method == "POST":
        if status == 200:
            return "login_success"
        if status == 401:
            return "login_failure"
    if status == 401:
        return "authentication_rejected"
    if status == 403:
        return "authorization_denied"
    if status >= 400:
        return "request_rejected"
    return "request_completed"


async def audit_middleware(request, call_next):
    # Avoid generating an audit record for each container health probe.
    if request.url.path in {"/health/live", "/health/ready"}:
        return await call_next(request)

    trace_id = str(uuid4())
    request.state.trace_id = trace_id
    started = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # Use the matched route template, not raw URLs or query parameters.
    matched_route = request.scope.get("route")
    route = getattr(matched_route, "path", "unmatched")
    principal = getattr(request.state, "audit_principal", None) or {}

    event = {
        "trace_id": trace_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "event_type": classify_event(
            route, request.method, response.status_code
        ),
        "user_id": principal.get("user_id"),
        "tenant_id": principal.get("tenant_id"),
        "method": request.method[:16],
        "route": route,
        "status_code": response.status_code,
        "duration_ms": int((perf_counter() - started) * 1000),
    }

    gate_event = getattr(request.state, "audit_event_type", None)
    if gate_event in {
        "prompt_injection_suspected",
        "intent_gate_rejected",
        "chat_clarification_required",
        "recommendations_presented",
        "knowledge_integrity_failed",
    } and (response.status_code < 500 or gate_event == "knowledge_integrity_failed"):
        event["event_type"] = gate_event

    try:
        await run_in_threadpool(persist_event, event)
        event["persisted"] = True
    except psycopg.Error:
        event["persisted"] = False
        event["audit_error"] = "database_unavailable"

    # No password, bearer token, request body or raw query string.
    print(json.dumps(event), flush=True)

    response.headers["X-Trace-ID"] = trace_id
    return response
