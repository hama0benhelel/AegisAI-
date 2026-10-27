BEGIN;

ALTER TABLE bws_ai.users
    DROP CONSTRAINT users_role_check;

ALTER TABLE bws_ai.users
    ADD CONSTRAINT users_role_check
    CHECK (
        role IN (
            'viewer', 'operator', 'tenant_admin',
            'client', 'security_admin'
        )
    );

-- Separate database identity for central security metadata.
-- No login until its credentials and backend configuration are ready.
CREATE ROLE aegisai_security_reader
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

GRANT CONNECT ON DATABASE aegisai TO aegisai_security_reader;
GRANT USAGE ON SCHEMA bws_ai TO aegisai_security_reader;

GRANT SELECT (
    id, trace_id, occurred_at, event_type,
    user_id, tenant_id, method, route,
    status_code, duration_ms, object_id
)
ON bws_ai.audit_events TO aegisai_security_reader;

CREATE POLICY audit_bws_security_read
    ON bws_ai.audit_events
    FOR SELECT TO aegisai_security_reader
    USING (true);

GRANT SELECT (
    id, tenant_id, user_id, trace_id,
    created_at, completed_at, provider, model,
    operation, prompt_version, status, reason,
    prompt_tokens, completion_tokens, total_tokens,
    duration_ms
)
ON bws_ai.llm_calls TO aegisai_security_reader;

CREATE POLICY llm_bws_security_read
    ON bws_ai.llm_calls
    FOR SELECT TO aegisai_security_reader
    USING (true);

COMMIT;
