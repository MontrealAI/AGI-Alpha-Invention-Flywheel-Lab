"""A single prospective source diagnostic; NEVER a redo of ActiveTender096's failed row.

Raw public bytes are transient. Output is a compact error/provenance receipt only.
No accounts, external contacts, bids, lead scoring, purchases or retries.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from research import active_tender096 as prior

TARGET = "ocds-h6vhtk-0692e8"
URL = prior.RECORD_PREFIX + TARGET
PATH = prior.RECORD_PATH + TARGET
MAX_BYTES = prior.MAX_BYTES
MAX_REQUESTS = 1


class NoRedirect(HTTPRedirectHandler):
    """Never send a second request to a redirected destination."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_mime(s):
    s = (s or "").split(";", 1)[0].strip().lower()
    return s if s in ("application/json", "application/ocds+json", "text/html") else "other_or_unknown"


def first_token(raw):
    b = raw.lstrip()[:1]
    return {b"{": "json_object", b"[": "json_array", b"<": "html_or_xml"}.get(b, "other_or_empty")


def classify(raw, expected_sha):
    """Check strict source format without exposing any source body."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        return {"strict_parse": "FAILED", "diagnostic": "SOURCE_SIZE"}
    if sha256(raw).hexdigest() != expected_sha:
        return {"strict_parse": "FAILED", "diagnostic": "SOURCE_HASH_CHANGED"}
    try:
        strict = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=prior.unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")),
        )
    except UnicodeDecodeError:
        return {"strict_parse": "FAILED", "diagnostic": "INVALID_UTF8"}
    except json.JSONDecodeError as exc:
        return {"strict_parse": "FAILED", "diagnostic": "MALFORMED_SOURCE_JSON",
                "json_line": exc.lineno, "json_column": exc.colno,
                "json_offset": exc.pos, "json_error": exc.msg[:80]}
    except ValueError as exc:
        # Only expose known local constant reasons; never include raw input fields.
        reason = str(exc)
        return {"strict_parse": "FAILED",
                "diagnostic": reason if reason in ("DUPLICATE_JSON_KEY", "NONFINITE_JSON") else "JSON_VALUE_ERROR"}
    if type(strict) is not dict:
        return {"strict_parse": "FAILED", "diagnostic": "NOT_JSON_OBJECT"}
    try:
        prior.decode(raw, expected_sha)
    except ValueError as exc:
        return {"strict_parse": "FAILED",
                "diagnostic": str(exc) if str(exc) in ("UNVERIFIED_OPEN_LICENCE", "AMBIGUOUS_OR_INVALID_TIME", "INVALID_TIME") else "SOURCE_SCHEMA_ERROR"}
    # Parsing a licensed source does not assert its content is a verified lead.
    try:
        prior.assess_record(raw, expected_sha, TARGET, utc_now(), utc_now())
        return {"strict_parse": "SUCCEEDED", "diagnostic": "PRIOR_STRICT_RECORD_PARSER_COMPATIBLE"}
    except ValueError:
        return {"strict_parse": "FAILED", "diagnostic": "PRIOR_RECORD_SCHEMA_INCOMPATIBLE"}


def fetch_one(opener=None):
    opener = opener if opener is not None else build_opener(NoRedirect())
    req = Request(URL, headers={"User-Agent": "AGI-Alpha-Source-Diagnostic/1.0",
                                "Accept": "application/json"})
    # No automatic retry or redirected GET.
    with opener.open(req, timeout=25) as resp:
        url = urlsplit(resp.geturl())
        if (resp.status != 200 or url.scheme != "https" or
                url.netloc != "www.find-tender.service.gov.uk" or
                url.path != PATH or url.query or url.fragment):
            raise ValueError("UNEXPECTED_HTTP_DESTINATION_OR_STATUS")
        mime = safe_mime(resp.headers.get("Content-Type", ""))
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("SOURCE_SIZE")
        return raw, mime


def diagnose(out, fetcher=None):
    destination = Path(out)
    if destination.exists() or destination.is_symlink():
        raise ValueError("OUTPUT_EXISTS_NO_REPLACEMENT")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "agi-alpha/active-tender096-single-record-diagnostic/v1",
        "fixed_ocid": TARGET, "fixed_url": URL, "requests_performed_max": MAX_REQUESTS,
        "capture_utc": None, "retrieval": "FAILED",
        "original_096_live_result": "FAILED_UNCHANGED",
        "original_selected": 5, "original_parsed": 4, "original_failed": 1,
        "historical_raw_source_retained": False,
        "same_bytes_as_historical": "UNVERIFIABLE",
        "raw_source_published": False, "authorized_bid_or_purchase": False,
        "native_account_operations": 0, "collected_revenue": None,
        "trailing_365_profit": None, "decision": "RESEARCH_ONLY_NO_BID",
    }
    try:
        raw, mime = (fetcher or fetch_one)()
        digest = sha256(raw).hexdigest()
        result.update({"capture_utc": utc_now(), "retrieval": "SUCCEEDED",
                       "source_sha256": digest, "source_bytes": len(raw),
                       "source_mime_class": mime, "first_nonwhitespace_token": first_token(raw),
                       **classify(raw, digest)})
    except (HTTPError, URLError, ValueError, TimeoutError, OSError) as exc:
        kind = "HTTP_ERROR" if isinstance(exc, HTTPError) else type(exc).__name__.upper()
        result["retrieval_failure_class"] = kind
        if isinstance(exc, HTTPError):
            result["http_status"] = exc.code
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = diagnose(args.out)
    if result["retrieval"] != "SUCCEEDED":
        raise SystemExit("SINGLE_SOURCE_DIAGNOSTIC_RETRIEVAL_FAILED")


if __name__ == "__main__":
    main()
