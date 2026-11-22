"""Eight frozen development/confirmation/adversarial checks from governance090 protocol."""
import copy
import tempfile
import unittest
from pathlib import Path

from research.governance090.impact import ImpactRegistry, digest, full_scan_impacts, read_strict, verify_chain


def base(tenant="A"):
    return {
        "tenant": tenant,
        "requirements": [
            {"id": "R1", "text": "Require verifiable model and output monitoring", "status": "active"},
            {"id": "R2", "text": "Require authorized human findings review", "status": "active"},
            {"id": "R3", "text": "Require recorded change history", "status": "active"}],
        "controls": [
            {"id": "C1", "requirements": ["R1"]},
            {"id": "C2", "requirements": ["R1", "R2"]},
            {"id": "C3", "requirements": ["R3"]}],
        "systems": [
            {"id": "S1", "controls": ["C1"]},
            {"id": "S2", "controls": ["C2"]},
            {"id": "S3", "controls": ["C3"]}],
        "reviewers": {"alice": {"tenant": tenant, "roles": ["reviewer"]},
                      "guest": {"tenant": tenant, "roles": ["reader"]},
                      "other": {"tenant": "B", "roles": ["reviewer"]}}
    }


def review(r, system, control, requirement, actor="alice", verdict="MET", tenant="A"):
    r.review(actor=actor, tenant=tenant, system=system, control=control,
             requirement=requirement, verdict=verdict,
             evidence_sha256=digest({"document": system, "rule": requirement}),
             annotation="fixture reviewer says evidence checked; NOT a legal finding")


