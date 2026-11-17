import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scoring import pair_return, metrics, endpoint_times


class ScoringTest(unittest.TestCase):
    def test_half_weights_and_sign(self):
        e = {"NVDA": 100, "GOOG": 200}
        x = {"NVDA": 110, "GOOG": 190}
        self.assertAlmostEqual(pair_return("NVDA", "GOOG", "LS", e, x), 0.075)
        self.assertAlmostEqual(pair_return("NVDA", "GOOG", "SL", e, x), -0.075)
        self.assertAlmostEqual(pair_return("GOOG", "NVDA", "LS", e, x), -0.075)

    def test_flat_missing_still_zero(self):
        self.assertEqual(pair_return("NVDA", "GOOG", "F", {}, {}), 0)

    def test_missing_active_not_zero(self):
        for missing in (None, float("nan"), 0, -1, float("inf")):
            self.assertIsNone(
                pair_return(
                    "NVDA",
                    "GOOG",
                    "LS",
                    {"NVDA": 1, "GOOG": 1},
                    {"NVDA": missing, "GOOG": 1},
                )
            )

    def test_invalid_action_or_pair(self):
        for a, b, c in (
            ("NVDA", "NVDA", "F"),
            ("X", "GOOG", "F"),
            ("NVDA", "GOOG", "BUY"),
        ):
            with self.assertRaises(ValueError):
                pair_return(a, b, c, {}, {})

    def test_compounding_not_sum(self):
        self.assertAlmostEqual(metrics([0.1, -0.1])["cr"], -0.01)

    def test_drawdown_includes_initial_equity(self):
        self.assertAlmostEqual(metrics([-0.2, 0.1])["max_drawdown"], 0.2)

    def test_gap_disclosed_not_zero_filled(self):
        m = metrics([0.1, None, -0.1], ["LS", "LS", "SL"])
        self.assertEqual(m["unscorable_count"], 1)
        self.assertEqual(m["settled_count"], 2)
        self.assertEqual(m["scope"], "observed_intervals_only_gaps_excluded")

    def test_win_rates_have_explicit_denominators(self):
        m = metrics([0.1, 0.0, -0.1], ["LS", "F", "SL"])
        self.assertAlmostEqual(m["win_rate_all_settled"], 1 / 3)
        self.assertAlmostEqual(m["win_rate_active"], 0.5)

    def test_schedule_uses_future_execution_nodes(self):
        r = {
            "timestamp": "2026-10-14T09:30:00-04:00",
            "action_due": "2026-10-14T10:25:00-04:00",
            "entry_at": "2026-10-14T10:30:00-04:00",
            "exit_at": "2026-10-14T11:30:00-04:00",
        }
        e, x = endpoint_times(r)
        self.assertEqual((e.hour, e.minute, x.hour, x.minute), (10, 30, 11, 30))
        r["entry_at"] = r["timestamp"]
        with self.assertRaises(ValueError):
            endpoint_times(r)

    def test_no_observations_is_not_zero_result(self):
        self.assertIsNone(metrics([None])["cr"])


if __name__ == "__main__":
    unittest.main()
