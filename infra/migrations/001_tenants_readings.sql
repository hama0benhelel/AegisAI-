BEGIN;

CREATE TABLE bws_ai.tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bws_ai.readings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES bws_ai.tenants(id),
    sensor_id TEXT NOT NULL,
    resource TEXT NOT NULL CHECK (resource IN ('water', 'energy')),
    value NUMERIC(14, 3) NOT NULL CHECK (value >= 0),
    unit TEXT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (resource = 'water' AND unit = 'm3')
        OR (resource = 'energy' AND unit = 'kWh')
    )
);

CREATE INDEX readings_tenant_time_idx
    ON bws_ai.readings (tenant_id, measured_at DESC);

ALTER TABLE bws_ai.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.tenants FORCE ROW LEVEL SECURITY;

ALTER TABLE bws_ai.readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.readings FORCE ROW LEVEL SECURITY;

CREATE POLICY tenants_isolation ON bws_ai.tenants
    FOR SELECT TO aegisai_app
    USING (
        id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

CREATE POLICY readings_isolation ON bws_ai.readings
    FOR SELECT TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT ON bws_ai.tenants, bws_ai.readings TO aegisai_app;

COMMIT;
