from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from producer import SENSORS, SOURCE, value_for


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.stamp = datetime(2026, 10, 26, tzinfo=timezone.utc)

    def test_four_distinct_sensors_and_tenant_mapping(self):
        self.assertEqual(len(SENSORS), 4)
        self.assertEqual(len({item[1] for item in SENSORS}), 4)
        for tenant, sensor, resource, unit in SENSORS:
            self.assertTrue(tenant.startswith("1111") if sensor.startswith("A-") else tenant.startswith("2222"))
            self.assertIn("-SIM-", sensor)
            self.assertEqual(unit, "m3" if resource == "water" else "kWh")
        self.assertEqual(SOURCE, "synthetic_live_v1")

    def test_values_are_deterministic_positive_and_finite(self):
        for _, sensor, resource, _ in SENSORS:
            for hour in range(24):
                stamp = self.stamp + timedelta(hours=hour)
                value = value_for(sensor, resource, stamp, hour)
                self.assertEqual(value, value_for(sensor, resource, stamp, hour))
                self.assertTrue(value.is_finite())
                self.assertGreater(value, 0)
                self.assertLess(value, 10000)
                self.assertEqual(value.as_tuple().exponent, -3)

    def test_fixed_laboratory_spikes(self):
        water_a = value_for("A-SIM-WATER-01", "water", self.stamp, 18)
        water_b = value_for("B-SIM-WATER-01", "water", self.stamp, 18)
        energy_a = value_for("A-SIM-ENERGY-01", "energy", self.stamp, 19)
        energy_b = value_for("B-SIM-ENERGY-01", "energy", self.stamp, 19)
        self.assertGreater(water_a, water_b * 4)
        self.assertGreater(energy_a, energy_b * 4)

    def test_invalid_inputs(self):
        for resource, stamp, hour in (
            ("gas", self.stamp, 1), ("water", self.stamp, 24),
            ("water", self.stamp.replace(tzinfo=None), 1),
        ):
            with self.assertRaises(ValueError):
                value_for("A-SIM-WATER-01", resource, stamp, hour)


if __name__ == "__main__":
    unittest.main(verbosity=2)
