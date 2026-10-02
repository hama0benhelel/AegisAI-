BEGIN;

ALTER TABLE bws_ai.users
    ADD CONSTRAINT users_tenant_id_unique UNIQUE (tenant_id, id);

ALTER TABLE bws_ai.audit_events
    ADD COLUMN object_id UUID;

CREATE TABLE bws_ai.proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES bws_ai.tenants(id),
    action_type TEXT NOT NULL DEFAULT 'create_inspection_task'
        CHECK (action_type = 'create_inspection_task'),
    sensor_id TEXT NOT NULL CHECK (length(sensor_id) BETWEEN 1 AND 100),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 5 AND 200),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'executed')),
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by UUID,
    decided_at TIMESTAMPTZ,
    decision_comment TEXT CHECK (length(decision_comment) <= 500),
    executed_by UUID,
    executed_at TIMESTAMPTZ,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, created_by)
        REFERENCES bws_ai.users(tenant_id, id),
    FOREIGN KEY (tenant_id, decided_by)
        REFERENCES bws_ai.users(tenant_id, id),
    FOREIGN KEY (tenant_id, executed_by)
        REFERENCES bws_ai.users(tenant_id, id),
    CHECK (
        (status = 'pending' AND decided_by IS NULL AND decided_at IS NULL)
        OR
        (status <> 'pending' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    ),
    CHECK (
        (status = 'executed' AND executed_by IS NOT NULL AND executed_at IS NOT NULL)
        OR
        (status <> 'executed' AND executed_by IS NULL AND executed_at IS NULL)
    )
);

CREATE TABLE bws_ai.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES bws_ai.tenants(id),
    proposal_id UUID NOT NULL UNIQUE,
    sensor_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, proposal_id)
        REFERENCES bws_ai.proposals(tenant_id, id),
    FOREIGN KEY (tenant_id, created_by)
        REFERENCES bws_ai.users(tenant_id, id)
);

CREATE INDEX proposals_tenant_time_idx
    ON bws_ai.proposals(tenant_id, created_at DESC);
CREATE INDEX tasks_tenant_time_idx
    ON bws_ai.tasks(tenant_id, created_at DESC);

ALTER TABLE bws_ai.proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.proposals FORCE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.tasks FORCE ROW LEVEL SECURITY;

CREATE POLICY proposals_tenant_scope ON bws_ai.proposals
    TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

CREATE POLICY tasks_tenant_scope ON bws_ai.tasks
    TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT ON bws_ai.proposals, bws_ai.tasks TO aegisai_app;

GRANT INSERT (tenant_id, action_type, sensor_id, title, created_by)
    ON bws_ai.proposals TO aegisai_app;

GRANT UPDATE (
    status, decided_by, decided_at, decision_comment,
    executed_by, executed_at
) ON bws_ai.proposals TO aegisai_app;

GRANT INSERT (tenant_id, proposal_id, sensor_id, title, created_by)
    ON bws_ai.tasks TO aegisai_app;

COMMIT;
