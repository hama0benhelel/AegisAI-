#!/usr/bin/env bash
# One explicit Compose definition for the prepared demonstration VM.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
exec sudo docker compose \
  -f compose.yaml \
  -f compose.monitoring.yaml \
  -f compose.agents.yaml \
  -f compose.simulation.yaml "$@"
