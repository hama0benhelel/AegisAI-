import json
import os
import ssl
from urllib.error import URLError
from urllib.request import HTTPSHandler, ProxyHandler, build_opener

URL = os.environ["ENERGY_AGENT_URL"] + "/health/live"


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
if status != 200 or body.get("service") != "energy-agent":
    raise SystemExit("FAIL: contrôle avec certificat backend.")
print("PASS: certificat serveur vérifié et certificat backend accepté")

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

print("Tests mTLS énergie réussis.")
