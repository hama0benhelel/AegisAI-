BEGIN;

CREATE TABLE bws_ai.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    user_id UUID,
    tenant_id UUID,
    method TEXT NOT NULL,
    route TEXT NOT NULL,
    status_code INTEGER NOT NULL CHECK (status_code BETWEEN 100 AND 599),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0)
);

CREATE INDEX audit_events_time_idx
    ON bws_ai.audit_events (occurred_at DESC);

CREATE INDEX audit_events_tenant_time_idx
    ON bws_ai.audit_events (tenant_id, occurred_at DESC);

CREATE INDEX audit_events_trace_idx
    ON bws_ai.audit_events (trace_id);

REVOKE ALL ON bws_ai.audit_events FROM PUBLIC;
GRANT INSERT ON bws_ai.audit_events TO aegisai_app;

COMMIT;
