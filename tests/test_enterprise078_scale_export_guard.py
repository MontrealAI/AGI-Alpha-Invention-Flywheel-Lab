"""Adversarial tests for fail-closed Enterprise078 public workflow exports."""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.enterprise078_scale_export_guard import prepare, zip_paths_safe


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
            for name in ("CAMPAIGN.json", "central/result.json", "central/review.json"):
                z.writestr("public/" + name, (public / name).read_bytes())
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

    def test_standalone_financial_receipt_cannot_diverge_from_verified_archive(self):
        self.success_fixture()
        (self.output / "public/central/review.json").write_text('{"accepted":false}')
        with self.assertRaisesRegex(ValueError, "PUBLIC_STANDALONE_AND_ARCHIVE_MISMATCH"):
            self.prepare(0)
        self.assertFalse(self.upload.exists())

    def test_zip_aliases_that_collide_on_extraction_are_refused(self):
        for index, alias in enumerate(("source//a.py", "source/./a.py", "source/a.py/")):
            with self.subTest(alias=alias):
                archive = self.root / f"noncanonical-{index}.zip"
                with zipfile.ZipFile(archive, "w") as z:
                    z.writestr("source/a.py", "original")
                    z.writestr(alias, "conflicting")
                with self.assertRaisesRegex(ValueError, "UNSAFE_PUBLIC_ARCHIVE_MEMBER"):
                    zip_paths_safe(archive)

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

    def test_source_identity_is_checked_out_code_not_virtual_pr_merge(self):
        with patch.dict(os.environ, {"GITHUB_SHA": "0" * 40}):
            receipt = self.prepare(1)
        self.assertEqual(receipt["github_event_sha"], "0" * 40)
        self.assertRegex(receipt["checked_out_source_sha"], r"^[a-f0-9]{40}$")
        self.assertNotEqual(receipt["checked_out_source_sha"], receipt["github_event_sha"])

    def test_symlinked_parent_directory_is_rejected(self):
        self.success_fixture()
        old = self.output / "public"
        safe = self.output / "real_public"
        old.rename(safe)
        old.symlink_to(safe, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "INPUT_NOT_REGULAR"):
            self.prepare(0)

    def test_staging_copy_failure_is_not_uploadable(self):
        self.success_fixture()
        original = shutil.copyfile
        calls = 0
        def fail_second_copy(src, dest, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("INJECTED_PARTIAL_COPY_FAILURE")
            return original(src, dest, *args, **kwargs)
        with patch("scripts.enterprise078_scale_export_guard.shutil.copyfile", side_effect=fail_second_copy):
            with self.assertRaisesRegex(OSError, "INJECTED_PARTIAL_COPY_FAILURE"):
                self.prepare(0)
        self.assertFalse(self.upload.exists())
        self.assertEqual(list(self.root.glob(".e078-private-stage-*")), [])

    def test_workflow_only_uploads_after_stage_and_preserves_world_verdict(self):
        workflow = Path(".github/workflows/enterprise078-scale.yml").read_text()
        self.assertIn("id: stage_public_evidence", workflow)
        self.assertIn("if: ${{ steps.stage_public_evidence.outcome == 'success' }}", workflow)
        self.assertIn('echo "financial_exit_code=$status" >> "$GITHUB_OUTPUT"', workflow)
        self.assertIn('exit "${{ steps.stage_public_evidence.outputs.financial_exit_code }}"', workflow)

    def test_workflow_never_uploads_old_wildcard_failure_logs(self):
        workflow = Path(".github/workflows/enterprise078-scale.yml").read_text()
        self.assertNotIn("*.failure.txt", workflow)
        self.assertNotIn("/enterprise078-scale/public/CAMPAIGN.json", workflow)
        self.assertIn("enterprise078_scale_export_guard.py", workflow)
        self.assertIn("enterprise078-scale-export", workflow)


if __name__ == "__main__":
    unittest.main()
