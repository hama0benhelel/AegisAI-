"""One bounded event per failed remote call; no body, exception text or credentials."""
from datetime import datetime, timezone
from functools import wraps
import json
from fastapi import HTTPException


def observed_agent_call(resource):
    if resource not in {"water", "energy", "gas"}:
        raise ValueError("Unknown agent")
    def decorate(function):
        @wraps(function)
        def invoke(rows, user, request):
            try:
                return function(rows, user, request)
            except HTTPException as error:
                if 500 <= error.status_code <= 599:
                    reason = (
                        "invalid_agent_response" if error.status_code == 502
                        else "agent_unavailable" if error.status_code == 503
                        else "agent_call_error"
                    )
                    print(json.dumps({
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                        "event_type": "agent_call_failed",
                        "target_service": resource + "-agent",
                        "resource": resource,
                        "tenant_id": str(user["tenant_id"]),
                        "user_id": str(user["id"]),
                        "trace_id": request.state.trace_id,
                        "status_code": error.status_code,
                        "reason": reason,
                    }), flush=True)
                raise
        return invoke
    return decorate
