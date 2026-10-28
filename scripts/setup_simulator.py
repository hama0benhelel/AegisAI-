import os
from pathlib import Path
import re
import secrets
import subprocess


def database(sql):
    result = subprocess.run([
        "sudo", "docker", "compose", "exec", "-T", "db",
        "psql", "-X", "-q", "-A", "-t", "-U", "postgres", "-d", "aegisai",
        "-v", "ON_ERROR_STOP=1",
    ], input=sql, text=True, capture_output=True)
    if result.returncode:
        raise SystemExit("FAIL : configuration SQL du simulateur refusée. Aucun secret affiché.")
    return result.stdout.strip()


if database("SELECT count(*) FROM pg_roles WHERE rolname = 'aegisai_simulator';") != "1":
    raise SystemExit("Appliquez migration 015 avant la configuration.")

path = Path(".env")
if not path.is_file() or path.is_symlink():
    raise SystemExit(".env doit être un fichier normal existant.")
matches = re.findall(r"^SIMULATOR_DB_PASSWORD=(.*)$", path.read_text(), re.M)
if len(matches) > 1:
    raise SystemExit("Variable SIMULATOR_DB_PASSWORD définie plusieurs fois.")
password = matches[0] if matches else secrets.token_hex(32)
if not re.fullmatch(r"[0-9a-f]{64}", password):
    raise SystemExit("Format du secret inattendu. Aucun changement.")
os.chmod(path, 0o600)
if not matches:
    with path.open("a") as stream:
        stream.write(f"\nSIMULATOR_DB_PASSWORD={password}\n")

database(f"""
    BEGIN;
    ALTER ROLE aegisai_simulator LOGIN PASSWORD '{password}';
    ALTER ROLE aegisai_simulator SET statement_timeout = '5s';
    COMMIT;
""")
print("SUCCESS : secret technique configuré et accès simulateur activé.")
