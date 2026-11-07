"""Preregistered strong-incumbent comparator; synthetic only, no cherry-picked cases."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(__file__).resolve().parents[1] / "reviews" / "continuity-restored-obligations-20261106"
sys.path.insert(0, str(BASE))

from witness_chain import make_demo_bundle, digest  # noqa: E402
from strong_incumbent import compare  # noqa: E402


def frozen_case():
    # Six events and v2 snapshot preregistered in
    # docs/continuity-omega/INCUMBENT_PARITY_PREREG_20261107.md.
    source = [
        {"sequence": 1, "type": "ACCEPT", "order_id": "A-100", "quantity": 1000,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 2, "type": "ACCEPT", "order_id": "B-200", "quantity": 800,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 3, "type": "AMEND", "order_id": "A-100", "quantity": 1100},
        {"sequence": 4, "type": "FULFILL", "order_id": "A-100", "quantity": 100},
        {"sequence": 5, "type": "ACCEPT", "order_id": "C-300", "quantity": 600,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 6, "type": "CANCEL", "order_id": "C-300"},
    ]
    restored = {
        "schema": "continuity-omega/restored-active-v2",
        "source_events_sha256": digest(source),
        "records": [
            {"order_id": "A-100", "gross_quantity": 1100,
             "fulfilled_quantity": 100, "source_event_sequences": [1, 3, 4]},
            {"order_id": "B-200", "gross_quantity": 800,
             "fulfilled_quantity": 0, "source_event_sequences": [2]},
        ],
    }
    # Local ephemeral simulation keys only. Public material is passed to the
    # verifier, no private key is printed or returned in a report.
    private = {r: Ed25519PrivateKey.generate() for r in ("ERP", "FULFILLMENT", "AUDITOR")}
    public = {r: key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        for r, key in private.items()}
    bundle = make_demo_bundle(source, restored, "LAB-001", private)
    return source, restored, bundle, public


def trial(source, restored, bundle, public, **overrides):
    args = {
        "role_public_keys": public,
        "latest_witness_anchor": digest(bundle["anchor"]),
        "min_witness_sequence": 6,
        "externally_expected_case_id": "LAB-001",
        "offsite_source_available": True,
        "offsite_source_pin": digest(frozen_case_source()),
        "offsite_restored_pin": digest(frozen_case_snapshot()),
    }
    args.update(overrides)
    return compare(source, restored, bundle, **args)


def frozen_case_source():
    # No generated keys needed for frozen evidence identities. The same six
    # event contents from the reference fixture are encoded here.
    return [
        {"sequence": 1, "type": "ACCEPT", "order_id": "A-100", "quantity": 1000,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 2, "type": "ACCEPT", "order_id": "B-200", "quantity": 800,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 3, "type": "AMEND", "order_id": "A-100", "quantity": 1100},
        {"sequence": 4, "type": "FULFILL", "order_id": "A-100", "quantity": 100},
        {"sequence": 5, "type": "ACCEPT", "order_id": "C-300", "quantity": 600,
         "product": "LABEL", "spec_sha256": "a" * 64, "deadline_hours": 48},
        {"sequence": 6, "type": "CANCEL", "order_id": "C-300"},
    ]


def frozen_case_snapshot():
    src = frozen_case_source()
    return {
        "schema": "continuity-omega/restored-active-v2",
        "source_events_sha256": digest(src),
        "records": [
            {"order_id": "A-100", "gross_quantity": 1100,
             "fulfilled_quantity": 100, "source_event_sequences": [1, 3, 4]},
            {"order_id": "B-200", "gross_quantity": 800,
             "fulfilled_quantity": 0, "source_event_sequences": [2]},
        ],
    }


class PreregisteredStrongIncumbentTests(unittest.TestCase):
    def test_01_competent_offsite_replay_matches_witness_functionally(self):
        items = frozen_case()
        out = trial(*items)
        self.assertEqual(out["incumbent"]["verdict"], "RECONCILED_SYNTHETIC")
        self.assertEqual(out["challenger"]["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")
        self.assertEqual(out["technical_verdict"], "FUNCTIONAL_PARITY_AS_OF_PINNED_SOURCE")
        self.assertFalse(out["current_obligations_verified"])

    def test_02_lost_partial_fulfillment_is_rejected_on_both_routes(self):
        items = frozen_case()
        damaged = copy.deepcopy(items[1])
        damaged["records"][0]["fulfilled_quantity"] = 0
        out = trial(items[0], damaged, items[2], items[3])
        self.assertNotEqual(out["incumbent"]["verdict"], "RECONCILED_SYNTHETIC")
        self.assertNotEqual(out["challenger"]["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")

    def test_03_cancelled_order_resurrection_is_not_a_recovered_outstanding_order(self):
        items = frozen_case()
        damaged = copy.deepcopy(items[1])
        damaged["records"].append(
            {"order_id": "C-300", "gross_quantity": 600,
             "fulfilled_quantity": 0, "source_event_sequences": [5, 6]})
        out = trial(items[0], damaged, items[2], items[3])
        self.assertNotEqual(out["incumbent"]["verdict"], "RECONCILED_SYNTHETIC")
        self.assertNotEqual(out["challenger"]["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")

    def test_04_assumed_missing_offsite_archive_does_not_prove_incumbent_inferior(self):
        items = frozen_case()
        out = trial(*items, offsite_source_available=False)
        self.assertEqual(out["technical_verdict"], "CONDITIONAL_EVIDENCE_AVAILABILITY_ONLY")
        self.assertFalse(out["competent_alternative_excluded"])
        self.assertEqual(out["commercial_decision"], "NO_DEPLOY")

    def test_05_missing_incumbent_external_pin_is_not_a_real_challenger_win(self):
        items = frozen_case()
        out = trial(*items, offsite_source_pin=None)
        self.assertEqual(out["technical_verdict"], "INCOMPARABLE_EXTERNAL_INCUMBENT_PINS")
        self.assertEqual(out["commercial_decision"], "NO_DEPLOY")

    def test_06_source_modification_rejected_under_unchanged_outside_pins(self):
        items = frozen_case()
        changed = copy.deepcopy(items[0])
        changed[2]["quantity"] = 1200
        out = trial(changed, items[1], items[2], items[3])
        self.assertNotEqual(out["incumbent"]["verdict"], "RECONCILED_SYNTHETIC")
        self.assertNotEqual(out["challenger"]["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")

    def test_07_old_valid_anchor_proves_only_old_as_of_view(self):
        items = frozen_case()
        old = trial(*items)
        self.assertEqual(old["technical_verdict"], "FUNCTIONAL_PARITY_AS_OF_PINNED_SOURCE")
        self.assertFalse(old["current_obligations_verified"])
        # Later cancellation creates a different world that old externally
        # pinned evidence cannot certify without a new truthful source update.
        extended = copy.deepcopy(items[0])
        extended.append({"sequence": 7, "type": "CANCEL", "order_id": "B-200"})
        newer = trial(extended, items[1], items[2], items[3])
        self.assertNotEqual(newer["challenger"]["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")
        self.assertNotEqual(newer["incumbent"]["verdict"], "RECONCILED_SYNTHETIC")

    def test_08_missing_witness_pin_keeps_valid_conventional_outcome(self):
        items = frozen_case()
        out = trial(*items, latest_witness_anchor=None)
        self.assertEqual(out["technical_verdict"], "INCUMBENT_RECONCILES_CHALLENGER_REFUSES")
        self.assertEqual(out["commercial_decision"], "NO_DEPLOY")

    def test_09_invalid_archive_availability_flag_is_not_a_positive_arm(self):
        items = frozen_case()
        out = trial(*items, offsite_source_available=1)
        self.assertEqual(out["incumbent"]["verdict"], "INVALID_ARCHIVE_AVAILABILITY_DECLARATION")
        self.assertEqual(out["technical_verdict"], "NO_QUALIFIED_DIFFERENTIAL")

    def test_10_valid_synthetic_evidence_never_books_hypothetical_profit(self):
        out = trial(*frozen_case())
        self.assertEqual(out["real_collections_usd"], 0)
        self.assertIsNone(out["native_trailing_365_profit_usd"])
        self.assertEqual(out["complete_cost_comparison"], "UNQUALIFIED_UNKNOWN_ACTUAL_COSTS")
        self.assertFalse(out["observed_customer_acceptance"])
        self.assertFalse(out["real_supplier_reservation"])
        self.assertEqual(out["commercial_decision"], "NO_DEPLOY")


if __name__ == "__main__":
    unittest.main()
