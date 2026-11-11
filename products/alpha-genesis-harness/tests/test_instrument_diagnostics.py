"""Actionable diagnostics for malformed expressions and instrument roots."""
import copy
import unittest

from bridge.instruments import evaluate


class InstrumentDiagnosticTests(unittest.TestCase):
    def test_non_object_root_reports_type_without_echoing_contents(self):
        for spec, expected_kind in ((None, "null"), (True, "boolean"), (27, "number"),
                                    (2.5, "number"), ("private-spec-value", "string"),
                                    (["private-spec-value"], "array")):
            with self.subTest(kind=type(spec).__name__), self.assertRaises(ValueError) as caught:
                evaluate(spec, {"secret": "private-input-value"})
            message = str(caught.exception)
            self.assertTrue(message.startswith("Unsupported instrument specification."))
            self.assertIn("Expected a JSON object at the root", message)
            self.assertIn("received " + expected_kind, message)
            self.assertNotIn("private-spec-value", message)
            self.assertNotIn("private-input-value", message)
            self.assertNotIn("Unsupported top-level keys", message)

    def test_misplaced_calculations_are_rejected_and_named_without_values(self):
        spec = {"inputs": ["x"], "outputs": {"result": {"op": "add", "args": [
            {"op": "mul", "args": [{"field": "x"}, 2]}, 1]}},
            "z_status": {"op": "gte", "args": [{"field": "x"}, 0]},
            "a_note": "private-spec-value"}
        original = copy.deepcopy(spec)
        with self.assertRaises(ValueError) as caught:
            evaluate(spec, {"x": 3, "secret": "private-input-value"})
        message = str(caught.exception)
        self.assertTrue(message.startswith("Unsupported instrument specification."))
        self.assertIn('Unsupported top-level keys: ["a_note", "z_status"]', message)
        self.assertIn('Allowed top-level keys: ["bindings", "conditions", "description", "inputs", "limitations", "name", "outputs"]', message)
        self.assertIn('Named calculations belong inside the "outputs" object', message)
        self.assertNotIn("private-spec-value", message)
        self.assertNotIn("private-input-value", message)
        self.assertEqual(spec, original)  # Diagnostics never repair model artifacts.

        # Explicit caller repair preserves supported nested expressions.
        spec["outputs"]["status"] = spec.pop("z_status")
        spec.pop("a_note")
        result = evaluate(spec, {"x": 3})
        self.assertEqual(result["output"], {"result": 7, "status": True})
        self.assertEqual(result["operations"], 8)
        with self.assertRaisesRegex(ValueError, "bound exhausted"):
            evaluate(spec, {"x": 3}, max_operations=7)

    def test_non_string_root_key_stays_rejected_without_rendering_object(self):
        class PrivateKey:
            def __str__(self):
                raise AssertionError("Diagnostic must not stringify arbitrary objects")
        spec = {"inputs": [], "outputs": {"result": 1}, PrivateKey(): "private-value"}
        with self.assertRaises(ValueError) as caught:
            evaluate(spec, {})
        self.assertIn("<non-string key>", str(caught.exception))
        self.assertNotIn("private-value", str(caught.exception))

    def test_unknown_key_diagnostic_escapes_controls_and_bounds_count_and_length(self):
        spec = {"inputs": [], "outputs": {"result": 1}}
        spec.update({f"key_{i:02d}\n" + "x" * 1000: "private-value" for i in range(12)})
        original = copy.deepcopy(spec)
        with self.assertRaises(ValueError) as caught:
            evaluate(spec, {})
        message = str(caught.exception)
        self.assertTrue(message.startswith("Unsupported instrument specification."))
        self.assertIn(r"key_00\n", message)
        self.assertNotIn("\n", message)
        self.assertIn("...[truncated]", message)
        self.assertIn("4 additional key names omitted", message)
        self.assertNotIn("key_08", message)
        self.assertNotIn("private-value", message)
        self.assertLess(len(message), 1200)
        self.assertEqual(spec, original)

    def test_nested_literal_object_stays_rejected_with_actionable_location(self):
        for wrapper in ("literal", "value", "const"):
            expression = {"op": "mul", "args": [{"field": "x"}, {wrapper: 2}]}
            spec = {"inputs": ["x"], "outputs": {"result": expression}}
            with self.subTest(wrapper=wrapper), self.assertRaises(ValueError) as caught:
                evaluate(spec, {"x": 3})
            self.assertIn('$.outputs["result"].args[1]', str(caught.exception))
            self.assertIn("raw JSON value", str(caught.exception))
            # The model must supply the repair; the interpreter never rewrites it.
            self.assertEqual(expression["args"][1], {wrapper: 2})
            expression["args"][1] = 2
            result = evaluate(spec, {"x": 3})
            self.assertEqual(result["output"], {"result": 6})
            self.assertEqual(result["operations"], 3)

    def test_extra_expression_keys_are_not_silently_accepted(self):
        spec = {"inputs": ["x"], "outputs": {"result": {
            "op": "add", "args": [{"field": "x"}, 7], "unexpected": True}}}
        with self.assertRaises(ValueError) as caught:
            evaluate(spec, {"x": 3})
        self.assertIn('$.outputs["result"]', str(caught.exception))
        self.assertIn("unexpected", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
