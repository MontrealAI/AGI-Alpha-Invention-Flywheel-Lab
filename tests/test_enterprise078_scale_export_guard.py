"""Adversarial tests for fail-closed Enterprise078 public workflow exports."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.enterprise078_scale_export_guard import prepare


class PublicExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / "run"
        self.output.mkdir()
        self.upload = self.root / "upload"
        self.stdout = self.root / "original.stdout"
        self.stderr = self.root / "original.stderr"
        self.stdout.write_text("PRIVATE_KEY_TEST_SENTINEL\n")
        self.stderr.write_text("SENSITIVE_STACK_TRACE_TEST_SENTINEL\n")

    def prepare(self, exit_code):
        return prepare(self.output, self.upload, self.stdout, self.stderr, exit_code, "central")

    def success_fixture(self, member="source/a.py"):
        public = self.output / "public"
        (public / "central").mkdir(parents=True)
        data = {"requested_worlds": ["central"], "results": [
            {"case": "central", "status": "NATIVE_AND_OPERATING_REPLAY_PASSED"}]}
        (public / "CAMPAIGN.json").write_text(json.dumps(data))
        (public / "central/result.json").write_text('{"accepted_artifacts":1}')
        (public / "central/review.json").write_text('{"accepted":true}')
        archive = self.output / "enterprise078-scale-keyfree.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(member, "public test fixture")
        (self.output / "PUBLIC_PACKAGE.json").write_text(json.dumps({
            "archive": archive.name, "bytes": archive.stat().st_size,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "private_state_included": False}))
        return archive

    def test_failure_diagnostics_never_leave_private_runner(self):
        (self.output / "central.failure.txt").write_text("PRIVATE_KEY_TEST_SENTINEL")
        (self.output / "public").mkdir()
        (self.output / "public/CAMPAIGN.json").write_text('{"stderr_tail":"PRIVATE_KEY_TEST_SENTINEL"}')
        receipt = self.prepare(1)
        self.assertEqual(receipt["status"], "FAILED_PRIVATE_DIAGNOSTICS_RETAINED_LOCALLY")
        self.assertEqual({p.name for p in self.upload.iterdir()}, {"SAFE_EXPORT_RECEIPT.json"})
        content = (self.upload / "SAFE_EXPORT_RECEIPT.json").read_text()
        self.assertNotIn("PRIVATE_KEY_TEST_SENTINEL", content)
        self.assertNotIn("SENSITIVE_STACK_TRACE_TEST_SENTINEL", content)
        self.assertEqual(receipt["stdout_sha256"], hashlib.sha256(self.stdout.read_bytes()).hexdigest())
        self.assertFalse(receipt["raw_logs_uploaded"])

    def test_success_only_exports_named_verified_public_files(self):
        self.success_fixture()
        (self.output / "secret.simulated-key").write_text("PRIVATE_KEY_TEST_SENTINEL")
        receipt = self.prepare(0)
        self.assertEqual(set(receipt["files_sha256"]), {
            "keyfree.zip", "PUBLIC_PACKAGE.json", "CAMPAIGN.json",
            "central.result.json", "central.review.json"})
        self.assertEqual(len(list(self.upload.iterdir())), 6)
        self.assertNotIn("PRIVATE_KEY_TEST_SENTINEL",
                         "".join(p.read_text(errors="replace") for p in self.upload.iterdir()))
        self.assertEqual(receipt["subprocess_exit_code"], 0)

    def test_altered_archive_digest_refused(self):
        self.success_fixture()
        manifest = self.output / "PUBLIC_PACKAGE.json"
        bad = json.loads(manifest.read_text())
        bad["sha256"] = "0" * 64
        manifest.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, "HASH_OR_PRIVACY"):
            self.prepare(0)
        self.assertFalse((self.upload / "SAFE_EXPORT_RECEIPT.json").exists())

    def test_private_archive_member_refused(self):
        self.success_fixture("private/authority.json")
        with self.assertRaisesRegex(ValueError, "UNSAFE_PUBLIC_ARCHIVE"):
            self.prepare(0)

    def test_campaign_raw_stderr_refused_even_on_zero_exit(self):
        self.success_fixture()
        path = self.output / "public/CAMPAIGN.json"
        d = json.loads(path.read_text())
        d["results"][0]["stderr_tail"] = "PRIVATE_KEY_TEST_SENTINEL"
        path.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError, "CAMPAIGN_NOT_SUCCESSFUL"):
            self.prepare(0)

    def test_symlink_result_refused(self):
        self.success_fixture()
        result = self.output / "public/central/review.json"
        result.unlink()
        result.symlink_to(self.stderr)
        with self.assertRaisesRegex(ValueError, "INPUT_NOT_REGULAR"):
            self.prepare(0)

    def test_no_stale_merge_or_path_escape(self):
        self.success_fixture()
        self.upload.mkdir()
        with self.assertRaisesRegex(ValueError, "FRESH_UPLOAD"):
            self.prepare(0)
        self.upload.rmdir()
        with self.assertRaisesRegex(ValueError, "INVALID_REGISTERED_WORLD"):
            prepare(self.output, self.upload, self.stdout, self.stderr, 1, "../private")

    def test_workflow_never_uploads_old_wildcard_failure_logs(self):
        workflow = Path(".github/workflows/enterprise078-scale.yml").read_text()
        self.assertNotIn("*.failure.txt", workflow)
        self.assertNotIn("/enterprise078-scale/public/CAMPAIGN.json", workflow)
        self.assertIn("enterprise078_scale_export_guard.py", workflow)
        self.assertIn("enterprise078-scale-export", workflow)


if __name__ == "__main__":
    unittest.main()
