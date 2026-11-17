"""Behavioral regression against the archived one-pass experiment; never calls API."""

import hashlib
import json
import pathlib
import sys
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from agent import ROOT, SYSTEM, decide, validate_annotations
from experiment import read_news
from replay_baselines import load_price_snapshots


class CachedReplayTests(unittest.TestCase):
    def test_frozen_prompt_and_parameters_unchanged(self):
        meta = json.loads((ROOT / "results/run_metadata.json").read_text())
        self.assertEqual(
            hashlib.sha256(SYSTEM.encode()).hexdigest(), meta["prompt_sha256"]
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "preregistration.json").read_bytes()).hexdigest(),
            meta["config_sha256"],
        )

    def test_all_123_decisions_match_original_artifacts(self):
        cfg = json.loads((ROOT / "preregistration.json").read_text())
        state = json.loads((ROOT / "sources/live-state.json").read_text())
        snaps = load_price_snapshots(ROOT)
        previous = {}
        count = 0
        for release in state["release_schedule"]:
            rid = release["round_id"]
            saved = json.loads(
                (
                    ROOT / "logs/decisions/full" / (rid.replace(":", "-") + ".json")
                ).read_text()
            )
            digest = saved["request_sha256"]
            raw = json.loads(
                (ROOT / "logs/llm" / digest / "validated.json").read_text()
            )
            annotations = validate_annotations(raw)
            news = read_news(release)
            current = snaps[datetime.fromisoformat(release["timestamp"])]
            for variant in cfg["variants"]:
                expected = json.loads(
                    (
                        ROOT
                        / "logs/decisions"
                        / variant
                        / (rid.replace(":", "-") + ".json")
                    ).read_text()
                )
                actual = decide(current, previous, news, annotations, cfg, variant)
                with self.subTest(round=rid, variant=variant):
                    for field in ("stock1", "stock2", "action", "reason", "details"):
                        self.assertEqual(actual[field], expected[field], field)
                count += 1
            previous = current
        self.assertEqual(count, 123)


if __name__ == "__main__":
    unittest.main()
