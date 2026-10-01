import getpass
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TENANT = "11111111-1111-4111-8111-111111111111"

USERS = [
    ("viewer.a@example.test", "viewer"),
    ("operator.a@example.test", "operator"),
]


def compose(*args, data=None):
    result = subprocess.run(
        ["sudo", "-n", "docker", "compose", *args],
        cwd=ROOT, input=data, text=True, capture_output=True,
    )
    if result.returncode:
        raise SystemExit("Commande échouée. Vérifiez sudo et les services.")
    return result.stdout.strip()


def quote(value):
    return "'" + value.replace("'", "''") + "'"


statements = ["BEGIN;"]

for email, role in USERS:
    while True:
        password = getpass.getpass(f"Password pour {email}: ")
        if not 12 <= len(password) <= 128:
            print("Entre 12 et 128 caractères.")
            continue
        confirmation = getpass.getpass("Confirmation: ")
        if password == confirmation:
            break
        print("Les mots de passe ne correspondent pas.")

    hashed = compose(
        "exec", "-T", "backend", "python", "-c",
        "import sys; from argon2 import PasswordHasher; "
        "print(PasswordHasher().hash(sys.stdin.read()))",
        data=password,
    )
    del password, confirmation

    if not hashed.startswith("$argon2id$"):
        raise SystemExit("Hash inattendu.")

    statements.append(
        "INSERT INTO bws_ai.users "
        "(tenant_id, email, password_hash, role) VALUES ("
        f"{quote(TENANT)}, {quote(email)}, {quote(hashed)}, {quote(role)}) "
        "ON CONFLICT (email) DO NOTHING;"
    )

statements.append("COMMIT;")

print(compose(
    "exec", "-T", "db",
    "psql", "-U", "postgres", "-d", "aegisai",
    "-v", "ON_ERROR_STOP=1",
    data="\n".join(statements),
))
print("Terminé. Les comptes existants restent inchangés.")
