"""Exercise the public document at the private service boundary."""
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path
import sys
import threading
import unittest

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from ignition.server import Service


class PublicFieldRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = Service(None, 0)
        cls.thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.service.shutdown()
        cls.service.server_close()
        cls.thread.join()

    def request(self, path, headers=None):
        with closing(HTTPConnection("127.0.0.1", self.service.server_port)) as client:
            client.request("GET", path, headers=headers or {})
            response = client.getresponse()
            return response.status, response.headers, response.read()

    def test_offline_exhibit_and_opaque_download(self):
        raw = (PRODUCT.parents[1] / "docs/frontier-omega-ignition/continuation/FRONTIER_FIELD.html").read_bytes()
        status, headers, body = self.request("/field?lang=fr&download=1")
        self.assertEqual((status, body), (200, raw))
        self.assertIn("FRONTIER_FIELD.html", headers["Content-Disposition"])
        directives = {item.split()[0]: item.split()[1:] for item in headers["Content-Security-Policy"].split(";") if item.strip()}
        self.assertEqual(directives["connect-src"], ["'none'"])
        self.assertIn("allow-scripts", directives["sandbox"])
        self.assertNotIn("allow-same-origin", directives["sandbox"])
        self.assertEqual(directives["frame-ancestors"], ["'none'"])

    def test_public_navigation_exception_is_confined_to_a_document(self):
        nav = {"Origin": "null", "Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}
        self.assertEqual(self.request("/field", nav)[0], 200)
        self.assertEqual(self.request("/api/status", nav)[0], 403)
        self.assertEqual(self.request("/field", dict(nav, **{"Sec-Fetch-Mode": "cors"}))[0], 403)


if __name__ == "__main__":
    unittest.main()
