import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify import DAY, JD_EPOCH, conventional, decide, require_match, trigger_pass, verify

D = Decimal


def observation(cid, days, mag, *, error="0.03", band=1, sign="t"):
    return {"i:objectId": "object", "i:candid": cid, "i:jd": JD_EPOCH + D(days), "i:fid": band,
            "i:magpsf": D(mag), "i:sigmapsf": D(error), "i:isdiffpos": sign}


# Synthetic rows serve only to exercise behavior missing in a real archive sample.
BASE = observation(101, "0.5", "18")
TRIGGER = observation(102, "2.5", "18.4")


class DirectTests(unittest.TestCase):
    def run_rows(self, rows, cutoff=7):
        return decide(["object"], rows, 0, int(D(str(cutoff))*DAY))

    def test_direction_failure_and_first_followup(self):
        first = observation(103, "3.51", "17.6")
        later = observation(104, "4.5", "18.5")
        result = self.run_rows([BASE, TRIGGER, first, later])
        row, = result["alerts"]
        self.assertEqual((row["direction"], row["status"], row["followup"]["candid"]), ("fading", "reversed", "103"))
        self.assertEqual(row["followup_delta_mag"], -0.4)
        for value, outcome in (("18.01", "not_reproduced"), ("18.45", "persisted")):
            different = self.run_rows([BASE, TRIGGER, observation(103, "3.51", value), later])
            self.assertEqual(different["alerts"][0]["status"], outcome)

    def test_same_midnight_and_future_suffix(self):
        initial = [BASE, TRIGGER]
        suffix = [observation(107, "3.00", "18.7"), observation(108, "4.25", "18.9", sign="f")]
        self.assertEqual(self.run_rows(initial, 3), self.run_rows(initial + suffix, 3))
        self.assertEqual(self.run_rows(initial, 3)["alerts"][0]["status"], "awaiting_repeat")
        self.assertEqual(self.run_rows(initial + suffix, "3.001")["alerts"][0]["status"], "persisted")
        self.assertEqual(self.run_rows(initial, 6)["alerts"][0]["status"], "coverage_gap")
        self.assertEqual(self.run_rows([observation(101, "4.5", "18"), observation(102, "6.5", "18.4")])[
            "alerts"][0]["status"], "right_censored")

    def test_only_registered_band_sign_dates_and_gap(self):
        invalid = [observation(103, "3.1", "18.4", band=2), observation(104, "4.5", "18.4", sign="f"),
                   observation(106, "4.5", "18.4", error="0"), observation(105, "6.0", "18.4")]
        result = self.run_rows([BASE, TRIGGER] + invalid)
        self.assertIsNone(result["alerts"][0]["followup"])
        self.assertEqual(result["alerts"][0]["status"], "coverage_gap")

    def test_ties_and_threshold_endpoints(self):
        # The two baseline options are each half a day from the ideal two-day lag.
        rows = [observation(11, "3.5", "18.5"), observation(10, "3.5", "18.40"),
                observation(20, "1.0", "18"), observation(19, "1.0", "18"), observation(18, "2.0", "18")]
        result, = self.run_rows(rows)["alerts"]
        self.assertEqual((result["baseline"]["candid"], result["trigger"]["candid"]), ("19", "10"))
        self.assertTrue(trigger_pass("20", "20.30", "0.06", "0.08", 3*DAY))
        self.assertFalse(trigger_pass("20", "20.299999", "0.06", "0.08", 3*DAY))
        self.assertTrue(trigger_pass("20", "19.80", "0.01", "0.01", 2*DAY))
        self.assertFalse(trigger_pass("20", "19.80", "0.01", "0.01", 2*DAY+1))

    def test_warm_history_and_reference_stream_are_separate_permissions(self):
        def tagged(cid, days, mag, field, channel):
            return {**observation(cid, days, mag), "i:field": field, "i:rcid": channel}
        refs = ("i:field", "i:rcid")
        rows = [tagged(100, "-1.5", "19", 2, 6), tagged(101, "-1.5", "18", 2, 7),
                tagged(102, "0.5", "18.4", 2, 7), tagged(103, "1.25", "17.2", 3, 7),
                tagged(104, "1.75", "18.36", 2, 7)]
        for warm, count in ((0, 0), (7, 1)):
            result = decide(["object"], rows, 0, 2*DAY, reference_fields=refs, baseline_lookback_days=warm)
            self.assertEqual((result["source_rows"], result["eligible_rows"], len(result["alerts"])), (3, 3, count))
            if warm:
                delivered = result["alerts"][0]
                self.assertEqual((delivered["baseline"]["candid"], delivered["followup"]["candid"],
                                  delivered["status"]), ("101", "104", "persisted"))
        # If the day's latest exposure switches field it cannot use an earlier current in a better-covered field.
        rows.append(tagged(105, "0.75", "18.5", 8, 7))
        self.assertEqual(decide(["object"], rows, 0, DAY, reference_fields=refs, baseline_lookback_days=7)["alerts"], [])

    def test_independent_complete_match_on_issued_then_withdrawn_notice(self):
        # Qualify the full nested schema on real temporal behavior even when a public primary cohort is quiet.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "invention/evolution"))
        from alert import evaluate_cohort
        rows = [{**observation(i + 1, days, mag), "i:field": field, "i:rcid": 6}
                for i, (days, mag, field) in enumerate([
                    ("-2", "17.8", 4), ("0.5", "18.4", 4), ("1.5", "18.34", 4),
                    ("2.5", "17.4", 4), ("3.5", "18.1", 6), ("4.5", "18.4", 4)])]
        statuses = set()
        for warm in (0, 7):
            for scoped in (False, True):
                for cutoff in (1, 2, 4, 7):
                    expected = decide(["object"], rows, 0, cutoff*DAY, baseline_lookback_days=warm,
                                      reference_fields=("i:field", "i:rcid") if scoped else ())
                    typed = evaluate_cohort("fixture", ["object"], rows, JD_EPOCH, JD_EPOCH + 7,
                                            JD_EPOCH + cutoff, baseline_lookback_days=warm, require_same_detector=scoped)
                    for key in ("id", "start_utc", "end_utc", "targets"):
                        del typed[key]
                    require_match(expected, typed)
                    statuses.update(a["status"] for a in expected["alerts"])
        self.assertTrue({"awaiting_repeat", "persisted", "not_reproduced"} <= statuses)

    def test_identical_ordinary_colour_products_can_hide_a_persisting_same_band_change(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "invention"))
        from photometry import measure
        from reuse import inventory
        common = [observation(101, "0.50", "18"), observation(102, "0.51", "18.2", band=2)]
        flat = common + [observation(103, "2.5", "18"), observation(104, "3.5", "18")]
        changed = common + [observation(103, "2.5", "18.5"), observation(104, "3.5", "18.5")]
        def original(rows):
            numeric = [{k: float(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in rows]
            return measure({"targets": [{"id": "object"}]}, numeric, [float(JD_EPOCH), float(JD_EPOCH + 7)], 120)
        self.assertEqual(original(flat), original(changed))
        self.assertEqual(self.run_rows(flat)["alerts"], [])
        self.assertEqual(self.run_rows(changed)["alerts"][0]["status"], "persisted")
        self.assertEqual(inventory()["verified_issuance_dispositions"], 2)

    def test_duplicate_observation_is_an_invalid_input(self):
        with self.assertRaisesRegex(ValueError, "repeated"):
            self.run_rows([BASE, TRIGGER, copy.deepcopy(BASE)])

    def test_every_published_event_boundary_and_each_nightly_revision(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "invention/evolution"))
        from alert import calculate
        from verify import SOURCES, from_jd, from_utc, read_cohort, stamp
        moments = set()
        for spec in SOURCES:
            start = from_utc(spec[1])
            end = start + 7 * DAY
            _, rows, _ = read_cohort(spec)
            moments.update(start + day*DAY for day in range(8))
            for row in rows:
                t = from_jd(row["i:jd"])
                if start <= t < end:
                    nearest_microsecond = t // 1000 * 1000
                    moments.update((nearest_microsecond, nearest_microsecond+1000))
        for ns in sorted(moments):
            cutoff = stamp(ns)
            self.assertTrue(verify(calculate(cutoff), as_of=cutoff)["agrees"], cutoff)

    def test_open_frozen_scopes_and_edited_negative(self):
        self.assertEqual(conventional("2026-10-31T22:00:00Z")["cohorts"], [])
        self.assertEqual(len(conventional("2026-11-10T00:00:00Z")["cohorts"]), 2)
        result = conventional()
        self.assertEqual(verify(result)["target_band_decisions"], 24)
        tampered = copy.deepcopy(result)
        tampered["cohorts"][0]["coverage"][0]["eligible_detections"] += 1
        with self.assertRaisesRegex(ValueError, "eligible_detections"):
            verify(tampered)
        tampered = copy.deepcopy(result)
        tampered["summary"]["alerts"] = False
        with self.assertRaisesRegex(ValueError, "alerts"):
            verify(tampered)
        with self.assertRaisesRegex(ValueError, "Count differs"):
            require_match([{"id": 1}], [{"id": 1}, {"id": 1}])


if __name__ == "__main__":
    unittest.main()
