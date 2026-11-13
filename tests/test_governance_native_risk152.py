"""Frozen Native Risk152 synthetic T1-T10, no private data or external evaluator."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from products.governance_impact140.native_risk152 import (
    SCHEMA, canonical, digest, evaluate, main, verify_receipt,
)


def sample():
    cases = []
    for group in ("A", "B"):
        for i, truth in enumerate((1, 1, 0, 0)):
            cases.append({"case_id": f"{group}-{i}", "truth": truth,
                          "prediction": truth, "group": group,
                          "repeat_prediction": truth,
                          "claimed_violation": False})
    return {"schema": SCHEMA, "system_id": "synthetic-system",
            "thresholds": {"max_missing_label_rate": "0.10", "min_accuracy": "0.75",
                           "max_tpr_gap": "0.25", "max_flip_rate": "0.10",
                           "max_claimed_violation_rate": "0", "min_group_positives": 2},
            "rows": cases}


class NativeRisk152(unittest.TestCase):
    def test_T1_exact_native_risk_dimensions_are_only_synthetic_signals(self):
        r = evaluate(sample())
        self.assertEqual(r["case_count"], 8)
        self.assertEqual(r["observed_denominators"]["positive_cases_per_group"], {"A": 2, "B": 2})
        self.assertEqual(r["signals"]["accuracy"]["observed"], {"numerator": 1, "denominator": 1})
        self.assertEqual(r["signals"]["tpr_gap"]["observed"], {"numerator": 0, "denominator": 1})
        self.assertEqual(set(r["signals"]), {"accuracy", "missing_label_rate", "tpr_gap",
                                            "flip_rate", "claimed_violation_rate"})
        self.assertEqual(r["authorization"], "NO_REVIEW_NO_COMPLIANCE_NO_REAL_WORLD_PERFORMANCE")
        self.assertNotIn("compliant", canonical(r).decode().lower())

    def test_T2_row_order_does_not_give_a_new_or_better_result(self):
        x = sample()
        y = copy.deepcopy(x)
        y["rows"] = list(reversed(y["rows"]))
        self.assertEqual(evaluate(x), evaluate(y))
        y["rows"][0]["prediction"] = 1-y["rows"][0]["prediction"]
        self.assertNotEqual(evaluate(x)["source_input_sha256"], evaluate(y)["source_input_sha256"])

    def test_T3_duplicate_invalid_and_unknown_fields_fail_closed(self):
        cases = []
        x = sample(); x["rows"].append(copy.deepcopy(x["rows"][0])); cases.append(x)
        x = sample(); x["rows"][0]["secret"] = "invalid"; cases.append(x)
        x = sample(); x["rows"][0]["prediction"] = True; cases.append(x)
        x = sample(); x["rows"][0]["claimed_violation"] = 1; cases.append(x)
        x = sample(); x["unknown"] = 0; cases.append(x)
        x = sample(); x["rows"][0]["group"] = []; cases.append(x)
        x = sample(); x["rows"][0]["case_id"] = " "; cases.append(x)
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate(invalid)

    def test_T4_no_nonexact_or_nonfinite_thresholds(self):
        for val in (0.1, 1, True, "0.1e0", "NaN", "Infinity", "-0.1", "1.01", "00.1", "0."):
            x = sample(); x["thresholds"]["max_flip_rate"] = val
            with self.subTest(val=val), self.assertRaises(ValueError):
                evaluate(x)
        for val in (True, 0, -1, "2", 1.5):
            x = sample(); x["thresholds"]["min_group_positives"] = val
            with self.subTest(val=val), self.assertRaises(ValueError):
                evaluate(x)

    def test_T5_missing_truth_and_repeat_do_not_disappear_from_denominator(self):
        x = sample(); x["rows"][0]["truth"] = None
        x["rows"][1]["repeat_prediction"] = None
        r = evaluate(x)
        for k in ("accuracy", "tpr_gap", "flip_rate"):
            self.assertEqual(r["signals"][k]["signal"], "UNABLE_TO_DETERMINE")
            self.assertIsNone(r["signals"][k]["observed"])
        self.assertEqual(r["observed_denominators"]["unlabeled_cases"], 1)
        self.assertEqual(r["observed_denominators"]["repeat_unknown_cases"], 1)

    def test_T6_group_coverage_and_minimal_support_are_required(self):
        x = sample(); x["thresholds"]["min_group_positives"] = 3
        self.assertEqual(evaluate(x)["signals"]["tpr_gap"]["signal"], "UNABLE_TO_DETERMINE")
        x = sample(); x["rows"][0]["group"] = None
        self.assertEqual(evaluate(x)["signals"]["tpr_gap"]["signal"], "UNABLE_TO_DETERMINE")
        x = sample()
        for row in x["rows"]:
            row["group"] = "A"
        self.assertEqual(evaluate(x)["signals"]["tpr_gap"]["signal"], "UNABLE_TO_DETERMINE")
        self.assertIn("NOT_FAIRNESS_PROOF", evaluate(sample())["group_metric_scope"])

    def test_T6_regression_zero_positive_group_cannot_disappear_from_tpr_support(self):
        # Preserve the original frozen T6 requirement for every observed group.
        # A group represented only by negatives has no defined TPR.
        x = sample()
        x["rows"].append({"case_id": "C-0", "truth": 0, "prediction": 0,
                          "group": "C", "repeat_prediction": 0,
                          "claimed_violation": False})
        r = evaluate(x)
        self.assertEqual(r["observed_denominators"]["positive_cases_per_group"],
                         {"A": 2, "B": 2, "C": 0})
        self.assertIsNone(r["signals"]["tpr_gap"]["observed"])
        self.assertEqual(r["signals"]["tpr_gap"]["signal"], "UNABLE_TO_DETERMINE")
        x["rows"].append({"case_id": "C-1", "truth": 1, "prediction": 1,
                          "group": "C", "repeat_prediction": 1,
                          "claimed_violation": False})
        r = evaluate(x)
        self.assertEqual(r["observed_denominators"]["positive_cases_per_group"]["C"], 1)
        self.assertEqual(r["signals"]["tpr_gap"]["signal"], "UNABLE_TO_DETERMINE")

    def test_T7_adverse_thresholds_are_retained_not_filtered(self):
        x = sample()
        x["rows"][0]["prediction"] = 0  # group A TPR 0.5 vs group B 1
        self.assertEqual(evaluate(x)["signals"]["tpr_gap"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")
        x = sample()
        for row in x["rows"]:
            row["prediction"] = 1-row["prediction"]
        self.assertEqual(evaluate(x)["signals"]["accuracy"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")
        x = sample(); x["rows"][0]["repeat_prediction"] = 0
        self.assertEqual(evaluate(x)["signals"]["flip_rate"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")
        x = sample(); x["rows"][0]["claimed_violation"] = True
        self.assertEqual(evaluate(x)["signals"]["claimed_violation_rate"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")
        x = sample(); x["rows"][0]["truth"] = None
        self.assertEqual(evaluate(x)["signals"]["missing_label_rate"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")

    def test_T8_untrusted_review_claim_never_authenticates_results(self):
        x = sample(); x["rows"][0]["claimed_review"] = "approved"
        r = evaluate(x)
        self.assertEqual(r["ignored_untrusted_review_claim_count"], 1)
        self.assertEqual(r["authorization"], "NO_REVIEW_NO_COMPLIANCE_NO_REAL_WORLD_PERFORMANCE")
        self.assertNotIn("reviewer_signature", r)
        self.assertEqual(r["claimed_violation_status"], "UNAUTHENTICATED_INPUT_ASSERTION_NOT_SAFETY_TEST")

    def test_T9_independent_anchors_required_and_mutation_rejected(self):
        x = sample(); r = evaluate(x)
        self.assertTrue(verify_receipt(r, anchored_receipt_sha256=r["receipt_sha256"],
                                       anchored_input_sha256=r["source_input_sha256"]))
        t = copy.deepcopy(r)
        t["signals"]["accuracy"]["observed"] = {"numerator": 0, "denominator": 1}
        t["receipt_sha256"] = digest({k: v for k, v in t.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "RECEIPT_ANCHOR_MISMATCH"):
            verify_receipt(t, anchored_receipt_sha256=r["receipt_sha256"],
                           anchored_input_sha256=r["source_input_sha256"])
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_ANCHORS_REQUIRED"):
            verify_receipt(r, anchored_receipt_sha256=r["receipt_sha256"], anchored_input_sha256="")
        with self.assertRaisesRegex(ValueError, "INPUT_ANCHOR_MISMATCH"):
            verify_receipt(r, anchored_receipt_sha256=r["receipt_sha256"], anchored_input_sha256="0"*64)

    def test_T10_cli_fails_closed_on_duplicate_fields_and_destination_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"input.json"; out = Path(tmp)/"receipt.json"
            p.write_text(json.dumps(sample()), encoding="utf-8")
            report = main(["--input", str(p), "--output", str(out)])
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), report)
            with self.assertRaises(FileExistsError):
                main(["--input", str(p), "--output", str(out)])
            p.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
                main(["--input", str(p), "--output", str(Path(tmp)/"duplicate.json")])
            p.write_bytes(b"\xff")
            with self.assertRaises(UnicodeDecodeError):
                main(["--input", str(p), "--output", str(Path(tmp)/"invalid.json")])
            p.write_text('[]', encoding="utf-8")
            with self.assertRaises(ValueError):
                main(["--input", str(p), "--output", str(Path(tmp)/"array.json")])


if __name__ == "__main__":
    unittest.main()
