BEGIN;

ALTER TABLE bws_ai.readings
    ADD COLUMN data_source TEXT NOT NULL DEFAULT 'manual_demo',
    ADD COLUMN interval_seconds INTEGER
        CHECK (interval_seconds > 0);

CREATE TABLE bws_ai.analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES bws_ai.tenants(id),
    requested_by UUID NOT NULL,
    agent TEXT NOT NULL CHECK (agent IN ('water', 'energy')),
    sensor_id TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, requested_by)
        REFERENCES bws_ai.users(tenant_id, id)
);

CREATE INDEX analyses_tenant_time_idx
    ON bws_ai.analyses(tenant_id, created_at DESC);

ALTER TABLE bws_ai.analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.analyses FORCE ROW LEVEL SECURITY;

CREATE POLICY analyses_tenant_scope ON bws_ai.analyses
    TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT ON bws_ai.analyses TO aegisai_app;
GRANT INSERT (
    tenant_id, requested_by, agent, sensor_id, rule_version, result
) ON bws_ai.analyses TO aegisai_app;

COMMIT;
