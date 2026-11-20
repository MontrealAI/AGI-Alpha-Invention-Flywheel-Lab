import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_radar import core, shadow


class ShadowTests(unittest.TestCase):
    def test_restart_deduplicates_friday_and_reports_degraded(self):
        now = core.instant("2026-11-20T13:00:01Z")
        fake = {"sources": [{"status": "error"}], "new_observations": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(shadow.ingest, "run", return_value=fake):
            db = Path(tmp) / "radar.sqlite3"
            atlas = {"cutoff": "2026-11-20", "milestones": []}
            first = shadow.run(db, atlas, [], now)
            second = shadow.run(db, atlas, [], now)
            self.assertTrue(first["coverage_degraded"])
            self.assertEqual(len(first["queued"]), 1)
            self.assertIn("Coverage degraded", first["queued"][0]["body"])
            self.assertEqual(second["queued"], [])
            self.assertEqual(first["delivery_attempts"], 0)
            self.assertEqual(len(shadow.drafts(db)), 1)

    def test_audit_persists_nonalert_decisions_once(self):
        now = core.instant("2026-11-20T13:00:01Z")
        fake = {"sources": [{"status": "ok"}], "new_observations": []}
        record = {"id": "control", "priority": 1, "recommendation": "PASS", "as_of": "2026-11-19",
                  "sources": [{"date": "2026-11-19"}]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(shadow.ingest, "run", return_value=fake):
            db = Path(tmp) / "radar.sqlite3"
            atlas = {"cutoff": "2026-11-20", "milestones": []}
            shadow.run(db, atlas, [record], now)
            shadow.run(db, atlas, [record], now)
            decisions = shadow.decisions(db)
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["result"]["decision"], "PASS")
            self.assertEqual(decisions[0]["record_digest"], core.digest(record))
