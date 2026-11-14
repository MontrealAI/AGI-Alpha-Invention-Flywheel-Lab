"""Frozen synthetic temporal-risk159 T1-T12: no measured field or commercial claim."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from products.governance_impact140 import native_drift159 as target
from products.governance_impact140 import native_risk152 as native


def sample():
    def rows(prefix, predictions):
        return [
            {"case_id": prefix+"1", "truth": 1, "prediction": predictions[0],
             "repeat_prediction": predictions[0], "group": "X", "claimed_violation": False},
            {"case_id": prefix+"2", "truth": 1, "prediction": predictions[1],
             "repeat_prediction": predictions[1], "group": "Y", "claimed_violation": False},
            {"case_id": prefix+"3", "truth": 0, "prediction": predictions[2],
             "repeat_prediction": predictions[2], "group": "X", "claimed_violation": False},
        ]
    return {
        "schema": target.SCHEMA, "system_id": "authored-synthetic-system",
        "prior_date": "2026-10-01", "current_date": "2026-11-01",
        "thresholds": {
            "max_missing_label_rate": "0", "min_accuracy": "0.75",
            "max_tpr_gap": "1", "max_flip_rate": "0",
            "max_claimed_violation_rate": "0", "min_group_positives": 1,
        },
        "prior_rows": rows("p", (1, 1, 0)),
        "current_rows": rows("c", (1, 0, 0)),
    }


def metric(report, name="accuracy"):
    return next(r for r in report["metric_comparisons"] if r["metric"] == name)


class FrozenTemporalDrift159(unittest.TestCase):
    def test_T1_new_adverse_quality_signal_is_not_approval(self):
        out = target.evaluate(sample())
        self.assertEqual(metric(out)["classification"], "NEW_ADVERSE_SYNTHETIC_SIGNAL")
        self.assertEqual(metric(out)["prior"]["observed"], {"numerator": 1, "denominator": 1})
        self.assertEqual(metric(out)["current"]["observed"], {"numerator": 2, "denominator": 3})
        self.assertTrue(out["requires_authorized_review"])
        self.assertEqual(out["actual_buyer_acceptance"], None)
        self.assertEqual(out["actual_complete_cost_usd"], None)
        self.assertNotIn("COMPLIANCE_CERTIFIED", json.dumps(out))

    def test_T2_fresh_normal_quality_still_requires_review(self):
        s = sample()
        s["current_rows"][1]["prediction"] = 1
        s["current_rows"][1]["repeat_prediction"] = 1
        out = target.evaluate(s)
        self.assertEqual(metric(out)["classification"], "BOTH_WITHIN_SYNTHETIC_THRESHOLDS")
        self.assertTrue(metric(out)["requires_authorized_review"])

    def test_T3_resolution_is_not_certification(self):
        s = sample()
        s["prior_rows"][1]["prediction"] = 0
        s["prior_rows"][1]["repeat_prediction"] = 0
        s["current_rows"][1]["prediction"] = 1
        s["current_rows"][1]["repeat_prediction"] = 1
        out = target.evaluate(s)
        self.assertEqual(metric(out)["classification"], "RESOLVED_SYNTHETIC_SIGNAL")
        self.assertEqual(out["authorization"], "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_APPROVAL")

    def test_T4_persistent_adverse(self):
        s = sample()
        s["prior_rows"][1]["prediction"] = 0
        s["prior_rows"][1]["repeat_prediction"] = 0
        self.assertEqual(metric(target.evaluate(s))["classification"],
                         "PERSISTENT_ADVERSE_SYNTHETIC_SIGNAL")

    def test_T5_unmeasured_quality_fail_closed(self):
        s = sample()
        s["current_rows"][1]["truth"] = None
        a = metric(target.evaluate(s))
        self.assertEqual(a["classification"], "UNQUALIFIED_OBSERVATION")
        self.assertIsNone(a["current"]["observed"])

    def test_T6_dates_case_disjointness_and_policy(self):
        mutations = [
            lambda s: s.__setitem__("current_date", s["prior_date"]),
            lambda s: s.__setitem__("prior_date", "2026-12-01"),
            lambda s: s.__setitem__("current_date", "2026-02-30"),
            lambda s: s.__setitem__("current_date", "11/01/2026"),
            lambda s: s["current_rows"][0].__setitem__("case_id", "p1"),
            lambda s: s["current_rows"].append(copy.deepcopy(s["current_rows"][0])),
            lambda s: s["thresholds"].__setitem__("min_accuracy", "1.2"),
            lambda s: s.__setitem__("prior_rows", []),
            lambda s: s.__setitem__("extra", "unknown"),
        ]
        for mutation in mutations:
            s = sample()
            mutation(s)
            with self.subTest(mutation=str(mutation)), self.assertRaises(ValueError):
                target.evaluate(s)

    def test_T7_source_digest_and_order_invariance(self):
        s = sample()
        before = copy.deepcopy(s)
        a = target.evaluate(s)
        self.assertEqual(s, before)
        s["prior_rows"].reverse()
        s["current_rows"].reverse()
        self.assertEqual(target.evaluate(s), a)
        s["current_rows"][1]["prediction"] = 1
        b = target.evaluate(s)
        self.assertNotEqual(a["current_raw_sha256"], b["current_raw_sha256"])
        self.assertNotEqual(a["receipt_sha256"], b["receipt_sha256"])
        self.assertEqual(a["prior_raw_sha256"], b["prior_raw_sha256"])

    def test_T8_external_anchors_not_self_approval(self):
        a = target.evaluate(sample())
        anchors = {"expected_receipt": a["receipt_sha256"],
                   "expected_prior_raw": a["prior_raw_sha256"],
                   "expected_current_raw": a["current_raw_sha256"]}
        self.assertTrue(target.verify_receipt(a, **anchors))
        for name in anchors:
            wrong = dict(anchors, **{name: "0"*64})
            with self.subTest(name=name), self.assertRaises(ValueError):
                target.verify_receipt(a, **wrong)
        forged = copy.deepcopy(a)
        metric(forged)["classification"] = "BOTH_WITHIN_SYNTHETIC_THRESHOLDS"
        forged["receipt_sha256"] = native.digest({k: v for k, v in forged.items()
                                                  if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "TEMPORAL_REPORT_ANCHOR_MISMATCH"):
            target.verify_receipt(forged, **anchors)

    def test_T9_strict_cli_duplicate_nonfinite_and_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            inp, out = Path(d)/"input.json", Path(d)/"out.json"
            inp.write_text(json.dumps(sample()), encoding="utf-8")
            a = target.main(["--input", str(inp), "--output", str(out)])
            self.assertEqual(json.loads(out.read_text())["receipt_sha256"], a["receipt_sha256"])
            with self.assertRaises(FileExistsError):
                target.main(["--input", str(inp), "--output", str(out)])
            with self.assertRaises(ValueError):
                target.main(["--input", str(inp), "--output", str(inp)])
            inp.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
                target.main(["--input", str(inp), "--output", str(Path(d)/"bad.json")])
            inp.write_text('{"schema":NaN}')
            with self.assertRaisesRegex(ValueError, "NONFINITE_JSON"):
                target.main(["--input", str(inp), "--output", str(Path(d)/"nan.json")])

    def test_T10_original_native_evaluator_recomputes_both_periods(self):
        s = sample()
        out = target.evaluate(s)
        prior = native.evaluate({"schema": native.SCHEMA, "system_id": s["system_id"],
                                 "thresholds": s["thresholds"], "rows": s["prior_rows"]})
        current = native.evaluate({"schema": native.SCHEMA, "system_id": s["system_id"],
                                   "thresholds": s["thresholds"], "rows": s["current_rows"]})
        self.assertEqual(out["prior_native_receipt_sha256"], prior["receipt_sha256"])
        self.assertEqual(out["current_native_receipt_sha256"], current["receipt_sha256"])
        self.assertEqual(metric(out)["prior"], prior["signals"]["accuracy"])
        self.assertEqual(metric(out)["current"], current["signals"]["accuracy"])

    def test_T11_claimed_reviews_do_not_enter_native_evidence(self):
        s = sample()
        s["current_rows"][0]["claimed_review"] = "approved"
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_REVIEW_CLAIMS_REFUSED"):
            target.evaluate(s)

    def test_T12_other_metrics_unmeasured_are_not_overridden(self):
        s = sample()
        s["current_rows"][0]["repeat_prediction"] = None
        out = target.evaluate(s)
        self.assertEqual(metric(out, "flip_rate")["classification"],
                         "UNQUALIFIED_OBSERVATION")
        self.assertTrue(out["requires_authorized_review"])


if __name__ == "__main__":
    unittest.main()
