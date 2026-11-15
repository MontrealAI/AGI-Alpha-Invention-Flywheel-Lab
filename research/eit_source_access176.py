"""EIT176: preregistered one-request, one-header public-source access diagnostic.

Not a scientific measurement, inference test, or financial operating interface.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "agi-alpha/eit176-single-header-access-diagnostic/v1"
SOURCE_URL = "https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content"
USER_AGENT = "AGI-ALPHA-EIT175-fixed-science-preflight/1"
ACCEPT = "*/*"  # The only intentional difference from the immutable EIT175 GET.
EXPECTED_SIZE = 12_482_688
EXPECTED_MD5 = "658694f69f64075b6fefec2e2c597131"
MAX_DOWNLOAD = 20 * 1024 * 1024


class Refused(ValueError):
    pass


def _permitted(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname == "zenodo.org" and parsed.port in (None, 443)


class SameZenodoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _permitted(newurl):
            raise Refused("UNAUTHORIZED_REDIRECT")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def exact_request():
    return Request(SOURCE_URL, headers={"Accept": ACCEPT, "User-Agent": USER_AGENT}, method="GET")


def verify_bytes(raw):
    if type(raw) is not bytes or len(raw) != EXPECTED_SIZE:
        raise Refused("EXACT_PUBLISHER_LENGTH_MISMATCH")
    if hashlib.md5(raw, usedforsecurity=False).hexdigest().lower() != EXPECTED_MD5:
        raise Refused("PUBLISHER_MD5_MISMATCH")
    return {"archive_size": len(raw), "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "archive_md5": EXPECTED_MD5}


def one_request(opener=None):
    if opener is None:
        opener = build_opener(SameZenodoRedirect())
    # The sole network operation: no alternate source, retry, range, or header ladder.
    with opener.open(exact_request(), timeout=60) as response:
        if response.status != 200 or not _permitted(response.geturl()):
            raise Refused("HTTP_OR_SOURCE_ORIGIN_CHANGED")
        raw = response.read(MAX_DOWNLOAD + 1)
    return verify_bytes(raw)


def run(output):
    target = Path(output).absolute()
    # Ensure a previously used receipt cannot cause another network attempt.
    if target.exists() or target.is_symlink():
        raise Refused("CREATE_ONLY_RECEIPT_REQUIRED")
    target.parent.mkdir(parents=True, exist_ok=True)
    started_wall = time.monotonic()
    started_cpu = time.process_time()
    receipt = {"schema": SCHEMA, "protocol_commit": "9d25e77ab479aee57c9c51379b9bbc9976084139",
               "parent_main": "75f8f722c923e448d8f1fb44aa762b6ba0cd5a46",
               "immutable_eit175_failed_workflow": 43747709304,
               "request_url": SOURCE_URL, "request_accept": ACCEPT,
               "status": "FAILED", "archive_sha256": None, "archive_size": None,
               "physical_reconstruction_tested": False, "real_commerce_claim": False}
    try:
        result = one_request()
        receipt.update(result)
        receipt["status"] = "ARCHIVE_BYTES_ACCESSIBLE"
        receipt["failure_code"] = None
    except HTTPError as exc:
        receipt["failure_code"] = "HTTP_STATUS_" + str(exc.code)
    except Refused as exc:
        receipt["failure_code"] = str(exc)
    except URLError:
        receipt["failure_code"] = "NETWORK_URL_ERROR"
    except (OSError, TimeoutError, ValueError):
        receipt["failure_code"] = "NETWORK_OR_SOURCE_ERROR"
    receipt["wall_seconds"] = time.monotonic() - started_wall
    receipt["self_cpu_seconds"] = time.process_time() - started_cpu
    payload = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    with os.fdopen(os.open(target, flags, 0o644), "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return 0 if receipt["status"] == "ARCHIVE_BYTES_ACCESSIBLE" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    return run(parser.parse_args().output)


if __name__ == "__main__":
    sys.exit(main())
