import getpass
import os
from pathlib import Path
import re
import secrets
import subprocess

COMPOSE = ["sudo", "docker", "compose"]
EMAIL = "security.admin@bws.example.test"
TENANT = "33333333-3333-4333-8333-333333333333"


def database(sql):
    result = subprocess.run(
        COMPOSE + [
            "exec", "-T", "db",
            "psql", "-X", "-q", "-A", "-t",
            "-U", "postgres", "-d", "aegisai",
            "-v", "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SystemExit(
            "FAIL: configuration SQL refusée. Détails sensibles non affichés."
        )
    return result.stdout.strip()


if database(
    f"SELECT count(*) FROM bws_ai.users WHERE email = '{EMAIL}';"
) != "0":
    raise SystemExit("Compte BWS déjà présent. Aucun changement.")

path = Path(".env")
if not path.is_file() or path.is_symlink():
    raise SystemExit(".env doit être un fichier normal existant.")

content = path.read_text()
matches = re.findall(r"^SECURITY_DB_PASSWORD=(.*)$", content, flags=re.M)
if len(matches) > 1:
    raise SystemExit("SECURITY_DB_PASSWORD défini plusieurs fois.")

db_password = matches[0] if matches else secrets.token_hex(32)
if not re.fullmatch(r"[0-9a-f]{64}", db_password):
    raise SystemExit("Format SECURITY_DB_PASSWORD inattendu. Aucun changement.")

password = getpass.getpass(f"Nouveau mot de passe pour {EMAIL}: ")
confirmation = getpass.getpass("Confirmez le mot de passe: ")
if password != confirmation:
    raise SystemExit("Mots de passe différents.")
if not 12 <= len(password) <= 128:
    raise SystemExit("Utilisez entre 12 et 128 caractères.")

result = subprocess.run(
    COMPOSE + [
        "exec", "-T", "backend", "python", "-c",
        "import sys; from argon2 import PasswordHasher; "
        "print(PasswordHasher().hash(sys.stdin.read()))",
    ],
    input=password,
    text=True,
    capture_output=True,
)
del password, confirmation

hashed = result.stdout.strip()
if result.returncode or not hashed.startswith("$argon2id$"):
    raise SystemExit("FAIL: génération du hash.")

# Save the generated secret before enabling the database login.
os.chmod(path, 0o600)
if not matches:
    with path.open("a") as stream:
        stream.write(f"\nSECURITY_DB_PASSWORD={db_password}\n")

escaped_hash = hashed.replace("'", "''")
database(f"""
BEGIN;

INSERT INTO bws_ai.tenants (id, name)
VALUES ('{TENANT}', 'BWS Security Administration');

INSERT INTO bws_ai.users
    (tenant_id, email, password_hash, role)
VALUES
    ('{TENANT}', '{EMAIL}', '{escaped_hash}', 'security_admin');

ALTER ROLE aegisai_security_reader
    LOGIN PASSWORD '{db_password}';

ALTER ROLE aegisai_security_reader
    SET default_transaction_read_only = on;

ALTER ROLE aegisai_security_reader
    SET statement_timeout = '5s';

COMMIT;
""")

print("SUCCESS: compte BWS créé et connexion de supervision configurée.")
print(f"Compte : {EMAIL}")
print("Rôle : security_admin")
