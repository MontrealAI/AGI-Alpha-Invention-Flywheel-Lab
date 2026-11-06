"""Independent prospective counterexamples for restored obligation provenance.

Research-only, on the exact CONTINUITY Ω 0.2 owner source.  These are
*red* acceptance requirements, not a substitute financial/recovery engine.
The recovered snapshot is intended to describe work still to be fulfilled,
not a complete authenticated historical ledger.

These tests deliberately fail against the pinned owner source until the
constructor and independent verifier agree on a stronger explicit schema.
Neither test modifies the historical source or a real account.
"""
import unittest

from continuity_omega.demo import case_for
from continuity_omega.engine import (
    DrillRejected, construct, digest, outstanding, restored_anomalies,
)
from continuity_omega.checker import audit


class RestoredObligationStateReview(unittest.TestCase):
    def test_correctly_absent_cancellation_is_not_missing_active_work(self):
        """A cancellation must not be resurrected merely to silence an audit."""
        orders = {
            "CANCEL-001": {
                "quantity": 600,
                "fulfilled": 0,
                "status": "CANCELLED",
            },
        }
        observed_active_snapshot = []
        self.assertEqual(
            restored_anomalies(orders, observed_active_snapshot),
            [],
            "An absent canceled obligation is not a missing outstanding order.",
        )

    def test_gross_quantity_without_fulfillment_provenance_cannot_prove_no_duplicate(self):
        """The original event history says 100 units were already fulfilled.

        A restored *gross-quantity-only* row cannot establish whether those
        100 units remain completed. A future schema may explicitly carry
        authenticated fulfillment state, or refuse to certify the snapshot.
        Either is acceptable; an empty diagnostic plus passing audit is not.
        """
        case = case_for()
        original = case["source_events"]
        case["source_events"] = [
            dict(original[0]),  # ACCEPT LBL-100: 1000
            dict(original[1]),  # ACCEPT LBL-200: 800
            dict(original[3]),  # AMEND LBL-100 to 1100
            {
                "sequence": 4,
                "type": "FULFILL",
                "order_id": "LBL-100",
                "quantity": 100,
            },
        ]
        for pos, event in enumerate(case["source_events"], 1):
            event["sequence"] = pos
        case["source_seal"] = digest(case["source_events"])
        case["restored_snapshot"] = [
            {"order_id": "LBL-100", "quantity": 1100},
            {"order_id": "LBL-200", "quantity": 800},
        ]
        # Under the reduced 1800-unit load the original 1800-unit supplier Q
        # becomes eligible and wins the normal lowest-quote selector. The
        # original fixture's supplier-cost line is bound to P, so prevent an
        # UNRELATED quote mismatch from masking this provenance test.
        case["suppliers"][1]["capacity_units"] = 1700
        try:
            handoff, passport = construct(case)
        except DrillRejected as exc:
            self.assertRegex(
                str(exc).lower(), r"restor|fulfill|provenance|snapshot",
                "Only a specific restoration/fulfillment refusal counts "
                "as safe fail-closed behavior, not arbitrary input rejection.",
            )
            return
        # Correct source replay owes 1000 + 800, not the snapshot's 1900.
        self.assertEqual(handoff["required_units"], 1800)
        result = audit(case, handoff, passport)
        active, replayed = outstanding(case["source_events"], case["objective"]["product"])
        self.assertEqual(sum(row["units"] for row in active), 1800)
        # A generic audit failure (for an unrelated reason) does NOT prove
        # that the restored snapshot revealed missing fulfillment state.
        self.assertTrue(
            restored_anomalies(replayed, case["restored_snapshot"]),
            "The restoration comparator silently accepted gross-only rows "
            "without a fulfillment-state witness; independent auditor: "
            + repr(result),
        )


if __name__ == "__main__":
    unittest.main()
