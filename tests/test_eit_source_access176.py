"""Offline fixed controls for separate EIT176 HTTP 406 diagnostic; no network."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from research import eit_source_access176 as e


class Reply(BytesIO):
    status = 200
    def geturl(self):
        return e.SOURCE_URL


class Opener:
    def __init__(self, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = []
    def open(self, req, timeout):
        self.calls.append((req, timeout))
        if self.exception:
            raise self.exception
        return self.response


class FixedAccess176Tests(unittest.TestCase):
    def test_exact_one_changed_header_and_get(self):
        req = e.exact_request()
        self.assertEqual(req.full_url, e.SOURCE_URL)
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.get_header("Accept"), "*/*")
        self.assertEqual(req.get_header("User-agent"), e.USER_AGENT)

    def test_one_network_request_no_fallback_on_406(self):
        err = HTTPError(e.SOURCE_URL, 406, "Not Acceptable", {}, None)
        client = Opener(exception=err)
        with self.assertRaises(HTTPError):
            e.one_request(client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][1], 60)

    def test_exact_bytes_success_under_fixture_identity(self):
        raw = b"fixed synthetic byte source"
        client = Opener(Reply(raw))
        with patch.object(e, "EXPECTED_SIZE", len(raw)), patch.object(
            e, "EXPECTED_MD5", hashlib.md5(raw, usedforsecurity=False).hexdigest()
        ):
            v = e.one_request(client)
        self.assertEqual(v["archive_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(client.calls), 1)

    def test_exact_size_refused(self):
        with self.assertRaisesRegex(e.Refused, "EXACT_PUBLISHER_LENGTH"):
            e.verify_bytes(b"incorrect-length")

    def test_same_length_changed_bytes_refused(self):
        raw = b"record"
        with patch.object(e, "EXPECTED_SIZE", len(raw)), patch.object(e, "EXPECTED_MD5", "0" * 32):
            with self.assertRaisesRegex(e.Refused, "PUBLISHER_MD5_MISMATCH"):
                e.verify_bytes(raw)

    def test_non_zenodo_redirect_refused(self):
        handler = e.SameZenodoRedirect()
        with self.assertRaisesRegex(e.Refused, "UNAUTHORIZED_REDIRECT"):
            handler.redirect_request(e.exact_request(), None, 302, "Found", {}, "https://foreign.example/a")
        with self.assertRaisesRegex(e.Refused, "UNAUTHORIZED_REDIRECT"):
            handler.redirect_request(e.exact_request(), None, 302, "Found", {}, "http://zenodo.org/a")

    def test_official_url_origin_and_port_required(self):
        self.assertTrue(e._permitted(e.SOURCE_URL))
        self.assertFalse(e._permitted("https://zenodo.org:444/api/records/24120439"))
        self.assertFalse(e._permitted("https://zenodo.org.evil.example/records"))

    def test_failed_406_is_durable_and_not_a_success(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            e, "one_request", side_effect=HTTPError(e.SOURCE_URL, 406, "Not Acceptable", {}, None)
        ):
            path = Path(tmp) / "receipt.json"
            self.assertEqual(e.run(path), 1)
            import json
            record = json.loads(path.read_text())
            self.assertEqual(record["failure_code"], "HTTP_STATUS_406")
            self.assertEqual(record["status"], "FAILED")
            self.assertIsNone(record["archive_sha256"])
            with self.assertRaisesRegex(e.Refused, "CREATE_ONLY_RECEIPT_REQUIRED"):
                e.run(path)

    def test_success_receipt_not_scientific_claim(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            e, "one_request", return_value={
                "archive_size": e.EXPECTED_SIZE, "archive_sha256": "f" * 64, "archive_md5": e.EXPECTED_MD5
            }
        ):
            path = Path(tmp) / "receipt.json"
            self.assertEqual(e.run(path), 0)
            import json
            record = json.loads(path.read_text())
            self.assertEqual(record["status"], "ARCHIVE_BYTES_ACCESSIBLE")
            self.assertFalse(record["physical_reconstruction_tested"])
            self.assertFalse(record["real_commerce_claim"])


if __name__ == "__main__":
    unittest.main()
