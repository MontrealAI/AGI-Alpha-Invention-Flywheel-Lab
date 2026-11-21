"""Frozen FIRSTCASH208 public-readonly acceptance — no live network in these tests."""
import unittest
from urllib.error import HTTPError, URLError

from scripts.firstcash208_shop_preflight import URL, MAX_BYTES, classify, probe, product_identity


class FakeResponse:
    def __init__(self, *, code=200, url=URL, body=b"", content_type="text/html"):
        self.code, self.url, self.body = code, url, body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def getcode(self):
        return self.code

    def read(self, amount):
        return self.body[:amount]


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response, self.error = response, error
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class ShopPreflightTests(unittest.TestCase):
    def test_visible_official_product_identity_and_price_metadata(self):
        body = b'<html><head><title>FRONTIER OMEGA - THE UNSEEN ADVANTAGE</title><meta property="product:price:amount" content="2995.00"><meta property="product:price:currency" content="CAD"></head></html>'
        transport = FakeOpener(FakeResponse(body=body))
        r = probe(opener=transport, timestamp="2026-11-21T06:00:00+00:00")
        self.assertEqual(r["status"], "PUBLIC_PRODUCT_VISIBLE")
        self.assertEqual(r["public_price_text"], "CAD 2995.00")
        self.assertEqual(r["paying_customers"], 0)
        self.assertIsNone(r["verified_collected_revenue"])
        self.assertFalse(r["paid_checkout_verified"])
        self.assertFalse(r["deployment_go"])
        self.assertEqual(r["bytes_read"], len(body))
        self.assertNotIn("html", str(r).lower())
        self.assertEqual(transport.requests[0][1], 20)

    def test_missing_product_identity(self):
        r = classify(200, URL, "text/html", b"<html><head><title>Unrelated catalog</title></head></html>")
        self.assertEqual(r["status"], "PUBLIC_PRODUCT_NOT_CONFIRMED")

    def test_generic_200_error_not_product(self):
        r = classify(200, URL, "text/html", b"<html><title>Just a moment -- Frontier - The Unseen Advantage</title></html>")
        self.assertEqual(r["status"], "PUBLIC_PRODUCT_NOT_CONFIRMED")

    def test_http_404_inaccessible_not_buyer_outage(self):
        transport = FakeOpener(error=HTTPError(URL, 404, "Not Found", {}, None))
        r = probe(opener=transport, timestamp="2026-11-21T06:00:00+00:00")
        self.assertEqual(r["status"], "INACCESSIBLE_FROM_RUNNER")
        self.assertEqual(r["http_status"], 404)
        self.assertEqual(r["error_class"], "HTTPError")
        self.assertFalse(r["deployment_go"])

    def test_off_host_final_redirect_fail_closed(self):
        body = b"<html><title>FRONTIER - THE UNSEEN ADVANTAGE</title></html>"
        result = classify(200, "https://another.example/sale", "text/html", body)
        self.assertEqual(result["status"], "INACCESSIBLE_FROM_RUNNER")
        r = probe(opener=FakeOpener(FakeResponse(url="https://another.example/sale", body=body)))
        self.assertEqual(r["status"], "INACCESSIBLE_FROM_RUNNER")
        self.assertFalse(r["final_url_matches_registered_host"])

    def test_network_error_not_asserted_shop_down(self):
        r = probe(opener=FakeOpener(error=URLError("test-only DNS failure")))
        self.assertEqual(r["status"], "INACCESSIBLE_FROM_RUNNER")
        self.assertEqual(r["error_class"], "URLError")
        self.assertNotIn("DNS failure", str(r))

    def test_visible_identity_with_no_metadata_has_unknown_price(self):
        body = "<html><h1>🌌 FRONTIER Ω — THE UNSEEN ADVANTAGE</h1><p>Pay $2,995 today</p></html>".encode()
        r = classify(200, URL, "text/html; charset=utf-8", body)
        self.assertEqual(r["status"], "PUBLIC_PRODUCT_VISIBLE")
        self.assertIsNone(r["public_price_text"])

    def test_size_limit_no_payload_retention_or_false_product(self):
        body = b"<h1>FRONTIER -- THE UNSEEN ADVANTAGE</h1>" + b"x" * MAX_BYTES
        r = probe(opener=FakeOpener(FakeResponse(body=body)))
        self.assertEqual(r["status"], "PUBLIC_PRODUCT_NOT_CONFIRMED")
        self.assertIsNone(r["body_sha256"])
        self.assertFalse(r["deployment_go"])

    def test_invalid_mime_must_not_validate(self):
        body = b"<h1>FRONTIER -- THE UNSEEN ADVANTAGE</h1>"
        self.assertEqual(classify(200, URL, "text/plain", body)["status"], "PUBLIC_PRODUCT_NOT_CONFIRMED")

    def test_identity_anchor_does_not_accept_disconnected_buzzwords(self):
        self.assertFalse(product_identity("FRONTIER " + "x" * 140 + " UNSEEN ADVANTAGE"))


if __name__ == "__main__":
    unittest.main()
