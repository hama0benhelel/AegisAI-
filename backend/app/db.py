import os

import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(
        host="db",
        dbname="aegisai",
        user="aegisai_app",
        password=os.environ["APP_DB_PASSWORD"],
        connect_timeout=3,
        options="-c statement_timeout=5000",
        row_factory=dict_row,
    )


def set_tenant(conn, tenant_id):
    conn.execute(
        "SELECT set_config('app.tenant_id', %s, true)",
        (str(tenant_id),),
    )
