import os
from pathlib import Path
import ssl

import uvicorn


def required_file(variable):
    value = os.environ.get(variable)
    if not value or not Path(value).is_file():
        raise RuntimeError(f"Required TLS file missing: {variable}")
    return value


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8443,
        ssl_certfile=required_file("TLS_CERT_FILE"),
        ssl_keyfile=required_file("TLS_KEY_FILE"),
        ssl_ca_certs=required_file("TLS_CA_FILE"),
        ssl_cert_reqs=ssl.CERT_REQUIRED,
        access_log=False,
        proxy_headers=False,
    )
