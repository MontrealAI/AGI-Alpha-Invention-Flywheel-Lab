"""Independent black-box tests for the non-operating restoration reference oracle.

This green review suite does NOT reclassify the intentionally red source-level
tests or claim correctness of CONTINUITY Omega owner implementation.
All inputs and buyer/order names are deliberately synthetic.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


PATH = (Path(__file__).resolve().parents[1] / "reviews" /
        "continuity-restored-obligations-20261106" / "reference_oracle.py")
SPEC = importlib.util.spec_from_file_location("continuity_restore_reference", PATH)
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)


def example():
    spec = "a" * 64
    events = [
        {"sequence": 1, "type": "ACCEPT", "order_id": "A-100",
         "quantity": 1000, "product": "LABEL", "spec_sha256": spec,
         "deadline_hours": 48},
        {"sequence": 2, "type": "ACCEPT", "order_id": "B-200",
         "quantity": 800, "product": "LABEL", "spec_sha256": spec,
         "deadline_hours": 48},
        {"sequence": 3, "type": "ACCEPT", "order_id": "C-300",
         "quantity": 600, "product": "LABEL", "spec_sha256": spec,
         "deadline_hours": 48},
        {"sequence": 4, "type": "AMEND", "order_id": "A-100", "quantity": 1100},
        {"sequence": 5, "type": "FULFILL", "order_id": "A-100", "quantity": 100},
        {"sequence": 6, "type": "CANCEL", "order_id": "C-300"},
    ]
    snapshot = {
        "schema": reference.SOURCE_SCHEMA,
        "source_events_sha256": reference.digest(events),
        "records": [
            {"order_id": "A-100", "gross_quantity": 1100,
             "fulfilled_quantity": 100, "source_event_sequences": [1, 4, 5]},
            {"order_id": "B-200", "gross_quantity": 800,
             "fulfilled_quantity": 0, "source_event_sequences": [2]},
        ],
    }
    return events, snapshot


def evaluate(events, snapshot):
    return reference.reconcile(
        events, snapshot, expected_source_sha256=reference.digest(events),
        expected_restored_sha256=reference.digest(snapshot),
    )


class SyntheticObligationReferenceTests(unittest.TestCase):
    def test_matched_partial_fulfillment_and_cancelled_absence(self):
        events, snapshot = example()
        result = evaluate(events, snapshot)
        self.assertEqual(result["verdict"], "RECONCILED_SYNTHETIC", result)
        self.assertTrue(result["complete"])
        self.assertIn("SYNTHETIC_ONLY", result["scope"])
        self.assertNotIn("AUTHENTICATED", result["authority"])

    def test_missing_both_caller_pins_never_claims_verified(self):
        events, snapshot = example()
        result = reference.reconcile(events, snapshot)
        self.assertEqual(result["verdict"], "UNVERIFIABLE")
        self.assertIn("BOTH_EXTERNAL_CALLER_PINS_REQUIRED", result["findings"])

    def test_gross_only_v1_cannot_prove_fulfillment(self):
        events, snapshot = example()
        snapshot["records"] = [
            {"order_id": "A-100", "quantity": 1100},
            {"order_id": "B-200", "quantity": 800},
        ]
        result = evaluate(events, snapshot)
        self.assertEqual(result["verdict"], "INVALID")
        self.assertIn("RESTORED_ROW_SHAPE_INVALID", result["findings"])

    def test_missing_active_is_a_discrepancy(self):
        events, snapshot = example()
        snapshot["records"].pop()
        result = evaluate(events, snapshot)
        self.assertIn("B-200:ACTIVE_ORDER_MISSING", result["findings"])

    def test_canceled_order_reappearance_is_a_discrepancy(self):
        events, snapshot = example()
        snapshot["records"].append({
            "order_id": "C-300", "gross_quantity": 600,
            "fulfilled_quantity": 0, "source_event_sequences": [3, 6],
        })
        self.assertIn("C-300:CANCELLED_ORDER_PRESENT",
                      evaluate(events, snapshot)["findings"])

    def test_fully_fulfilled_order_absence_is_legitimate(self):
        events, snapshot = example()
        events.append({
            "sequence": 7, "type": "FULFILL", "order_id": "A-100", "quantity": 1000,
        })
        snapshot["source_events_sha256"] = reference.digest(events)
        snapshot["records"] = [r for r in snapshot["records"]
                               if r["order_id"] != "A-100"]
        self.assertEqual(evaluate(events, snapshot)["verdict"], "RECONCILED_SYNTHETIC")

    def test_fully_fulfilled_order_reappearance_is_detected(self):
        events, snapshot = example()
        events.append({
            "sequence": 7, "type": "FULFILL", "order_id": "A-100", "quantity": 1000,
        })
        snapshot["source_events_sha256"] = reference.digest(events)
        self.assertIn("A-100:COMPLETED_ORDER_PRESENT",
                      evaluate(events, snapshot)["findings"])

    def test_fulfillment_counter_reset_is_detected(self):
        events, snapshot = example()
        snapshot["records"][0]["fulfilled_quantity"] = 0
        self.assertIn("A-100:FULFILLED_QUANTITY_MISMATCH",
                      evaluate(events, snapshot)["findings"])

    def test_gross_quantity_rewrite_is_detected(self):
        events, snapshot = example()
        snapshot["records"][0]["gross_quantity"] = 1000
        self.assertIn("A-100:GROSS_QUANTITY_MISMATCH",
                      evaluate(events, snapshot)["findings"])

    def test_source_sequences_replay_is_detected(self):
        events, snapshot = example()
        snapshot["records"][0]["source_event_sequences"] = [1, 4]
        self.assertIn("A-100:SOURCE_EVENT_SEQUENCES_MISMATCH",
                      evaluate(events, snapshot)["findings"])

    def test_external_snapshot_pin_rejects_resealed_counter(self):
        events, snapshot = example()
        old_pin = reference.digest(snapshot)
        snapshot["records"][0]["fulfilled_quantity"] = 0
        result = reference.reconcile(
            events, snapshot, expected_source_sha256=reference.digest(events),
            expected_restored_sha256=old_pin,
        )
        self.assertIn("EXTERNAL_REFERENCE_CHANGED", result["findings"])
        self.assertFalse(result["complete"])

    def test_external_source_pin_rejects_resealed_case(self):
        events, snapshot = example()
        old_pin = reference.digest(events)
        events[4]["quantity"] = 50
        snapshot["source_events_sha256"] = reference.digest(events)
        result = reference.reconcile(
            events, snapshot, expected_source_sha256=old_pin,
            expected_restored_sha256=reference.digest(snapshot),
        )
        self.assertIn("EXTERNAL_REFERENCE_CHANGED", result["findings"])

    def test_incorrect_restored_source_reference_is_detected(self):
        events, snapshot = example()
        snapshot["source_events_sha256"] = "0" * 64
        self.assertIn("RESTORED_REFERENCES_DIFFERENT_SOURCE",
                      evaluate(events, snapshot)["findings"])

    def test_unsupported_order_is_not_silently_accepted(self):
        events, snapshot = example()
        snapshot["records"].append({
            "order_id": "X-999", "gross_quantity": 300,
            "fulfilled_quantity": 0, "source_event_sequences": [7],
        })
        self.assertIn("X-999:UNSUPPORTED_ORDER_PRESENT",
                      evaluate(events, snapshot)["findings"])

    def test_duplicate_snapshot_order_fails_closed(self):
        events, snapshot = example()
        snapshot["records"].append(copy.deepcopy(snapshot["records"][0]))
        result = evaluate(events, snapshot)
        self.assertEqual(result["verdict"], "INVALID")
        self.assertIn("RESTORED_DUPLICATE_ORDER", result["findings"])

    def test_boolean_and_negative_quantities_fail_closed(self):
        for value in (True, -1, 1101, "100"):
            with self.subTest(value=value):
                events, snapshot = example()
                snapshot["records"][0]["fulfilled_quantity"] = value
                self.assertEqual(evaluate(events, snapshot)["verdict"], "INVALID")

    def test_changed_event_sequence_fails_closed(self):
        events, snapshot = example()
        events[4]["sequence"] = 9
        result = evaluate(events, snapshot)
        self.assertEqual(result["verdict"], "INVALID")
        self.assertIn("SOURCE_SEQUENCE_CHANGED", result["findings"])

    def test_duplicate_accept_fails_closed(self):
        events, snapshot = example()
        events.append({
            "sequence": 7, "type": "ACCEPT", "order_id": "A-100",
            "quantity": 1, "product": "LABEL", "spec_sha256": "a" * 64,
            "deadline_hours": 48,
        })
        self.assertIn("SOURCE_DUPLICATE_ACCEPT",
                      evaluate(events, snapshot)["findings"])

    def test_overfulfillment_fails_closed(self):
        events, snapshot = example()
        events.append({
            "sequence": 7, "type": "FULFILL", "order_id": "B-200",
            "quantity": 801,
        })
        self.assertIn("SOURCE_OVERFULFILL",
                      evaluate(events, snapshot)["findings"])

    def test_reinstatement_is_not_silently_supported(self):
        events, snapshot = example()
        events.append({
            "sequence": 7, "type": "AMEND", "order_id": "C-300",
            "quantity": 601,
        })
        self.assertIn("SOURCE_INACTIVE_TARGET",
                      evaluate(events, snapshot)["findings"])

    def test_noncanonical_floats_refused(self):
        events, snapshot = example()
        events[0]["quantity"] = float("nan")
        result = reference.reconcile(
            events, snapshot, expected_source_sha256="a" * 64,
            expected_restored_sha256=reference.digest(snapshot),
        )
        self.assertEqual(result["verdict"], "INVALID")

    def test_no_mutation_on_reconciliation(self):
        events, snapshot = example()
        old_events, old_snapshot = copy.deepcopy(events), copy.deepcopy(snapshot)
        evaluate(events, snapshot)
        self.assertEqual(events, old_events)
        self.assertEqual(snapshot, old_snapshot)


if __name__ == "__main__":
    unittest.main()
