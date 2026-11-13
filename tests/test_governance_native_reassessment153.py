"""Prospectively fixed native reassessment153 T1–T10, synthetic only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from products.governance_impact140 import engine
from products.governance_impact140 import native_reassessment153 as target
from products.governance_impact140 import native_risk152 as native


def sample():
    rows = [
        {"case_id": "a", "truth": 1, "prediction": 1, "group": "X",
         "repeat_prediction": 1, "claimed_violation": False},
        {"case_id": "b", "truth": 1, "prediction": 0, "group": "Y",
         "repeat_prediction": 0, "claimed_violation": False},
        {"case_id": "c", "truth": 0, "prediction": 0, "group": "X",
         "repeat_prediction": 0, "claimed_violation": False},
    ]
    thresholds = {
        "max_missing_label_rate": "0", "min_accuracy": "0.5",
        "max_tpr_gap": "1", "max_flip_rate": "0",
        "max_claimed_violation_rate": "0", "min_group_positives": 1,
    }
    before = {"system_id": "finance", "requirement_id": "R1", "version": "v1",
              "metric": "accuracy", "thresholds": thresholds}
    after = copy.deepcopy(before)
    after["version"] = "v2"
    after["thresholds"]["min_accuracy"] = "0.75"
    return {
        "schema": target.SCHEMA,
        "governance": {
            "systems": [
                {"id": "finance", "tags": ["finance"]},
                {"id": "warehouse", "tags": ["production"]},
            ],
            "requirements_before": [
                {"id": "R1", "version": "v1", "control": "accuracy lower threshold",
                 "applies_to": ["finance"]},
                {"id": "R2", "version": "v1", "control": "inventory",
                 "applies_to": ["production"]},
            ],
            "requirements_after": [
                {"id": "R1", "version": "v2", "control": "accuracy higher threshold",
                 "applies_to": ["finance"]},
                {"id": "R2", "version": "v1", "control": "inventory",
                 "applies_to": ["production"]},
            ],
            "evidence": [
                {"id": "self-assertion", "system_id": "finance",
                 "requirement_id": "R1", "version": "v1",
                 "claimed_status": "met", "review_claim": "approved"},
            ],
        },
        "observations": [{"system_id": "finance", "rows": rows}],
        "before_policies": [before],
        "after_policies": [after],
    }


class NativeReassessment153(unittest.TestCase):
    def test_T1_exact_policy_amendment_detects_adverse_raw_risk(self):
        data = sample()
        result = target.reassess(data)
        one = result["current_reassessments"][0]
        self.assertEqual(one["native_signal"]["observed"], {"numerator": 2, "denominator": 3})
        self.assertEqual(one["old_native_signal"]["observed"], {"numerator": 2, "denominator": 3})
        self.assertEqual(one["old_native_signal"]["signal"], "WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD")
        self.assertEqual(one["native_signal"]["signal"], "ADVERSE_SYNTHETIC_THRESHOLD")
        self.assertEqual((one["old_version"], one["version"], one["metric"]), ("v1", "v2", "accuracy"))
        self.assertTrue(one["reassessment_required"])
        self.assertEqual(one["change_kind"], "modified")
        self.assertEqual(one["governance_status_unchanged"], "unable_to_determine")
        self.assertEqual(result["governance_impacted_systems"], ["finance"])
        self.assertEqual(result["governance_receipt_sha256"],
                         engine.assess(data["governance"])["receipt_sha256"])

    def test_T2_source_mutation_and_row_order(self):
        data = sample()
        first = target.reassess(data)
        data["observations"][0]["rows"].reverse()
        self.assertEqual(first, target.reassess(data))
        data["observations"][0]["rows"][0]["prediction"] = 1
        changed = target.reassess(data)
        self.assertNotEqual(first["receipt_sha256"], changed["receipt_sha256"])
        self.assertNotEqual(first["current_reassessments"][0]["native_receipt_sha256"],
                            changed["current_reassessments"][0]["native_receipt_sha256"])

    def test_T3_unmeasured_coverage_does_not_disappear(self):
        data = sample()
        data["after_policies"] = []
        out = target.reassess(data)
        self.assertEqual(out["current_reassessments"], [])
        self.assertEqual(
            {(row["system_id"], row["requirement_id"])
             for row in out["current_findings_without_native_risk_policy"]},
            {("finance", "R1"), ("warehouse", "R2")})
        self.assertEqual(len(out["prior_policy_results"]), 1)

    def test_T4_fail_closed_unknown_data_and_support(self):
        for mutation, metric in (
            (lambda d: d["observations"][0]["rows"][0].__setitem__("truth", None), "accuracy"),
            (lambda d: d["observations"][0]["rows"][0].__setitem__("repeat_prediction", None), "flip_rate"),
            (lambda d: d["observations"][0]["rows"][1].__setitem__("group", None), "tpr_gap"),
            (lambda d: d["after_policies"][0]["thresholds"].__setitem__("min_group_positives", 2), "tpr_gap"),
        ):
            data = sample()
            mutation(data)
            data["after_policies"][0]["metric"] = metric
            data["before_policies"] = []
            result = target.reassess(data)
            self.assertEqual(result["current_reassessments"][0]["native_signal"]["signal"],
                             "UNABLE_TO_DETERMINE")
            self.assertIsNone(result["current_reassessments"][0]["native_signal"]["observed"])
        data = sample()
        data["observations"] = []
        self.assertEqual(target.reassess(data)["current_reassessments"][0]["native_signal"]["signal"],
                         "UNABLE_TO_DETERMINE")

    def test_T5_invalid_policy_bindings_and_external_scores_rejected(self):
        mutations = [
            lambda d: d["observations"].append(copy.deepcopy(d["observations"][0])),
            lambda d: d["after_policies"].append(copy.deepcopy(d["after_policies"][0])),
            lambda d: d["after_policies"][0].__setitem__("version", "v1"),
            lambda d: d["after_policies"][0].__setitem__("system_id", "unknown"),
            lambda d: d["after_policies"][0].__setitem__("requirement_id", "unknown"),
            lambda d: d["after_policies"][0].__setitem__("system_id", "warehouse"),
            lambda d: d["after_policies"][0].__setitem__("metric", "imported_score"),
            lambda d: d["after_policies"][0]["thresholds"].__setitem__("min_accuracy", "1.1"),
            lambda d: d["after_policies"][0].__setitem__("external_score", 0.95),
            lambda d: d["observations"][0].__setitem__("precomputed_score", 0.95),
        ]
        for mutate in mutations:
            data = sample()
            mutate(data)
            with self.subTest(mutate=str(mutate)), self.assertRaises(ValueError):
                target.reassess(data)

    def test_T6_input_review_claim_is_not_approval(self):
        out = target.reassess(sample())
        self.assertEqual(out["authorization"], target.AUTHORIZATION)
        self.assertNotIn("compliant", json.dumps(out).lower())
        self.assertNotEqual(out["governance_findings"][0]["status"], "met")
        self.assertTrue(out["governance_findings"][0].get("reported_approval_ignored", False) or
                        any(x.get("historical_evidence_id") == "self-assertion"
                            for x in out["governance_findings"]))
        self.assertEqual(out["current_reassessments"][0]["authorization"], target.AUTHORIZATION)

    def test_T7_control_change_without_version_bump(self):
        data = sample()
        data["governance"]["requirements_after"][0]["version"] = "v1"
        data["after_policies"][0]["version"] = "v1"
        out = target.reassess(data)
        self.assertTrue(out["current_reassessments"][0]["reassessment_required"])
        self.assertEqual(out["current_reassessments"][0]["change_kind"], "modified")
        self.assertEqual(out["current_reassessments"][0]["governance_status_unchanged"],
                         "unable_to_determine")

    def test_T8_cli_refuses_bad_input_duplicate_fields_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.json"
            dest = Path(temp) / "result.json"
            source.write_text(json.dumps(sample()), encoding="utf-8")
            out = target.main(["--input", str(source), "--output", str(dest)])
            self.assertEqual(out["receipt_sha256"], json.loads(dest.read_text())["receipt_sha256"])
            with self.assertRaises(FileExistsError):
                target.main(["--input", str(source), "--output", str(dest)])
            with self.assertRaises(ValueError):
                target.main(["--input", str(source), "--output", str(source)])
            source.write_bytes(b"\xff")
            with self.assertRaises(UnicodeDecodeError):
                target.main(["--input", str(source), "--output", str(Path(temp) / "bad.json")])
            source.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
                target.main(["--input", str(source), "--output", str(Path(temp) / "bad2.json")])
            source.write_text("[]")
            with self.assertRaises(ValueError):
                target.main(["--input", str(source), "--output", str(Path(temp) / "bad3.json")])

    def test_T9_external_anchored_hash_not_self_approval(self):
        data = sample()
        out = target.reassess(data)
        anchor = out["receipt_sha256"]
        gov_anchor = engine.assess(data["governance"])["receipt_sha256"]
        self.assertTrue(target.verify_receipt(
            out, anchored_receipt_sha256=anchor, anchored_governance_sha256=gov_anchor))
        fake = copy.deepcopy(out)
        fake["current_reassessments"][0]["native_signal"]["signal"] = "WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD"
        fake["receipt_sha256"] = engine.sha256({k: v for k, v in fake.items() if k != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "REASSESSMENT_RECEIPT_ANCHOR_MISMATCH"):
            target.verify_receipt(fake, anchored_receipt_sha256=anchor,
                                  anchored_governance_sha256=gov_anchor)
        with self.assertRaisesRegex(ValueError, "GOVERNANCE_ANCHOR_MISMATCH"):
            target.verify_receipt(out, anchored_receipt_sha256=anchor,
                                  anchored_governance_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_"):
            target.verify_receipt(out, anchored_receipt_sha256="not-a-hash",
                                  anchored_governance_sha256=gov_anchor)

    def test_T11_raw_only_digest_binds_unmeasured_cases_and_is_policy_invariant(self):
        data = sample()
        a = target.reassess(data)
        self.assertEqual(a["prior_policy_results"][0]["raw_case_sha256"],
                         a["current_reassessments"][0]["raw_case_sha256"])
        self.assertNotEqual(a["prior_policy_results"][0]["source_input_sha256"],
                            a["current_reassessments"][0]["source_input_sha256"])
        self.assertEqual(a["raw_case_digests"]["finance"],
                         a["current_reassessments"][0]["raw_case_sha256"])
        data["observations"].append({"system_id": "warehouse", "rows": [
            {"case_id": "z", "truth": 1, "prediction": 1,
             "group": "A", "repeat_prediction": 1, "claimed_violation": False}]})
        b = target.reassess(data)
        self.assertNotEqual(a["receipt_sha256"], b["receipt_sha256"])
        self.assertIn("warehouse", b["raw_case_digests"])
        data["observations"][-1]["rows"][0]["prediction"] = 0
        c = target.reassess(data)
        self.assertNotEqual(b["raw_case_digests"]["warehouse"], c["raw_case_digests"]["warehouse"])
        self.assertNotEqual(b["receipt_sha256"], c["receipt_sha256"])
        data["observations"][-1]["rows"][0]["prediction"] = 42
        with self.assertRaises(ValueError):
            target.reassess(data)

    def test_T10_native_receipt_recomputed_by_existing_evaluator(self):
        data = sample()
        out = target.reassess(data)
        policy = data["after_policies"][0]
        actual = native.evaluate({
            "schema": native.SCHEMA,
            "system_id": policy["system_id"],
            "thresholds": policy["thresholds"],
            "rows": data["observations"][0]["rows"],
        })
        row = out["current_reassessments"][0]
        self.assertEqual(row["native_receipt_sha256"], actual["receipt_sha256"])
        self.assertEqual(row["source_input_sha256"], actual["source_input_sha256"])
        self.assertEqual(row["native_signal"], actual["signals"][policy["metric"]])
        self.assertEqual(out["scope"], "OFFLINE_SYNTHETIC_LINKED_REASSESSMENT_ONLY")


if __name__ == "__main__":
    unittest.main()
