import os
from pathlib import Path
import shutil
import subprocess

if not shutil.which("openssl"):
    raise SystemExit("OpenSSL absent. Installez-le avant de continuer.")

root = Path.home() / ".local/share/aegisai-pki"
if root.exists():
    raise SystemExit("Dossier PKI déjà présent. Aucun certificat remplacé.")

os.umask(0o077)
root.mkdir(parents=True, mode=0o755)
root.chmod(0o755)

authority = root / "authority"
authority.mkdir(mode=0o700)

for name in ("backend", "water"):
    folder = root / name
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)


def openssl(*arguments):
    subprocess.run(
        ["openssl", *map(str, arguments)],
        check=True,
        stdout=subprocess.DEVNULL,
    )


ca_key = authority / "ca.key"
ca_cert = authority / "ca.crt"

openssl(
    "req", "-x509", "-newkey", "rsa:3072", "-nodes",
    "-keyout", ca_key, "-out", ca_cert,
    "-days", "365", "-sha256",
    "-subj", "/CN=AegisAI Lab Agent CA",
    "-addext", "basicConstraints=critical,CA:TRUE",
    "-addext", "keyUsage=critical,keyCertSign,cRLSign",
)

for name, common_name, usage, san in (
    ("backend", "aegisai-backend", "clientAuth", None),
    ("water", "water-agent", "serverAuth", "DNS:water-agent"),
):
    folder = root / name
    key = folder / "key.pem"
    csr = authority / f"{name}.csr"
    cert = folder / "cert.pem"
    extensions = authority / f"{name}.ext"

    text = (
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature,keyEncipherment\n"
        f"extendedKeyUsage={usage}\n"
        "subjectKeyIdentifier=hash\n"
        "authorityKeyIdentifier=keyid,issuer\n"
    )
    if san:
        text += f"subjectAltName={san}\n"
    extensions.write_text(text)

    openssl(
        "req", "-new", "-newkey", "rsa:2048", "-nodes",
        "-keyout", key, "-out", csr,
        "-subj", f"/CN={common_name}",
    )
    openssl(
        "x509", "-req", "-in", csr,
        "-CA", ca_cert, "-CAkey", ca_key,
        "-set_serial", "1001" if name == "backend" else "1002",
        "-out", cert, "-days", "90", "-sha256",
        "-extfile", extensions,
    )

    shutil.copyfile(ca_cert, folder / "ca.pem")
    cert.chmod(0o444)
    (folder / "ca.pem").chmod(0o444)
    key.chmod(0o400)

openssl("verify", "-CAfile", ca_cert,
        "-purpose", "sslclient", root / "backend/cert.pem")
openssl("verify", "-CAfile", ca_cert,
        "-purpose", "sslserver", root / "water/cert.pem")

print("SUCCESS: certificats de laboratoire générés et vérifiés.")
print("La clé de la CA reste hors des conteneurs.")
