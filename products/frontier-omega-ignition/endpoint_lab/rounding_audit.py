"""Conservative, opt-in display-precision audit of the pinned Endpoint Lab runs.

This is an uncertainty *scenario*, not a measurement of hidden raw values.
It preserves decide.py's literal-displayed-value decision and source authority.
"""
import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re

from decide import decide, strict_json, validate

PLAIN = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")


def rounding_envelope(displayed):
    """Closed outer envelope assuming nearest displayed decimal place.

    Closed endpoints intentionally include both half-step ties, independent of
    the submitter's unreported tie-breaking convention.
    """
    if not isinstance(displayed, str) or not PLAIN.fullmatch(displayed):
        raise ValueError("Expected a published positive plain-decimal string.")
    value = Decimal(displayed)
    if not value.is_finite() or value <= 0:
        raise ValueError("Expected a positive finite published measurement.")
    half_unit = Decimal("0.5").scaleb(value.as_tuple().exponent)
    return value - half_unit, value + half_unit


def conservative_reasons(row, contract, latency_limit, rate_floor):
    """Only inspect runs that have passed *all* original source/point gates."""
    reasons = []
    ttft_lower, ttft_upper = rounding_envelope(row["ttft_p90_ms"])
    if ttft_upper > latency_limit:
        reasons.append("first_token_within_display_rounding")
    mode = contract["rate_metric"]
    if mode == "reported_tps_per_user":
        rate_lower, _ = rounding_envelope(row["tps_per_user"])
        if rate_lower < rate_floor:
            reasons.append("user_rate_within_display_rounding")
    elif mode == "inverse_p90_tpot":
        _, tpot_upper = rounding_envelope(row["tpot_p90_ms"])
        # Multiplication is exact; a rounded reciprocal would be unsafe here.
        if tpot_upper * rate_floor > 1000:
            reasons.append("output_token_time_within_display_rounding")
    else:
        raise ValueError("No observed agentic end-to-end rate to robustly score.")
    return reasons


def audit(contract):
    """Compare the original literal decision with a conditional worst-case one.

    No hidden raw observations are inferred and no eligibility reason is erased.
    The price, access and point-accuracy gates remain those of the original.
    """
    result = decide(contract)
    latency_limit, rate_floor = validate(contract)
    robust, sensitive = [], []
    for row in result["eligible"]:
        reasons = conservative_reasons(row, contract, latency_limit, rate_floor)
        if reasons:
            sensitive.append({**row, "precision_reasons": reasons})
        else:
            robust.append(row)
    max_load = max((row["concurrency"] for row in robust), default=None)
    selected = [row for row in robust if row["concurrency"] == max_load]
    nominal_selected = {(row["source"], row["run"]) for row in result["selected"]}
    sensitive_ids = {(row["source"], row["run"]) for row in sensitive}
    return {
        "schema": "frontier-endpoints/display-precision-audit/v1",
        "assumption": "If each published positive decimal is nearest-rounded to its last printed place; closed half-unit bounds.",
        "scope": "Conditional display-precision sensitivity only; not a fresh measurement, physical SLA, price, access, or production recommendation.",
        "original_decision": result,
        "conservative_decision": "supported" if selected else "withheld",
        "conservative_selected": selected,
        "conservative_eligible_count": len(robust),
        "display_supported_but_precision_sensitive": sensitive,
        "original_selected_all_conservative": bool(nominal_selected) and nominal_selected.isdisjoint(sensitive_ids),
        "next_measurement": "Acquire raw precision and repeat the measured workload and source status on intended traffic before infrastructure selection.",
        "audit_script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--case", help="Optional key in a registered contracts JSON object")
    p.add_argument("--output", type=Path, help="Fresh receipt path (never overwrites)")
    args = p.parse_args()
    try:
        obj = strict_json(args.contract.read_bytes())
        result = audit(obj[args.case] if args.case else obj)
        data = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as target:
                target.write(data)
        else:
            print(data, end="")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.exit(2, f"Display-precision audit: {exc}\n")


if __name__ == "__main__":
    main()
