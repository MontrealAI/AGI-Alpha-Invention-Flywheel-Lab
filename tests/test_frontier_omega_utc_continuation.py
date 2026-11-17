"""Preregistered UTC continuation cases; no real buyer, payment, or native account."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from frontier_omega.crossings import CrossingInventory, main


MOCK_UTC = datetime(2026, 12, 31, 14, 0, tzinfo=timezone.utc)
MOCK_DATE = "2026-12-31"
HISTORICAL_DATE = "2026-11-16"


class UTCContinuationReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="frontier-utc-continuation-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "canonical-owner-test-state"
        self.sensor = CrossingInventory(self.root)
        self.assertEqual(self.sensor.seed()["total_problems"], 52)
        # Actual watcher advances the one canonical research clock on the fixed
        # future-date simulation, without polling the web or touching money.
        with patch("frontier_omega.crossings.datetime") as clock:
            clock.now.return_value = MOCK_UTC
            receipt = self.sensor.watch(interval=0.05, cycles=1)
        self.assertEqual(receipt["cycles"], 1)
        self.assertEqual(receipt["financial_authority"], "NONE")

    def cli(self, command, *args):
        output = StringIO()
        with patch("frontier_omega.crossings.datetime") as clock:
            clock.now.return_value = MOCK_UTC
            with redirect_stdout(output):
                main(["--root", str(self.root), command, *args])
        return json.loads(output.getvalue())

    def test_t1_omitted_date_refresh_continues_after_watch_without_reset(self):
        before = {p["id"]: p for p in self.sensor.inventory.reservoir.rows("problems")}
        self.cli("refresh")
        view = json.loads(
            (self.root / "FRONTIER-ECONOMIC-OPPORTUNITIES.json").read_text()
        )
        self.assertEqual(view["as_of"], MOCK_DATE)
        self.assertEqual(view["historical_baseline"], "2026-11-26")
        after = {p["id"]: p for p in self.sensor.inventory.reservoir.rows("problems")}
        self.assertEqual(before, after)
        self.assertEqual(len(after), 52)

    def test_t2_omitted_date_list_uses_live_utc_window(self):
        result = self.cli("list", "--limit", "8")
        self.assertEqual(result["total_problems"], 52)
        self.assertEqual(len(result["priorities"]), 8)
        self.assertTrue(all(x["action"] == "MONITOR" for x in result["priorities"]))

    def test_t3_explicit_history_is_read_only_and_regression_stays_rejected(self):
        historic = self.cli("list", "--as-of", HISTORICAL_DATE, "--limit", "8")
        self.assertTrue(all(x["action"] == "REPLAY_CANDIDATE"
                            for x in historic["priorities"]))
        with self.assertRaisesRegex(ValueError, "REFRESH_CLOCK_REGRESSION"):
            self.cli("refresh", "--as-of", HISTORICAL_DATE)
        self.assertEqual(len(self.sensor.inventory.reservoir.rows("problems")), 52)
        self.assertEqual(
            json.loads((self.root / "FRONTIER-ECONOMIC-OPPORTUNITIES.json").read_text())["as_of"],
            MOCK_DATE,
        )


if __name__ == "__main__":
    unittest.main()
