# SPDX-License-Identifier: Apache-2.0
"""Independent adversarial JSON equality parity, separate from repair fixtures."""
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.instruments import evaluate

SPEC = {"name": "Independent structural equality", "inputs": ["left", "right"],
        "outputs": {"same": {"op": "eq", "args": [{"field": "left"}, {"field": "right"}]}}}
VALUES = [None, False, True, 0, 1, 1.0, -0.0, "0", "", [], {}, [False], [0], [True], [1],
          {"value": False}, {"value": 0}, {"value": [1, {"b": True}]}, {"value": [1.0, {"b": 1}]}]


class IndependentInstrumentEqualityTests(unittest.TestCase):
    def test_nested_false_acceptance_and_structural_boundaries(self):
        checks = [
            ([{"approved": [False]}], [{"approved": [0]}], False),
            ({"checks": [[True], {"status": False}]}, {"checks": [[1], {"status": 0}]}, False),
            ({"checks": [[1.0], {"status": False}]}, {"checks": [[1], {"status": False}]}, True),
            ({"a": 1, "b": [2.0]}, {"b": [2], "a": 1.0}, True),
            ({"a": []}, {"a": {}}, False),
            ({"a": None}, {}, False),
            ([0, False], [False, 0], False),
            (["é"], ["e\u0301"], False),
        ]
        for left, right, expected in checks:
            with self.subTest(left=left, right=right):
                self.assertIs(evaluate(SPEC, {"left": left, "right": right})["output"]["same"], expected)

    @unittest.skipUnless(shutil.which("node"), "Node required for independent cross-runtime parity")
    def test_all_361_json_type_pairs_match_actual_browser_execution(self):
        cases = [{"left": a, "right": b} for a, b in itertools.product(VALUES, repeat=2)]
        program = r'''
const fs = require('node:fs');
const engine = require(process.argv[1]);
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const outcomes = payload.cases.map(input => {
  const result = engine.executeInstrument(payload.spec, input);
  if (result.verdict !== 'PASSED IN SCOPE') throw new Error(JSON.stringify(result));
  return result.outputs.same;
});
process.stdout.write(JSON.stringify(outcomes));
'''
        result = subprocess.run([shutil.which("node"), "-e", program, str(PRODUCT / "app/engine.js")],
                                input=json.dumps({"spec": SPEC, "cases": cases}), text=True,
                                capture_output=True, check=True, timeout=20)
        browser = json.loads(result.stdout)
        self.assertEqual(len(browser), 361)
        for index, inputs in enumerate(cases):
            with self.subTest(index=index, inputs=inputs):
                self.assertIs(evaluate(SPEC, inputs)["output"]["same"], browser[index])


if __name__ == "__main__":
    unittest.main()
