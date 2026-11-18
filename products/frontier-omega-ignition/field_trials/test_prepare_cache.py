"""The CPU preparer can retry a transient read but cannot admit different bytes."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_cache as cache


class Response(io.BytesIO):
    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data) if length is None else length)}

    def geturl(self):
        return "https://release-assets.githubusercontent.com/example?signed=hidden"


class Prefetch(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.dest = self.root / "inputs"
        self.receipt = self.root / "prepare.json"
        self.content = b"fixed public input"
        self.url = "https://github.com/example/release"
        self.asset = ("llama.tar.gz", self.url, len(self.content), hashlib.sha256(self.content).hexdigest())
        self.sleep = self.enterContext(patch.object(cache.time, "sleep"))
        self.open = self.enterContext(patch.object(cache, "build_opener")).return_value.open
        self.enterContext(patch.object(cache, "ASSETS", (self.asset,)))
        self.enterContext(patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}))

    def run_preparation(self, expected):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cache.record_preparation(self.dest, self.receipt), expected)
        raw = self.receipt.read_text()
        self.assertNotIn("signed=hidden", raw)
        result = json.loads(raw)
        self.assertEqual(expected, result["prepared"])
        return result["assets"][0] if result["assets"] else result

    def error(self, status, headers=None):
        return HTTPError(Response(b"").geturl(), status, "failure", headers or {}, None)

    def test_gateway_failure_recovers_once_and_subsequent_use_is_local(self):
        self.open.side_effect = [self.error(502), Response(self.content)]
        record = self.run_preparation(True)
        self.assertEqual(record["name"], self.asset[0])
        self.assertEqual(record["origin"], self.url)
        self.assertEqual(record["status"], "verified_download")
        first, second = record["attempts"]
        self.assertEqual((first["http_status"], first["response_host"]), (502, "release-assets.githubusercontent.com"))
        self.assertEqual(second["received_sha256"], self.asset[3])
        self.sleep.assert_called_once_with(2)
        self.assertEqual(self.run_preparation(True)["status"], "verified_existing")
        self.assertEqual(self.open.call_count, 2)

    def test_wrong_download_and_existing_file_are_quarantined(self):
        wrong = b"x" * len(self.content)
        self.open.return_value = Response(wrong)
        record = self.run_preparation(False)
        self.assertEqual((self.dest / record["attempts"][0]["quarantine"]).read_bytes(), wrong)
        dest = self.dest / self.asset[0]
        self.assertFalse(dest.exists())
        dest.write_bytes(wrong)
        record = self.run_preparation(False)
        self.assertEqual((self.dest / record["quarantine"]).read_bytes(), wrong)
        self.assertFalse(dest.exists())
        self.assertEqual(self.open.call_count, 1)
        self.sleep.assert_not_called()

    def test_failed_transports_are_bounded_and_permanent_statuses_stop(self):
        self.open.side_effect = [self.error(502) for _ in range(3)]
        record = self.run_preparation(False)
        self.assertEqual([attempt["http_status"] for attempt in record["attempts"]], [502, 502, 502])
        for status, headers in [(403, {}), (429, {"Retry-After": "90"})]:
            self.open.side_effect = [self.error(status, headers)]
            record = self.run_preparation(False)
            self.assertEqual(len(record["attempts"]), 1)
            self.assertEqual(record["attempts"][0]["http_status"], status)

    def test_declared_transfer_interruption_restarts_from_the_pinned_origin(self):
        self.open.side_effect = [Response(b"prefix", len(self.content)), Response(self.content)]
        record = self.run_preparation(True)
        self.assertEqual([attempt['bytes_read'] for attempt in record['attempts']], [6, len(self.content)])
        self.assertEqual([call.args[0] for call in self.open.call_args_list], [self.url, self.url])

    def test_unexpected_redirect_and_elapsed_hosted_window_fail_closed(self):
        handler = cache.PublisherRedirect("github.com")
        for target in ("https://example.org/file", "http://release-assets.githubusercontent.com/file", "https://user@github.com/file"):
            with self.assertRaises(ValueError):
                handler.redirect_request(Request(self.url), None, 302, "", {}, target)
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "AGI_JOB_START_EPOCH": "100"}):
            result = self.run_preparation(False)
            self.assertEqual((result["status"], result["stage"]), ("failed", "platform_window"))
        self.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
