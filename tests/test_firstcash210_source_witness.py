"""FIRSTCASH210 adversarial offline checks; live pinned-source fetch is separate CI evidence."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("firstcash210", ROOT / "tools/firstcash210_source_witness.py")
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)
SAMPLE = b"# Synthetic source, not evidence\n"  # Never presented as the remote document.


class FakeResponse:
    def __init__(self, body=SAMPLE, status=200, url=kit.RAW_URL, reported_length=None):
        self.stream = BytesIO(body)
        self.status = status
        self.url = url
        self.headers = {"Content-Length": str(len(body) if reported_length is None else reported_length)}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()

    def read(self, size):
        return self.stream.read(size)

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class SourceWitnessTests(unittest.TestCase):
    def use_fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name) / "bundle"

    def test_fixed_source_is_full_commit_and_registered_path(self):
        self.assertEqual(kit.validate_source_url(kit.SOURCE_URL), kit.RAW_URL)
        self.assertEqual(len(kit.COMMIT), 40)
        self.assertEqual(kit.EXPECTED_BLOB, "184291fa360326fe3cb44b213b74053ba486817a")

    def test_unpinned_pr_is_not_independent_source(self):
        with self.assertRaises(kit.Refusal):
            kit.validate_source_url("https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/506")

    def test_reject_host_traversal_and_mutable_refs(self):
        bad = [
            kit.SOURCE_URL + "?download=1",
            kit.SOURCE_URL + "#L1",
            kit.SOURCE_URL.replace("https:", "http:"),
            kit.SOURCE_URL.replace("github.com", "github.com.evil.org"),
            kit.SOURCE_URL.replace("github.com/", "user:password@github.com/"),
            kit.SOURCE_URL.replace(kit.COMMIT, "main"),
            kit.SOURCE_URL.replace(kit.COMMIT, kit.COMMIT[:8]),
            kit.SOURCE_URL.replace("campaign/unseen-first-cash-206/ADMISSION.md", "../ADMISSION.md"),
            "https://localhost/secret",
            "file:///etc/passwd",
            "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/" + kit.COMMIT + "/other",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(kit.Refusal):
                kit.validate_source_url(url)

    def test_one_request_bounded_and_blob_verified_injection(self):
        opener = FakeOpener(FakeResponse())
        with patch.object(kit, "EXPECTED_BLOB", kit.git_blob(SAMPLE)):
            data = kit.fetch_public_source(opener=opener)
        self.assertEqual(data, SAMPLE)
        self.assertEqual(opener.calls, [(kit.RAW_URL, 12)])

    def test_refuse_redirect_disguised_as_success(self):
        opener = FakeOpener(FakeResponse(url="https://example.org/misleading"))
        with self.assertRaisesRegex(kit.Refusal, "UNEXPECTED_HTTP_SOURCE"):
            kit.fetch_public_source(opener=opener)

    def test_refuse_http_non_200(self):
        with self.assertRaisesRegex(kit.Refusal, "UNEXPECTED_HTTP_SOURCE"):
            kit.fetch_public_source(opener=FakeOpener(FakeResponse(status=206)))

    def test_refuse_wrong_or_modified_pinned_blob(self):
        with self.assertRaisesRegex(kit.Refusal, "PINNED_GIT_BLOB_MISMATCH"):
            kit.fetch_public_source(opener=FakeOpener(FakeResponse()))

    def test_refuse_content_length_and_actual_oversize(self):
        with self.assertRaisesRegex(kit.Refusal, "OVERSIZE_SOURCE"):
            kit.fetch_public_source(opener=FakeOpener(FakeResponse(reported_length=kit.MAX_BYTES + 1)))
        with self.assertRaisesRegex(kit.Refusal, "EMPTY_OR_OVERSIZE_SOURCE"):
            kit.fetch_public_source(opener=FakeOpener(FakeResponse(body=b"x" * (kit.MAX_BYTES + 1), reported_length=0)))

    def test_refuse_network_failure_not_retry(self):
        opener = FakeOpener(TimeoutError("network unavailable"))
        with self.assertRaisesRegex(kit.Refusal, "FETCH_FAILED"):
            kit.fetch_public_source(opener=opener)
        self.assertEqual(len(opener.calls), 1)

    def test_refuse_empty_source(self):
        with self.assertRaisesRegex(kit.Refusal, "EMPTY_OR_OVERSIZE_SOURCE"):
            kit.fetch_public_source(opener=FakeOpener(FakeResponse(body=b"")))

    def test_synthetic_positive_offline_copy_replay(self):
        output = self.use_fixture()
        with patch.object(kit, "EXPECTED_BLOB", kit.git_blob(SAMPLE)):
            witness = kit.create_bundle(output, SAMPLE, "2026-11-21T11:00:00Z")
            self.assertEqual(kit.verify_bundle(output)["source_sha256"], hashlib.sha256(SAMPLE).hexdigest())
            self.assertEqual(witness["scope"],
                             "PUBLIC_PINNED_SOURCE_BYTES_ONLY_NOT_INDEPENDENT_FACT_OR_COMMERCE")
            with self.assertRaisesRegex(kit.Refusal, "OUTPUT_MUST_NOT_EXIST"):
                kit.create_bundle(output, SAMPLE, "2026-11-21T11:00:00Z")

    def test_refuse_tampered_local_source(self):
        output = self.use_fixture()
        with patch.object(kit, "EXPECTED_BLOB", kit.git_blob(SAMPLE)):
            kit.create_bundle(output, SAMPLE, "2026-11-21T11:00:00Z")
            (output / "SOURCE.md").write_bytes(SAMPLE + b"modified")
            with self.assertRaisesRegex(kit.Refusal, "PINNED_GIT_BLOB_MISMATCH"):
                kit.verify_bundle(output)

    def test_refuse_manifest_rewrite_and_duplicate_json(self):
        output = self.use_fixture()
        with patch.object(kit, "EXPECTED_BLOB", kit.git_blob(SAMPLE)):
            kit.create_bundle(output, SAMPLE, "2026-11-21T11:00:00Z")
            p = output / "WITNESS.json"
            original = p.read_bytes()
            p.write_bytes(original.replace(b"PUBLIC_PINNED_SOURCE_BYTES_ONLY_NOT_INDEPENDENT_FACT_OR_COMMERCE",
                                           b"BUYER_PAID_AND_ACCEPTED"))
            with self.assertRaisesRegex(kit.Refusal, "WITNESS_REPLAY_MISMATCH"):
                kit.verify_bundle(output)
            p.write_bytes(original.replace(b'"schema":', b'"schema":"fake","schema":'))
            with self.assertRaisesRegex(kit.Refusal, "DUPLICATE_JSON_KEY"):
                kit.verify_bundle(output)

    def test_reject_symlink_to_alternate_public_document(self):
        output = self.use_fixture()
        with patch.object(kit, "EXPECTED_BLOB", kit.git_blob(SAMPLE)):
            kit.create_bundle(output, SAMPLE, "2026-11-21T11:00:00Z")
            p = output / "SOURCE.md"
            alternative = output.parent / "other.md"
            alternative.write_bytes(SAMPLE)
            p.unlink()
            p.symlink_to(alternative)
            with self.assertRaisesRegex(kit.Refusal, "UNSAFE_OR_MISSING_FILE"):
                kit.verify_bundle(output)


if __name__ == "__main__":
    unittest.main()
