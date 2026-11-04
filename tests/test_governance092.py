"""Governance092: eight frozen graph migration tests; preregistered in PROTOCOL.md."""
from __future__ import annotations

import copy
import unittest

from research.governance090.impact import ImpactRegistry, digest


def fixture():
    return {
        "tenant": "A",
        "requirements": [
            {"id": "R1", "text": "Review output trace", "status": "active"},
            {"id": "R2", "text": "Retain human decision log", "status": "active"},
        ],
        "controls": [
            {"id": "C1", "requirements": ["R1"]},
            {"id": "C2", "requirements": ["R2"]},
        ],
        "systems": [
            {"id": "S1", "controls": ["C1"]},
            {"id": "S2", "controls": ["C2"]},
        ],
        "reviewers": {
            "alice": {"tenant": "A", "roles": ["reviewer"]},
            "guest": {"tenant": "A", "roles": ["reader"]},
        },
    }


def claim():
    # Caller-asserted provenance, NOT a fetched or independently certified web hash.
    return {
        "url": "https://www.canada.ca/en/government/system/digital-government/digital-government-innovations/responsible-use-ai/automated-decision-making/algorithmic-impact-assessment.html",
        "locator": "3.1 Reviewing and updating the AIA",
        "observed_date": "2026-11-04",
        "excerpt_sha256": digest("AIA scheduled and system-change reassessment; fixture paraphrase"),
    }


def tables(r):
    return (copy.deepcopy(list(r.requirements.values())),
            copy.deepcopy(list(r.controls.values())),
            copy.deepcopy(list(r.systems.values())))


def apply(r, rs=None, cs=None, ss=None, declared=None, source=None,
          actor="alice", tenant="A", expected_tip=None):
    before = tables(r)
    return r.migrate(
        actor=actor, tenant=tenant, expected_tip=r.tip if expected_tip is None else expected_tip,
        requirements=before[0] if rs is None else rs,
        controls=before[1] if cs is None else cs,
        systems=before[2] if ss is None else ss,
        declared={"requirements": [], "controls": [], "systems": []} if declared is None else declared,
        source=claim() if source is None else source,
    )


def review(r, s="S1", c="C1", q="R1"):
    r.review(actor="alice", tenant="A", system=s, control=c, requirement=q,
             verdict="MET", evidence_sha256=digest({"for": [s, c, q]}),
             annotation="Synthetic human review fixture, not actual policy compliance")


def change(**kw):
    v = {"requirements": [], "controls": [], "systems": []}
    v.update(kw)
    return v