class Governance090Frozen(unittest.TestCase):
    def test_D1_changed_requirement_invalidates_only_mapped(self):
        r = ImpactRegistry(base())
        review(r, "S1", "C1", "R1")
        review(r, "S3", "C3", "R3")
        self.assertTrue(r.evaluate()["systems"]["S1"]["all_controls_met"])
        revision = copy.deepcopy(base()["requirements"])
        revision[0]["text"] += "; new monitoring interval"
        impact = r.update(revision)
        self.assertEqual(impact["affected_systems"], ["S1", "S2"])
        finding1 = r.evaluate()["systems"]["S1"]["findings"][0]
        self.assertEqual(finding1["status"], "UNDETERMINED")
        self.assertTrue(r.evaluate()["systems"]["S3"]["all_controls_met"])
        self.assertTrue(r.audit(r.tip))

    def test_D2_retired_obligation_does_not_disappear(self):
        r = ImpactRegistry(base())
        review(r, "S2", "C2", "R2")
        revision = copy.deepcopy(base()["requirements"])
        revision[1]["status"] = "retired"
        impact = r.update(revision)
        self.assertEqual(impact["affected_systems"], ["S2"])
        findings = r.evaluate()["systems"]["S2"]["findings"]
        self.assertEqual(next(f["status"] for f in findings if f["requirement"] == "R2"), "RETIRED_REVIEW_REQUIRED")
        self.assertTrue(any(e["payload"].get("kind") == "review" for e in r.events))
        with self.assertRaisesRegex(ValueError, "RETIRED_REQUIREMENT"):
            review(r, "S2", "C2", "R2")

    def test_D3_missing_or_negative_does_not_certify(self):
        r = ImpactRegistry(base())
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])
        review(r, "S1", "C1", "R1", verdict="NOT_MET")
        self.assertEqual(r.evaluate()["systems"]["S1"]["findings"][0]["status"], "NOT_MET")
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertFalse(r.evaluate()["qualified_compliance"])
        with self.assertRaisesRegex(ValueError, "INVALID_VERDICT"):
            review(r, "S1", "C1", "R1", verdict="ACCEPTED_GLOBAL")

    def test_D4_reviewer_scope_and_append_only(self):
        r = ImpactRegistry(base())
        tip = r.tip
        with self.assertRaisesRegex(ValueError, "REVIEWER_NOT_AUTHORIZED"):
            review(r, "S1", "C1", "R1", actor="guest")
        with self.assertRaisesRegex(ValueError, "REVIEWER_NOT_AUTHORIZED"):
            review(r, "S1", "C1", "R1", actor="other")
        with self.assertRaisesRegex(ValueError, "REVIEWER_NOT_AUTHORIZED"):
            review(r, "S1", "C1", "R1", tenant="B")
        self.assertEqual(r.tip, tip)
        review(r, "S1", "C1", "R1", verdict="NOT_MET")
        prior = copy.deepcopy(r.events[-1])
        review(r, "S1", "C1", "R1", verdict="PARTIAL")
        self.assertEqual(r.events[-2], prior)
        self.assertEqual(r.evaluate()["systems"]["S1"]["findings"][0]["status"], "PARTIAL")
        self.assertTrue(r.audit(r.tip))

    def test_H1_two_paths_one_unrelated_control(self):
        r = ImpactRegistry(base())
        revision = copy.deepcopy(base()["requirements"])
        revision[0]["text"] += " changed"
        impact = r.update(revision)
        ordinary = full_scan_impacts(r.systems, r.controls, set(impact["changed_requirements"]))
        self.assertEqual(ordinary, ["S1", "S2"])
        self.assertEqual(impact["affected_systems"], ordinary)
        self.assertEqual(impact["changed_requirements"], ["R1"])
        self.assertNotIn("S3", impact["affected_systems"])

    def test_H2_no_op_cross_tenant_same_names_and_stale_evidence(self):
        a = ImpactRegistry(base("A"))
        b = ImpactRegistry(base("B"))
        review(a, "S1", "C1", "R1")
        before = a.tip
        noop = a.update(copy.deepcopy(base("A")["requirements"]))
        self.assertEqual(noop["affected_systems"], [])
        self.assertEqual(a.tip, before)
        # Same labels across tenants are not a permission bridge.
        with self.assertRaisesRegex(ValueError, "REVIEWER_NOT_AUTHORIZED"):
            b.review(actor="alice", tenant="A", system="S1", control="C1", requirement="R1",
                     verdict="MET", evidence_sha256=digest("test"), annotation="wrong tenant")
        self.assertFalse(b.evaluate()["systems"]["S1"]["all_controls_met"])
        new = copy.deepcopy(base("A")["requirements"])
        new[0]["text"] += "; amended"
        a.update(new)
        self.assertFalse(a.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertEqual(a.evaluate()["systems"]["S1"]["findings"][0]["status"], "UNDETERMINED")

    def test_A1_reject_duplicate_json_object_members(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ambiguous.json"
            p.write_text('{"tenant":"A","tenant":"B"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY:tenant"):
                read_strict(p)
            p.write_text('{"tenant":"A","v":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NONFINITE"):
                read_strict(p)

    def test_A2_replay_detects_order_content_and_external_tip_forgery(self):
        r = ImpactRegistry(base())
        review(r, "S1", "C1", "R1")
        review(r, "S1", "C1", "R1", verdict="NOT_MET")
        original_tip = r.tip
        self.assertTrue(verify_chain(r.events, original_tip))
        swapped = copy.deepcopy(r.events)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        with self.assertRaisesRegex(ValueError, "JOURNAL_ORDER|JOURNAL_CONTENT"):
            verify_chain(swapped, original_tip)
        altered = copy.deepcopy(r.events)
        altered[2]["payload"]["verdict"] = "MET"
        with self.assertRaisesRegex(ValueError, "JOURNAL_CONTENT"):
            verify_chain(altered, original_tip)
        # An independently pinned tip must survive even a recomputed hash chain.
        forged = copy.deepcopy(r.events)
        forged[2]["payload"]["verdict"] = "MET"
        forged[2]["hash"] = digest({"seq": 2, "previous": forged[2]["previous"], "payload": forged[2]["payload"]})
        with self.assertRaisesRegex(ValueError, "JOURNAL_TIP_CHANGED"):
            verify_chain(forged, original_tip)


if __name__ == "__main__":
    unittest.main()
