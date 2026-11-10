"""Regression for the malformed literal observed in hosted local trial 3f4e1785."""
import unittest

from bridge.instruments import evaluate


class InstrumentDiagnosticTests(unittest.TestCase):
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
