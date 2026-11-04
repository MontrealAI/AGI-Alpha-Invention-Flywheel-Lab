"""Frozen-source diagnostic regressions: not the original 096 acceptance test."""
import hashlib
import json
from pathlib import Path
import tempfile
from unittest import TestCase

from research import active_tender096_diagnostic as d


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    obj = {
        "license": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "records": [{
            "ocid": d.TARGET,
            "releases": [{
                "ocid": d.TARGET, "id": "T1",
                "date": "2026-11-03T00:00:00Z", "tag": ["tender"],
                "tender": {"title": "Public research only", "status": "active",
                           "tenderPeriod": {"endDate": "2026-12-08T12:00:00Z"}},
                "buyer": {"name": "Public organization",
                          "contactPoint": {"email": "SENSITIVE-CONTACT-DO-NOT-EXPORT"}},
            }],
        }],
    }
    return json.dumps(obj).encode()


class SourceDiagnosticTests(TestCase):
    def test_target_is_historical_failed_row_only(self):
        self.assertEqual(d.TARGET, "ocds-h6vhtk-0692e8")
        self.assertTrue(d.URL.endswith(d.TARGET))
        self.assertEqual(d.MAX_REQUESTS, 1)
        self.assertEqual(d.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil.example"), None)

    def test_one_valid_licensed_source_is_parser_compatible_only(self):
        raw = fixture()
        result = d.classify(raw, sha(raw))
        self.assertEqual(result["strict_parse"], "SUCCEEDED")
        self.assertEqual(result["diagnostic"], "PRIOR_STRICT_RECORD_PARSER_COMPATIBLE")

    def test_malformed_truncated_json_reports_exact_error_offset_without_body(self):
        raw = b'{"license":'
        x = d.classify(raw, sha(raw))
        self.assertEqual(x["diagnostic"], "MALFORMED_SOURCE_JSON")
        self.assertGreaterEqual(x["json_offset"], 0)
        self.assertNotIn("source_bytes_content", x)

    def test_html_misserved_as_json_never_becomes_lead(self):
        raw = b"<html>error</html>"
        self.assertEqual(d.first_token(raw), "html_or_xml")
        self.assertEqual(d.classify(raw, sha(raw))["diagnostic"], "MALFORMED_SOURCE_JSON")

    def test_duplicate_key_and_nonfinite_rejected(self):
        for raw, reason in ((b'{"license":"x","license":"y"}', "DUPLICATE_JSON_KEY"),
                            (b'{"license":"x","value":NaN}', "NONFINITE_JSON")):
            with self.subTest(reason=reason):
                self.assertEqual(d.classify(raw, sha(raw))["diagnostic"], reason)

    def test_source_utf8_hash_size_and_licence_controls(self):
        self.assertEqual(d.classify(b"\\xff".decode("unicode_escape").encode("latin-1"), sha(b"\\xff".decode("unicode_escape").encode("latin-1")))["diagnostic"], "INVALID_UTF8")
        raw = fixture()
        self.assertEqual(d.classify(raw, "0" * 64)["diagnostic"], "SOURCE_HASH_CHANGED")
        oversize = b"x" * (d.MAX_BYTES + 1)
        self.assertEqual(d.classify(oversize, sha(oversize))["diagnostic"], "SOURCE_SIZE")
        self.assertEqual(d.classify(b'{"license":"https://not-official.example/"}',
                                    sha(b'{"license":"https://not-official.example/"}'))["diagnostic"], "UNVERIFIED_OPEN_LICENCE")

    def test_one_capture_and_compact_receipt_without_source_or_financial_operations(self):
        raw = fixture()
        calls = []
        def fake_fetch():
            calls.append(d.URL)
            return raw, "application/json"
        with tempfile.TemporaryDirectory() as tmp:
            p = str(Path(tmp) / "one.json")
            x = d.diagnose(p, fetcher=fake_fetch)
            self.assertEqual(calls, [d.URL])
            self.assertEqual(x["retrieval"], "SUCCEEDED")
            self.assertEqual(x["strict_parse"], "SUCCEEDED")
            self.assertEqual(x["original_096_live_result"], "FAILED_UNCHANGED")
            self.assertEqual(x["same_bytes_as_historical"], "UNVERIFIABLE")
            self.assertFalse(x["authorized_bid_or_purchase"])
            self.assertEqual(x["native_account_operations"], 0)
            self.assertEqual(x["decision"], "RESEARCH_ONLY_NO_BID")
            text = Path(p).read_text()
            self.assertNotIn("SENSITIVE-CONTACT", text)
            self.assertNotIn("Public organization", text)
            with self.assertRaisesRegex(ValueError, "OUTPUT_EXISTS_NO_REPLACEMENT"):
                d.diagnose(p, fetcher=fake_fetch)
            self.assertEqual(len(calls), 1)

    def test_transport_failure_stays_failure_without_retry(self):
        calls = []
        def refused():
            calls.append(1)
            raise TimeoutError("timeout")
        with tempfile.TemporaryDirectory() as tmp:
            x = d.diagnose(str(Path(tmp) / "one.json"), fetcher=refused)
            self.assertEqual(calls, [1])
            self.assertEqual(x["retrieval"], "FAILED")
            self.assertEqual(x["retrieval_failure_class"], "TIMEOUTERROR")
            self.assertEqual(x["original_parsed"], 4)
            self.assertEqual(x["original_failed"], 1)

    def test_http_destination_validation_rejects_redirect_and_wrong_origin(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "application/json"}
            def __init__(self, url): self.url = url
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def geturl(self): return self.url
            def read(self, *_): return fixture()
        class FakeOpener:
            def __init__(self, url): self.url=url; self.calls=0
            def open(self, req, timeout): self.calls+=1; return FakeResponse(self.url)
        for url in ("http://www.find-tender.service.gov.uk"+d.PATH,
                    "https://not-official.example"+d.PATH,
                    d.URL+"?next=1"):
            with self.subTest(url=url):
                opener=FakeOpener(url)
                with self.assertRaisesRegex(ValueError, "UNEXPECTED_HTTP_DESTINATION_OR_STATUS"):
                    d.fetch_one(opener)
                self.assertEqual(opener.calls, 1)
