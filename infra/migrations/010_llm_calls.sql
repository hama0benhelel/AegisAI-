BEGIN;

CREATE TABLE bws_ai.llm_calls (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES bws_ai.tenants(id),
    user_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    provider text NOT NULL DEFAULT 'groq',
    model text NOT NULL,
    operation text NOT NULL,
    prompt_version text NOT NULL,
    status text NOT NULL DEFAULT 'started'
        CHECK (status IN ('started', 'success', 'fallback')),
    reason text,
    input_context jsonb NOT NULL,
    output_text text,
    prompt_tokens integer CHECK (prompt_tokens >= 0),
    completion_tokens integer CHECK (completion_tokens >= 0),
    total_tokens integer CHECK (total_tokens >= 0),
    duration_ms integer CHECK (duration_ms >= 0),
    FOREIGN KEY (tenant_id, user_id)
        REFERENCES bws_ai.users(tenant_id, id)
);

CREATE INDEX llm_calls_tenant_time_idx
    ON bws_ai.llm_calls (tenant_id, created_at DESC);

ALTER TABLE bws_ai.llm_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.llm_calls FORCE ROW LEVEL SECURITY;

CREATE POLICY llm_calls_tenant
ON bws_ai.llm_calls
FOR ALL TO aegisai_app
USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
);

REVOKE ALL ON bws_ai.llm_calls FROM PUBLIC, aegisai_app;
GRANT SELECT ON bws_ai.llm_calls TO aegisai_app;

GRANT INSERT (
    tenant_id, user_id, trace_id, model, operation,
    prompt_version, input_context
) ON bws_ai.llm_calls TO aegisai_app;

GRANT UPDATE (
    completed_at, status, reason, output_text,
    prompt_tokens, completion_tokens, total_tokens, duration_ms
) ON bws_ai.llm_calls TO aegisai_app;

COMMIT;
