from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import unittest
from fastapi.testclient import TestClient
from app.main import app

class GasContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        start = datetime(2026, 10, 1, tzinfo=timezone.utc)
        self.body = {"operation": "analyze_consumption", "resource": "gas", "tenant_id": str(uuid4()),
                     "requested_by": str(uuid4()), "trace_id": str(uuid4()), "sensor_id": "A-GAS-TEST",
                     "rows": [{"id": str(uuid4()), "sensor_id": "A-GAS-TEST", "value": "0.100",
                               "unit": "m3", "measured_at": (start + timedelta(hours=i)).isoformat(),
                               "data_source": "synthetic_test", "interval_seconds": 3600} for i in range(24)]}
    def test_normal_and_spike(self):
        normal = self.client.post("/internal/analyze", json=self.body)
        self.assertEqual(normal.status_code, 200)
        self.assertEqual(normal.json()["result"]["agent"], "gas")
        self.assertEqual(normal.json()["result"]["classification"], "normal")
        self.body["rows"][-1]["value"] = "0.500"
        spike = self.client.post("/internal/analyze", json=self.body).json()["result"]
        self.assertEqual(spike["classification"], "high_consumption")
        self.assertIsNone(spike["confidence_probability"])
    def test_invalid_contracts(self):
        mutations = [lambda b: b.update(resource="water"), lambda b: b["rows"].pop(),
                     lambda b: b["rows"][0].update(sensor_id="B-GAS-OTHER"),
                     lambda b: b["rows"][0].update(unit="kWh"),
                     lambda b: b["rows"][0].update(value="NaN"),
                     lambda b: b["rows"][1].update(id=b["rows"][0]["id"]),
                     lambda b: b.update(command="execute"),
                     lambda b: b["rows"][1].update(measured_at=b["rows"][0]["measured_at"])]
        for mutate in mutations:
            body = deepcopy(self.body)
            mutate(body)
            self.assertEqual(self.client.post("/internal/analyze", json=body).status_code, 422)

if __name__ == "__main__":
    unittest.main(verbosity=2)
