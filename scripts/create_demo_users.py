import getpass
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

USERS = [
    ("admin.a@example.test", "11111111-1111-4111-8111-111111111111"),
    ("admin.b@example.test", "22222222-2222-4222-8222-222222222222"),
]


def compose(*args, data=None):
    result = subprocess.run(
        ["sudo", "-n", "docker", "compose", *args],
        cwd=ROOT,
        input=data,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        # Do not print subprocess output that could contain password hashes.
        raise SystemExit(
            "Commande Docker/PostgreSQL échouée. "
            "Vérifiez sudo et l'état des services."
        )
    return result.stdout.strip()


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


statements = ["BEGIN;"]

for email, tenant_id in USERS:
    while True:
        password = getpass.getpass(f"Mot de passe pour {email}: ")
        if not 12 <= len(password) <= 128:
            print("Choisissez entre 12 et 128 caractères.")
            continue
        confirmation = getpass.getpass("Confirmez le mot de passe: ")
        if password != confirmation:
            print("Les mots de passe ne correspondent pas.")
            continue
        break

    password_hash = compose(
        "exec", "-T", "backend", "python", "-c",
        "import sys; from argon2 import PasswordHasher; "
        "print(PasswordHasher().hash(sys.stdin.read()))",
        data=password,
    )
    del password, confirmation

    if not password_hash.startswith("$argon2id$"):
        raise SystemExit("Hash Argon2id attendu, création interrompue.")

    statements.append(
        "INSERT INTO bws_ai.users "
        "(tenant_id, email, password_hash, role) VALUES ("
        f"{sql_literal(tenant_id)}, "
        f"{sql_literal(email)}, "
        f"{sql_literal(password_hash)}, "
        "'tenant_admin') "
        "ON CONFLICT (email) DO NOTHING;"
    )

statements.append("COMMIT;")

output = compose(
    "exec", "-T", "db",
    "psql", "-U", "postgres", "-d", "aegisai",
    "-v", "ON_ERROR_STOP=1",
    data="\n".join(statements),
)

print(output)
print("Terminé. Les comptes déjà existants restent inchangés.")
