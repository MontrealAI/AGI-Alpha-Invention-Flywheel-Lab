"""Adversarial checks of the copied policy's recovery-only source boundary."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from portfolio071 import recovery_controller as controller


class RecoveryControllerBoundaryTests(unittest.TestCase):
    def substitute_controller_text(self, text):
        original = Path.read_bytes
        target = Path(controller.__file__)

        def read(path):
            return text.encode() if path == target else original(path)

        return patch.object(Path, "read_bytes", read)

    def test_exact_policy_is_accepted(self):
        result = controller.validate_controller()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["operation_markers"], 18)
        self.assertEqual(result["original_policy_sha256"], controller.ORIGINAL_POLICY_SHA256)

    def test_cost_timing_horizon_and_refusal_changes_are_rejected(self):
        source = Path(controller.__file__).read_text()
        replacements = (
            ("amount_usd = COSTS_USD[cost_name]", "amount_usd = 0 * COSTS_USD[cost_name]"),
            ("day == 180", "day == 181"),
            ("horizon_hour = horizon_days * 24", "horizon_hour = horizon_days * 25"),
            ("state['available'] < needed", "state['available'] < 0"),
        )
        for old, new in replacements:
            with self.subTest(old=old):
                self.assertIn(old, source)
                altered = source.replace(old, new, 1)
                with self.substitute_controller_text(altered):
                    with self.assertRaisesRegex(ValueError, "RECOVERY_ECONOMIC_POLICY_AST_DIFFERS"):
                        controller.validate_controller()

    def test_missing_operation_marker_is_rejected(self):
        source = Path(controller.__file__).read_text()
        line = next(line for line in source.splitlines(keepends=True)
                    if line.lstrip().startswith("account.mark('stable-original-line-"))
        with self.substitute_controller_text(source.replace(line, "", 1)):
            with self.assertRaisesRegex(ValueError, "RECOVERY_ECONOMIC_POLICY_AST_DIFFERS"):
                controller.validate_controller()

    def test_helper_rebinding_is_rejected(self):
        with patch.object(controller, "commercial_choice", lambda *args: None):
            with self.assertRaisesRegex(ValueError, "ORIGINAL_ECONOMIC_HELPER_BINDING_CHANGED"):
                controller.validate_controller()

    def test_output_writer_rebinding_is_rejected(self):
        with patch.object(controller, "_write_new", lambda *args: "forged"):
            with self.assertRaisesRegex(ValueError, "RECOVERY_OUTPUT_WRITER_BINDING_CHANGED"):
                controller.validate_controller()


if __name__ == "__main__":
    unittest.main()
