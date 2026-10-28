BEGIN;

ALTER TABLE bws_ai.users
    DROP CONSTRAINT users_role_check;

ALTER TABLE bws_ai.users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('viewer', 'operator', 'tenant_admin', 'client'));

COMMIT;
