BEGIN;

ALTER TABLE bws_ai.chat_conversations
    ADD COLUMN period text NOT NULL DEFAULT 'latest'
    CHECK (period IN ('latest', 'today', 'yesterday'));

GRANT UPDATE (period) ON bws_ai.chat_conversations TO aegisai_app;

COMMIT;
