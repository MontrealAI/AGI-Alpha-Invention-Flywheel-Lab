"""Preregistered OSCAL171 finite adversarial checks; synthetic only."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from products.governance_impact140 import engine as native
from research import governance_oscal171 as bridge

UID = "11111111-1111-4111-8111-111111111111"


def example():
    group = {"id": "g", "title": "Governance", "controls": [
        {"id": "c1", "title": "retain evidence",
         "parts": [{"name": "statement", "prose": "retain decision evidence"}]},
        {"id": "c2", "title": "monitor outcomes"}]}
    catalog = {"catalog": {
        "uuid": UID, "metadata": {"title": "Synthetic only", "version": "1"},
        "controls": [], "groups": [group]}}
    return {
        "schema": bridge.SCHEMA, "before_catalog": copy.deepcopy(catalog),
        "after_catalog": copy.deepcopy(catalog),
        "systems": [{"id": "finance-system", "tags": ["finance"]},
                    {"id": "ops-system", "tags": ["ops"]}],
        "before_scope": {"c1": {"applies_to": ["finance"]},
                         "c2": {"applies_to": ["ops"]}},
        "after_scope": {"c1": {"applies_to": ["finance"]},
                        "c2": {"applies_to": ["ops"]}},
        "evidence": []
    }


class FixedOSCAL171(unittest.TestCase):
    def test_t1_native_direct_parity(self):
        data = example()
        got = bridge.assess(data)
        self.assertEqual(got["native_receipt"], native.assess(got["native_input"]))
        self.assertEqual({r["id"] for r in got["after_controls"]}, {"c1", "c2"})
        self.assertEqual(got["native_receipt"]["impacted_systems"], [])
        self.assertEqual(
            {(f["system_id"], f["requirement_id"]) for f in got["native_receipt"]["findings"]},
            {("finance-system", "c1"), ("ops-system", "c2")})

    def test_t2_unchanged_metadata_version_changed_content_invalidates(self):
        data = example()
        old = bridge.assess(data)
        data["evidence"] = [{
            "id": "untrusted-claim", "system_id": "finance-system",
            "requirement_id": "c1", "version": old["before_controls"][0]["version"],
            "claimed_status": "met", "review_claim": "approved"
        }]
        data["after_catalog"]["catalog"]["groups"][0]["controls"][0]["parts"][0]["prose"] = "discard evidence"
        got = bridge.assess(data)
        finding = next(f for f in got["native_receipt"]["findings"] if f["requirement_id"] == "c1")
        self.assertNotEqual(got["before_controls"][0]["version"], got["after_controls"][0]["version"])
        self.assertEqual(got["before"]["catalog_version"], got["after"]["catalog_version"])
        self.assertEqual(finding["status"], "unable_to_determine")
        self.assertEqual(finding["historical_evidence_id"], "untrusted-claim")
        self.assertEqual(got["native_receipt"]["impacted_systems"], ["finance-system"])

    def test_t3_added_retired_and_quarantined(self):
        data = example()
        previous = bridge.assess(data)
        data["after_catalog"]["catalog"]["groups"][0]["controls"].pop()
        data["after_catalog"]["catalog"]["controls"].append({"id": "c3", "title": "verify decision"})
        data["after_scope"] = {"c1": {"applies_to": ["finance"]},
                               "c3": {"applies_to": ["finance"]}}
        data["evidence"] = [{
            "id": "cross-scope", "system_id": "finance-system",
            "requirement_id": "c2", "version": previous["before_controls"][1]["version"],
            "claimed_status": "met"
        }]
        r = bridge.assess(data)["native_receipt"]
        self.assertEqual({x["kind"] for x in r["changes"]}, {"added", "retired"})
        self.assertEqual(r["impacted_systems"], ["finance-system", "ops-system"])
        self.assertEqual([x["id"] for x in r["quarantined_evidence"]], ["cross-scope"])
        self.assertFalse(any(f["status"] == "met" for f in r["findings"]))

    def test_t4_missing_unknown_duplicates_fail_closed(self):
        d = example()
        del d["after_scope"]["c1"]
        with self.assertRaisesRegex(ValueError, "EVERY_OSCAL_CONTROL"):
            bridge.assess(d)
        d = example()
        d["after_scope"]["c2"]["applies_to"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "SCOPE_MUST_MATCH"):
            bridge.assess(d)
        d = example()
        d["after_catalog"]["catalog"]["controls"].append({"id": "c1", "title": "duplicate"})
        with self.assertRaisesRegex(ValueError, "DUPLICATE_OSCAL_IDENTIFIER"):
            bridge.assess(d)
        d = example()
        d["after_scope"]["c1"]["applies_to"] = ["finance", "finance"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SCOPE_TAG"):
            bridge.assess(d)

    def test_t5_context_change_only_affects_descendants(self):
        d = example()
        root = {"id": "root", "title": "unrelated"}
        for stage in ("before", "after"):
            d[f"{stage}_catalog"]["catalog"]["controls"].append(copy.deepcopy(root))
            d[f"{stage}_scope"]["root"] = {"applies_to": ["ops"]}
        d["after_catalog"]["catalog"]["groups"][0]["title"] = "changed context"
        got = bridge.assess(d)
        older = {x["id"]: x["version"] for x in got["before_controls"]}
        newer = {x["id"]: x["version"] for x in got["after_controls"]}
        self.assertNotEqual(older["c1"], newer["c1"])
        self.assertNotEqual(older["c2"], newer["c2"])
        self.assertEqual(older["root"], newer["root"])

    def test_t6_source_integrity_immutable_external_anchors(self):
        d = example()
        copy_before = copy.deepcopy(d)
        report = bridge.assess(d)
        self.assertEqual(report, bridge.assess(d))
        self.assertEqual(d, copy_before)
        self.assertTrue(bridge.verify_receipt(
            report, expected_input_sha256=native.sha256(d),
            expected_receipt_sha256=report["receipt_sha256"]))
        modified = copy.deepcopy(report)
        modified["after"]["catalog_version"] = "tampered"
        with self.assertRaisesRegex(ValueError, "RECEIPT_CONTENT_CHANGED"):
            bridge.verify_receipt(modified, expected_input_sha256=native.sha256(d),
                                  expected_receipt_sha256=report["receipt_sha256"])
        d["after_catalog"]["catalog"]["groups"][0]["controls"][0]["title"] = "changed"
        with self.assertRaisesRegex(ValueError, "EXTERNAL_INPUT_ANCHOR_MISMATCH"):
            bridge.verify_receipt(report, expected_input_sha256=native.sha256(d),
                                  expected_receipt_sha256=report["receipt_sha256"])

    def test_t7_strict_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, dst = root / "input.json", root / "out.json"
            src.write_text(json.dumps(example()), encoding="utf-8")
            prefix = [sys.executable, "-m", "research.governance_oscal171", "--input", str(src), "--output"]
            self.assertEqual(subprocess.run(prefix + [str(dst)], capture_output=True).returncode, 0)
            self.assertTrue(dst.is_file())
            self.assertNotEqual(subprocess.run(prefix + [str(dst)], capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(prefix + [str(src)], capture_output=True).returncode, 0)
            src.write_text('{"schema":1,"schema":2}', encoding="utf-8")
            self.assertNotEqual(subprocess.run(prefix + [str(root / "other.json")], capture_output=True).returncode, 0)
            src.write_text('{"schema":NaN}', encoding="utf-8")
            self.assertNotEqual(subprocess.run(prefix + [str(root / "another.json")], capture_output=True).returncode, 0)

    def test_t8_no_approval_or_finance(self):
        r = bridge.assess(example())
        self.assertEqual(r["authorization"], "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE")
        self.assertEqual(r["native_receipt"]["authorization"],
                         "NO_AUTHENTICATED_REVIEW_OR_COMPLIANCE_CERTIFICATE")
        self.assertIsNone(r["complete_actual_cost"])
        self.assertTrue(all(f["review_status"] == "pending_authorized_independent_review"
                            for f in r["native_receipt"]["findings"]))


if __name__ == "__main__":
    unittest.main()
