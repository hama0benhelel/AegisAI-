BEGIN;

CREATE TABLE bws_ai.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES bws_ai.tenants(id),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (
        role IN ('viewer', 'operator', 'tenant_admin')
    ),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (email = lower(btrim(email))),
    CHECK (length(email) BETWEEN 3 AND 254)
);

CREATE INDEX users_tenant_idx ON bws_ai.users (tenant_id);

ALTER TABLE bws_ai.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.users FORCE ROW LEVEL SECURITY;

CREATE POLICY users_tenant_isolation ON bws_ai.users
    FOR SELECT TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT (id, tenant_id, email, role, is_active, created_at)
    ON bws_ai.users TO aegisai_app;

COMMIT;
