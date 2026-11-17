"""Buyer-side exact request and delivery-acceptance helpers.

Run in the BUYER's controlled environment using their pre-registered key and
trusted checker. Neither an operator-supplied signature nor an invented buyer
identity is evidence of genuine independent customer participation.

No payment, Stripe call or production account is created by these helpers.
"""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import stat
import time
import zipfile

from . import checker
from .core import authenticate, canonical, contract, digest, parse, sign


MAX_PACKAGE_BYTES = 20_000_000
MAX_FILES = 32
MAX_TOTAL_UNCOMPRESSED = 30_000_000


def _key(key):
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("BUYER_OWNED_KEY_AT_LEAST_32_BYTES_REQUIRED")
    return key


def sign_request(c, key, *, now=None):
    """Generate a genuine buyer-authored request only in their chosen environment."""
    c = contract(c)
    _key(key)
    now = int(time.time()) if now is None else now
    if type(now) is not int or now >= c["expires_at"]:
        raise ValueError("BUYER_REQUEST_EXPIRED")
    if (c["price_microUSD"] > c["buyer_budget_microUSD"] or
        c["price_microUSD"] >= c["outside_option_microUSD"]):
        raise ValueError("BUYER_BUDGET_OR_OUTSIDE_OPTION_DOES_NOT_JUSTIFY_PURCHASE")
    return sign({"kind": "request", "buyer": c["buyer"], "expires_at": c["expires_at"],
                 "contract": c}, key)


def verify_archive(archive, receipt, artifact, c):
    """Verify the exact delivered ZIP, manifest, instrument, and host checker.

    Bytes come from the buyer's independent receipt/archive transport. The
    buyer must obtain the checker/evaluator from a trusted source, not silently
    accept a supplier-controlled executable.
    """
    if type(archive) is not bytes or not 1 <= len(archive) <= MAX_PACKAGE_BYTES:
        raise ValueError("BOUNDED_CUSTOMER_PACKAGE_REQUIRED")
    if type(receipt) is not dict or set(receipt) != {
            "artifact_sha256", "package_sha256", "bytes", "files", "acceptance"}:
        raise ValueError("EXACT_DELIVERY_RECEIPT_REQUIRED")
    if type(receipt["bytes"]) is not int or receipt["bytes"] != len(archive):
        raise ValueError("DELIVERED_PACKAGE_BYTE_COUNT_CHANGED")
    if receipt["package_sha256"] != hashlib.sha256(archive).hexdigest():
        raise ValueError("DELIVERED_PACKAGE_DIGEST_CHANGED")
    if type(receipt["files"]) is not dict or not 1 <= len(receipt["files"]) <= MAX_FILES:
        raise ValueError("BOUNDED_DELIVERY_MANIFEST_REQUIRED")
    if any(type(k) is not str or not k or "/" in k or "\\" in k
           or k in (".", "..") for k in receipt["files"]):
        raise ValueError("UNSAFE_CUSTOMER_PACKAGE_ENTRY")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names = z.namelist()
        if (len(names) != len(set(names)) or len(names) > MAX_FILES + 1
            or set(names) != set(receipt["files"]) | {"MANIFEST.json"}):
            raise ValueError("DELIVERY_MANIFEST_AND_ZIP_CONTENT_MISMATCH")
        files = {}
        total = 0
        for item in z.infolist():
            if (item.is_dir() or "/" in item.filename or "\\" in item.filename
                or item.filename in (".", "..")
                or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("UNSAFE_CUSTOMER_PACKAGE_ENTRY")
            total += item.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("DELIVERED_ARCHIVE_UNCOMPRESSED_LIMIT")
            with z.open(item, "r") as stream:
                payload = stream.read(MAX_TOTAL_UNCOMPRESSED + 1)
            if len(payload) != item.file_size:
                raise ValueError("INCOMPLETE_CUSTOMER_PACKAGE_ENTRY")
            files[item.filename] = payload
    manifest = parse(files.pop("MANIFEST.json"))
    if manifest != receipt["files"]:
        raise ValueError("DELIVERED_FILE_MANIFEST_CHANGED")
    for name, payload in files.items():
        if hashlib.sha256(payload).hexdigest() != manifest[name]:
            raise ValueError("DELIVERED_FILE_BYTES_CHANGED")
    c = contract(c)
    if files.get("instrument.json") != canonical(artifact["instrument"]):
        raise ValueError("DELIVERED_INSTRUMENT_NOT_BOUND_TO_ARTIFACT")
    independent = checker.verify(c, artifact)
    if (receipt["artifact_sha256"] != digest(artifact)
        or receipt["acceptance"] != independent
        or manifest.get("acceptance.json") != hashlib.sha256(canonical(independent)).hexdigest()):
        raise ValueError("SUPPLIER_ACCEPTANCE_OR_ARTIFACT_MISMATCH")
    return {
        "verified": True,
        "scope": "FINITE_BUYER_ACCEPTANCE_REEXECUTED_NOT_GENERAL_CERTIFICATION",
        "contract_sha256": digest(c),
        "artifact_sha256": digest(artifact),
        "package_sha256": receipt["package_sha256"],
        "buyer_independence": "NOT_PROVEN_BY_HMAC_OR_THIS_FUNCTION"
    }


def sign_verified_delivery(c, artifact, receipt, archive, key, *, now=None):
    """Only sign acceptance after independently re-executed declared cases."""
    _key(key)
    c = contract(c)
    now = int(time.time()) if now is None else now
    if type(now) is not int or now >= c["expires_at"]:
        raise ValueError("CUSTOMER_ACCEPTANCE_DEADLINE_EXPIRED")
    checked = verify_archive(archive, receipt, artifact, c)
    return sign({
        "kind": "acceptance",
        "buyer": c["buyer"],
        "contract_sha256": checked["contract_sha256"],
        "artifact_sha256": checked["artifact_sha256"],
        "package_sha256": checked["package_sha256"],
        "accepted": True,
        "expires_at": c["expires_at"]
    }, key)
