#!/usr/bin/env python3
"""Read-only public product-page preflight. No order, login, form, cookie or payout calls."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

URL = "https://www.quebecartificialintelligence.com/shop/p/frontier-the-unseen-advantage"
MAX_BYTES = 512 * 1024
MAX_REDIRECTS = 3


class RedirectBlocked(Exception):
    """No unexpected origin or excess redirect may be contacted."""


def allowed(url: str) -> bool:
    p = urlsplit(url)
    return p.scheme == "https" and p.hostname == "www.quebecartificialintelligence.com" and p.port in (None, 443) and not p.username and not p.password


class LockedRedirects(HTTPRedirectHandler):
    def __init__(self):
        super().__init__()
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > MAX_REDIRECTS or not allowed(newurl):
            raise RedirectBlocked("redirect limit or host policy")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_h1 = False
        self.title = []
        self.headings = []
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
            self.headings.append("")
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:title", "twitter:title", "product:price:amount", "product:price:currency"):
                self.metadata[key] = str(a.get("content") or "")[:180]

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, value):
        if self.in_title:
            self.title.append(value)
        if self.in_h1 and self.headings:
            self.headings[-1] += value


def product_identity(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.upper())
    return bool(re.search(r"\bFRONTIER\b.{0,110}\bUNSEEN\s+ADVANTAGE\b", normalized))


def classify(status: int, final_url: str, content_type: str, body: bytes) -> dict:
    output = {"status": "PUBLIC_PRODUCT_NOT_CONFIRMED", "public_price_text": None}
    if status != 200 or not allowed(final_url):
        output["status"] = "INACCESSIBLE_FROM_RUNNER"
        return output
    if len(body) > MAX_BYTES or "html" not in content_type.lower():
        return output
    html = body.decode("utf-8", errors="replace")
    h = Headings()
    h.feed(html)
    labels = ["".join(h.title), *h.headings, h.metadata.get("og:title", ""), h.metadata.get("twitter:title", "")]
    blocked = ("captcha", "access denied", "checking your browser", "just a moment", "page not found", "404 not found")
    if any(b in (" ".join(labels)).lower() for b in blocked):
        return output
    if not any(product_identity(s[:200]) for s in labels):
        return output
    output["status"] = "PUBLIC_PRODUCT_VISIBLE"
    value = h.metadata.get("product:price:amount", "")
    currency = h.metadata.get("product:price:currency", "")
    if re.fullmatch(r"\d{1,8}(?:\.\d{1,2})?", value) and currency in ("CAD", "USD"):
        output["public_price_text"] = currency + " " + value
    return output


def probe(opener=None, timestamp=None) -> dict:
    when = timestamp or datetime.now(timezone.utc).isoformat()
    result = {
        "schema": "firstcash208-public-readonly/v1",
        "source_commit": os.environ.get("FIRSTCASH208_SOURCE_SHA") or os.environ.get("GITHUB_SHA") or None,
        "observed_utc": when,
        "requested_url": URL,
        "final_url_matches_registered_host": None,
        "http_status": None,
        "status": "INACCESSIBLE_FROM_RUNNER",
        "public_price_text": None,
        "bytes_read": 0,
        "body_sha256": None,
        "error_class": None,
        "paying_customers": 0,
        "verified_collected_revenue": None,
        "paid_checkout_verified": False,
        "deployment_go": False,
        "scope": "Public read-only availability preflight; not browser, merchant or payment validation",
    }
    transport = opener or build_opener(LockedRedirects())
    req = Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; FIRSTCASH208-ReadOnlyResearch/1.0)", "Accept": "text/html"})
    try:
        with transport.open(req, timeout=20) as response:
            final = response.geturl()
            result["final_url_matches_registered_host"] = allowed(final)
            status = response.getcode()
            result["http_status"] = status
            if status != 200 or not allowed(final):
                return result
            content_type = response.headers.get("Content-Type", "")
            body = response.read(MAX_BYTES + 1)
            result["bytes_read"] = len(body)
            if len(body) <= MAX_BYTES:
                result["body_sha256"] = hashlib.sha256(body).hexdigest()
            result.update(classify(status, final, content_type, body))
    except HTTPError as exc:
        result["http_status"] = exc.code
        result["error_class"] = "HTTPError"
    except (URLError, TimeoutError, RedirectBlocked, OSError, ValueError) as exc:
        result["error_class"] = type(exc).__name__
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", required=True)
    args = p.parse_args()
    receipt = probe()
    with open(args.receipt, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
