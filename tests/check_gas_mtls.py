import json
import os
import ssl
import socket
from urllib.parse import urlsplit
from urllib.error import URLError
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

URL = os.environ["GAS_AGENT_URL"] + "/health/live"


def context(with_certificate):
    ctx = ssl.create_default_context(cafile=os.environ["AGENT_CA_FILE"])
    if with_certificate:
        ctx.load_cert_chain(
            os.environ["AGENT_CERT_FILE"],
            os.environ["AGENT_KEY_FILE"],
        )
    return ctx


def fetch(ctx):
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))
    with opener.open(URL, timeout=5) as response:
        return response.status, json.load(response)


status, body = fetch(context(True))
if status != 200 or body.get("service") != "gas-agent":
    raise SystemExit("FAIL: contrôle avec certificat backend.")
print("PASS: certificat serveur vérifié et certificat backend accepté")

address = urlsplit(URL)
try:
    with socket.create_connection((address.hostname, address.port or 443), timeout=5) as raw:
        with context(True).wrap_socket(raw, server_hostname="wrong-agent.invalid"):
            raise SystemExit("FAIL: identité serveur incorrecte acceptée")
except ssl.SSLCertVerificationError:
    print("PASS: certificat serveur refusé pour un autre nom de service")

try:
    fetch(context(False))
except URLError as error:
    if not isinstance(error.reason, (ssl.SSLError, ConnectionResetError)):
        raise SystemExit(
            "FAIL: erreur réseau non attribuable au contrôle TLS."
        )
    print("PASS: connexion sans certificat client refusée")
except (ssl.SSLError, ConnectionResetError):
    print("PASS: connexion sans certificat client refusée")
except Exception as error:
    raise SystemExit(
        f"À examiner: fermeture de connexion ({type(error).__name__})."
    ) from None
else:
    raise SystemExit("FAIL: connexion acceptée sans certificat client.")

print("Tests mTLS gaz réussis.")
