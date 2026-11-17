import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from agent import TICKERS, coverage_cap, validate_annotations, decide

ROOT = pathlib.Path(__file__).resolve().parents[1]


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "preregistration.json").read_text())
        self.p = {t: 100.0 for t in TICKERS}
        self.n = [
            {
                "ticker": t,
                "summary": "Company event.",
                "news_count": 1,
                "coverage_status": "partial_search_sample",
            }
            for t in TICKERS
        ]
        self.a = {
            t: {
                "sentiment": 1.0 if i == 0 else -1.0 if i == 1 else 0.0,
                "confidence": 1.0,
                "event": "other",
                "reason": "Event.",
            }
            for i, t in enumerate(TICKERS)
        }

    def test_partial_cap(self):
        a = decide(self.p, {}, self.n, self.a, self.cfg)
        self.assertEqual(a["details"]["NVDA"]["confidence"], 0.6)
        self.assertEqual(a["action"], "LS")

    def test_missing_news_not_no_event(self):
        self.n[0]["summary"] = ""
        a = decide(self.p, {}, self.n, self.a, self.cfg)
        self.assertFalse(a["details"]["NVDA"]["eligible"])

    def test_unknown_coverage_excludes(self):
        self.n[0]["coverage_status"] = "unknown"
        self.assertEqual(coverage_cap("unknown"), 0)
        self.assertFalse(
            decide(self.p, {}, self.n, self.a, self.cfg)["details"]["NVDA"]["eligible"]
        )

    def test_low_gap_flat(self):
        for x in self.a.values():
            x["sentiment"] = 0
        self.assertEqual(decide(self.p, {}, self.n, self.a, self.cfg)["action"], "F")

    def test_minimum_eligible(self):
        p = {t: 100.0 for t in TICKERS[:5]}
        self.assertEqual(decide(p, {}, self.n, self.a, self.cfg)["action"], "F")

    def test_first_momentum_zero(self):
        a = decide(self.p, {}, self.n, self.a, self.cfg, "no_news")
        self.assertEqual(a["action"], "F")
        self.assertTrue(all(x["momentum"] == 0 for x in a["details"].values()))

    def test_no_risk_still_no_missing_price(self):
        self.p["NVDA"] = None
        a = decide(self.p, {}, self.n, self.a, self.cfg, "no_risk")
        self.assertFalse(a["details"]["NVDA"]["eligible"])

    def test_duplicate_annotation_rejected(self):
        rows = [dict(self.a[t], ticker=t) for t in TICKERS]
        rows[1]["ticker"] = "NVDA"
        with self.assertRaises(ValueError):
            validate_annotations({"annotations": rows})

    def test_nan_annotation_rejected(self):
        rows = [dict(self.a[t], ticker=t) for t in TICKERS]
        rows[0]["sentiment"] = float("nan")
        with self.assertRaises(ValueError):
            validate_annotations({"annotations": rows})


if __name__ == "__main__":
    unittest.main()
