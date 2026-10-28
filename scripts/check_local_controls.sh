#!/usr/bin/env bash
# Isolated tests run in fresh backend processes; providers and DB are mocked.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
for test in \
  test_conversational_gate test_semantic_router test_gas_routing \
  test_advice_security test_llm_controls test_provider_envelopes \
  test_water_response_controls test_energy_response_controls \
  test_gas_response_controls test_agent_observability test_monitoring_helpers; do
  echo "=== $test ==="
  # monitoring helpers import a sibling module; supply it without mounting secrets.
  if [[ "$test" == test_monitoring_helpers ]]; then
    python3 "tests/$test.py"
  else
    bash scripts/aegis.sh exec -T backend python - < "tests/$test.py"
  fi
done
echo 'PASS : tous les contrôles locaux sélectionnés.'
