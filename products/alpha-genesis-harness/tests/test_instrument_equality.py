# SPDX-License-Identifier: Apache-2.0
"""JSON equality regressions and parity with the shipped browser evaluator."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.instruments import evaluate
from bridge.workflows import equivalent


SPEC = {"name": "JSON equality", "inputs": ["left", "right"],
        "outputs": {"equal": {"op": "eq", "args": [{"field": "left"}, {"field": "right"}]}}}


def cases():
    rows = []
    for boolean, number in [(True, 1), (True, 1.0), (False, 0), (False, 0.0)]:
        for wrap in [lambda value: value, lambda value: [value], lambda value: {"value": value},
                     lambda value: {"rows": [{"value": [value]}]}]:
            rows.extend([(wrap(boolean), wrap(number), False), (wrap(number), wrap(boolean), False)])
    rows.extend([
        (1, 1.0, True), (0, -0.0, True), (1.25, 1.25, True), (1.25, 1.5, False),
        ([1, 2.0], [1.0, 2], True), ([], [], True), ({}, {}, True),
        ({"rows": [{"x": 3, "enabled": True}], "label": None},
         {"label": None, "rows": [{"enabled": True, "x": 3.0}]}, True),
        ([True, False, None, "1"], [True, False, None, "1"], True),
        ([1, 2], [2, 1], False), ([1], [1, 2], False), ([], {}, False),
        ({"x": 1}, {"y": 1}, False), ({"x": 1}, {"x": 1, "y": None}, False),
        ({"x": [1]}, {"x": 1}, False), ({"x": None}, {}, False),
        ("1", 1, False), (None, False, False), (None, None, True),
    ])
    return rows


class InstrumentEqualityTests(unittest.TestCase):
    def test_recursive_equality_preserves_json_types_and_numeric_equivalence(self):
        for left, right, expected in cases():
            with self.subTest(left=left, right=right):
                actual = evaluate(SPEC, {"left": left, "right": right})["output"]["equal"]
                self.assertIs(actual, expected)
                self.assertIs(equivalent(left, right), expected)

    @unittest.skipUnless(shutil.which("node"), "Node is required for browser evaluator parity")
    def test_same_cases_match_shipped_javascript_evaluator(self):
        program = r'''
const fs = require('node:fs');
const engine = require('./app/engine.js');
const {spec, cases} = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(([left, right]) => {
  const result = engine.executeInstrument(spec, {left, right});
  if (result.verdict !== 'PASSED IN SCOPE') throw new Error(JSON.stringify(result));
  return result.outputs.equal;
});
process.stdout.write(JSON.stringify(results));
'''
        rows = cases()
        process = subprocess.run([shutil.which("node"), "-e", program], cwd=PRODUCT,
                                 input=json.dumps({"spec": SPEC, "cases": rows}),
                                 capture_output=True, text=True, check=True)
        actual = json.loads(process.stdout)
        self.assertEqual(actual, [expected for _, _, expected in rows])
        self.assertEqual(actual, [evaluate(SPEC, {"left": left, "right": right})["output"]["equal"]
                                  for left, right, _ in rows])


if __name__ == "__main__":
    unittest.main()
