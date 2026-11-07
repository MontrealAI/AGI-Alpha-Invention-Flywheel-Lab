"""Ephemeral-key synthetic-only adversarial proof-of-custody review.

These fixtures do not assert actual independent people, buyer consent, supplier
capacity, shipment, payments, or an authorized native-account transition.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE = Path(__file__).resolve().parents[1] / "reviews" / "continuity-restored-obligations-20261106"
sys.path.insert(0, str(BASE))
from witness_chain import make_demo_bundle, verify, digest, WitnessRefused  # noqa E402


def fixture():
    events = [
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
    snapshot = {"schema": "continuity-omega/restored-active-v2",
                "source_events_sha256": digest(events),
                "records": [{"order_id": "A-100", "gross_quantity": 1100,
                             "fulfilled_quantity": 100, "source_event_sequences": [1, 3, 4]},
                            {"order_id": "B-200", "gross_quantity": 800,
                             "fulfilled_quantity": 0, "source_event_sequences": [2]}]}
    # Generated exclusively in memory, NEVER committed or serialized.
    keys = {role: Ed25519PrivateKey.generate() for role in ("ERP", "FULFILLMENT", "AUDITOR")}
    public = {r: k.public_key().public_bytes(serialization.Encoding.Raw,
                                            serialization.PublicFormat.Raw)
              for r, k in keys.items()}
    bundle = make_demo_bundle(events, snapshot, "LAB-001", keys)
    external_latest = digest(bundle["anchor"])
    return events, snapshot, bundle, public, external_latest, keys


def run(items, *, min_sequence=None, external=None):
    events, snapshot, bundle, public, latest, _ = items
    return verify(events, snapshot, bundle, pinned_public_keys=public,
                  expected_latest_anchor_sha256=latest if external is None else external,
                  expected_min_sequence=len(events) if min_sequence is None else min_sequence)


class SyntheticWitnessTests(unittest.TestCase):
    def test_01_valid_partial_and_cancelled_absence_requires_three_roles(self):
        items = fixture()
        result = run(items)
        self.assertEqual(result["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY", result)
        self.assertEqual(result["replay_verdict"], "RECONCILED_SYNTHETIC")
        self.assertEqual(result["latest_anchor_sha256"], items[4])
        self.assertFalse(result["real_delivery"])
        self.assertFalse(result["financial_authority"])
        self.assertFalse(result["buyer_acceptance"])
        self.assertEqual(set(items[2]["receipts"][3]["signatures"]), {"ERP", "FULFILLMENT"})

    def test_02_no_external_anchor_never_success(self):
        items = fixture()
        result = run(items, external="")
        self.assertEqual(result["reason"], "EXTERNAL_LATEST_ANCHOR_REQUIRED")

    def test_03_monotonic_counter_required_outside_payload(self):
        items = fixture()
        self.assertEqual(run(items, min_sequence=7)["reason"],
                         "EXTERNAL_MONOTONIC_COUNTER_REGRESSION")

    def test_04_unsigned_fulfillment_refused(self):
        items = fixture()
        items[2]["receipts"][3]["signatures"].pop("FULFILLMENT")
        self.assertEqual(run(items)["reason"],
                         "RECEIPT_MISSING_INDEPENDENT_FULFILLMENT_WITNESS")

    def test_05_erp_signature_cannot_impersonate_fulfillment(self):
        items = fixture()
        items[2]["receipts"][3]["signatures"]["FULFILLMENT"] = items[2]["receipts"][3]["signatures"]["ERP"]
        self.assertEqual(run(items)["reason"], "WITNESS_SIGNATURE_INVALID")

    def test_06_different_pinned_role_key_rejected(self):
        items = fixture()
        wrong = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        items[3]["ERP"] = wrong
        self.assertEqual(run(items)["reason"], "WITNESS_SIGNATURE_INVALID")

    def test_07_identical_keys_cannot_be_declared_independent(self):
        items = fixture()
        items[3]["FULFILLMENT"] = items[3]["ERP"]
        self.assertEqual(run(items)["reason"], "INDEPENDENT_ROLE_KEYS_REQUIRED")

    def test_08_forged_source_even_with_self_updated_snapshot_hash_refused(self):
        items = fixture()
        items[0][3]["quantity"] = 50
        items[1]["source_events_sha256"] = digest(items[0])
        self.assertNotEqual(run(items)["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")

    def test_09_recovered_fulfillment_counter_erasure_refused(self):
        items = fixture()
        items[1]["records"][0]["fulfilled_quantity"] = 0
        self.assertEqual(run(items)["reason"], "ANCHOR_SOURCE_OR_SNAPSHOT_CHANGED")

    def test_10_snapshot_complete_forgery_and_resigning_by_wrong_auditor_refused(self):
        items = fixture()
        items[1]["records"][0]["fulfilled_quantity"] = 0
        items[2]["anchor"]["body"]["restored_snapshot_sha256"] = digest(items[1])
        items[2]["anchor"]["signature"] = items[5]["ERP"].sign(
            __import__("json").dumps(items[2]["anchor"]["body"],
                sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hex()
        self.assertEqual(run(items)["reason"], "ANCHOR_SIGNATURE_INVALID")

    def test_11_external_hold_detects_fully_resigned_fork(self):
        items = fixture()
        new_events = copy.deepcopy(items[0])
        new_events[1]["quantity"] = 801
        new_snapshot = copy.deepcopy(items[1])
        new_snapshot["source_events_sha256"] = digest(new_events)
        new_snapshot["records"][1]["gross_quantity"] = 801
        newly_signed = make_demo_bundle(new_events, new_snapshot, "LAB-001", items[5])
        items[0][:] = new_events
        items[1].clear(); items[1].update(new_snapshot)
        items[2].clear(); items[2].update(newly_signed)
        self.assertEqual(run(items)["reason"], "EXTERNAL_LATEST_ANCHOR_MISMATCH")

    def test_12_cross_case_receipt_replay_refused(self):
        items = fixture()
        items[2]["case_id"] = "OTHER-001"
        self.assertEqual(run(items)["reason"], "CHAIN_EVENT_OR_PREDECESSOR_CHANGED")

    def test_13_missing_or_reordered_receipt_refused(self):
        for mutate in (lambda a: a.pop(), lambda a: a.reverse()):
            items = fixture()
            mutate(items[2]["receipts"])
            self.assertNotEqual(run(items)["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")

    def test_14_fabricated_fulfillment_proof_on_acceptance_refused(self):
        items = fixture()
        items[2]["receipts"][0]["signatures"]["FULFILLMENT"] = "0" * 128
        self.assertEqual(run(items)["reason"],
                         "RECEIPT_MISSING_INDEPENDENT_FULFILLMENT_WITNESS")

    def test_15_truncated_source_and_history_refused(self):
        items = fixture()
        del items[0][4:]
        del items[2]["receipts"][4:]
        self.assertEqual(run(items)["reason"], "ANCHOR_SOURCE_OR_SNAPSHOT_CHANGED")

    def test_16_bad_restored_v1_gross_only_refused(self):
        items = fixture()
        items[1]["records"] = [{"order_id": "A-100", "quantity": 1100},
                                {"order_id": "B-200", "quantity": 800}]
        self.assertEqual(run(items)["reason"], "ANCHOR_SOURCE_OR_SNAPSHOT_CHANGED")

    def test_17_event_witnesses_do_not_override_bad_replay(self):
        items = fixture()
        items[0][3]["quantity"] = 1101  # independently invalid overfulfillment
        items[1]["source_events_sha256"] = digest(items[0])
        new_bundle = make_demo_bundle(items[0], items[1], "LAB-001", items[5])
        items[2].clear(); items[2].update(new_bundle)
        result = run(items, external=digest(new_bundle["anchor"]))
        self.assertEqual(result["reason"], "INDEPENDENT_REPLAY_OR_RESTORATION_DISCREPANCY")

    def test_18_no_private_keys_exported_in_bundle_or_result(self):
        items = fixture()
        import json
        blob = json.dumps(items[2])
        self.assertEqual(set(items[2]), {"schema", "case_id", "receipts", "anchor"})
        self.assertNotIn("private_key", blob)
        self.assertNotIn("secret", blob)
        self.assertNotIn("private_key", json.dumps(run(items)))

    def test_19_boolean_minimum_counter_fails_closed(self):
        items = fixture()
        self.assertEqual(run(items, min_sequence=True)["reason"],
                         "EXTERNAL_MIN_SEQUENCE_REQUIRED")

    def test_21_signed_boolean_receipt_counter_is_not_canonical_integer(self):
        items = fixture()
        # A signer that emits JSON true instead of 1 cannot exploit Python's
        # True == 1 equality. Rebuild every later chain link honestly so this
        # is an isolated canonical-shape test, not a hash-chain break.
        from witness_chain import _encode
        prev = "0" * 64
        for i, (event, receipt) in enumerate(zip(items[0], items[2]["receipts"]), 1):
            body = receipt["body"]
            body["sequence"] = True if i == 1 else i
            body["previous_receipt_sha256"] = prev
            for role in receipt["signatures"]:
                receipt["signatures"][role] = items[5][role].sign(_encode(body)).hex()
            prev = digest(receipt)
        anchor_body = items[2]["anchor"]["body"]
        anchor_body["head_receipt_sha256"] = prev
        items[2]["anchor"]["signature"] = items[5]["AUDITOR"].sign(_encode(anchor_body)).hex()
        result = run(items, external=digest(items[2]["anchor"]))
        self.assertEqual(result["reason"], "CHAIN_EVENT_OR_PREDECESSOR_CHANGED")

    def test_22_signed_float_anchor_counter_is_not_canonical_integer(self):
        items = fixture()
        from witness_chain import _encode
        body = items[2]["anchor"]["body"]
        body["last_sequence"] = float(len(items[0]))
        items[2]["anchor"]["signature"] = items[5]["AUDITOR"].sign(_encode(body)).hex()
        result = run(items, external=digest(items[2]["anchor"]))
        self.assertEqual(result["reason"], "ANCHOR_SOURCE_OR_SNAPSHOT_CHANGED")

    def test_20_unchanged_inputs_and_identity_after_verification(self):
        items = fixture()
        old = copy.deepcopy(items[:5])
        self.assertEqual(run(items)["verdict"], "VERIFIED_SYNTHETIC_CUSTODY_ONLY")
        self.assertEqual(items[:5], old)


    def test_23_rejected_external_anchor_cannot_be_reused_as_verified_latest(self):
        items = fixture()
        wrong = "0" * 64 if items[4] != "0" * 64 else "1" * 64
        result = run(items, external=wrong)
        self.assertEqual(result["reason"], "EXTERNAL_LATEST_ANCHOR_MISMATCH")
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIsNone(result["latest_anchor_sha256"])

    def test_24_signed_but_replay_invalid_chain_cannot_issue_verified_latest(self):
        items = fixture()
        items[0][3]["quantity"] = 1101  # Must fail independent overfulfillment.
        items[1]["source_events_sha256"] = digest(items[0])
        updated = make_demo_bundle(items[0], items[1], "LAB-001", items[5])
        items[2].clear()
        items[2].update(updated)
        result = run(items, external=digest(updated["anchor"]))
        self.assertEqual(result["reason"], "INDEPENDENT_REPLAY_OR_RESTORATION_DISCREPANCY")
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIsNone(result["latest_anchor_sha256"])


if __name__ == "__main__":
    unittest.main()
