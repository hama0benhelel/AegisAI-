import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
targets = []

compose = [
    "sudo", "docker", "compose",
    "-f", "compose.yaml",
    "-f", "compose.monitoring.yaml",
    "-f", "compose.agents.yaml",
]
services = ("backend", "frontend", "water-agent", "energy-agent", "gas-agent")

for service in services:
    container_ids = subprocess.run(
        compose + ["ps", "-q", service],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()

    if len(container_ids) != 1:
        raise SystemExit(
            f"Un conteneur actif attendu pour {service}. Configuration inchangée."
        )

    info = json.loads(subprocess.run(
        ["sudo", "docker", "inspect", container_ids[0]],
        check=True,
        capture_output=True,
        text=True,
    ).stdout)[0]

    if info["HostConfig"]["LogConfig"]["Type"] != "json-file":
        raise SystemExit(f"Logging driver non compatible pour {service}.")

    path = info["LogPath"]
    if (
        not path.startswith("/var/lib/docker/containers/")
        or not path.endswith("-json.log")
    ):
        raise SystemExit(f"Chemin inattendu pour {service}.")

    targets.append(
        "    {__path__ = " + json.dumps(path)
        + ', job = "aegisai", service = ' + json.dumps(service) + "},"
    )

template = root / "infra/monitoring/alloy/config.alloy.template"
output = root / "infra/monitoring/alloy/config.alloy"

content = template.read_text()
if content.count("__TARGETS__") != 1:
    raise SystemExit("Template invalide. Configuration inchangée.")

generated = content.replace("__TARGETS__", "\n".join(targets))

temporary_path = None
try:
    with tempfile.NamedTemporaryFile(
        mode="w", dir=output.parent, delete=False, prefix=".alloy-"
    ) as temporary:
        temporary.write(generated)
        temporary_path = Path(temporary.name)

    os.chmod(temporary_path, 0o644)
    os.replace(temporary_path, output)
finally:
    if temporary_path is not None:
        temporary_path.unlink(missing_ok=True)

print("Configuration Alloy actualisée : " + ", ".join(services))
