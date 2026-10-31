"""Publication binding regressions only; no business execution or gate bypass."""
import hashlib
import json
from pathlib import Path
import unittest

from connected_enterprise.runner import identity

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "docs/completion015"
DELTA = ROOT / "evidence/completion015/qualification/COMPOSED_RELEASE_DELTA.json"

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

class PublicationBindingTests(unittest.TestCase):
    def setUp(self):
        self.publication = read(PAPERS / "PUBLICATION.json")
        self.delta = read(DELTA)
        self.binding = self.delta["pr30_publication_binding"]
        self.prior = read(ROOT / self.binding["prior_records"]["publication"]["path"])
        self.prior_delta = read(ROOT / self.binding["prior_records"]["composed_release_delta"]["path"])

    def test_current_publication_matches_actual_source_identity(self):
        current = identity(ROOT)
        self.assertEqual(current["sha256"], self.publication["source_sha256"])
        self.assertEqual(current["sha256"], self.delta["release_qualification_source_sha256"])
        self.assertEqual(current["sha256"], self.binding["current_source_sha256"])
        self.assertEqual(len(current["files"]), self.delta["release_identity_files"])

    def test_exact_prior_source_recovered_by_removing_only_added_planner(self):
        current = identity(ROOT)
        files = dict(current["files"])
        added = self.binding["added_identity_file"]
        self.assertEqual(files.pop(added["path"]), added["sha256"])
        self.assertEqual(canonical_sha(files), self.prior["source_sha256"])
        self.assertEqual(len(files), self.prior_delta["release_identity_files"])
        self.assertEqual(self.delta["release_identity_files"], self.prior_delta["release_identity_files"] + 1)

    def test_embedded_and_external_release_delta_are_identical(self):
        self.assertEqual(self.publication["release_source_delta"], self.delta)
        old = self.prior_delta["changed_or_added_identity_files"]
        new = self.delta["changed_or_added_identity_files"]
        self.assertEqual(set(new) - set(old), {"portfolio_scale/staged_coupling.py"})
        for path, value in old.items():
            self.assertEqual(new[path], value)
        self.assertEqual(self.delta["performance016"], self.prior_delta["performance016"])

    def test_prior_records_remain_byte_exact(self):
        for record in self.binding["prior_records"].values():
            path = ROOT / record["path"]
            self.assertFalse(path.is_symlink())
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record["sha256"])
            git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            self.assertEqual(git_blob, record["git_blob"])

    def test_historical_paper_and_failure_scope_are_unchanged(self):
        allowed_changes = {"source_sha256", "source_binding_scope", "release_source_delta"}
        self.assertEqual(
            {k: v for k, v in self.publication.items() if k not in allowed_changes},
            {k: v for k, v in self.prior.items() if k not in allowed_changes})
        for name, digest in self.prior["files"].items():
            self.assertEqual(Path(name).name, name)
            self.assertEqual(sha(PAPERS / name), digest)
        self.assertEqual(sha(PAPERS / "PDF_QA.json"), self.prior["pdf_qa_sha256"])
        self.assertIn("do not retrospectively qualify", self.publication["source_binding_scope"])
        self.assertIn("does not establish that the paper exercised", self.publication["source_binding_scope"])

    def test_binding_regression_and_metadata_do_not_enter_operating_identity(self):
        files = identity(ROOT)["files"]
        excluded = ["tests/test_publication_binding.py", "docs/completion015/PUBLICATION.json",
                    "evidence/completion015/qualification/COMPOSED_RELEASE_DELTA.json"]
        excluded += [r["path"] for r in self.binding["prior_records"].values()]
        for path in excluded:
            self.assertNotIn(path, files)

if __name__ == "__main__":
    unittest.main()
