"""Pinned independent machine-asset001 failure-mode and ordinary-control witness.

This is a *review experiment*. A successful witness command never certifies the
reviewed product or any economic claim. No account, payment or outside data.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "https://raw.githubusercontent.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
HEAD = "76f1a29c7752ea3fab7e756c4159ec2bc74839c0"
PATH = "products/frontier_machine_asset_001/gate.py"
BLOB = "115cf8531df65a66dcc679e2d35cb03394cea11a"
PROTOCOL = "7bf458dd64cc43aa2ffcb9e095b844f183afe379"


def git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def checked_source() -> tuple[bytes, str]:
    url = BASE + "/" + HEAD + "/" + PATH
    req = Request(url, headers={"User-Agent": "MONTREAL.AI-source-bound-research-witness"})
    with urlopen(req, timeout=30) as response:
        raw = response.read(250_000)
    actual = git_blob(raw)
    if actual != BLOB:
        raise RuntimeError("PINNED_ORIGINAL_GIT_BLOB_MISMATCH")
    return raw, url


def load_source(raw: bytes, folder: Path):
    path = folder / "gate.py"
    path.write_bytes(raw)
    spec = importlib.util.spec_from_file_location("pinned_asset001_gate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("IMPORT_SPEC_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def positive_input():
    return {
        "contract": {
            "id_field": "id",
            "rules": [
                {"from": "name", "to": "label", "op": "strip"},
                {"from": "country", "to": "region", "op": "upper"},
                {"from": "comment", "to": "note", "op": "lower"},
                {"from": "qty", "to": "count", "op": "copy"},
            ],
        },
        "source_rows": [
            {"id": "alpha", "name": "  Émile  ", "country": "ca", "comment": "BONJOUR", "qty": 2},
            {"id": "beta", "name": "  Chloé 🌟 ", "country": "fr", "comment": "SALUT", "qty": 3},
            {"id": "gamma", "name": " Renée ", "country": "us", "comment": "TEST", "qty": 0},
        ],
    }


def strong_ordinary_control(payload):
    """Straightforward, competent free Python standard-library solution."""
    rows = []
    for r in payload["source_rows"]:
        rows.append({
            "id": r["id"],
            "label": r["name"].strip(),
            "region": r["country"].upper(),
            "note": r["comment"].lower(),
            "count": r["qty"],
        })
    return rows


def probe(module, payload, what):
    """Record a product refusal separately from a genuinely uncaught exception."""
    try:
        on_wire = json.dumps(payload, ensure_ascii=True, allow_nan=False)
        parsed = module.strict_json(on_wire)
        result = module.run(parsed)
        accepted = bool(result["receipt"]["accepted"])
        return {
            "case": what,
            "outcome": "UNEXPECTED_ACCEPTANCE" if accepted else "WELL_FORMED_REFUSAL",
            "errors": result["receipt"].get("errors", []),
        }
    except Exception as exc:
        # Intentionally do not export the request, source row or exception string.
        return {"case": what, "outcome": "UNCAUGHT_EXCEPTION", "exception_type": type(exc).__name__}


def run_witness():
    start = time.perf_counter()
    r0 = resource.getrusage(resource.RUSAGE_SELF)
    raw, url = checked_source()
    with tempfile.TemporaryDirectory(prefix="machine-asset002-") as d:
        module = load_source(raw, Path(d))
        payload = positive_input()
        actual = module.run(payload)
        incumbent = strong_ordinary_control(payload)
        if not actual["receipt"]["accepted"] or actual["delivery"] != incumbent:
            raise AssertionError("POSITIVE_COMPARISON_FAILED")
        expected = [
            {"id": "alpha", "label": "Émile", "region": "CA", "note": "bonjour", "count": 2},
            {"id": "beta", "label": "Chloé 🌟", "region": "FR", "note": "salut", "count": 3},
            {"id": "gamma", "label": "Renée", "region": "US", "note": "test", "count": 0},
        ]
        if actual["delivery"] != expected:
            raise AssertionError("INDEPENDENT_ORDINARY_EXPECTATION_MISMATCH")

        bad_id = copy.deepcopy(payload)
        bad_id["source_rows"][0]["id"] = "\ud800"
        bad_text = copy.deepcopy(payload)
        bad_text["source_rows"][0]["name"] = "\ud800"
        findings = [
            probe(module, bad_id, "UNPAIRED_SURROGATE_ID"),
            probe(module, bad_text, "UNPAIRED_SURROGATE_REQUIRED_TEXT"),
        ]
        clean = probe(module, payload, "LEGITIMATE_NON_ASCII_CONTROL")
        if clean["outcome"] != "UNEXPECTED_ACCEPTANCE":
            raise AssertionError("LEGITIMATE_NON_ASCII_CONTROL_FAILED")
        if any(row["outcome"] == "UNCAUGHT_EXCEPTION" for row in findings):
            status = "FAILED_UNCAUGHT_EXCEPTION"
        elif all(row["outcome"] == "WELL_FORMED_REFUSAL" for row in findings):
            status = "ACHIEVED_FAIL_CLOSED"
        else:
            status = "FAILED_UNEXPECTED_ACCEPTANCE_OR_OTHER"

        r1 = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "schema": "montreal.ai/machine-asset002-independent-witness/v1",
            "preregistration_commit": PROTOCOL,
            "source_commit": HEAD,
            "source_git_blob_sha1": git_blob(raw),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_url": url,
            "source_verified_before_import": True,
            "ordinary_control": "competent Python stdlib direct transform; one registered positive example",
            "positive_same_output": actual["delivery"] == incumbent,
            "positive_rows": len(incumbent),
            "malformed_input_cases": findings,
            "legitimate_unicode_control": "ACCEPTED",
            "product_input_safety_verdict": status,
            "witness_execution_status": "ACHIEVED_INDEPENDENT_NEGATIVE_OR_POSITIVE_EVIDENCE",
            "commercial": {
                "actual_external_buyers": 0,
                "actual_collected_USD": 0,
                "complete_profit_USD": None,
                "native_account_used": False,
                "licensed_high_value_source": "UNKNOWN",
                "buyer_willingness_to_pay": "UNKNOWN",
                "specialist_complete_alternative": "UNQUALIFIED",
                "decision": "NO_BID_NO_DEPLOY",
                "no_cash_or_private_credentials_used": True,
            },
            "resources": {
                "process_cpu_seconds": round((r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime), 6),
                "wall_seconds": round(time.perf_counter() - start, 6),
                "self_max_rss_KiB": r1.ru_maxrss,
                "complete_host_or_model_billing_USD": None,
            },
            "python": platform.python_version(),
            "scope": "one fixed pinned public kernel + one strong ordinary transformation; no external demand or general security certification",
        }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: witness.py RESULT.json")
    out = Path(sys.argv[1])
    if out.exists():
        raise SystemExit("FRESH_RESULT_PATH_REQUIRED")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = run_witness()
    out.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n")
    print("WITNESS_RECORDED source_git_blob=" + result["source_git_blob_sha1"])
    print("PRODUCT_INPUT_SAFETY_VERDICT=" + result["product_input_safety_verdict"])
    print("COMMERCIAL_VERDICT=NO_BID_NO_DEPLOY")
    for row in result["malformed_input_cases"]:
        print(row["case"] + "=" + row["outcome"] + ":" + row.get("exception_type", ""))
    # A zero exit only means the independent witness was collected. A product
    # failure stays FAILED and is never a passing product-qualification test.


if __name__ == "__main__":
    main()
