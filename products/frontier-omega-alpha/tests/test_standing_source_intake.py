"""Exercise source production, signatures, versions and staging with public records."""
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

RESEARCH = Path(__file__).resolve().parents[1] / "research"
sys.path.insert(0, str(RESEARCH / "autonomous_endpoint"))
from common import sha
from cycle import signature
from record_intake import (MANIFEST, RELEASE_SCHEMA, admit_snapshot, install_snapshot, produce, read_slot,
                           retire_expired)
from standing_authority import protected


class StandingSourceIntake(unittest.TestCase):
    def test_public_source_produces_two_versions_with_staging_retry_and_retirement(self):
        with TemporaryDirectory() as private:
            root = Path(private)
            publisher, evaluator, stage = (root / p for p in ("publisher", "evaluator", "retained"))
            for directory in (publisher, evaluator, stage):
                directory.mkdir(mode=0o700)
            outbox = publisher / "outbox"
            outbox.mkdir(mode=0o700)
            key = signature(publisher, {"fixture": True})["evaluator_public_key_sha256"]
            independent = signature(evaluator, {"fixture": True})["evaluator_public_key_sha256"]
            self.assertNotEqual(key, independent)
            owner = os.geteuid()
            actual = [RESEARCH / name / "evidence" / "confirmation.json" for name in ("photometry_resilience", "measurement_gap")]
            contract = b"Public source lifecycle test with previously signed research evidence.\n"
            now = datetime.now(timezone.utc)
            until = (now + timedelta(minutes=15)).isoformat()
            encode = lambda raw: base64.b64encode(raw).decode()
            releases = [{"schema": RELEASE_SCHEMA, "scope_id": "public-research-receipts", "source_revision_sha256": sha(p.read_bytes()),
                         "valid_from": (now-timedelta(minutes=1)).isoformat(), "valid_until": until,
                         "records": {"requirements.txt": encode(contract), "public-receipt.json": encode(p.read_bytes())}} for p in actual]
            script = root / "approved-source-adapter.py"
            script.write_text("print(" + repr(json.dumps(releases)) + ")\n")
            authority = {"record_publisher": {"key_sha256": key, "scope_id": "public-research-receipts",
                                              "requirements_sha256": sha(contract)},
                         "evaluator_key_sha256": independent, "valid_until": (now+timedelta(hours=1)).isoformat(),
                         "operating_requirements_file": "requirements.txt", "max_input_bytes": 256000, "retention_days": 1}
            scope = {"publisher_uid": owner, "adapter_sha256": sha(script.read_bytes()), "adapter_wall_seconds": 5,
                     "max_versions_per_run": 5}
            # The temporary approved adapter is owned by the test runner. No Mac root authority is simulated as evidence.
            def on_runner(path, **kwargs):
                if path == script:
                    kwargs["owner"] = owner
                return protected(path, **kwargs)
            with patch("record_intake.protected", side_effect=on_runner):
                self.assertEqual(produce(authority, scope, root, publisher, outbox)["published"], 2)
                self.assertEqual(produce(authority, scope, root, publisher, outbox)["already_present"], 2)
            version_paths = list(outbox.iterdir())
            self.assertEqual(len(version_paths), 2)
            for path in version_paths:
                snapshot = read_slot(outbox, path.name, owner, authority["max_input_bytes"])
                manifest = admit_snapshot(snapshot, authority, now, root)
                self.assertEqual(manifest["source_revision_sha256"], sha(snapshot["public-receipt.json"]))
                tampered = snapshot | {"requirements.txt": contract+b"different scope"}
                with self.assertRaisesRegex(ValueError, "SOURCE_VERSIONS_DO_NOT_MATCH_SIGNED_HASHES"):
                    admit_snapshot(tampered, authority, now, root)
                self.assertEqual(install_snapshot(stage, sha(snapshot[MANIFEST]), snapshot), "published")
                self.assertEqual(install_snapshot(stage, sha(snapshot[MANIFEST]), snapshot), "already_present")
            other = stage / ("f"*64)
            other.mkdir()
            self.assertEqual(retire_expired(stage, owner, authority, now), 0)
            self.assertEqual(retire_expired(stage, owner, authority, now+timedelta(minutes=16)), 2)
            self.assertEqual(list(stage.iterdir()), [other])

    @unittest.skipUnless(sys.platform.startswith("linux"), "off-host denial check")
    def test_cannot_activate_intake_off_host(self):
        script = RESEARCH / "autonomous_endpoint" / "record_intake.py"
        attempt = subprocess.run([sys.executable, "-B", str(script), "stage", "--authority-root", "/nonexistent",
                                  "--owner-pin", "test-fixture"], capture_output=True, check=False)
        self.assertEqual(attempt.returncode, 1)
        self.assertEqual(json.loads(attempt.stdout)["state"], "ABSTAIN")
