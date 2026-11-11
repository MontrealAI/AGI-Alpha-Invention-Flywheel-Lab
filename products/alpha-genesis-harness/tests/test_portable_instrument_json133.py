# SPDX-License-Identifier: Apache-2.0
"""Frozen HARNESS133 CLI regressions for unambiguous exported JSON instrument bytes."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PRODUCT = Path(__file__).resolve().parents[1]
RUNNER = PRODUCT / "bridge" / "instruments.py"
VALID_SPEC = '{"inputs":["x"],"outputs":{"value":{"field":"x"}}}'


class PortableInstrumentJSON133Tests(unittest.TestCase):
    def run_runner(self, raw_spec, raw_input):
        with tempfile.TemporaryDirectory(prefix="harness133-") as directory:
            root = Path(directory)
            spec_path, input_path = root / "instrument.json", root / "input.json"
            spec_path.write_text(raw_spec, encoding="utf-8")
            input_path.write_text(raw_input, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-B", str(RUNNER), str(spec_path), str(input_path)],
                capture_output=True, text=True, timeout=15, cwd=root, check=False,
            )

    def assert_refused(self, raw_spec, raw_input):
        result = self.run_runner(raw_spec, raw_input)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Invalid JSON", result.stderr)
        self.assertNotIn("PRIVATE_MARKER_133", result.stderr)

    def test_duplicate_top_level_output_contract_is_refused(self):
        self.assert_refused(
            '{"inputs":["x"],"outputs":{"value":1},"outputs":{"value":2}}',
            '{"x":7}',
        )

    def test_duplicate_nested_operation_is_refused(self):
        self.assert_refused(
            '{"inputs":["x"],"outputs":{"value":{"op":"add","op":"mul","args":[2,3]}}}',
            '{"x":7}',
        )

    def test_equivalent_escaped_input_key_is_duplicate(self):
        self.assert_refused(
            VALID_SPEC,
            '{"x":1,"\\u0078":2}',
        )

    def test_even_identical_repeated_key_is_duplicate(self):
        self.assert_refused(VALID_SPEC, '{"x":3,"x":3}')

    def test_nonstandard_constant_in_inert_metadata_is_refused(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                self.assert_refused(
                    '{"inputs":["x"],"outputs":{"value":{"field":"x"}},'
                    '"description":' + token + '}',
                    '{"x":7}',
                )

    def test_finite_json_exponent_overflow_in_inert_metadata_is_refused(self):
        for token in ("1e309", "-1e309"):
            with self.subTest(token=token):
                self.assert_refused(
                    '{"inputs":["x"],"outputs":{"value":{"field":"x"}},'
                    '"description":' + token + '}',
                    '{"x":7}',
                )

    def test_finite_scientific_notation_remains_accepted(self):
        result = self.run_runner(VALID_SPEC, '{"x":1e2}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["output"], {"value": 100})

    def test_valid_portable_execution_is_unchanged(self):
        result = self.run_runner(VALID_SPEC, '{"x":7}')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["output"], {"value": 7})
        self.assertEqual(output["scope"], "Bounded declarative execution; acceptance must be checked separately.")


if __name__ == "__main__":
    unittest.main()
