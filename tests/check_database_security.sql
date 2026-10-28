\set ON_ERROR_STOP on
-- Prepared lab only. No INSERT/UPDATE/DELETE, role or policy changes.
BEGIN READ ONLY;
DO $$
DECLARE
    role_name text;
    table_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['aegisai_app', 'aegisai_security_reader', 'aegisai_simulator'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname = role_name
              AND NOT rolsuper AND NOT rolbypassrls
              AND NOT rolcreaterole AND NOT rolcreatedb
        ) THEN
            RAISE EXCEPTION 'FAIL: role absent ou trop privilegie: %', role_name;
        END IF;
    END LOOP;
    FOREACH table_name IN ARRAY ARRAY[
        'tenants','users','readings','audit_events','proposals','tasks',
        'analyses','chat_confirmations','chat_conversations','llm_calls'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'bws_ai' AND c.relname = table_name
              AND c.relrowsecurity AND c.relforcerowsecurity
        ) THEN
            RAISE EXCEPTION 'FAIL: RLS non forcee: %', table_name;
        END IF;
    END LOOP;
    IF has_table_privilege('aegisai_app', 'bws_ai.audit_events', 'DELETE')
       OR has_any_column_privilege('aegisai_app', 'bws_ai.audit_events', 'UPDATE') THEN
        RAISE EXCEPTION 'FAIL: audit modifiable par application';
    END IF;
    IF has_any_column_privilege('aegisai_security_reader', 'bws_ai.readings', 'SELECT')
       OR has_any_column_privilege('aegisai_security_reader', 'bws_ai.users', 'SELECT')
       OR has_column_privilege('aegisai_security_reader', 'bws_ai.llm_calls', 'input_context', 'SELECT')
       OR has_column_privilege('aegisai_security_reader', 'bws_ai.llm_calls', 'output_text', 'SELECT')
       OR has_table_privilege('aegisai_security_reader', 'bws_ai.audit_events', 'DELETE')
       OR has_any_column_privilege('aegisai_security_reader', 'bws_ai.audit_events', 'UPDATE') THEN
        RAISE EXCEPTION 'FAIL: privileges excessifs du lecteur securite';
    END IF;
    IF NOT has_column_privilege('aegisai_security_reader', 'bws_ai.audit_events', 'trace_id', 'SELECT')
       OR NOT has_column_privilege('aegisai_security_reader', 'bws_ai.llm_calls', 'total_tokens', 'SELECT') THEN
        RAISE EXCEPTION 'FAIL: metadonnees supervision inaccessibles';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'aegisai_security_reader'
          AND 'default_transaction_read_only=on' = ANY(rolconfig)
    ) THEN
        RAISE EXCEPTION 'FAIL: defaut read-only du lecteur securite absent';
    END IF;
    IF has_any_column_privilege('aegisai_simulator', 'bws_ai.users', 'SELECT')
       OR has_any_column_privilege('aegisai_simulator', 'bws_ai.audit_events', 'SELECT')
       OR has_table_privilege('aegisai_simulator', 'bws_ai.readings', 'DELETE')
       OR has_any_column_privilege('aegisai_simulator', 'bws_ai.readings', 'UPDATE') THEN
        RAISE EXCEPTION 'FAIL: privileges excessifs du simulateur';
    END IF;
    RAISE NOTICE 'PASS: roles limites, RLS forcee et privileges de colonnes';
END $$;

SET LOCAL ROLE aegisai_app;
SELECT set_config('app.tenant_id', '', true);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM bws_ai.readings) THEN
        RAISE EXCEPTION 'FAIL: mesures visibles sans contexte tenant';
    END IF;
    RAISE NOTICE 'PASS: aucune mesure sans contexte tenant';
END $$;

SELECT set_config('app.tenant_id', '11111111-1111-4111-8111-111111111111', true);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM bws_ai.readings) THEN
        RAISE EXCEPTION 'FAIL: donnees de controle A absentes';
    END IF;
    IF EXISTS (SELECT 1 FROM bws_ai.readings
        WHERE tenant_id <> '11111111-1111-4111-8111-111111111111'::uuid) THEN
        RAISE EXCEPTION 'FAIL: mesures hors tenant A';
    END IF;
    RAISE NOTICE 'PASS: mesures visibles uniquement pour A';
END $$;

SELECT set_config('app.tenant_id', '22222222-2222-4222-8222-222222222222', true);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM bws_ai.readings) THEN
        RAISE EXCEPTION 'FAIL: donnees de controle B absentes';
    END IF;
    IF EXISTS (SELECT 1 FROM bws_ai.readings
        WHERE tenant_id <> '22222222-2222-4222-8222-222222222222'::uuid) THEN
        RAISE EXCEPTION 'FAIL: mesures hors tenant B';
    END IF;
    RAISE NOTICE 'PASS: mesures visibles uniquement pour B';
END $$;
ROLLBACK;
