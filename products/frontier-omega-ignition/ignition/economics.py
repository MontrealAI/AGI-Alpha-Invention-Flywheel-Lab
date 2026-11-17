"""Operator-attributed commercial scenarios, independent of technical acceptance and accounts."""
from __future__ import annotations

import math
import re
from decimal import Decimal, localcontext
from fractions import Fraction

CATEGORIES = {
    "search_construction": "Opportunity search, failed attempts, design and construction",
    "compute_inference": "Compute and inference across all attempts",
    "data_tools": "Data, tools, dependencies and licences",
    "human_intervention": "Human research, review and operational work",
    "acquisition_distribution": "Acquisition, distribution and delivery",
    "deployment_onboarding": "Deployment, integration and onboarding",
    "verification_rework": "Acceptance testing, corrections and replacements",
    "support_maintenance": "Post-delivery support and maintenance",
    "retained_obligations": "Reliability, liability and remaining obligations",
    "opportunity_cost": "MONTREAL.AI's foregone internal work and reserved capacity",
}
NARRATIVE = {"rights", "payment_timing", "funding", "willingness_to_pay", "strongest_alternative"}
PROVENANCE = {"assumption", "quote", "measurement"}
DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
COMMON = {"low", "high", "provenance", "source"}


def _text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError(f"{field} requires 1–2000 characters")
    return value.strip()


def _money(value):
    if not isinstance(value, str) or len(value) > 64 or not DECIMAL.fullmatch(value):
        raise ValueError("Money bounds must be unsigned decimal strings of up to 64 characters")
    return Decimal(value)


def _attribution(row):
    if not isinstance(row.get("provenance"), str) or row["provenance"] not in PROVENANCE:
        raise ValueError("Declare assumption, quote or measurement as provenance")
    _text(row.get("source"), "source or explicit assumption rationale")


def _interval(row, cost=False):
    expected = COMMON | ({"basis"} if cost else set())
    if not isinstance(row, dict) or set(row) != expected:
        raise ValueError("Amount requires low, high, provenance and source; cost lines also require basis")
    if cost and (not isinstance(row["basis"], str) or row["basis"] not in {"fixed", "per_unit"}):
        raise ValueError("Cost basis must be fixed or per_unit")
    _attribution(row)
    if _money(row["low"]) > _money(row["high"]):
        raise ValueError("A low bound cannot exceed its high bound")


def validate_case(case):
    """A present category is the operator's proposed full coverage of that category."""
    if not isinstance(case, dict) or set(case) - ({"currency", "unit", "horizon", "costs", "price",
                                                   "volume", "participants"} | NARRATIVE):
        raise ValueError("Unknown or invalid commercial case fields")
    if not isinstance(case.get("currency"), str) or not re.fullmatch(r"[A-Z]{3}", case["currency"]):
        raise ValueError("Declare one three-letter currency for the entire scenario")
    for key in ("unit", "horizon"):
        _text(case.get(key), key)
    costs = case.get("costs", {})
    if not isinstance(costs, dict) or set(costs) - CATEGORIES.keys():
        raise ValueError("Unrecognized cost category")
    for lines in costs.values():
        if not isinstance(lines, list) or not 1 <= len(lines) <= 24:
            raise ValueError("Each provided cost category needs 1–24 attributed lines")
        for line in lines:
            _interval(line, cost=True)
    if "price" in case:
        _interval(case["price"])
    if "volume" in case:
        vol = case["volume"]
        if (not isinstance(vol, dict) or set(vol) != {"units", "provenance", "source"} or
                type(vol["units"]) is not int or vol["units"] < 0):
            raise ValueError("Volume requires nonnegative whole units, provenance and a source")
        _attribution(vol)
    for field in NARRATIVE.intersection(case):
        row = case[field]
        if not isinstance(row, dict) or set(row) != {"claim", "provenance", "source"}:
            raise ValueError(f"{field} requires claim, provenance and source")
        _text(row["claim"], field)
        _attribution(row)
    participants = case.get("participants", [])
    if not isinstance(participants, list) or len(participants) > 32:
        raise ValueError("Participants must be a list of up to 32 proposed roles")
    for row in participants:
        if not isinstance(row, dict) or set(row) != {"role", "incentive", "outside_option", "provenance", "source"}:
            raise ValueError("Each participant needs a role, incentive, outside option, provenance and source")
        for field in ("role", "incentive", "outside_option"):
            _text(row[field], field)
        _attribution(row)
    return case


