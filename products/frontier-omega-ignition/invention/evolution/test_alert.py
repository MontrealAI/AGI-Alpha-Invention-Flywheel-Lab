"""Regression tests for event-time changes and the independently observed repeat."""
import csv
import io
import json
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

if __package__:
    from . import alert
else:
    import alert


START = D("2461345.5")


def row(candid, offset, mag, *, err=".04", target="Star", fid=1, sign="t", field=21, rcid=0):
    return {"i:objectId": target, "i:candid": candid, "i:jd": START + D(offset), "i:magpsf": D(mag),
            "i:sigmapsf": D(err), "i:fid": fid, "i:isdiffpos": sign, "i:field": field, "i:rcid": rcid}


def run(rows, through="7", **kwargs):
    return alert.evaluate_cohort("fixture", ["Star"], rows, START, START+7, START+D(through), **kwargs)


class EventTimeTest(unittest.TestCase):
    def setUp(self):
        self.first = row(10, ".1", "19", err=".06")
        self.trigger = row(11, "3.1", "18.7", err=".08")

    def test_exact_thresholds_and_first_repeat_can_withdraw(self):
        first_repeat = row(12, "4.2", "19.01")
        better_but_later = row(13, "4.5", "18.5")
        history = [self.first, self.trigger, better_but_later, first_repeat]
        candidate, = run(history, through="4")["alerts"]
        self.assertEqual(candidate["direction"], "brightening")
        self.assertEqual(candidate["gates"], dict(change=True, rate=True, formal_error=True))
        self.assertEqual(candidate["status"], "awaiting_repeat")
        self.assertIsNone(candidate["followup"])
        self.assertEqual(candidate["delta_mag"], -.3)
        self.assertEqual(candidate["rate_mag_per_day"], -.1)
        final, = run(history)["alerts"]
        self.assertEqual((final["followup"]["candid"], final["status"], final["action"]),
                         ("12", "not_reproduced", "withdraw_review_alert"))

    def test_first_later_measurement_and_uncertainty(self):
        for value, status in [("18.8", "persisted"), ("19.2", "reversed"), ("18.81", "not_reproduced")]:
            with self.subTest(value=value):
                repeat = row(13, "4.4", value, err=".08")
                other = row(16, "4.4", "18.4")
                initial, = run([repeat, self.trigger, self.first, other])["alerts"]
                self.assertEqual(initial["status"], status)
                self.assertEqual(initial["followup"]["candid"], "13")
                self.assertEqual(initial["followup_formal_error_mag"], .1)

    def test_missing_followup_after_deadline_vs_right_censoring(self):
        early, = run([self.first, self.trigger])["alerts"]
        self.assertEqual((early["status"], early["deadline_utc"]), ("coverage_gap", "2026-11-08T00:00:00Z"))
        late, = run([row(10, "3.9", "19"), row(11, "6.2", "19.5"), row(12, "7", "20")])["alerts"]
        self.assertEqual(late["status"], "right_censored")
        self.assertIsNone(late["followup"])

    def test_no_lookahead_and_half_open_issue(self):
        # An observation exactly at the decision instant belongs to the next prefix.
        future = row(12, "4", "19.4")
        without = run([self.first, self.trigger], through="4")
        self.assertEqual(run([self.first, self.trigger, future], through="4"), without)
        actual, = run([self.first, self.trigger, future], through="4.1")["alerts"]
        self.assertEqual(actual["issued_utc"], without["alerts"][0]["issued_utc"])
        self.assertEqual((actual["status"], actual["followup"]["candid"]), ("reversed", "12"))
        self.assertFalse(run([self.first, self.trigger], through="3.99")["alerts"])
        self.assertEqual(actual["baseline"]["candid"], "10")

    def test_current_anchor_and_repeat_ties(self):
        # Lags 3 and 1 are tied in distance to the specified two-day reference.
        history = [row(4, ".1", "18"), row(7, ".1", "20"), row(8, "2.1", "18"),
                   row(10, "3.1", "18.5"), row(11, "3.1", "18"),
                   row(15, "4.1", "18.6"), row(14, "4.1", "18.7")]
        final, = run(history)["alerts"]
        self.assertEqual([final[k]["candid"] for k in ("baseline", "trigger", "followup")], ["4", "10", "14"])
        self.assertEqual(final["direction"], "fading")

    def test_half_day_minimum_and_first_eligible_repetition(self):
        history = [row(1, "1.4", "18"), row(2, "1.9", "18.4"),
                   row(3, "2.3", "17"), row(4, "2.4", "18.5")]
        result, = run(history)["alerts"]
        self.assertEqual(result["followup"]["candid"], "4")
        self.assertEqual(result["status"], "persisted")
        self.assertFalse(run([row(1, "1.400001", "18"), row(2, "1.9", "18.4")])["alerts"])

    def test_invalid_and_cross_band_values_cannot_be_witnesses(self):
        history = [self.first, self.trigger, row(12, "4.1", "17", fid=2),
                   row(13, "4.2", "16", sign="f"), row(14, "4.4", "17", err="0"),
                   row(15, "4.5", "NaN"), row(16, "4.6", "18", fid=3), row(17, "4.7", "19", err="Infinity")]
        a, = run(history)["alerts"]
        self.assertEqual(a["status"], "coverage_gap")
        with self.assertRaisesRegex(ValueError, "identity"):
            run([self.first, self.first])

    def test_detector_and_warm_history_are_scoped(self):
        prior = row(10, "-1.2", "18")
        current = row(11, ".8", "18.5")
        wrong_stream = row(12, "1.4", "17", rcid=2)
        proper_repeat = row(13, "1.6", "18.6")
        missing_ref = row(14, ".9", "20", field=None)
        history = [prior, current, wrong_stream, proper_repeat, missing_ref]
        warm = run(history, through="2", baseline_lookback_days=7, require_same_detector=True)
        a, = warm["alerts"]
        self.assertEqual([a[k]["candid"] for k in ("baseline", "trigger", "followup")], ["10", "11", "13"])
        self.assertEqual((a["status"], a["baseline"]["rcid"]), ("persisted", 0))
        self.assertEqual((warm["source_rows"], warm["eligible_rows"], warm["eligible_baseline_history_rows"]),
                         (4, 3, 1))
        self.assertFalse(run(history, through="2", require_same_detector=True)["alerts"])
        # Select the latest current first and then match its detector. An older
        # current from a stream with an attractive baseline must not take its place.
        hidden = run([prior, current, row(20, ".9", "19.0", rcid=3)], through="1",
                     baseline_lookback_days=7, require_same_detector=True)
        self.assertFalse(hidden["alerts"])

    def test_open_data_identity_and_prefix(self):
        first = alert.calculate("2026-11-01T00:00:00Z")
        self.assertEqual([c["id"] for c in first["cohorts"]], ["nov01"])
        self.assertEqual(first["cohorts"][0]["eligible_rows"], 0)
        self.assertEqual(len(first["cohorts"][0]["coverage"]), 12)
        self.assertEqual(alert.calculate("2026-10-31T23:59:59Z")["cohorts"], [])
        final = alert.calculate()
        self.assertEqual(alert.json_bytes(final), (alert.HERE/"RESULT.json").read_bytes())
        self.assertEqual(alert.csv_bytes(final), (alert.HERE/"worklist.csv").read_bytes())
        self.assertEqual([c["source_rows"] for c in final["cohorts"]], [44, 25])
        self.assertEqual([sum(r["comparisons"] for r in c["coverage"]) for c in final["cohorts"]], [26, 14])
        self.assertEqual(final["summary"]["alerts"], 0)
        self.assertEqual(len(final["overlap"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"changed.json"
            p.write_text('["edited"]')
            with self.assertRaisesRegex(ValueError, "digest"):
                alert.checked_bytes(p, "0"*64)
        rows = list(csv.DictReader(io.StringIO(alert.csv_bytes(final).decode())))
        self.assertEqual(len(rows), 24)
        self.assertTrue(any(r["strongest_baseline_candid"] for r in rows))
        self.assertTrue(all(not r["issued_utc"] for r in rows))

    def test_subthreshold_values_stay_below_gate_before_display_rounding(self):
        result = run([row(1, ".1", "18", err=".06"), row(2, "3.1", "18.29999999", err=".08")])
        group = result["coverage"][0]
        self.assertEqual(group["strongest_comparison"]["delta_mag"], .3)
        self.assertEqual(group["strongest_comparison"]["gates"],
                         {"change": True, "rate": False, "formal_error": False})
        self.assertEqual(group["status"], "no_trigger")


if __name__ == "__main__":
    unittest.main()
