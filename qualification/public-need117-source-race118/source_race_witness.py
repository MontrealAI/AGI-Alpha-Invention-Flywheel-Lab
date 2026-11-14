#!/usr/bin/env python3
"""Independent, pinned-source negative witness for public-need117 CSV TOCTOU."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import time

from interpret import build
from verify import verify

COLUMNS = "case_id,period,group,label,model_output\n"
A = COLUMNS + "SYN-A1,2026-11,alpha,0,0\nSYN-A2,2026-11,alpha,1,0\n"
B = COLUMNS + "SYN-B1,2026-11,alpha,0,0\nSYN-B2,2026-11,alpha,1,0\n"
PINNED_SOURCE = "9e9b501c84ffe7b7969027c43eb465aff81f8499"

def run():
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    assert A != B
    with TemporaryDirectory() as td:
        root = Path(td)
        sample = root / "sample.csv"
        sample.write_text(A, encoding="utf-8")
        receipt = root / "RESULT.json"
        receipt.write_text(json.dumps(build(sample, sample_role="EXPOSED_DEMO",
                                             review_status="UNVERIFIED", population_frame="UNKNOWN")))
        baseline_accepted = verify(sample, receipt) is True
        old_read = Path.read_bytes
        swap_seen = [False]

        def replace_between_hash_and_recount(path):
            raw = old_read(path)
            if path == sample and not swap_seen[0]:
                sample.write_text(B, encoding="utf-8")
                swap_seen[0] = True
            return raw

        exception_name = None
        adversarial_accepted = False
        try:
            with patch.object(Path, "read_bytes", replace_between_hash_and_recount):
                adversarial_accepted = verify(sample, receipt) is True
        except (OSError, ValueError, TypeError, AssertionError) as exc:
            exception_name = type(exc).__name__ + ": " + str(exc)[:150]
        recorded = json.loads(receipt.read_text())["input_sha256"]
        seen = hashlib.sha256(sample.read_bytes()).hexdigest()
        mismatch = recorded != seen
        vulnerability = baseline_accepted and swap_seen[0] and mismatch and adversarial_accepted
        return {
            "schema": "agi-alpha/qualification118-source-race/v1",
            "owner_source_commit": PINNED_SOURCE,
            "scope": "PINNED OWNER PR316; synthetic deterministic schedule only; no govt data or commerce",
            "baseline_accepted": baseline_accepted,
            "source_replaced_after_hash_before_recount": swap_seen[0],
            "A_sha256": hashlib.sha256(A.encode()).hexdigest(),
            "B_sha256": hashlib.sha256(B.encode()).hexdigest(),
            "recorded_input_sha256": recorded,
            "recounted_file_sha256": seen,
            "source_digest_mismatch": mismatch,
            "adversarial_accepted": adversarial_accepted,
            "adversarial_exception": exception_name,
            "security_verdict": "FAIL_DIFFERENT_BYTES_ACCEPTED" if vulnerability else (
                "PASS_DIFFERENT_BYTES_REJECTED" if baseline_accepted and swap_seen[0] and mismatch and not adversarial_accepted
                else "INCONCLUSIVE"),
            "wall_seconds": round(time.perf_counter() - start_wall, 6),
            "self_cpu_seconds": round(time.process_time() - start_cpu, 6),
            "claim_limit": "A diagnostic run exit-zero is not source-custody security success; this is not observed buyer activity."
        }

if __name__ == "__main__":
    result = run()
    outfile = Path(__file__).with_name("SOURCE_RACE_RESULT.json")
    outfile.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    assert result["baseline_accepted"] and result["source_replaced_after_hash_before_recount"], "INVALID_PROBE"
    assert result["security_verdict"] != "INCONCLUSIVE", "INCONCLUSIVE_PROBE"
