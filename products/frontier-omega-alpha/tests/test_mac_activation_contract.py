"""Offline checks for Mac program contracts. These tests establish no host authority."""
from pathlib import Path
import subprocess
import sys
import unittest

LIB = Path(__file__).resolve().parents[1] / "research" / "autonomous_endpoint"
sys.path.insert(0, str(LIB))
from mac_activation import CONSTRUCTOR_RIGHTS, EVAL_RIGHTS, LABEL, SCOPE, plist_document, validate_roles


class MacActivationContractTests(unittest.TestCase):
    def test_permission_matrix_rejects_actual_constructor_read_report(self):
        authority = {"evaluator_uid": 811, "evaluator_gid": 821, "constructor_uid": 831}
        approved = {"machine_binding_sha256": "fixture", "runtime_files": {}, "administrator_uid": 841}
        measured = {"schema": SCOPE, "machine_binding_sha256": "fixture", "runtime_files": {},
                    "administrator_uid": 841, "signing_canary_verified": True,
                    "evaluator": {"uid": 811, "gid": 821, "operations": EVAL_RIGHTS},
                    "constructor": {"uid": 831, "gid": 832, "operations": CONSTRUCTOR_RIGHTS}}
        validate_roles(measured, authority, approved)
        failed = measured["constructor"] | {"operations": CONSTRUCTOR_RIGHTS | {"key_read": True}}
        with self.assertRaisesRegex(ValueError, "ACTUAL_MAC_PERMISSION_MATRIX_NOT_SATISFIED"):
            validate_roles(measured | {"constructor": failed}, authority, approved)
        with self.assertRaisesRegex(ValueError, "MAC_CANARY_IDENTITY_MISMATCH"):
            validate_roles(measured | {"signing_canary_verified": False}, authority, approved)

    def test_daemon_uses_evaluator_identity_and_approved_schedule(self):
        root, state = Path("/Library/FrontierEvaluator"), Path("/private/var/db/frontier-evaluator")
        plist = plist_document(root, state, "owner-anchor-fixture", {"evaluator_user": "frontier-evaluator"}, 482)
        self.assertEqual((plist["Label"], plist["UserName"], plist["StartInterval"]), (LABEL, "frontier-evaluator", 482))
        self.assertEqual(plist["ProgramArguments"][-8:], [str(LIB / "mac_activation.py"), "run", "--authority-root",
                         str(root), "--private-state", str(state), "--owner-pin", "owner-anchor-fixture"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires definitively off-host Linux")
    def test_on_device_canary_refuses_linux(self):
        run = subprocess.run([sys.executable, "-B", str(LIB / "mac_activation.py"), "canary", "--authority-root",
                              "/nonexistent", "--private-state", "/nonexistent", "--owner-pin", "unapproved"], capture_output=True)
        self.assertEqual(run.returncode, 1)
        self.assertIn(b"ACTUAL_MAC_STUDIO_REQUIRED", run.stdout)
