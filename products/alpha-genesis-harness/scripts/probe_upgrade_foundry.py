#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the real native foundry evaluator without credentials or model inference."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.adapters import BridgeError
from bridge.upgrade_foundry import (NativeEvaluator, UpgradeFoundryService, _authority_manifest,
                                    _manifest, _protocol, _snapshot, _write_snapshot)
from bridge.workflows import _atomic, encoded


def probe(binary):
    started = time.perf_counter()
    receipt = {"schema": "harness-foundry-native-probe/v1", "scope": "Actual credential-free native sandbox and original HARNESS interpreter evaluation. No model-written candidate, OAuth or inference request.",
               "status": "NOT_TESTED", "live_model_construction": "NOT_TESTED", "generated_code_executed": False}
    try:
        files = _snapshot(PRODUCT)
        receipt["source_manifest"] = _manifest(files)
        receipt["evaluator_authority"] = _authority_manifest(binary)
        protocol = _protocol(0)  # Fixed engineering reproduction, not fresh external confirmation.
        with tempfile.TemporaryDirectory(prefix="harness-foundry-native-probe-") as temp:
            baseline = Path(temp) / "baseline"
            _write_snapshot(baseline, files)
            rows = NativeEvaluator(binary).run(baseline, protocol["cases"])
            verdict = UpgradeFoundryService._judge(protocol["cases"], rows)
        receipt.update(status="PASS" if verdict["passed"] else "FAIL", verification=verdict)
    except BridgeError as error:
        blocked = error.code.startswith(("CODEX_SANDBOX", "FOUNDRY_SANDBOX_BLOCKED"))
        receipt.update(status="BLOCKED" if blocked else "FAIL", error_code=error.code, reason=error.message)
    except (OSError, ValueError, TypeError) as error:
        receipt.update(status="FAIL", error_code=type(error).__name__, reason="Native evaluator did not produce a valid complete receipt.")
    receipt["wall_seconds"] = time.perf_counter() - started
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("Use a new output path; old failures are not overwritten.")
    receipt = probe(args.executable)
    _atomic(args.output, encoded(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k not in {"source_manifest", "evaluator_authority"}}, indent=2))
    raise SystemExit(0 if receipt["status"] == "PASS" else 2 if receipt["status"] == "BLOCKED" else 1)


if __name__ == "__main__": main()
