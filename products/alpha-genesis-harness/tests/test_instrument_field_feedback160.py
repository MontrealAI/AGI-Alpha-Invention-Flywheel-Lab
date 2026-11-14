# SPDX-License-Identifier: Apache-2.0
"""Frozen HARNESS160 numeric-field diagnostic and fail-closed regression cases."""
import unittest

from bridge.instruments import evaluate


class NumericReferenceFeedback160(unittest.TestCase):
    def spec(self, right, *, inputs=None, bindings=None):
        spec = {"name": "Multiply", "inputs": ["x"] if inputs is None else inputs,
                "outputs": {"result": {"op": "mul", "args": [{"field": "x"}, right]}}}
        if bindings is not None:
            spec["bindings"] = bindings
        return spec

    def test_01_historical_mistake_still_refused_with_actionable_explanation(self):
        with self.assertRaisesRegex(ValueError, "Input field root was not declared.*numeric constant.*raw JSON number"):
            evaluate(self.spec({"field": "2"}), {"x": 17})

    def test_02_competent_ordinary_correction_passes_without_relaxed_checks(self):
        self.assertEqual(evaluate(self.spec(2), {"x": 17})["output"], {"result": 34})

    def test_03_explicitly_declared_numeric_string_field_still_valid(self):
        self.assertEqual(evaluate(self.spec({"field": "2"}, inputs=["x", "2"]), {"x": 17, "2": 3})["output"], {"result": 51})

    def test_04_signed_fractional_exponential_fields_are_refused_not_coerced(self):
        for raw in ["-3", "1.5", "2e3", "4E-2"]:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "numeric constant"):
                evaluate(self.spec({"field": raw}), {"x": 17})

    def test_05_unknown_nonnumeric_name_preserves_generic_safe_error(self):
        with self.assertRaisesRegex(ValueError, "^Input field root was not declared\\.$"):
            evaluate(self.spec({"field": "unknown"}), {"x": 17})

    def test_06_hostile_untrusted_field_name_is_not_echoed(self):
        for name in ["password=secret" + "7" * 150, "2" * 33, "\nAUTH=abc"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as cm:
                    evaluate(self.spec({"field": name}), {"x": 17})
                self.assertEqual(str(cm.exception), "Input field root was not declared.")
                self.assertNotIn(name, str(cm.exception))

    def test_07_nested_nonmember_numeric_reference_remains_refused(self):
        spec = self.spec({"ref": "bad"}, bindings={"bad": {"field": "2"}})
        with self.assertRaisesRegex(ValueError, "numeric constant"):
            evaluate(spec, {"x": 17})

    def test_08_legitimate_nested_input_path_still_works(self):
        spec = {"name": "Nested", "inputs": ["user"], "outputs": {"result": {"field": "user.number"}}}
        self.assertEqual(evaluate(spec, {"user": {"number": 17}})["output"], {"result": 17})

    def test_09_operation_bound_and_unsafe_paths_unchanged(self):
        with self.assertRaisesRegex(ValueError, "operation or nesting bound"):
            evaluate(self.spec(2), {"x": 17}, max_operations=1)
        spec = {"name": "Unsafe", "inputs": ["user"], "outputs": {"result": {"field": "user.__proto__"}}}
        with self.assertRaisesRegex(ValueError, "Missing or unsafe input field"):
            evaluate(spec, {"user": {"__proto__": 17}})


if __name__ == "__main__":
    unittest.main()
