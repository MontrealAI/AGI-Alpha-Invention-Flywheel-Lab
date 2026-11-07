"""Eight new fixed constructive conventional-control cases, preregistered first."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "reviews" / "continuity-restored-obligations-20261106"
sys.path.insert(0, str(BASE))

from conventional_rebuilder import restore  # noqa: E402
from reference_oracle import reconcile, digest  # noqa: E402
from test_continuity_strong_incumbent_parity import frozen_case_source, frozen_case_snapshot  # noqa: E402


def run(source, pin="AUTO_TEST_FROZEN"):
    # Test-side hashing models an independently retained expected digest.
    # It is NOT proof of real external offsite custody.
    independent_pin = digest(frozen_case_source()) if pin == "AUTO_TEST_FROZEN" else pin
    return restore(source, independently_held_offsite_source_sha256=independent_pin)


class ConventionalConstructiveControl(unittest.TestCase):
    def test_01_construct_and_independently_reconcile_remaining_orders(self):
        source = frozen_case_source()
        got = run(source)
        self.assertEqual(got["verdict"], "CONVENTIONAL_OFFSITE_REPLAY_SYNTHETIC", got)
        expected = frozen_case_snapshot()
        self.assertEqual(got["restored_snapshot"], expected)
        check = reconcile(source, got["restored_snapshot"],
                          expected_source_sha256=digest(source),
                          expected_restored_sha256=digest(expected))
        self.assertEqual(check["verdict"], "RECONCILED_SYNTHETIC", check)

    def test_02_changed_event_is_refused_against_preexisting_offsite_pin(self):
        source = frozen_case_source()
        source[2]["quantity"] = 1200
        got = run(source)
        self.assertEqual(got["verdict"], "REFUSED")
        self.assertEqual(got["reason"], "OFFSITE_SOURCE_PIN_MISMATCH")
        self.assertIsNone(got["restored_snapshot"])

    def test_03_missing_independent_source_identity_is_not_silent_repair(self):
        got = run(frozen_case_source(), pin=None)
        self.assertEqual(got["verdict"], "REFUSED")
        self.assertEqual(got["reason"], "EXTERNAL_OFFSITE_SOURCE_PIN_REQUIRED")

    def test_04_cancelled_order_not_resurrected(self):
        got = run(frozen_case_source())
        self.assertEqual([x["order_id"] for x in got["restored_snapshot"]["records"]],
                         ["A-100", "B-200"])
        self.assertNotIn("C-300", [x["order_id"] for x in got["restored_snapshot"]["records"]])

    def test_05_fully_fulfilled_order_excluded_with_history_preserved(self):
        source = frozen_case_source()
        source.append({"sequence": 7, "type": "FULFILL", "order_id": "A-100", "quantity": 1000})
        got = run(source, pin=digest(source))
        self.assertEqual(got["verdict"], "CONVENTIONAL_OFFSITE_REPLAY_SYNTHETIC", got)
        self.assertEqual([x["order_id"] for x in got["restored_snapshot"]["records"]], ["B-200"])
        self.assertEqual(got["restored_snapshot"]["source_events_sha256"], digest(source))

    def test_06_amendment_cannot_erase_prior_fulfillment(self):
        source = frozen_case_source()
        source.append({"sequence": 7, "type": "AMEND", "order_id": "A-100", "quantity": 99})
        got = run(source, pin=digest(source))
        self.assertEqual(got["verdict"], "REFUSED")
        self.assertEqual(got["reason"], "AMENDMENT_ERASES_FULFILLMENT")

    def test_07_noninteger_quantity_and_sequence_gap_fail_closed(self):
        for changed in (True, -1, 0, 1.5):
            source = frozen_case_source()
            source[3]["quantity"] = changed
            got = run(source, pin=digest(source))
            self.assertEqual(got["verdict"], "REFUSED", (changed, got))
        source = frozen_case_source()
        source[3]["sequence"] = 9
        got = run(source, pin=digest(source))
        self.assertEqual(got["verdict"], "REFUSED")
        self.assertEqual(got["reason"], "SOURCE_EVENT_SEQUENCE_INVALID")

    def test_08_updated_source_pin_changes_result_without_currentness_claim(self):
        source = frozen_case_source()
        source.append({"sequence": 7, "type": "CANCEL", "order_id": "B-200"})
        got = run(source, pin=digest(source))
        self.assertEqual(got["verdict"], "CONVENTIONAL_OFFSITE_REPLAY_SYNTHETIC", got)
        self.assertEqual([x["order_id"] for x in got["restored_snapshot"]["records"]], ["A-100"])
        self.assertFalse(got["currentness_verified"])
        self.assertFalse(got["real_archive_custody"])
        self.assertIsNone(got["business_profit_usd"])


if __name__ == "__main__":
    unittest.main()
