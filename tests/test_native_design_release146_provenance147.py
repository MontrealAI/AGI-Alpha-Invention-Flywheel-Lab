"""Review147: released native design proof must authenticate public transport provenance.

This suite is synthetic adversarial validation of transport receipt logic, not a
new buyer experiment, operating account, release qualification, or economic claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import qualify_native_design_public_release as verifier


class NativeRelease146ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        self.commit = "b" * 40
        self.source_sha = "a" * 64
        self.published = {"source_commit": self.commit,
                          "source_sha256": self.source_sha}
        for name in ("connected014-source.zip", "RELEASE_MANIFEST.json", "SHA256SUMS.txt"):
            (self.assets / name).write_bytes(("public-" + name).encode())
        self.receipt_path = self.root / "RELEASE_DOWNLOAD.json"
        self.receipt = {
            "schema": "agi-alpha/connected014-actual-release-download/v1",
            "actual_release_download": True,
            "source_commit": self.commit,
            "source_sha256": self.source_sha,
            "tag": "connected014-" + self.commit,
            "release_url": (
                "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
                "/releases/tag/connected014-" + self.commit),
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.assets.iterdir())
            },
        }
        self.write_receipt()

    def write_receipt(self, value=None):
        self.receipt_path.write_text(json.dumps(
            self.receipt if value is None else value, sort_keys=True))

    def check(self):
        return verifier.validate_download_receipt(
            self.assets, self.commit, self.published, self.receipt_path)

    def test_valid_download_receipt_is_bound_to_exact_sha(self):
        self.assertEqual(self.check(), verifier._hash(self.receipt_path))

    def test_missing_false_synthetic_source_tag_and_extra_fields_fail(self):
        for field, replacement in (
            ("schema", "unknown"),
            ("actual_release_download", False),
            ("actual_release_download", 1),
            ("source_commit", "c" * 40),
            ("source_sha256", "d" * 64),
            ("tag", "connected014-" + "c" * 40),
            ("release_url", "https://example.test/fake-release"),
        ):
            with self.subTest(field=field, replacement=replacement):
                changed = copy.deepcopy(self.receipt)
                changed[field] = replacement
                self.write_receipt(changed)
                with self.assertRaisesRegex(
                        ValueError, "AUTHENTICATED_RELEASE_DOWNLOAD_RECEIPT_REQUIRED"):
                    self.check()
        for change in (lambda row: row.pop("release_url"),
                       lambda row: row.update(extra="unregistered")):
            changed = copy.deepcopy(self.receipt)
            change(changed)
            self.write_receipt(changed)
            with self.assertRaisesRegex(
                    ValueError, "AUTHENTICATED_RELEASE_DOWNLOAD_RECEIPT_REQUIRED"):
                self.check()

    def test_missing_or_mismatched_asset_and_later_mutation_fail(self):
        for change in (
            lambda row: row["files"].pop("connected014-source.zip"),
            lambda row: row["files"].update({"connected014-source.zip": "0" * 64}),
            lambda row: row["files"].update({"account/authority.key": "0" * 64}),
        ):
            changed = copy.deepcopy(self.receipt)
            change(changed)
            self.write_receipt(changed)
            with self.assertRaises(ValueError):
                self.check()
        self.write_receipt()
        (self.assets / "connected014-source.zip").write_bytes(b"tampered-after-download")
        with self.assertRaisesRegex(
                ValueError, "RELEASE_DOWNLOAD_RECEIPT_ASSET_CHANGED"):
            self.check()

    def test_missing_symlink_or_duplicate_json_fields_fail(self):
        self.receipt_path.unlink()
        with self.assertRaisesRegex(ValueError, "UNSYMLINKED_PUBLIC_RECEIPT_REQUIRED"):
            self.check()
        private = self.root / "private.json"
        private.write_text("must-not-read")
        self.receipt_path.symlink_to(private)
        with self.assertRaisesRegex(ValueError, "UNSYMLINKED_PUBLIC_RECEIPT_REQUIRED"):
            self.check()
        self.receipt_path.unlink()
        self.receipt_path.write_text('{"schema":"first","schema":"second"}')
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PUBLIC_RECEIPT_FIELD"):
            self.check()

    def test_seal_uses_verified_transport_not_self_asserted_success(self):
        self.source = self.root / "source"
        self.source.mkdir()
        files = {}
        for name in sorted(verifier.REQUIRED):
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("source-bound-" + name)
            files[name] = verifier._hash(target)
        (self.source / "SOURCE_MANIFEST.json").write_text(json.dumps({
            "executing_source": {"sha256": self.source_sha},
            "files": files,
        }))
        self.public_path = self.root / "PUBLIC.json"
        self.public_path.write_text(json.dumps({
            "source_sha256": self.source_sha,
            "confirmed_positive_funded_successor_opportunity": True,
            "comparative_advantage_on_one_fresh_seed": True,
            "heldout_recommendation": {"challenger_accepted": True},
            "matched_confirmation_profit_delta_microUSD": 12,
        }))
        proof = self.root / "proof.json"
        copy = self.root / "public-copy.json"
        with patch.object(verifier, "verify_assets", return_value=self.published):
            verifier.seal(self.assets, self.commit, self.source, self.public_path,
                          proof, copy, self.receipt_path)
        result = json.loads(proof.read_text())
        self.assertEqual(result["authenticated_download_receipt_sha256"],
                         verifier._hash(self.receipt_path))
        self.assertEqual(result["native_public_sha256"],
                         verifier._hash(self.public_path))
        self.assertEqual(result["actual_paid_commerce"], False)
        self.assertEqual(result["native_adversarial_regressions"],
                         "GITHUB_WORKFLOW_STEP_OBSERVATION_NOT_INDEPENDENT_CERTIFICATION")
        self.assertEqual(copy.read_bytes(), self.public_path.read_bytes())
        proof.unlink()
        copy.unlink()
        self.receipt["actual_release_download"] = False
        self.write_receipt()
        with patch.object(verifier, "verify_assets", return_value=self.published):
            with self.assertRaisesRegex(
                    ValueError, "AUTHENTICATED_RELEASE_DOWNLOAD_RECEIPT_REQUIRED"):
                verifier.seal(self.assets, self.commit, self.source, self.public_path,
                              proof, copy, self.receipt_path)
        self.assertFalse(proof.exists())
        self.assertFalse(copy.exists())


if __name__ == "__main__":
    unittest.main()
