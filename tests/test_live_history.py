import pathlib
import sys
import unittest
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from live import select_session_history


class LiveHistoryTests(unittest.TestCase):
    def setUp(self):
        self.old = datetime.fromisoformat("2026-10-23T14:30:00-04:00")
        self.start = datetime.fromisoformat("2026-11-02T09:30:00-05:00")
        self.next = datetime.fromisoformat("2026-11-02T10:30:00-05:00")
        self.later = datetime.fromisoformat("2026-11-02T11:30:00-05:00")
        self.snaps = {
            self.old: {"NVDA": 1.0},
            self.start: {"NVDA": 2.0},
            self.next: {"NVDA": 3.0},
            self.later: {"NVDA": 4.0},
        }

    def test_old_session_and_future_never_become_first_history(self):
        timestamp, prices = select_session_history(self.snaps, self.start, self.start)
        self.assertIsNone(timestamp)
        self.assertEqual(prices, {})

    def test_previous_within_session_retained(self):
        timestamp, prices = select_session_history(self.snaps, self.next, self.start)
        self.assertEqual(timestamp, self.start)
        self.assertEqual(prices, {"NVDA": 2.0})

    def test_immediate_previous_only(self):
        timestamp, prices = select_session_history(self.snaps, self.later, self.start)
        self.assertEqual(timestamp, self.next)

    def test_future_session_rejected(self):
        with self.assertRaises(ValueError):
            select_session_history(self.snaps, self.start, self.next)

    def test_naive_session_rejected(self):
        with self.assertRaises(ValueError):
            select_session_history(self.snaps, self.start, datetime(2026, 11, 2, 9, 30))


if __name__ == "__main__":
    unittest.main()