def _usage(calls):
    if isinstance(calls, dict) and ("completed" in calls or "failed" in calls):
        finished, failed = calls.get("completed", []), calls.get("failed", [])
    elif isinstance(calls, dict):
        finished, failed = list(calls.values()), []
    else:
        finished, failed = calls or [], []
    unique, seen = [], set()
    missing_receipts = 0
    elapsed = []
    for attempt in [*finished, *failed]:
        receipts = attempt.get("receipt") or attempt.get("receipts") or []
        if not receipts:
            missing_receipts += 1
        wall = attempt.get("elapsed_seconds")
        if type(wall) in (float, int) and math.isfinite(wall) and wall >= 0:
            elapsed.append(wall)
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            identity = (receipt.get("run_id"), receipt.get("request_sha256"), receipt.get("recorded_at"))
            if any(identity) and identity in seen:
                continue
            seen.add(identity)
            unique.append(receipt)
    counts = {}
    for key in ("input_tokens", "output_tokens"):
        values = [(r.get("usage") or {}).get(key) for r in unique]
        known = [v for v in values if type(v) is int and v >= 0]
        counts[key] = {"observed_sum": sum(known) if known else None, "reporting_receipts": len(known)}
    app_calls = [r["application_model_calls"] for r in unique
                 if type(r.get("application_model_calls")) is int and r["application_model_calls"] >= 0]
    return {"completed_steps": len(finished), "failed_attempts": len(failed), "unique_receipts": len(unique),
            "attempts_without_receipts": missing_receipts,
            "recorded_application_model_calls": sum(app_calls) if app_calls else None,
            "assisted_exchanges": sum(r.get("status") == "reviewed_exchange" for r in unique),
            "tokens": counts, "observed_step_wall_seconds": round(sum(elapsed), 6) if elapsed else None,
            "human_work_seconds": None, "incurred_cost": None,
            "scope": "Wall time and reported tokens are telemetry. Operator-assisted exchanges have unmeasured external model and human use."}


def _show(amount):
    return format(amount, "f")


def _bounds(pair):
    return {"low": _show(pair[0]), "high": _show(pair[1])}


def _scenario(case):
    costs = case.get("costs", {})
    missing = [key for key in CATEGORIES if key not in costs]
    with localcontext() as ctx:
        # Each monetary input has at most 64 decimal characters. Keep exact
        # integer volumes and all digits of sums and products, including carry.
        volume = case.get("volume", {}).get("units")
        ctx.prec = 150 + (len(str(volume)) if volume is not None else 0)
        sums = {"fixed": [Decimal(0), Decimal(0)], "per_unit": [Decimal(0), Decimal(0)]}
        for lines in costs.values():
            for row in lines:
                pair = sums[row["basis"]]
                pair[0] += _money(row["low"])
                pair[1] += _money(row["high"])
        result = {
            "scope": {k: case[k] for k in ("currency", "unit", "horizon")},
            "cost_inputs": costs, "unpriced_categories": missing,
            "covered_cost_subtotals": {k: _bounds(pair) for k, pair in sums.items()} if costs else None,
            "proposed_unit_price": case.get("price"), "volume": case.get("volume"),
            "projected_gross_revenue": None, "modeled_total_economic_cost": None,
            "modeled_economic_contribution": None, "per_unit_contribution": None, "break_even_units": None,
        }
        price = case.get("price")
        revenue = None
        if price and volume is not None:
            revenue = [_money(price[k]) * volume for k in ("low", "high")]
            result["projected_gross_revenue"] = _bounds(revenue)
        if missing:
            return result
        fixed, variable = sums["fixed"], sums["per_unit"]
        if volume is not None:
            total = [f + v * volume for f, v in zip(fixed, variable)]
            result["modeled_total_economic_cost"] = _bounds(total)
            if revenue is not None:
                result["modeled_economic_contribution"] = _bounds([revenue[0] - total[1], revenue[1] - total[0]])
        if price:
            margin = [_money(price["low"]) - variable[1], _money(price["high"]) - variable[0]]
            result["per_unit_contribution"] = _bounds(margin)

            def units(setup, contribution):
                if contribution <= 0:
                    return None
                return max(1, math.ceil(Fraction(setup) / Fraction(contribution)))

            result["break_even_units"] = {
                "favorable": units(fixed[0], margin[1]), "adverse": units(fixed[1], margin[0]),
                "definition": "Positive whole paid deliveries covering fixed economic cost, conditional on strictly "
                              "positive unit contribution. Null denotes no positive-margin threshold in that bound."}
        return result


def assessment(mission, research, calls):
    """Commercial evidence remains separate from technical acceptance, funding and cash."""
    research = research or {}
    selected = research.get("selected") or {}
    case = mission.get("resources", {}).get("commercial_case")
    result = {
        "schema": "ignition-commercial-assessment/1", "status": "unknown",
        "beneficiary": mission.get("beneficiary") or None, "outcome": selected.get("outcome") or mission.get("purpose"),
        "research_hypotheses": {k: selected.get(k) for k in ("value", "alternative", "test", "scale", "obstruction")},
        "source_rights": [{"url": s.get("url"), "declared": s.get("rights")} for s in research.get("signals", [])],
        "operator_evidence": {}, "participants": [], "missing_cost_categories": list(CATEGORIES),
        "missing_commercial_evidence": sorted(NARRATIVE), "usage": _usage(calls),
        "scenario": None, "verified_demand": None, "booked_revenue": None, "collected_revenue": None, "funding_received": None,
        "scope": "No financial transactions or independent verification of operator evidence. Scenario contribution "
                 "includes opportunity cost. Commercial assumptions do not change technical acceptance.",
    }
    if case is None:
        return result
    try:
        validate_case(case)
    except (ValueError, TypeError) as exc:
        result.update(status="invalid_case", error=str(exc))
        return result
    result["scenario"] = _scenario(case)
    result["missing_cost_categories"] = result["scenario"]["unpriced_categories"]
    result["operator_evidence"] = {k: case[k] for k in sorted(NARRATIVE) if k in case}
    result["missing_commercial_evidence"] = sorted(NARRATIVE - case.keys())
    result["participants"] = case.get("participants", [])
    result["status"] = "partial_scenario" if result["missing_cost_categories"] or "price" not in case else "bounded_scenario"
    return result
