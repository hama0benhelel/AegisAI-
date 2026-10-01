BEGIN;

CREATE ROLE aegisai_auth_reader
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

GRANT USAGE ON SCHEMA bws_ai TO aegisai_auth_reader;

GRANT SELECT (id, tenant_id, email, password_hash, is_active)
    ON bws_ai.users TO aegisai_auth_reader;

CREATE POLICY users_auth_lookup ON bws_ai.users
    FOR SELECT TO aegisai_auth_reader
    USING (true);

CREATE FUNCTION bws_ai.lookup_login(p_email TEXT)
RETURNS TABLE (
    id UUID,
    tenant_id UUID,
    password_hash TEXT,
    is_active BOOLEAN
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT u.id, u.tenant_id, u.password_hash, u.is_active
    FROM bws_ai.users AS u
    WHERE u.email = p_email;
$$;

GRANT CREATE ON SCHEMA bws_ai TO aegisai_auth_reader;
ALTER FUNCTION bws_ai.lookup_login(TEXT) OWNER TO aegisai_auth_reader;
REVOKE CREATE ON SCHEMA bws_ai FROM aegisai_auth_reader;

REVOKE ALL ON FUNCTION bws_ai.lookup_login(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION bws_ai.lookup_login(TEXT) TO aegisai_app;

COMMIT;
