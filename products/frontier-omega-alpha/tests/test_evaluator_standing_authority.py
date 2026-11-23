"""External approval and aggregate-only rejection tests without granting authority."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "autonomous_endpoint"))
from common import atomic, sha
from cycle import signature, verify
from standing_authority import BATCH_SCHEMA, SCHEMA, active_approval, admit_batch, cleanup_managed_runs, validate_metrics, verify_aggregate


class StandingAuthorityTests(unittest.TestCase):
    def fixture(self, key="evaluator-fingerprint"):
        now = datetime.now(timezone.utc)
        return {"schema": SCHEMA, "purpose": "non-production-only", "state": "ACTIVE",
                "valid_from": (now - timedelta(hours=1)).isoformat(), "valid_until": (now + timedelta(hours=1)).isoformat(),
                "code_sha256": {"score.py": "example"}, "records_sha256": {"contract.json": "example"},
                "score_entry": "score.py", "operating_requirements_file": "contract.json", "run_wall_seconds": 1, "max_input_bytes": 1000,
                "retention_days": 1, "evaluator_key_sha256": key, "revoked_key_sha256": [],
                "new_spend_authorized": False, "publish": "signed-aggregate-only"}

    def test_reject_expired_revoked_unapproved_input_and_spend(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(active_approval(self.fixture(), now)["state"], "ACTIVE")
        faults = [("valid_until", (now - timedelta(seconds=1)).isoformat()), ("state", "REVOKED"),
                  ("revoked_key_sha256", ["evaluator-fingerprint"]), ("new_spend_authorized", True),
                  ("operating_requirements_file", "untested-contract.json")]
        for field, value in faults:
            with self.subTest(field=field), self.assertRaises(ValueError):
                active_approval(self.fixture() | {field: value}, now)

    def test_owner_and_evaluator_keys_are_independent_and_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owner = root / "owner"
            evaluator = root / "evaluator"
            owner.mkdir()
            evaluator.mkdir()
            key = signature(evaluator, {"fixture": True})["evaluator_public_key_sha256"]
            approval = root / "approval.json"
            approval_envelope = signature(owner, self.fixture(key))
            atomic(approval, approval_envelope)
            signer = approval_envelope["evaluator_public_key_sha256"]
            self.assertNotEqual(key, signer)
            public = root / "aggregate.json"
            metrics = {"accepted": 1, "abstained": 1, "cases": 2, "rejected": 0}
            body = {"schema": "frontier-omega-alpha/independent-evaluator-aggregate-v1", "scope": "non-production-only",
                    "authority_envelope_sha256": sha(approval.read_bytes()),
                    "input_version_binding_sha256": sha(b"example-version"), "metrics": metrics}
            atomic(public, signature(evaluator, body))
            self.assertEqual(verify_aggregate(public, approval, signer), metrics)
            with self.assertRaisesRegex(ValueError, "UNTRUSTED_EVALUATOR_KEY"):
                verify_aggregate(public, approval, key)
            atomic(approval, signature(owner, self.fixture(key) | {"revoked_key_sha256": [key]}))
            with self.assertRaisesRegex(ValueError, "EVALUATOR_REVOKED"):
                verify_aggregate(public, approval, signer)

    def test_two_signed_input_versions_use_one_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            envelope = self.fixture()
            publisher = signature(directory, {"fixture": True})["evaluator_public_key_sha256"]
            authority = envelope | {"record_publisher": {"key_sha256": publisher, "scope_id": "registered-source",
                                 "requirements_sha256": "fixed-contract"}}
            now = datetime.now(timezone.utc)
            fields = {"schema": BATCH_SCHEMA, "scope_id": "registered-source", "valid_from": envelope["valid_from"],
                      "valid_until": envelope["valid_until"]}
            version = directory / "intake.json"
            for seen in ("sample-one", "sample-two"):
                files = {"contract.json": "fixed-contract", "cases.json": seen}
                atomic(version, signature(directory, fields | {"records_sha256": files}))
                data = verify(version, publisher)["receipt"]
                self.assertEqual(admit_batch(data, active_approval(authority, now), now)[0], files)
            with self.assertRaisesRegex(ValueError, "INPUT_VERSION_OUTSIDE_APPROVED_SCOPE"):
                admit_batch(data | {"scope_id": "other-source"}, authority, now)
            with self.assertRaisesRegex(ValueError, "INPUT_VERSION_CHANGED_APPROVED_REQUIREMENTS"):
                admit_batch(data | {"records_sha256": {"contract.json": "different-contract", "cases.json": "data"}}, authority, now)

    def test_aggregate_field_gate_and_managed_retention(self):
        sample = {"accepted": 0, "abstained": 1, "cases": 1, "rejected": 0}
        for invalid in (sample | {"unapproved_record": "raw"}, sample | {"abstained": True}, sample | {"cases": 2}):
            with self.assertRaises(ValueError):
                validate_metrics(invalid)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases = root / "managed-runs"
            cases.mkdir(mode=0o700)
            active, expired = cases / "case-active", cases / "case-expired"
            active.mkdir()
            expired.mkdir()
            now = datetime.now(timezone.utc)
            atomic(active / "retention.json", {"delete_after": (now + timedelta(hours=1)).isoformat()})
            atomic(expired / "retention.json", {"delete_after": (now - timedelta(hours=1)).isoformat()})
            untouched = root / "unmanaged.json"
            untouched.touch()
            cleanup_managed_runs(root)
            self.assertFalse(expired.exists())
            self.assertTrue(active.exists())
            self.assertTrue(untouched.exists())
