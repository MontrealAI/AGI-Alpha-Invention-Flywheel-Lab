"""Local buyer workflow for the finite, explicitly supported numerical outcome.

This is a working narrow example, not the proposed general Genesis product.
It reads one buyer-controlled JSON request and writes a fresh local directory.
No network, account, model provider, purchase or outside action is invoked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import time

from .kernel import construct, execute, retained_assets, validate_request, digest
from .verify import verify, qualify
from .experiment import numpy_reference


def run(request, destination, *, repeats=3):
    validate_request(request)
    if type(repeats) is not int or not 1 <= repeats <= 20:
        raise ValueError("BOUNDED_EXPLICIT_MEASUREMENT_REPEATS_REQUIRED")
    path = Path(destination).resolve()
    path.mkdir(parents=True, exist_ok=False)
    plan = construct(request, "adaptive", retained_assets())
    artifact = execute(request, plan)
    acceptance = verify(request, artifact)
    qualification = qualify(request, artifact)
    timings = []
    # Rotate order to avoid granting our producer a systematic warm-up edge.
    for index in range(repeats):
        pair = {}
        for mode in (("candidate", "numpy") if index % 2 else ("numpy", "candidate")):
            started = time.perf_counter()
            if mode == "candidate":
                p = construct(request, "adaptive", retained_assets())
                result = execute(request, p)
                verdict = verify(request, result)
                pair[mode] = {"accepted": verdict["accepted"], "wall_seconds": time.perf_counter() - started}
            else:
                reference = numpy_reference(request)
                pair[mode] = {"accepted": reference["accepted"], "wall_seconds": time.perf_counter() - started}
        timings.append(pair)
    candidate = statistics.median(r["candidate"]["wall_seconds"] for r in timings)
    reference = statistics.median(r["numpy"]["wall_seconds"] for r in timings)
    all_measurements_accepted = all(r[m]["accepted"] for r in timings for m in ("candidate", "numpy"))
    if not acceptance["accepted"] or not qualification["accepted"]:
        next_action = "DECLINE_THIS_CONTRACT: acceptance or qualification failed; retain source and counterexample."
    elif not all_measurements_accepted:
        next_action = "INVESTIGATE_REPRODUCIBILITY: a matched timing delivery failed acceptance; speed comparison is unresolved."
    elif candidate >= reference:
        next_action = "USE_STRONG_DIRECT_ALTERNATIVE: measured complete candidate workflow is slower on this request."
    else:
        next_action = "STAGE_BUYER_BILL_VALIDATION: measured host improvement warrants checking representative repeated work and genuinely avoidable cost before purchase."
    report = {
        "schema": "omega-savings/buyer-workflow/v1", "request_sha256": digest(request),
        "ambition": request["goal"], "hypotheses": plan["hypotheses"],
        "alternatives": ["NumPy direct solve with identical independent acceptance", "Competent SciPy LU/reuse/Woodbury implementation", "Use existing solution and make no purchase"],
        "constructed_capability": {"method": plan["method"], "program_sha256": plan["program_sha256"], "scope": plan["construction_scope"]},
        "acceptance": acceptance, "qualification": qualification,
        "decisive_test": {"order_rotated_repeats": repeats, "all_deliveries_accepted": all_measurements_accepted, "timings": timings,
            "candidate_complete_median_seconds": candidate, "numpy_complete_median_seconds": reference,
            "note": "Single-host complete construction/execution/verification timing. First qualification is additional. No cloud-price conversion."},
        "next_action": next_action, "actual_external_spending_microUSD": 0,
        "unmeasured_costs": ["Buyer preparation and installation time", "Actual host and included subscription resource bill", "Representative workload transfer and cash avoidability"],
        "permissions": {"network": False, "external_actions": False, "buyer_owns_input_and_output": True},
        "product_vision_limit": "Finite numerical request interface; general natural-language autonomous business construction, paid onboarding and customer demand not demonstrated.",
    }
    for name, content in (("request.json", request), ("plan.json", plan), ("result.json", artifact), ("REPORT.json", report)):
        (path / name).write_text(json.dumps(content, sort_keys=True, indent=2, allow_nan=False) + "\n")
    (path / "worker.py").write_text(plan["program"] if plan["program"] else "raise SystemExit('Contract declined; inspect REPORT.json')\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    result = run(json.loads(Path(args.request).read_text()), args.output, repeats=args.repeats)
    print(json.dumps({"report": str(Path(args.output).resolve() / "REPORT.json"), "next_action": result["next_action"]}))


if __name__ == "__main__":
    main()
