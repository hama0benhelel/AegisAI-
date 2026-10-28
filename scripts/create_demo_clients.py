import getpass
import json
import subprocess

COMPOSE = ["sudo", "docker", "compose"]

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
            "FAIL: opération SQL refusée. Aucun détail sensible affiché."
        )
    return result.stdout.strip()

accounts = (
    ("client.a@example.test", "11111111-1111-4111-8111-111111111111"),
    ("client.b@example.test", "22222222-2222-4222-8222-222222222222"),
)

for email, tenant in accounts:
    exists = database(
        f"SELECT count(*) FROM bws_ai.users WHERE email = '{email}';"
    )
    if exists != "0":
        raise SystemExit(
            f"{email} existe déjà. Arrêt sans modification des comptes."
        )
    exists = database(
        f"SELECT count(*) FROM bws_ai.tenants WHERE id = '{tenant}';"
    )
    if exists != "1":
        raise SystemExit(f"Tenant absent pour {email}. Arrêt.")

prepared = []

for email, tenant in accounts:
    password = getpass.getpass(f"Nouveau mot de passe pour {email}: ")
    confirmation = getpass.getpass("Confirmez le mot de passe: ")

    if password != confirmation:
        raise SystemExit("Mots de passe différents. Aucun compte créé.")
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
        raise SystemExit("FAIL: génération du hash. Aucun compte créé.")

    escaped_hash = hashed.replace("'", "''")
    prepared.append(
        "INSERT INTO bws_ai.users "
        "(tenant_id, email, password_hash, role) "
        f"VALUES ('{tenant}', '{email}', '{escaped_hash}', 'client');"
    )

database("BEGIN;\n" + "\n".join(prepared) + "\nCOMMIT;")
print("SUCCESS: les deux comptes client ont été créés.")
print(database(
    "SELECT email, role, is_active FROM bws_ai.users "
    "WHERE email IN ('client.a@example.test', 'client.b@example.test') "
    "ORDER BY email;"
))
