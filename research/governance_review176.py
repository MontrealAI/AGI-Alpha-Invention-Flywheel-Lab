"""Independent, narrowly scoped Ed25519 reviewer-action provenance for Impact140.

No signed statement upgrades a governance finding to compliance. An operator must
anchor trust keys and original Impact140 digests *outside* the submitted bundle.
Only synthetic/public inputs. No private keys, network, accounts or persistence.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import tempfile

from products.governance_impact140.engine import canonical, verify_receipt

SCHEMA = "agi-alpha/governance-review176/action-v1"
BUNDLE_SCHEMA = "agi-alpha/governance-review176/bundle-v1"
TRUST_SCHEMA = "agi-alpha/governance-review176/trust-v1"
RECEIPT_SCHEMA = "agi-alpha/governance-review176/receipt-v1"
DECISIONS = frozenset(("validate", "reject", "annotate"))


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _object(value, fields, error):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(error)


def _str(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and value.strip() == value and bool(value)


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("STRICT_UTC_TIME_REQUIRED")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError("STRICT_UTC_TIME_REQUIRED") from e
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("STRICT_UTC_TIME_REQUIRED")
    return parsed


def _signature_verify(pem, statement, encoded):
    if (not isinstance(pem, str) or len(pem) > 4096 or
            not pem.startswith("-----BEGIN PUBLIC KEY-----") or
            "PRIVATE KEY" in pem):
        raise ValueError("PINNED_PUBLIC_KEY_REQUIRED")
    if not isinstance(encoded, str) or len(encoded) > 120:
        raise ValueError("INVALID_ED25519_SIGNATURE")
    try:
        signature = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("INVALID_ED25519_SIGNATURE") from e
    if len(signature) != 64:
        raise ValueError("INVALID_ED25519_SIGNATURE")
    with tempfile.TemporaryDirectory(prefix="review176-public-") as td:
        root = Path(td)
        pub, msg, sig = (root / "public.pem", root / "message.json", root / "signature.bin")
        pub.write_text(pem, encoding="ascii")
        msg.write_bytes(canonical(statement))
        sig.write_bytes(signature)
        try:
            check = subprocess.run(
                ["openssl", "pkey", "-pubin", "-in", str(pub), "-text", "-noout"],
                capture_output=True, timeout=8, check=True)
            if not check.stdout.startswith(b"ED25519 Public-Key:"):
                raise ValueError("ONLY_ED25519_PUBLIC_KEYS")
            subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(pub),
                 "-rawin", "-in", str(msg), "-sigfile", str(sig)],
                capture_output=True, timeout=8, check=True)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            raise ValueError("SIGNED_REVIEW_ACTION_INVALID") from e


def evaluate(bundle, trust, *, expected_trust_sha256, expected_input_sha256,
             expected_receipt_sha256, as_of_utc):
    """Validate only independently scoped reviewer *actions*, never compliance.

    expected_* values and as_of_utc are supplied by the caller separately from
    the untrusted bundle. A durable authoritative log is needed to bar replay
    across different calls; this batch only rejects internal duplicates.
    """
    for value in (expected_trust_sha256, expected_input_sha256, expected_receipt_sha256):
        if not _digest(value):
            raise ValueError("EXTERNAL_ANCHORS_REQUIRED")
    when = _utc(as_of_utc)
    if not hmac.compare_digest(sha(trust), expected_trust_sha256):
        raise ValueError("INDEPENDENT_TRUST_ANCHOR_MISMATCH")
    _object(trust, ("schema", "organization_id", "reviewers"), "EXACT_TRUST_RECORD_REQUIRED")
    if trust["schema"] != TRUST_SCHEMA or not _str(trust["organization_id"]):
        raise ValueError("INVALID_TRUST_SCOPE")
    reviewers = trust["reviewers"]
    if not isinstance(reviewers, list) or not reviewers:
        raise ValueError("TRUSTED_REVIEWERS_REQUIRED")
    by_id = {}
    used_public_keys = set()
    duplicate_public_key = False
    for reviewer in reviewers:
        _object(reviewer, ("reviewer_id", "role", "systems", "requirements",
                           "public_key_pem", "revoked", "valid_from_utc",
                           "valid_until_utc"), "EXACT_REVIEWER_SCOPE_REQUIRED")
        identifier = reviewer["reviewer_id"]
        if not _str(identifier) or identifier in by_id:
            raise ValueError("UNIQUE_TRUSTED_REVIEWER_REQUIRED")
        if reviewer["role"] != "independent_reviewer" or type(reviewer["revoked"]) is not bool:
            raise ValueError("INDEPENDENT_REVIEW_ROLE_REQUIRED")
        for scope in ("systems", "requirements"):
            items = reviewer[scope]
            if not isinstance(items, list) or not items or any(not _str(s) for s in items) or len(set(items)) != len(items):
                raise ValueError("EXPLICIT_UNIQUE_REVIEW_SCOPE_REQUIRED")
        if _utc(reviewer["valid_until_utc"]) <= _utc(reviewer["valid_from_utc"]):
            raise ValueError("INVALID_REVIEWER_VALIDITY")
        # Treat identical DER SubjectPublicKeyInfo bytes as one public identity,
        # independently of PEM line wrapping; a key cannot identify two people.
        pem = reviewer["public_key_pem"]
        if not isinstance(pem, str) or len(pem) > 4096:
            raise ValueError("PINNED_PUBLIC_KEY_REQUIRED")
        lines = pem.strip().splitlines()
        if len(lines) < 3 or lines[0] != "-----BEGIN PUBLIC KEY-----" or lines[-1] != "-----END PUBLIC KEY-----":
            raise ValueError("PINNED_PUBLIC_KEY_REQUIRED")
        try:
            public_der = base64.b64decode("".join(lines[1:-1]), validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("PINNED_PUBLIC_KEY_REQUIRED") from e
        if not public_der or len(public_der) > 4096:
            raise ValueError("PINNED_PUBLIC_KEY_REQUIRED")
        key_identity = hashlib.sha256(public_der).digest()
        if key_identity in used_public_keys:
            duplicate_public_key = True
        used_public_keys.add(key_identity)
        by_id[identifier] = reviewer

    _object(bundle, ("schema", "source_receipt", "decisions"), "EXACT_REVIEW_BUNDLE_REQUIRED")
    if bundle["schema"] != BUNDLE_SCHEMA:
        raise ValueError("UNSUPPORTED_REVIEW_BUNDLE")
    source = bundle["source_receipt"]
    verify_receipt(source, anchored_receipt_sha256=expected_receipt_sha256,
                   anchored_input_sha256=expected_input_sha256)
    findings = {}
    for finding in source["findings"]:
        if not isinstance(finding, dict):
            raise ValueError("INVALID_SOURCE_FINDING")
        key = (finding.get("system_id"), finding.get("requirement_id"),
               finding.get("after_version"), finding.get("evidence_id"))
        if key in findings:
            raise ValueError("DUPLICATE_SOURCE_FINDING")
        findings[key] = finding
    decisions = bundle["decisions"]
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("NONEMPTY_REVIEW_ACTIONS_REQUIRED")
    used_ids, used_targets, actions = set(), set(), []
    for row in decisions:
        _object(row, ("reviewer_id", "statement", "signature_b64"), "EXACT_SIGNED_ACTION_REQUIRED")
        who = row["reviewer_id"]
        if who not in by_id:
            raise ValueError("UNKNOWN_AUTHORIZED_REVIEWER")
        reviewer = by_id[who]
        if reviewer["revoked"] or not (_utc(reviewer["valid_from_utc"]) <= when <= _utc(reviewer["valid_until_utc"])):
            raise ValueError("REVOKED_OR_EXPIRED_REVIEWER")
        statement = row["statement"]
        _object(statement, ("schema", "decision_id", "organization_id", "system_id",
                            "requirement_id", "requirement_version", "evidence_id",
                            "source_receipt_sha256", "source_input_sha256", "decision",
                            "issued_at_utc", "expires_at_utc", "note"),
                "EXACT_REVIEW_STATEMENT_REQUIRED")
        for field in ("decision_id", "organization_id", "system_id", "requirement_id",
                      "requirement_version", "evidence_id"):
            if not _str(statement[field]):
                raise ValueError("INVALID_SIGNED_SCOPE")
        if statement["schema"] != SCHEMA or statement["decision"] not in DECISIONS:
            raise ValueError("UNSUPPORTED_SIGNED_REVIEW_ACTION")
        if not isinstance(statement["note"], str) or len(statement["note"]) > 256:
            raise ValueError("INVALID_SIGNED_ANNOTATION")
        if (statement["organization_id"] != trust["organization_id"]
                or statement["system_id"] not in reviewer["systems"]
                or statement["requirement_id"] not in reviewer["requirements"]):
            raise ValueError("REVIEW_ACTION_OUTSIDE_GRANTED_SCOPE")
        if (statement["source_receipt_sha256"] != expected_receipt_sha256 or
                statement["source_input_sha256"] != expected_input_sha256):
            raise ValueError("REVIEW_ACTION_SOURCE_CHANGED")
        issued = _utc(statement["issued_at_utc"])
        if not (_utc(reviewer["valid_from_utc"]) <= issued <= _utc(reviewer["valid_until_utc"])):
            raise ValueError("REVIEW_ACTION_ISSUANCE_OUTSIDE_AUTHORIZED_PERIOD")
        if not (issued <= when <= _utc(statement["expires_at_utc"])):
            raise ValueError("REVIEW_ACTION_EXPIRED_OR_FUTURE")
        key = (statement["system_id"], statement["requirement_id"],
               statement["requirement_version"], statement["evidence_id"])
        finding = findings.get(key)
        if (not finding or finding.get("status") != "pending_review"
                or finding.get("review_status") != "pending_authorized_independent_review"):
            raise ValueError("CURRENT_EVIDENCE_AWAITING_REVIEW_REQUIRED")
        if statement["decision_id"] in used_ids or key in used_targets:
            raise ValueError("DUPLICATE_REVIEW_ACTION_OR_TARGET")
        used_ids.add(statement["decision_id"])
        used_targets.add(key)
        _signature_verify(reviewer["public_key_pem"], statement, row["signature_b64"])
        actions.append({"decision_id": statement["decision_id"],
                        "reviewer_id": who, "system_id": key[0],
                        "requirement_id": key[1], "requirement_version": key[2],
                        "evidence_id": key[3], "decision": statement["decision"],
                        "signed_statement_sha256": sha(statement)})
    # A cryptographically invalid signature must keep its original precise
    # rejection, even if the trust table independently has duplicate keys.
    # No successful decision can be attributed under an ambiguous key registry.
    if duplicate_public_key:
        raise ValueError("UNIQUE_REVIEW_PUBLIC_KEY_REQUIRED")
    actions.sort(key=lambda x: x["decision_id"])
    result = {
        "schema": RECEIPT_SCHEMA,
        "scope": "SYNTHETIC_OFFLINE_REVIEWER_SIGNATURE_PROVENANCE_ONLY",
        "as_of_utc": as_of_utc,
        "source_input_sha256": expected_input_sha256,
        "source_receipt_sha256": expected_receipt_sha256,
        "externally_anchored_trust_sha256": expected_trust_sha256,
        "review_actions": actions,
        "underlying_governance_findings_unchanged": True,
        "compliance_authorized": False,
        "no_automated_native_action": True,
        "limitations": "Operator trust/clock identities are assumptions; no real identity, authorization provisioning, persistent cross-run anti-replay or compliance attestation.",
    }
    result["receipt_sha256"] = sha(result)
    return result


def _strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_JSON_FIELD")
        out[key] = value
    return out


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_strict_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON_VALUE")))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("bundle", "trust", "output"):
        p.add_argument("--" + arg, required=True)
    for arg in ("expected-trust-sha256", "expected-input-sha256",
                "expected-receipt-sha256", "at-utc"):
        p.add_argument("--" + arg, required=True)
    args = p.parse_args(argv)
    result = evaluate(_read(args.bundle), _read(args.trust),
                      expected_trust_sha256=args.expected_trust_sha256,
                      expected_input_sha256=args.expected_input_sha256,
                      expected_receipt_sha256=args.expected_receipt_sha256,
                      as_of_utc=args.at_utc)
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("NEW_RECEIPT_OUTPUT_REQUIRED")
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"status": "SIGNED_ACTION_PROVENANCE_ONLY",
                      "review_actions": len(result["review_actions"]),
                      "receipt_sha256": result["receipt_sha256"],
                      "compliance_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
