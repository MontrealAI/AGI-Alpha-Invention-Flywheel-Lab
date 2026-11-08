"""Offline public-document passage witness, not legal/commercial/identity assurance.

Source integrity is hash-to-supplied-bytes, NOT proof of official issuer signature.
Use only for read-only public documents. No enterprise accounts or private records.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ALLOWED = {
    "tbs-directive-2025": (
        "https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=32592",
        "2025-06-24"),
    "ssc-challenge-2026": (
        "https://www.ised-isde.canada.ca/site/innovative-solutions-canada/en/"
        "artificial-intelligence-ai-decision-making-process-visibility-traceability-and-compliance-governance",
        "2026-10-30"),
}
CLAIMS = (
    ("A0", "tbs-directive-2025", "6.1.1", "6.1.2",
     "Completing, approving and publishing the final results"),
    ("A1", "tbs-directive-2025", "6.3.2", "6.3.3",
     "Monitoring the outcomes of the automated decision system"),
    ("A2", "ssc-challenge-2026", "Allow for authorised reviewers",
     "Support the assessment and reassessment of risks",
     "validate reject, modify or annotate findings"),
)
MAX_BYTES = 2 * 1024 * 1024
BAD_FORMAT = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(data):
    return sha256(data).hexdigest()


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.body = False
        self.suppression = []
    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.body = True
        if tag in ("script", "style", "noscript", "svg", "template"):
            self.suppression.append(tag)
    def handle_endtag(self, tag):
        if self.suppression and tag == self.suppression[-1]:
            self.suppression.pop()
        if tag == "body":
            self.body = False
    def handle_data(self, data):
        if self.body and not self.suppression:
            self.parts.append(data)


def norm(value):
    if type(value) is not str or not value.strip() or any(c in value for c in BAD_FORMAT):
        raise ValueError("INVALID_TEXT_OR_INVISIBLE_CHAR")
    return " ".join(unicodedata.normalize("NFKC", unescape(value)).split())


def visible(blob):
    if type(blob) is not bytes or not blob or len(blob) > MAX_BYTES:
        raise ValueError("INVALID_SOURCE_BYTES")
    parser = VisibleHTML()
    parser.feed(blob.decode("utf-8", errors="strict"))
    parser.close()
    return norm(" ".join(parser.parts))


def bounded_quote(text, anchor, stop, quote):
    a, b, q = norm(anchor), norm(stop), norm(quote)
    if any(text.count(item) != 1 for item in (a, b)):
        raise ValueError("MISSING_OR_DUPLICATE_ANCHOR")
    start, end = text.find(a) + len(a), text.find(b)
    if end <= start or q not in text[start:end]:
        raise ValueError("QUOTE_NOT_IN_BOUND_SECTION")
    return dict(start=start, end=end, quote=q)


def document(ident, url, blob):
    if ident not in ALLOWED or url != ALLOWED[ident][0]:
        raise ValueError("UNREGISTERED_DOCUMENT_OR_URL")
    return dict(id=ident, url=url, published_version=ALLOWED[ident][1],
                sha256=sha(blob), bytes=len(blob), text=visible(blob))


def verify_claims(documents, claims):
    if type(documents) is not dict or type(claims) not in (tuple, list):
        raise ValueError("INVALID_INPUT")
    if len(set(documents)) != len(documents):
        raise ValueError("DUPLICATE_DOCUMENT")
    keys = set()
    rows = []
    for claim in claims:
        if type(claim) is not dict or set(claim) != {
            "id", "document", "url", "source_sha256", "anchor", "stop", "quote"
        }:
            raise ValueError("INVALID_CLAIM_SCHEMA")
        key = claim["id"]
        if type(key) is not str or not key or key in keys:
            raise ValueError("DUPLICATE_CLAIM_ID")
        keys.add(key)
        doc = documents.get(claim["document"])
        if doc is None or claim["url"] != doc["url"]:
            raise ValueError("DOCUMENT_REFERENCE_MISMATCH")
        if claim["source_sha256"] != doc["sha256"]:
            raise ValueError("STALE_OR_SWAPPED_SOURCE")
        location = bounded_quote(doc["text"], claim["anchor"],
                                 claim["stop"], claim["quote"])
        rows.append(dict(id=key, document=doc["id"], source_sha256=doc["sha256"],
                         section_start=norm(claim["anchor"]), section_end=norm(claim["stop"]),
                         quote_sha256=sha(location["quote"].encode("utf-8")),
                         status="EXACT_PASSAGE_FOUND_NOT_SEMANTICALLY_VERIFIED"))
    return sorted(rows, key=lambda r: r["id"])


def make_claim(code, doc, anchor, stop, quote):
    return dict(id=code, document=doc["id"], url=doc["url"],
                source_sha256=doc["sha256"], anchor=anchor, stop=stop, quote=quote)


def packet(documents, claims):
    proof = verify_claims(documents, claims)
    payload = dict(schema="public-regulatory-citation097/v1",
                   evidence_tier="PUBLIC_BYTES_LOCAL_INTEGRITY_ONLY_NOT_ORIGIN_AUTHENTICATION",
                   sources=[{k: doc[k] for k in ("id", "url", "published_version", "sha256", "bytes")}
                            for _, doc in sorted(documents.items())],
                   accepted_claims=proof, accepted=len(proof),
                   legal_assessment=False, buyer_acceptance=False, real_commerce=False)
    return dict(**payload, packet_sha256=sha(canonical(payload)))


def verify_packet(result, documents, claims):
    expected = packet(documents, claims)
    if result != expected:
        raise ValueError("PACKET_OR_SOURCE_REPLAY_MISMATCH")
    return True


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target, start = urlsplit(newurl), urlsplit(req.full_url)
        if (target.scheme != "https" or target.hostname != start.hostname
                or target.port is not None or target.username is not None):
            raise ValueError("UNAUTHORIZED_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def retrieve(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.port is not None or p.username is not None or p.password:
        raise ValueError("UNREGISTERED_OR_UNSAFE_URL")
    if url not in {v[0] for v in ALLOWED.values()}:
        raise ValueError("UNREGISTERED_OR_UNSAFE_URL")
    opener = build_opener(SameHostRedirect)
    with opener.open(Request(url, headers={"User-Agent": "AGI-Alpha-public-source-research/1.0"}),
                     timeout=15) as response:
        if urlsplit(response.geturl()).hostname != p.hostname:
            raise ValueError("UNAUTHORIZED_REDIRECT")
        blob = response.read(MAX_BYTES + 1)
    if not blob or len(blob) > MAX_BYTES:
        raise ValueError("INVALID_SOURCE_BYTES")
    return blob


def observe(output):
    """One registered attempt per public URL; no retries or replacement sources."""
    start_wall, start_cpu = time.monotonic(), time.process_time()
    docs, failures = {}, []
    for ident, (url, _) in ALLOWED.items():
        try:
            docs[ident] = document(ident, url, retrieve(url))
        except Exception as exc:
            failures.append(dict(document=ident, error=type(exc).__name__,
                                 detail=str(exc)[:200]))
    observed = {"schema": "public-regulatory-citation097/observation-v1",
                "observed_utc": datetime.now(timezone.utc).isoformat(),
                "attempted": list(ALLOWED), "failures": failures,
                "sources": [{k: v[k] for k in ("id", "url", "sha256", "bytes")}
                            for _, v in sorted(docs.items())]}
    if not failures:
        claims = [make_claim(code, docs[ident], a, b, q)
                  for code, ident, a, b, q in CLAIMS]
        try:
            observed["packet"] = packet(docs, claims)
            verify_packet(observed["packet"], docs, claims)
            observed["accepted"] = True
        except Exception as exc:
            observed["failures"].append(dict(document="cross-source",
                                            error=type(exc).__name__, detail=str(exc)[:200]))
    observed.setdefault("accepted", False)
    observed["measured_process_cpu_seconds"] = round(time.process_time() - start_cpu, 6)
    observed["measured_wall_seconds"] = round(time.monotonic() - start_wall, 6)
    observed["host_model_account_billing_usd"] = None
    path = Path(output)
    if path.exists():
        raise ValueError("REFUSE_OVERWRITE_OLDER_RESULT")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(observed) + b"\n")
    return 0 if observed["accepted"] else 1


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["observe"])
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    return observe(a.output)


if __name__ == "__main__":
    sys.exit(main())
