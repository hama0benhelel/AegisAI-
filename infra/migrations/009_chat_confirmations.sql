BEGIN;

CREATE TABLE bws_ai.chat_confirmations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES bws_ai.tenants(id),
    requested_by uuid NOT NULL,
    resource text NOT NULL CHECK (resource IN ('water', 'energy')),
    sensor_id text NOT NULL CHECK (length(sensor_id) BETWEEN 1 AND 100),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL
        DEFAULT (clock_timestamp() + interval '10 minutes'),
    decided_at timestamptz,
    analysis_id uuid UNIQUE,
    FOREIGN KEY (tenant_id, requested_by)
        REFERENCES bws_ai.users(tenant_id, id),
    FOREIGN KEY (tenant_id, analysis_id)
        REFERENCES bws_ai.analyses(tenant_id, id),
    CHECK (expires_at > created_at),
    CHECK (
        (status = 'pending' AND decided_at IS NULL AND analysis_id IS NULL)
        OR
        (status = 'cancelled' AND decided_at IS NOT NULL AND analysis_id IS NULL)
        OR
        (status = 'confirmed' AND decided_at IS NOT NULL AND analysis_id IS NOT NULL)
    )
);

CREATE INDEX chat_confirmations_tenant_user_idx
    ON bws_ai.chat_confirmations (tenant_id, requested_by, created_at DESC);

ALTER TABLE bws_ai.chat_confirmations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.chat_confirmations FORCE ROW LEVEL SECURITY;

CREATE POLICY chat_confirmations_tenant
ON bws_ai.chat_confirmations
FOR ALL TO aegisai_app
USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
)
WITH CHECK (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
);

REVOKE ALL ON bws_ai.chat_confirmations FROM PUBLIC, aegisai_app;
GRANT SELECT ON bws_ai.chat_confirmations TO aegisai_app;

GRANT INSERT (
    tenant_id, requested_by, resource, sensor_id, snapshot
) ON bws_ai.chat_confirmations TO aegisai_app;

GRANT UPDATE (
    status, decided_at, analysis_id
) ON bws_ai.chat_confirmations TO aegisai_app;

COMMIT;
