"""Adversarial synthetic-only controls for prospective Blue Sky 180 intake."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from research.blue_sky064.observation178 import assess
from research.blue_sky064 import measurement180 as m

ROOT = Path(__file__).resolve().parents[1]


def synthetic():
    return {
        "schema": m.INPUT_SCHEMA,
        "indentation_mm": {"low": 0.01, "high": 0.10},
        "force_readings_N": {
            "low": {"static_force_N": 2.0, "dynamic_force_N": 1.0},
            "high": {"static_force_N": 7.0, "dynamic_force_N": 3.0},
        },
        "absolute_force_error_bound_N": 0.01,
        "measurement_authority": "UNVERIFIED_EXTERNAL_INPUT",
    }


def write(path, data):
    path.write_text(json.dumps(data, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


class UnverifiedExternalMeasurement180(unittest.TestCase):
    def run_input(self, data, raw=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.json"
            if raw is None:
                write(path, data)
            else:
                path.write_text(raw, encoding="utf-8")
            return m.interpret_unverified(path)

    def test_positive_interval_is_conditional_and_never_physical(self):
        p = synthetic()
        r = self.run_input(p)
        self.assertEqual(r["schema"], m.OUTPUT_SCHEMA)
        self.assertEqual(r["conditional_mathematical_assessment"],
                         assess(p["force_readings_N"], .01, .05))
        self.assertEqual(r["conditional_mathematical_assessment"]["conditional_math_verdict"],
                         "CONDITIONALLY_CERTIFIED")
        self.assertEqual(r["decision"], "HOLD_NO_DEPLOY_UNVERIFIED_INPUT")
        for flag in ("physical_measurement_verified", "independent_force_error_calibration_verified",
                     "beneficiary_acceptance_verified", "commercial_payment_verified",
                     "financial_authority_or_account_action"):
            self.assertIs(r[flag], False)
        self.assertEqual(r["source_registration_sha256"], m.REGISTRATION_SHA256)
        self.assertEqual(r["frozen_indentation_mm"], {"low": .01, "high": .1})

    def test_refutation_and_inconclusiveness_preserve_no_deploy(self):
        p = synthetic()
        p["force_readings_N"]["high"] = {"static_force_N": 1., "dynamic_force_N": 1.}
        p["absolute_force_error_bound_N"] = 0.
        negative = self.run_input(p)
        self.assertEqual(negative["conditional_mathematical_assessment"]["conditional_math_verdict"],
                         "CONDITIONALLY_REFUTED")
        p["force_readings_N"]["high"] = {"static_force_N": 2.05, "dynamic_force_N": 1.}
        p["absolute_force_error_bound_N"] = .1
        ambiguous = self.run_input(p)
        self.assertEqual(ambiguous["conditional_mathematical_assessment"]["conditional_math_verdict"],
                         "INDETERMINATE")
        for obj in (negative, ambiguous):
            self.assertEqual(obj["decision"], "HOLD_NO_DEPLOY_UNVERIFIED_INPUT")

    def test_no_retuned_or_swapped_loads(self):
        for loads in [{"low": .1, "high": .01}, {"low": .01}, {"low": .01, "high": .1001},
                      {"low": True, "high": .1}, {"low": .01, "high": .1, "extra": .1}]:
            with self.subTest(loads=loads):
                p = synthetic()
                p["indentation_mm"] = loads
                with self.assertRaisesRegex(ValueError, "EXACT_FROZEN_INDENTATIONS"):
                    self.run_input(p)

    def test_strict_schema_and_false_authority_rejected(self):
        for mutation in ("missing", "extra", "changed_schema", "claimed_verified"):
            with self.subTest(mutation=mutation):
                p = synthetic()
                if mutation == "missing":
                    del p["measurement_authority"]
                if mutation == "extra":
                    p["approved_by"] = "laboratory"
                if mutation == "changed_schema":
                    p["schema"] = "new-authority"
                if mutation == "claimed_verified":
                    p["measurement_authority"] = "CERTIFIED"
                with self.assertRaises(ValueError):
                    self.run_input(p)

    def test_bad_forces_error_and_denominators_rejected(self):
        for value in (True, "2.0", None, -1., 0., float("inf")):
            with self.subTest(value=str(value)):
                p = synthetic()
                p["force_readings_N"]["low"]["static_force_N"] = value
                with self.assertRaises(ValueError):
                    if value == float("inf"):
                        with tempfile.TemporaryDirectory() as d:
                            path = Path(d) / "x.json"
                            path.write_text(json.dumps(p), encoding="utf-8")
                            m.interpret_unverified(path)
                    else:
                        self.run_input(p)
        for e in (-1., True, "0.01", 1.):
            with self.subTest(e=str(e)):
                p = synthetic()
                p["absolute_force_error_bound_N"] = e
                with self.assertRaises(ValueError):
                    self.run_input(p)

    def test_duplicate_json_keys_rejected(self):
        p = synthetic()
        raw = json.dumps(p).replace('"schema":', '"schema": "spoof", "schema":', 1)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            self.run_input(p, raw=raw)

    def test_input_hash_is_exact_bytes_and_no_raw_identity_copied(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "synthetic.json"
            write(path, synthetic())
            report = m.interpret_unverified(path)
            self.assertEqual(report["input_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertNotIn("force_readings_N", report)
            self.assertEqual(report["source_type"], "EXTERNAL_SUBMISSION_NOT_AUTHENTICATED")

    def test_symlink_and_oversized_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "real.json"
            write(real, synthetic())
            link = Path(d) / "link.json"
            link.symlink_to(real)
            with self.assertRaisesRegex(ValueError, "NON_SYMLINK"):
                m.interpret_unverified(link)
            real.write_bytes(b" " * 16385)
            with self.assertRaisesRegex(ValueError, "BOUNDED_REGULAR_INPUT"):
                m.interpret_unverified(real)

    def test_altered_or_missing_registered_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            input_path = Path(d) / "input.json"
            write(input_path, synthetic())
            fake = Path(d) / "registration.json"
            fake.write_text('{"test_indentation_mm": [0.01, 0.1]}')
            with patch.object(m, "REGISTRATION_PATH", fake):
                with self.assertRaisesRegex(ValueError, "REGISTERED_SOURCE_HASH_MISMATCH"):
                    m.interpret_unverified(input_path)
            with patch.object(m, "REGISTRATION_PATH", Path(d) / "missing.json"):
                with self.assertRaisesRegex(ValueError, "REGULAR_INPUT_REQUIRED"):
                    m.interpret_unverified(input_path)

    def test_cli_clean_report_and_existing_output_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            input_path, out = root/"synthetic.json", root/"result.json"
            write(input_path, synthetic())
            cmd = [sys.executable, "-B", "-m", "research.blue_sky064.measurement180",
                   "--input", str(input_path), "--output", str(out)]
            first = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads(out.read_text())
            self.assertFalse(receipt["physical_measurement_verified"])
            self.assertEqual(receipt["decision"], "HOLD_NO_DEPLOY_UNVERIFIED_INPUT")
            old = out.read_bytes()
            second = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(out.read_bytes(), old)
            self.assertIn("NEW_ABSOLUTE_NON_SYMLINK_REPORT_REQUIRED", second.stderr)

    def test_invalid_input_never_creates_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path, out = root/"fake.json", root/"result.json"
            bad = synthetic()
            bad["measurement_authority"] = "REAL_AUTHORITY"
            write(path, bad)
            result = subprocess.run(
                [sys.executable, "-B", "-m", "research.blue_sky064.measurement180",
                 "--input", str(path), "--output", str(out)],
                cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