class Governance092Frozen(unittest.TestCase):
    def test_M1_add_requirement_control_and_system_no_fictitious_approval(self):
        r = ImpactRegistry(fixture())
        rs, cs, ss = tables(r)
        rs.append({"id": "R3", "text": "Review after a change in use", "status": "active"})
        cs.append({"id": "C3", "requirements": ["R3"]})
        ss.append({"id": "S3", "controls": ["C3"]})
        receipt = apply(r, rs, cs, ss, declared=change(requirements=["R3"], controls=["C3"], systems=["S3"]))
        self.assertEqual(receipt["affected_systems"], ["S3"])
        self.assertEqual(r.evaluate()["systems"]["S3"]["findings"][0]["status"], "UNDETERMINED")
        self.assertFalse(r.evaluate()["systems"]["S3"]["all_controls_met"])
        self.assertTrue(r.audit(r.tip))

    def test_M2_added_link_invalidates_reviewed_control_unrelated_remains(self):
        r = ImpactRegistry(fixture())
        review(r)
        review(r, "S2", "C2", "R2")
        self.assertTrue(r.evaluate()["systems"]["S1"]["all_controls_met"])
        rs, cs, _ = tables(r)
        rs.append({"id": "R3", "text": "New coverage", "status": "active"})
        cs[0]["requirements"].append("R3")
        receipt = apply(r, rs=rs, cs=cs, declared=change(requirements=["R3"], controls=["C1"]))
        self.assertEqual(receipt["affected_systems"], ["S1"])
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertEqual(next(f for f in r.evaluate()["systems"]["S1"]["findings"] if f["requirement"] == "R3")["status"], "UNDETERMINED")
        self.assertTrue(r.evaluate()["systems"]["S2"]["all_controls_met"])

    def test_M3_explicit_control_reassignment_does_not_resurrect_old_findings(self):
        r = ImpactRegistry(fixture())
        review(r)
        _, cs, _ = tables(r)
        cs[0]["requirements"] = ["R2"]
        receipt = apply(r, cs=cs, declared=change(controls=["C1"]))
        self.assertEqual(receipt["affected_systems"], ["S1"])
        findings = r.evaluate()["systems"]["S1"]["findings"]
        self.assertEqual([(f["control"], f["requirement"], f["status"]) for f in findings],
                         [("C1", "R2", "UNDETERMINED")])
        self.assertTrue(r.audit(r.tip))

    def test_M4_stale_tip_and_wrong_authority_fail_without_mutation(self):
        r = ImpactRegistry(fixture())
        rs, cs, ss = tables(r)
        rs[0]["text"] = "Changed obligation"
        before = copy.deepcopy(r.events)
        args = dict(rs=rs, declared=change(requirements=["R1"]))
        for override in ({"expected_tip": "0" * 64},
                         {"tenant": "B"},
                         {"actor": "guest"}):
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    apply(r, **args, **override)
                self.assertEqual(r.events, before)
                self.assertEqual(r.tip, before[-1]["hash"])
                self.assertEqual(tables(r), (copy.deepcopy(fixture()["requirements"]),
                                             copy.deepcopy(fixture()["controls"]),
                                             copy.deepcopy(fixture()["systems"])))

    def test_M5_undeclared_missing_source_dangling_and_deletion_fail_closed(self):
        r = ImpactRegistry(fixture())
        rs, cs, ss = tables(r)
        bad = []
        changed = copy.deepcopy(rs)
        changed[0]["text"] = "Unannounced"
        bad.append(dict(rs=changed))
        bad.append(dict(rs=changed, declared=change(requirements=["R1"]), source={}))
        dangling = copy.deepcopy(cs)
        dangling[0]["requirements"] = ["UNKNOWN"]
        bad.append(dict(cs=dangling, declared=change(controls=["C1"])))
        bad.append(dict(rs=rs[1:], declared=change(requirements=["R1"])))
        bad.append(dict(cs=cs[1:], declared=change(controls=["C1"])))
        bad.append(dict(ss=ss[1:], declared=change(systems=["S1"])))
        old_events = copy.deepcopy(r.events)
        old_tables = tables(r)
        for case in bad:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    apply(r, **case)
                self.assertEqual(r.events, old_events)
                self.assertEqual(tables(r), old_tables)

    def test_M6_semantic_noop_has_no_new_event_or_changed_digest(self):
        r = ImpactRegistry(fixture())
        rs, cs, ss = tables(r)
        old_tip = r.tip
        receipt = apply(r, rs=list(reversed(rs)), cs=list(reversed(cs)), ss=list(reversed(ss)))
        self.assertEqual(r.tip, old_tip)
        self.assertEqual(receipt["before_sha256"], receipt["after_sha256"])
        self.assertEqual(receipt["affected_systems"], [])
        self.assertEqual(len(r.events), 1)

    def test_M7_policy_rollback_does_not_reauthorize_old_met(self):
        r = ImpactRegistry(fixture())
        review(r)
        original = copy.deepcopy(tables(r)[0])
        revised = copy.deepcopy(original)
        revised[0]["text"] = "Revised AIA requirement"
        apply(r, rs=revised, declared=change(requirements=["R1"]))
        self.assertEqual(r.evaluate()["systems"]["S1"]["findings"][0]["status"], "UNDETERMINED")
        apply(r, rs=original, declared=change(requirements=["R1"]))
        self.assertEqual(r.evaluate()["systems"]["S1"]["findings"][0]["status"], "UNDETERMINED")
        self.assertTrue(r.audit(r.tip))

    def test_M8_clean_reassessment_immutable_prior_events_full_traversal_agrees(self):
        r = ImpactRegistry(fixture())
        review(r)
        review(r, "S2", "C2", "R2")
        original = copy.deepcopy(r.events)
        rs, cs, ss = tables(r)
        cs.append({"id": "C3", "requirements": ["R1"]})
        ss[0]["controls"].append("C3")
        receipt = apply(r, cs=cs, ss=ss, declared=change(controls=["C3"], systems=["S1"]))
        # Independent exhaustive comparator over old/new incidence without reverse indexes.
        old = fixture()
        old_links = {(s["id"], c, q) for s in old["systems"] for c in s["controls"]
                     for row in old["controls"] if row["id"] == c for q in row["requirements"]}
        new_links = {(s["id"], c, q) for s in ss for c in s["controls"]
                     for row in cs if row["id"] == c for q in row["requirements"]}
        expected = sorted({s for s, c, q in old_links | new_links if (s == "S1" or c == "C3")})
        self.assertEqual(receipt["affected_systems"], expected)
        self.assertEqual(r.events[:len(original)], original)
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertTrue(r.evaluate()["systems"]["S2"]["all_controls_met"])
        review(r, "S1", "C1", "R1")
        review(r, "S1", "C3", "R1")
        self.assertTrue(r.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertTrue(r.audit(r.tip))


if __name__ == "__main__":
    unittest.main()
