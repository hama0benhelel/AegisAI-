import os

import psycopg
from psycopg.rows import dict_row


def connect_security():
    return psycopg.connect(
        host="db",
        dbname="aegisai",
        user="aegisai_security_reader",
        password=os.environ["SECURITY_DB_PASSWORD"],
        connect_timeout=3,
        options=(
            "-c statement_timeout=5000 "
            "-c default_transaction_read_only=on"
        ),
        row_factory=dict_row,
    )
