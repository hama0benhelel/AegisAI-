import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
targets = []

for service in ("backend", "frontend"):
    container = subprocess.run(
        ["sudo", "docker", "compose", "ps", "-q", service],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()

    if not container:
        raise SystemExit(f"Container {service} introuvable.")

    info = json.loads(subprocess.run(
        ["sudo", "docker", "inspect", container],
        check=True, capture_output=True, text=True,
    ).stdout)[0]

    if info["HostConfig"]["LogConfig"]["Type"] != "json-file":
        raise SystemExit(f"Logging driver non compatible pour {service}.")

    path = info["LogPath"]
    if not path.startswith("/var/lib/docker/containers/") or not path.endswith("-json.log"):
        raise SystemExit(f"Chemin inattendu pour {service}.")

    targets.append(
        '    {__path__ = ' + json.dumps(path)
        + ', job = "aegisai", service = ' + json.dumps(service) + '},'
    )

template = root / "infra/monitoring/alloy/config.alloy.template"
output = root / "infra/monitoring/alloy/config.alloy"

text = template.read_text()
if text.count("__TARGETS__") != 1:
    raise SystemExit("Template invalide.")

output.write_text(text.replace("__TARGETS__", "\n".join(targets)))
print("Configuration Alloy actualisée pour backend et frontend.")
