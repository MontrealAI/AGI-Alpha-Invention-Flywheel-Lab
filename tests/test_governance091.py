"""Governance091 preregistered R1-R6: independently review post-revision approvals.

This is a separate research review, not an edit to the frozen Governance090 eight.
"""
import copy
import unittest

from research.governance090.impact import ImpactRegistry, digest, verify_chain


def specification():
    return {
        "tenant": "public-fixture",
        "requirements": [
            {"id": "R1", "text": "A: retain traceable evidence", "status": "active"},
            {"id": "R3", "text": "Independently review a different control", "status": "active"},
        ],
        "controls": [
            {"id": "C1", "requirements": ["R1"]},
            {"id": "C3", "requirements": ["R3"]},
        ],
        "systems": [
            {"id": "S1", "controls": ["C1"]},
            {"id": "S3", "controls": ["C3"]},
        ],
        "reviewers": {
            "reviewer": {"tenant": "public-fixture", "roles": ["reviewer"]}
        },
    }


def approval(registry, system="S1", control="C1", requirement="R1"):
    registry.review(
        actor="reviewer", tenant="public-fixture",
        system=system, control=control, requirement=requirement,
        verdict="MET", evidence_sha256=digest({"review": system, "requirement": requirement}),
        annotation="Synthetic affirmative human assertion; not a legal compliance decision",
    )


def status(registry, system):
    return registry.evaluate()["systems"][system]["findings"][0]["status"]


def new_requirements(registry, *, r1_text=None, r1_status=None):
    rows = copy.deepcopy(list(registry.requirements.values()))
    if r1_text is not None:
        rows[0]["text"] = r1_text
    if r1_status is not None:
        rows[0]["status"] = r1_status
    return rows


def ordinary_replay(events):
    """Independent chronological control; an update revokes earlier mapped reviews."""
    approvals = {}
    for event in events:
        payload = event["payload"]
        if payload["kind"] == "update":
            for changed in payload["changed"]:
                for key in list(approvals):
                    if key[2] == changed:
                        del approvals[key]
        elif payload["kind"] == "review":
            key = (payload["system"], payload["control"], payload["requirement"])
            approvals[key] = payload["verdict"]
    return approvals


class Governance091Frozen(unittest.TestCase):
    def test_R1_A_B_A_reversion_must_not_resurrect_old_approval(self):
        r = ImpactRegistry(specification())
        approval(r)
        self.assertEqual(status(r, "S1"), "MET")
        r.update(new_requirements(r, r1_text="B: additional review"))
        self.assertEqual(status(r, "S1"), "UNDETERMINED")
        r.update(new_requirements(r, r1_text="A: retain traceable evidence"))
        self.assertEqual(status(r, "S1"), "UNDETERMINED")
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])
        self.assertTrue(r.audit(r.tip))

    def test_R2_retire_then_reactivate_must_not_resurrect_old_approval(self):
        r = ImpactRegistry(specification())
        approval(r)
        r.update(new_requirements(r, r1_status="retired"))
        self.assertEqual(status(r, "S1"), "RETIRED_REVIEW_REQUIRED")
        r.update(new_requirements(r, r1_status="active"))
        self.assertEqual(status(r, "S1"), "UNDETERMINED")
        self.assertFalse(r.evaluate()["systems"]["S1"]["all_controls_met"])

    def test_R3_noop_keeps_valid_epoch_and_does_not_write_event(self):
        r = ImpactRegistry(specification())
        approval(r)
        before_tip, before_length = r.tip, len(r.events)
        change = r.update(new_requirements(r))
        self.assertEqual(change["changed_requirements"], [])
        self.assertEqual(r.tip, before_tip)
        self.assertEqual(len(r.events), before_length)
        self.assertEqual(status(r, "S1"), "MET")

    def test_R4_fresh_reapproval_after_reversion_is_valid_and_chain_audits(self):
        r = ImpactRegistry(specification())
        approval(r)
        r.update(new_requirements(r, r1_text="B: additional review"))
        r.update(new_requirements(r, r1_text="A: retain traceable evidence"))
        self.assertEqual(status(r, "S1"), "UNDETERMINED")
        old_approval = next(e for e in r.events if e["payload"].get("kind") == "review")
        approval(r)
        finding = r.evaluate()["systems"]["S1"]["findings"][0]
        self.assertEqual(finding["status"], "MET")
        self.assertNotEqual(finding["event_hash"], old_approval["hash"])
        self.assertTrue(verify_chain(r.events, r.tip))

    def test_R5_unrelated_approval_and_ordinary_event_replay_agree(self):
        r = ImpactRegistry(specification())
        approval(r)
        approval(r, "S3", "C3", "R3")
        r.update(new_requirements(r, r1_text="B: additional review"))
        r.update(new_requirements(r, r1_text="A: retain traceable evidence"))
        oracle = ordinary_replay(r.events)
        self.assertEqual(oracle.get(("S1", "C1", "R1"), "UNDETERMINED"), "UNDETERMINED")
        self.assertEqual(oracle.get(("S3", "C3", "R3")), "MET")
        self.assertEqual(status(r, "S1"), oracle.get(("S1", "C1", "R1"), "UNDETERMINED"))
        self.assertEqual(status(r, "S3"), oracle.get(("S3", "C3", "R3"), "UNDETERMINED"))

    def test_R6_no_global_compliance_and_external_tip_is_required(self):
        r = ImpactRegistry(specification())
        approval(r)
        self.assertFalse(r.evaluate()["qualified_compliance"])
        self.assertTrue(verify_chain(r.events, r.tip))
        wrong_tip = "0" * 64
        with self.assertRaisesRegex(ValueError, "JOURNAL_TIP_CHANGED"):
            verify_chain(r.events, wrong_tip)
        changed = copy.deepcopy(r.events)
        changed[-1]["payload"]["verdict"] = "NOT_MET"
        with self.assertRaisesRegex(ValueError, "JOURNAL_CONTENT"):
            verify_chain(changed, r.tip)


if __name__ == "__main__":
    unittest.main()
