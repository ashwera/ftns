import unittest
from signalforge.capacity_timeline import compare_project, exact_share


class CapacityTimelineTests(unittest.TestCase):
    def test_trial_or_different_unit_cannot_be_called_cod_delay(self):
        expected = dict(project="Example plant", unit="3", capacity_mw="660", milestone="COD", date="2025-03-31", source_id="schedule")
        actual = {**expected, "milestone": "trial_completion", "date": "2025-06-12", "source_id": "filing"}
        self.assertEqual("not_comparable", compare_project(expected, actual)["status"])
        self.assertEqual("not_comparable", compare_project(expected, {**actual, "milestone": "COD", "unit": "2"})["status"])
        self.assertEqual(76, compare_project(expected, {**actual, "milestone": "COD", "date": "2025-06-15"})["slippage_days"])

    def test_exact_direct_ratio_and_invalid_operands(self):
        self.assertEqual("4.72", exact_share("725", "15376")["percent_display"])
        self.assertNotEqual(exact_share("725", "15376"), exact_share("709", "15376"))
        for n, d in [(1, 0), (2, 1), ("NaN", 1), (-1, 1)]:
            with self.assertRaises(ValueError): exact_share(n, d)
