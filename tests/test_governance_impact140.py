"""Frozen public-demand140 T1–T9 adversarial synthetic checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from products.governance_impact140.engine import assess, canonical, main, sha256, verify_receipt


def sample():
    return {
        "systems": [
            {"id": "finance", "tags": ["finance"]},
            {"id": "plant", "tags": ["production"]},
            {"id": "other", "tags": ["operations"]},
        ],
        "requirements_before": [
            {"id": "R1", "version": "v1", "control": "log", "applies_to": ["finance"]},
            {"id": "R3", "version": "v1", "control": "archive", "applies_to": ["production"]},
            {"id": "R4", "version": "v1", "control": "inventory", "applies_to": ["operations"]},
        ],
        "requirements_after": [
            {"id": "R1", "version": "v2", "control": "log+review", "applies_to": ["finance"]},
            {"id": "R2", "version": "v1", "control": "explain", "applies_to": ["finance"]},
            {"id": "R4", "version": "v1", "control": "inventory", "applies_to": ["operations"]},
        ],
        "evidence": [
            {"id": "ev-old", "system_id": "finance", "requirement_id": "R1",
             "version": "v1", "claimed_status": "met", "review_claim": "approved"},
            {"id": "ev-new", "system_id": "finance", "requirement_id": "R1",
             "version": "v2", "claimed_status": "met", "review_claim": "approved"},
            {"id": "ev-plant", "system_id": "plant", "requirement_id": "R3",
             "version": "v1", "claimed_status": "partial"},
            {"id": "ev-other", "system_id": "other", "requirement_id": "R4",
             "version": "v1", "claimed_status": "met", "review_claim": "passed"},
        ],
    }


def finding(report, sid, rid):
    return next(row for row in report["findings"] if
                row["system_id"] == sid and row["requirement_id"] == rid)


class GovernanceImpact140(unittest.TestCase):
    def test_T1_duplicate_and_bad_claims_fail_closed(self):
        for mutate in (
            lambda p: p["systems"].append(copy.deepcopy(p["systems"][0])),
            lambda p: p["requirements_after"].append(
                copy.deepcopy(p["requirements_after"][0])),
            lambda p: p["evidence"][0].update(claimed_status="verified"),
        ):
            data = sample()
            mutate(data)
            with self.assertRaises(ValueError):
                assess(data)

    def test_duplicate_evidence_id_across_distinct_systems_fails_closed(self):
        data = sample()
        data["evidence"][1]["id"] = data["evidence"][0]["id"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_EVIDENCE_ID"):
            assess(data)

    def test_T2_new_rule_is_not_auto_satisfied(self):
        report = assess(sample())
        r = finding(report, "finance", "R2")
        self.assertEqual(r["status"], "unable_to_determine")
        self.assertIsNone(r["evidence_id"])
        self.assertEqual(report["authorization"],
                         "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE")

    def test_T3_prior_evidence_is_invalidated_by_new_version(self):
        report = assess(sample())
        r = finding(report, "finance", "R1")
        self.assertEqual(r["status"], "unable_to_determine")
        self.assertTrue(r["change_impacts_system"])
        self.assertEqual(r["reason"], "changed_requirement_invalidates_prior_evidence")
        self.assertEqual(r["historical_evidence_id"], "ev-old")

    def test_T4_retirement_preserves_before_identity(self):
        report = assess(sample())
        self.assertEqual(finding(report, "plant", "R3")["status"], "not_applicable")
        retire = next(row for row in report["changes"] if row["id"] == "R3")
        self.assertEqual(retire["kind"], "retired")
        self.assertEqual(retire["before"]["version"], "v1")
        self.assertEqual(finding(report, "plant", "R3")["historical_evidence_id"], "ev-plant")

    def test_T5_unrelated_system_stays_unaffected(self):
        report = assess(sample())
        self.assertEqual(report["impacted_systems"], ["finance", "plant"])
        r = finding(report, "other", "R4")
        self.assertFalse(r["change_impacts_system"])
        self.assertEqual(r["status"], "pending_review")

    def test_T6_self_asserted_approval_never_becomes_compliance(self):
        report = assess(sample())
        for sid, rid in (("finance", "R1"), ("other", "R4")):
            self.assertTrue(finding(report, sid, rid)["reported_approval_ignored"])
            self.assertNotEqual(finding(report, sid, rid)["status"], "met")

    def test_T7_deterministic_independently_recomputable_receipt(self):
        a, b = assess(sample()), assess(sample())
        self.assertEqual(canonical(a), canonical(b))
        digest = a.pop("receipt_sha256")
        self.assertEqual(digest, sha256(a))
        a["changes"][0]["kind"] = "false"
        self.assertNotEqual(digest, sha256(a))

    def test_T8_no_cross_system_evidence_and_unknown_refs_fail(self):
        data = sample()
        data["evidence"].append({
            "id": "fake", "system_id": "plant", "requirement_id": "R2",
            "version": "v1", "claimed_status": "met"})
        report = assess(data)
        self.assertFalse(any(x["evidence_id"] == "fake" for x in report["findings"]))
        self.assertEqual(finding(report, "finance", "R2")["status"],
                         "unable_to_determine")
        data["evidence"][-1]["requirement_id"] = "UNREGISTERED"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EVIDENCE"):
            assess(data)

    def test_T9_empty_invalid_and_duplicate_json_fail(self):
        for payload in (None, {}, {"systems": []}, []):
            with self.assertRaises(ValueError):
                assess(payload)
        with self.assertRaisesRegex(ValueError, "NONEMPTY_GOVERNANCE"):
            assess({"systems": [], "requirements_before": [],
                    "requirements_after": [], "evidence": []})
        data = sample()
        data["evidence"][0]["version"] = "never-registered"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EVIDENCE_REQUIREMENT_VERSION"):
            assess(data)
        data = sample()
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / "in.json", Path(tmp) / "out.json"
            src.write_text(json.dumps(data), encoding="utf-8")
            main(["--input", str(src), "--output", str(dest)])
            self.assertEqual(json.loads(dest.read_text())["receipt_sha256"],
                             assess(data)["receipt_sha256"])
            with self.assertRaises(FileExistsError):
                main(["--input", str(src), "--output", str(dest)])
            src.write_text('{"systems":[],"systems":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
                main(["--input", str(src), "--output", str(Path(tmp) / "fail.json")])

    def test_external_receipt_anchor_rejects_rehashed_tampering_and_cross_input(self):
        original = sample()
        report = assess(original)
        receipt_anchor = report["receipt_sha256"]
        input_anchor = sha256(original)
        self.assertTrue(verify_receipt(
            report, anchored_receipt_sha256=receipt_anchor,
            anchored_input_sha256=input_anchor))
        tampered = copy.deepcopy(report)
        tampered["findings"][0]["status"] = "met"
        tampered["receipt_sha256"] = sha256(
            {key: val for key, val in tampered.items() if key != "receipt_sha256"})
        with self.assertRaisesRegex(ValueError, "RECEIPT_ANCHOR_MISMATCH"):
            verify_receipt(tampered, anchored_receipt_sha256=receipt_anchor,
                           anchored_input_sha256=input_anchor)
        with self.assertRaisesRegex(ValueError, "INPUT_ANCHOR_MISMATCH"):
            verify_receipt(report, anchored_receipt_sha256=receipt_anchor,
                           anchored_input_sha256="0" * 64)
        missing = copy.deepcopy(report)
        del missing["receipt_sha256"]
        with self.assertRaisesRegex(ValueError, "RECEIPT_ANCHOR_MISMATCH"):
            verify_receipt(missing, anchored_receipt_sha256=receipt_anchor,
                           anchored_input_sha256=input_anchor)
        with self.assertRaisesRegex(ValueError, "EXTERNAL_SHA256_ANCHORS_REQUIRED"):
            verify_receipt(report, anchored_receipt_sha256=receipt_anchor,
                           anchored_input_sha256="untrusted")

    def test_change_without_version_bump_still_invalidates_evidence(self):
        data = sample()
        data["requirements_after"][0]["version"] = "v1"
        # A second v2 assertion would be invalid after removing v2 from the source.
        data["evidence"] = [row for row in data["evidence"] if row["id"] != "ev-new"]
        report = assess(data)
        self.assertEqual(finding(report, "finance", "R1")["status"],
                         "unable_to_determine")
        self.assertTrue(finding(report, "finance", "R1")["change_impacts_system"])


    def test_unapplied_registered_evidence_never_silently_disappears(self):
        data = sample()
        data["evidence"].append({
            "id": "cross-scope-claim", "system_id": "plant",
            "requirement_id": "R2", "version": "v1", "claimed_status": "met",
            "review_claim": "approved",
        })
        receipt = assess(data)
        quarantine = receipt["quarantined_evidence"]
        self.assertEqual(len(quarantine), 1)
        self.assertEqual(quarantine[0]["id"], "cross-scope-claim")
        self.assertEqual(quarantine[0]["system_id"], "plant")
        self.assertEqual(quarantine[0]["requirement_id"], "R2")
        self.assertEqual(quarantine[0]["version"], "v1")
        self.assertEqual(
            quarantine[0]["reason"],
            "NO_APPLICABLE_REQUIREMENT_FOR_SYSTEM_AND_VERSION")
        self.assertEqual(
            quarantine[0]["authorization"], "NO_COMPLIANCE_OR_REVIEW_APPROVAL")
        self.assertEqual(receipt["evidence_reconciliation"], {
            "input_evidence_count": 5,
            "referenced_evidence_count": 4,
            "quarantined_evidence_count": 1,
        })
        self.assertFalse(any(
            row.get("evidence_id") == "cross-scope-claim" or
            row.get("historical_evidence_id") == "cross-scope-claim"
            for row in receipt["findings"]))
        self.assertTrue(verify_receipt(
            receipt, anchored_input_sha256=sha256(data),
            anchored_receipt_sha256=receipt["receipt_sha256"]))

    def test_reconciliation_counts_shared_historical_and_current_id_once(self):
        data = sample()
        data["requirements_after"][0]["version"] = "v1"
        data["evidence"] = [
            x for x in data["evidence"] if x["id"] != "ev-new"]
        receipt = assess(data)
        row = finding(receipt, "finance", "R1")
        self.assertEqual(row["historical_evidence_id"], "ev-old")
        self.assertEqual(row["evidence_id"], "ev-old")
        self.assertEqual(row["status"], "unable_to_determine")
        self.assertEqual(receipt["evidence_reconciliation"], {
            "input_evidence_count": 3,
            "referenced_evidence_count": 3,
            "quarantined_evidence_count": 0,
        })

    def test_quarantine_order_and_referenced_identity_partition(self):
        data = sample()
        data["evidence"].extend([
            {"id": "zz-unapplied", "system_id": "finance",
             "requirement_id": "R3", "version": "v1", "claimed_status": "met"},
            {"id": "aa-unapplied", "system_id": "plant",
             "requirement_id": "R2", "version": "v1", "claimed_status": "met"},
        ])
        receipt = assess(data)
        quarantine_ids = [x["id"] for x in receipt["quarantined_evidence"]]
        self.assertEqual(quarantine_ids, ["aa-unapplied", "zz-unapplied"])
        referenced = {
            row[field] for row in receipt["findings"]
            for field in ("evidence_id", "historical_evidence_id")
            if row.get(field) is not None
        }
        submitted = {item["id"] for item in data["evidence"]}
        self.assertFalse(referenced & set(quarantine_ids))
        self.assertEqual(referenced | set(quarantine_ids), submitted)
        self.assertEqual(receipt["evidence_reconciliation"], {
            "input_evidence_count": 6,
            "referenced_evidence_count": 4,
            "quarantined_evidence_count": 2,
        })


if __name__ == "__main__":
    unittest.main()
