BEGIN;

CREATE TABLE bws_ai.chat_conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    resource text CHECK (resource IN ('water', 'energy')),
    sensor_id text CHECK (length(sensor_id) BETWEEN 1 AND 100),
    analysis_id uuid,
    confirmation_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL
        DEFAULT (clock_timestamp() + interval '30 minutes'),

    FOREIGN KEY (tenant_id, user_id)
        REFERENCES bws_ai.users(tenant_id, id),

    FOREIGN KEY (tenant_id, analysis_id)
        REFERENCES bws_ai.analyses(tenant_id, id),

    CHECK (
        (resource IS NULL AND sensor_id IS NULL)
        OR (resource IS NOT NULL AND sensor_id IS NOT NULL)
    ),
    CHECK (expires_at > created_at)
);

CREATE INDEX chat_conversations_owner_idx
    ON bws_ai.chat_conversations (tenant_id, user_id, updated_at DESC);

ALTER TABLE bws_ai.chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bws_ai.chat_conversations FORCE ROW LEVEL SECURITY;

CREATE POLICY chat_conversations_owner
    ON bws_ai.chat_conversations
    FOR ALL TO aegisai_app
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
    );

REVOKE ALL ON bws_ai.chat_conversations FROM PUBLIC, aegisai_app;

GRANT SELECT ON bws_ai.chat_conversations TO aegisai_app;
GRANT INSERT (tenant_id, user_id)
    ON bws_ai.chat_conversations TO aegisai_app;
GRANT UPDATE (
    resource, sensor_id, analysis_id, confirmation_id,
    updated_at, expires_at
) ON bws_ai.chat_conversations TO aegisai_app;

COMMIT;
