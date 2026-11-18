import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

# Discovery runs from repository root as well as directly in this directory.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit
from cohort import DATES, FIELDS, sha
import triage


class ReprocessingQueue(unittest.TestCase):
    def test_all_frozen_routes_against_originals_and_delivery(self):
        with (HERE / "archive-queue.csv").open(newline="") as fh:
            frozen = list(csv.reader(fh))
        self.assertEqual(sha((HERE / "archive-queue.csv").read_bytes()),
                         "288145a6b9a8ea2ddcb91903571f963cc74b247b078ebe58479ce01f6774a71a")
        for route in ("retained", "ordinary", "direct"):
            rows = [FIELDS, *triage.make_queue(route, DATES, Decimal(1))]
            audit.check(rows, DATES, 1)
            self.assertEqual([list(r) for r in rows], frozen)

    def test_preliminary_and_absent(self):
        by_date = {r[0]: r for r in triage.make_queue("direct", DATES, Decimal(1))}
        for epoch, reason in [("2026-09-02", "reference_preliminary"), ("2026-10-02", "reference_absent")]:
            self.assertEqual(by_date[epoch][3:], ("", "", "", "defer", reason))
        self.assertEqual(by_date["2026-09-01"][5:7], ("-1.0466", "reprocess"))

    def test_distinct_purpose_changes_decisions(self):
        day = [date(2026, 9, 1)]
        for tolerance, wanted in [("0.1", "reprocess"), ("1.0466", "review"), ("2", "retain")]:
            for route in ("retained", "ordinary", "direct"):
                result = triage.make_queue(route, day, Decimal(tolerance))
                audit.check([FIELDS, *result], day, tolerance)
                self.assertEqual(result[0][6], wanted)

    def test_exact_inclusive_guards(self):
        pred = ("prediction", "0.00100", "")
        for final_value in ("1.9000", "2.1000"):
            final = ("final", final_value, "0.1000")
            self.assertEqual(triage.policy(pred, final, Decimal(1))[-2], "review")
        self.assertEqual(triage.policy(("rapid", ".005", ""), None, 1)[-1], "forecast_absent")
        with self.assertRaises(ValueError):
            triage.exact_ticks("0.00101", Decimal(10000))

    def test_wrong_sign_date_and_row_population(self):
        rows = [list(FIELDS), *map(list, triage.make_queue("ordinary", DATES, Decimal("1")))]
        corrupted = [list(r) for r in rows]
        corrupted[-4][5] = "1.0466"
        with self.assertRaises(ValueError):
            audit.check(corrupted, DATES, 1)
        for bad in [rows[:-1], [*rows, rows[-1]], [rows[0], rows[2], rows[1], *rows[3:]]]:
            with self.assertRaises(ValueError):
                audit.check(bad, DATES, 1)

    def test_logic_rejects_wrong_units_and_foreign_source(self):
        original = triage.checked_facts("reference", "html")
        with patch.object(triage, "checked_facts", return_value=original.replace("[msec]", "[sec]")):
            with self.assertRaisesRegex(ValueError, "unit"):
                triage.html_grid("reference", "retained")
        import cohort
        with tempfile.TemporaryDirectory() as temp, patch.object(cohort, "HERE", Path(temp)):
            (Path(temp) / "facts").mkdir()
            (Path(temp) / "facts/reference.txt").write_text("substituted source")
            (Path(temp) / "SOURCES.json").write_bytes((HERE / "SOURCES.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "changed"):
                cohort.checked_facts("reference", "txt")

    def test_existing_delivery_survives_and_unsupported_population_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "work.csv"
            target.write_text("prior")
            argv = [sys.executable, str(HERE / "triage.py"), "--output", str(target)]
            for options in [[], ["--date", "2026-08-01", "--date", "2026-08-01"],
                            ["--date", "2027-01-01"], ["--tolerance-ms", "NaN"]]:
                with self.subTest(options=options):
                    self.assertNotEqual(subprocess.run(argv + options, capture_output=True).returncode, 0)
                    self.assertEqual(target.read_text(), "prior")


if __name__ == "__main__":
    unittest.main()
