BEGIN;

ALTER TABLE bws_ai.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.audit_events FORCE ROW LEVEL SECURITY;

-- The backend must still record anonymous and rejected requests.
CREATE POLICY audit_append ON bws_ai.audit_events
    FOR INSERT TO aegisai_app
    WITH CHECK (true);

CREATE POLICY audit_tenant_read ON bws_ai.audit_events
    FOR SELECT TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT ON bws_ai.audit_events TO aegisai_app;

COMMIT;
