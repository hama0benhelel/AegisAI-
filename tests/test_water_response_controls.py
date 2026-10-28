import copy
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from uuid import uuid4

from fastapi import HTTPException

from app.consumption_rules import analyze
from app.water_client import analyze_water


class WaterResponseTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.user = {"id": uuid4(), "tenant_id": uuid4()}
        self.request = SimpleNamespace(
            state=SimpleNamespace(trace_id=str(uuid4()))
        )
        self.rows = [
            {
                "id": uuid4(),
                "sensor_id": "TEST-WATER-01",
                "value": Decimal("35" if index == 23 else "10"),
                "unit": "m3",
                "measured_at": start + timedelta(hours=index),
                "data_source": "response_control_test",
                "interval_seconds": 3600,
            }
            for index in range(24)
        ]
        self.envelope = {
            "tenant_id": str(self.user["tenant_id"]),
            "trace_id": self.request.state.trace_id,
            "result": analyze("water", self.rows),
        }

    def invoke(self, envelope=None, network_error=None):
        opener = MagicMock()
        if network_error:
            opener.open.side_effect = network_error
        else:
            response = opener.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = json.dumps(envelope).encode()

        with patch.dict(os.environ, {
                 "WATER_AGENT_URL": "https://water-agent:8443",
                 "AGENT_CA_FILE": "test-ca", "AGENT_CERT_FILE": "test-cert",
                 "AGENT_KEY_FILE": "test-key",
             }), patch("app.water_client.ssl.create_default_context"), \
             patch("app.water_client.build_opener", return_value=opener):
            return analyze_water(self.rows, self.user, self.request)

    def test_valid_response(self):
        result = self.invoke(self.envelope)
        self.assertEqual(result, self.envelope["result"])

    def test_modified_responses_are_rejected(self):
        cases = {}

        changed = copy.deepcopy(self.envelope)
        changed["tenant_id"] = str(uuid4())
        cases["autre tenant"] = changed

        changed = copy.deepcopy(self.envelope)
        changed["trace_id"] = str(uuid4())
        cases["autre trace"] = changed

        changed = copy.deepcopy(self.envelope)
        changed["result"]["sources"][0]["reading_id"] = str(uuid4())
        cases["source remplacée"] = changed

        changed = copy.deepcopy(self.envelope)
        changed["result"]["latest_value"] = 999
        cases["valeur modifiée"] = changed

        changed = copy.deepcopy(self.envelope)
        changed["result"]["suggested_proposal"]["sensor_id"] = "OTHER-SENSOR"
        cases["action sur un autre capteur"] = changed

        for label, envelope in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(HTTPException) as caught:
                    self.invoke(envelope)
                self.assertEqual(caught.exception.status_code, 502)

    def test_network_timeout_is_unavailable(self):
        with self.assertRaises(HTTPException) as caught:
            self.invoke(network_error=URLError(TimeoutError()))
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main(verbosity=2)
