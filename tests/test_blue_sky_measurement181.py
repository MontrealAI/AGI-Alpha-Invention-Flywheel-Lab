"""Preregistered local-path substitution controls; inputs are synthetic, not sensors."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.blue_sky064 import measurement180 as m


def sample(high=7.0):
    return {
        "schema": m.INPUT_SCHEMA,
        "indentation_mm": {"low": 0.01, "high": 0.10},
        "force_readings_N": {
            "low": {"static_force_N": 2.0, "dynamic_force_N": 1.0},
            "high": {"static_force_N": high, "dynamic_force_N": 3.0}
        },
        "absolute_force_error_bound_N": 0.01,
        "measurement_authority": "UNVERIFIED_EXTERNAL_INPUT",
    }


def serialized(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class Race181DescriptorTests(unittest.TestCase):
    def sources(self, directory):
        root = Path(directory)
        primary, secondary = root / "candidate.json", root / "other.json"
        first, second = serialized(sample(7)), serialized(sample(3))
        primary.write_bytes(first)
        secondary.write_bytes(second)
        return primary, secondary, first, second

    def test_replacement_at_path_read_must_not_accept_swapped_target(self):
        """P0 baseline: old stat -> Path.read_bytes follows a newly planted link."""
        with tempfile.TemporaryDirectory() as d:
            primary, secondary, first, second = self.sources(d)
            original_read = Path.read_bytes
            replaced = [False]

            def swap_on_read(path):
                if path == primary and not replaced[0]:
                    replaced[0] = True
                    primary.unlink()
                    primary.symlink_to(secondary)
                return original_read(path)

            with patch.object(Path, "read_bytes", autospec=True, side_effect=swap_on_read):
                result = m.interpret_unverified(primary)
            self.assertEqual(result["input_sha256"], hashlib.sha256(first).hexdigest(),
                             "Earlier no-symlink checks must not authorize a different target")
            self.assertNotEqual(result["input_sha256"], hashlib.sha256(second).hexdigest())
            self.assertFalse(result["physical_measurement_verified"])

    def test_swap_just_before_final_descriptor_open_fails_closed(self):
        """The requested file must be opened O_NOFOLLOW, not followed after path checks."""
        with tempfile.TemporaryDirectory() as d:
            primary, secondary, _, _ = self.sources(d)
            original_open = os.open
            swapped = [False]

            def swap_final(path, flags, *args, **kwargs):
                if path == primary.name and "dir_fd" in kwargs and not swapped[0]:
                    swapped[0] = True
                    primary.unlink()
                    primary.symlink_to(secondary)
                return original_open(path, flags, *args, **kwargs)

            with patch.object(m.os, "open", side_effect=swap_final):
                with self.assertRaisesRegex(ValueError, "NON_SYMLINK"):
                    m.interpret_unverified(primary)
            self.assertTrue(swapped[0], "Expected descriptor-pinned final open must occur")

    def test_swap_after_file_descriptor_open_retains_original_bytes(self):
        """An already opened file descriptor cannot be redirected by a later rename."""
        with tempfile.TemporaryDirectory() as d:
            primary, secondary, first, second = self.sources(d)
            original_open = os.open
            swapped = [False]

            def swap_after_open(path, flags, *args, **kwargs):
                fd = original_open(path, flags, *args, **kwargs)
                if path == primary.name and "dir_fd" in kwargs and not swapped[0]:
                    swapped[0] = True
                    primary.unlink()
                    primary.symlink_to(secondary)
                return fd

            with patch.object(m.os, "open", side_effect=swap_after_open):
                result = m.interpret_unverified(primary)
            self.assertTrue(swapped[0], "Input must be opened relative to a pinned directory")
            self.assertEqual(result["input_sha256"], hashlib.sha256(first).hexdigest())
            self.assertNotEqual(result["input_sha256"], hashlib.sha256(second).hexdigest())
            self.assertEqual(result["decision"], "HOLD_NO_DEPLOY_UNVERIFIED_INPUT")

    def test_in_place_change_during_bounded_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            primary, _, _, _ = self.sources(d)
            initial_inode = primary.stat().st_ino
            original_read = os.read
            changed = [False]

            def change_during_read(fd, size):
                data = original_read(fd, size)
                if data and not changed[0] and os.fstat(fd).st_ino == initial_inode:
                    changed[0] = True
                    with primary.open("ab") as stream:
                        stream.write(b" ")
                return data

            with patch.object(m.os, "read", side_effect=change_during_read):
                with self.assertRaisesRegex(ValueError, "INPUT_CHANGED_OR_OVERSIZED"):
                    m.interpret_unverified(primary)
            self.assertTrue(changed[0])

    def test_original_conditional_math_and_refusal_stay_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            primary, _, first, _ = self.sources(d)
            report = m.interpret_unverified(primary)
            self.assertEqual(report["input_sha256"], hashlib.sha256(first).hexdigest())
            self.assertEqual(report["conditional_mathematical_assessment"]["conditional_math_verdict"],
                             "CONDITIONALLY_CERTIFIED")
            self.assertFalse(report["independent_force_error_calibration_verified"])
            self.assertFalse(report["physical_measurement_verified"])
            self.assertFalse(report["commercial_payment_verified"])
            self.assertEqual(report["decision"], "HOLD_NO_DEPLOY_UNVERIFIED_INPUT")


if __name__ == "__main__":
    unittest.main()
