#!/usr/bin/env python3
"""Pinned-owner negative diagnostic for producer CSV bytes vs SHA binding."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import time

from interpret import build
from verify import verify

PINNED_OWNER = "9e9b501c84ffe7b7969027c43eb465aff81f8499"
HEADER = "case_id,period,group,label,model_output\n"
A = HEADER + "SYN-A1,2026-11,alpha,0,0\nSYN-A2,2026-11,alpha,1,1\n"
B = HEADER + "SYN-B1,2026-11,alpha,0,1\nSYN-B2,2026-11,alpha,1,0\n"


def audit():
    t, cpu = time.perf_counter(), time.process_time()
    assert A != B
    with TemporaryDirectory() as temporary:
        p = Path(temporary) / "sample.csv"
        p.write_text(A, encoding="utf-8")
        params = {"sample_role": "EXPOSED_DEMO", "review_status": "UNVERIFIED", "population_frame": "UNKNOWN"}
        baseline = build(p, **params)
        baseline_path = Path(temporary) / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        positive_control = verify(p, baseline_path) is True
        assert baseline["input_sha256"] == hashlib.sha256(A.encode()).hexdigest()

        p.write_text(B, encoding="utf-8")
        reference_b = build(p, **params)
        p.write_text(A, encoding="utf-8")
        swapped = [False]
        orig_read = Path.read_bytes

        def swap_after_producer_hash(path):
            raw = orig_read(path)
            if path == p and not swapped[0]:
                p.write_text(B, encoding="utf-8")
                swapped[0] = True
            return raw

        adversarial_report = None
        adverse_exception = None
        try:
            with patch.object(Path, "read_bytes", swap_after_producer_hash):
                adversarial_report = build(p, **params)
        except (ValueError, OSError, UnicodeError, TypeError) as exc:
            adverse_exception = type(exc).__name__ + ": " + str(exc)[:160]

        report_hash = adversarial_report.get("input_sha256") if adversarial_report else None
        groups = adversarial_report.get("groups") if adversarial_report else None
        result_file = Path(temporary) / "adverse.json"
        if adversarial_report is not None:
            result_file.write_text(json.dumps(adversarial_report), encoding="utf-8")
        subsequent_verifier_rejected = False
        subsequent_verifier_error = None
        if result_file.exists():
            try:
                verify(p, result_file)
            except (ValueError, OSError) as exc:
                subsequent_verifier_rejected = True
                subsequent_verifier_error = type(exc).__name__ + ": " + str(exc)[:160]

        mismatch = (positive_control and swapped[0] and
                    report_hash == hashlib.sha256(A.encode()).hexdigest() and
                    groups == reference_b["groups"] and groups != baseline["groups"] and
                    hashlib.sha256(p.read_bytes()).hexdigest() == hashlib.sha256(B.encode()).hexdigest())
        verdict = ("FAIL_PRODUCER_MISMATCH_ACCEPTED" if mismatch else
                   "PASS_PRODUCER_MISMATCH_REJECTED" if positive_control and swapped[0] and adversarial_report is None else
                   "INCONCLUSIVE")
        return {
            "schema": "agi-alpha/qualification119-producer-snapshot/v1",
            "target_source_commit": PINNED_OWNER,
            "protocol_freeze_commit": "7fa4bb89d3164df95102b1f2164149efda94320f",
            "cases": ["baseline_A", "one_deterministic_swap_after_producer_hash"],
            "baseline_accepted_by_independent_verifier": positive_control,
            "swap_exercised": swapped[0],
            "a_sha256": hashlib.sha256(A.encode()).hexdigest(),
            "b_sha256": hashlib.sha256(B.encode()).hexdigest(),
            "reported_sha256": report_hash,
            "baseline_groups": baseline["groups"],
            "replacement_groups": reference_b["groups"],
            "adversarial_groups": groups,
            "adversarial_exception": adverse_exception,
            "subsequent_verifier_rejected": subsequent_verifier_rejected,
            "subsequent_verifier_error": subsequent_verifier_error,
            "source_binding_verdict": verdict,
            "wall_seconds": round(time.perf_counter() - t, 6),
            "process_cpu_seconds": round(time.process_time() - cpu, 6),
            "claim_limit": "Negative synthetic owner-source witness; no real population or customer, no paid commerce, no native-account or release qualification."
        }


if __name__ == "__main__":
    result = audit()
    outfile = Path(__file__).with_name("RESULT.json")
    outfile.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    assert result["baseline_accepted_by_independent_verifier"] and result["swap_exercised"], "INVALID_PROBE"
    assert result["source_binding_verdict"] != "INCONCLUSIVE", "INCONCLUSIVE_PROBE"
