"""Offline, fail-closed commercial opportunity screening; never a bid or account action."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

SCHEMA = "agi-alpha/commercial-source-admission/v1"
REQUIRED = (
    "legal_eligibility", "trl_5_to_9", "essential_outcomes", "interoperable_delivery",
    "rights_and_permissions", "dated_capacity", "independent_acceptance",
    "cost_complete_and_reserves", "outside_option_comparison",
)
COSTS = (
    "development_and_failures", "acquisition_including_lost_quotes", "onboarding",
    "production_and_suppliers", "independent_verification", "repair", "support",
    "maintenance", "tools_and_inference", "infrastructure", "channel_share",
    "refunds", "taxes", "capital_cost", "remaining_claims",
)
ROUTES = {"incumbent_integration", "open_instrument", "human_conventional", "no_deploy"}

def _date(raw):
    if not isinstance(raw, str):
        raise ValueError("ISO_DATE_REQUIRED")
    try:
        parsed = dt.date.fromisoformat(raw)
    except ValueError as e:
        raise ValueError("ISO_DATE_REQUIRED") from e
    if parsed.isoformat() != raw:
        raise ValueError("ISO_DATE_REQUIRED")
    return parsed

def _pairs(pairs):
    found = {}
    for k, v in pairs:
        if k in found:
            raise ValueError("DUPLICATE_JSON_FIELD")
        found[k] = v
    return found

def _nonnegative(value):
    return type(value) is int and value >= 0

def _criterion(value, today):
    if not isinstance(value, dict) or set(value) != {"status", "source", "checked_on", "independent"}:
        raise ValueError("EXACT_EVIDENCE_DESCRIPTOR_REQUIRED")
    if value["status"] not in ("unknown", "failed", "claimed_verified"):
        raise ValueError("EVIDENCE_STATUS_REQUIRED")
    if value["status"] != "claimed_verified":
        return False
    # Input claims are not authenticated by this offline program. A passing
    # record grants review-readiness only, never a certification or bid.
    source = value["source"]
    if not isinstance(source, str) or not source.startswith("https://") or len(source) > 2048:
        return False
    if value["independent"] is not True:
        return False
    checked = _date(value["checked_on"])
    return checked <= today and (today - checked).days <= 14

def evaluate(document, *, on_date):
    today = _date(on_date)
    if not isinstance(document, dict) or set(document) != {"schema", "opportunity", "arrangements"} or document["schema"] != SCHEMA:
        raise ValueError("EXACT_ADMISSION_INPUT_REQUIRED")
    opp = document["opportunity"]
    if not isinstance(opp, dict) or set(opp) != {
        "id", "official_source", "checked_on", "posted_on", "closes_on",
        "kind", "currency", "maximum_contract_value_cents", "estimated_awards", "buyer"
    }:
        raise ValueError("EXACT_OFFICIAL_OPPORTUNITY_REQUIRED")
    if not isinstance(opp["official_source"], str) or not opp["official_source"].startswith("https://"):
        raise ValueError("OFFICIAL_SOURCE_REQUIRED")
    if opp["currency"] != "CAD" or opp["kind"] not in {"RFI", "RFP", "PHASE2_CHALLENGE"}:
        raise ValueError("SUPPORTED_CURRENCY_AND_PURCHASE_TYPE_REQUIRED")
    if not _nonnegative(opp["maximum_contract_value_cents"]) or not _nonnegative(opp["estimated_awards"]):
        raise ValueError("BOUNDED_PUBLIC_PROPOSAL_PARAMETERS_REQUIRED")
    if not isinstance(opp["id"], str) or not opp["id"] or not isinstance(opp["buyer"], str) or not opp["buyer"]:
        raise ValueError("BUYER_AND_OPPORTUNITY_ID_REQUIRED")
    checked = _date(opp["checked_on"])
    posted = _date(opp["posted_on"])
    closing = _date(opp["closes_on"])
    if checked < posted or closing < posted:
        raise ValueError("INCONSISTENT_OFFICIAL_DATES")
    timely = checked <= today <= closing and (today - checked).days <= 14
    arrangements = document["arrangements"]
    if not isinstance(arrangements, list) or len(arrangements) != 4 or {x.get("route") for x in arrangements if isinstance(x, dict)} != ROUTES:
        raise ValueError("FOUR_DISTINCT_ARRANGEMENTS_REQUIRED")
    results = []
    for item in arrangements:
        if not isinstance(item, dict) or set(item) != {
            "route", "criteria", "costs_cents", "current_available_cash_cents",
            "peak_cash_required_cents", "proposed_price_cents"
        }:
            raise ValueError("EXACT_ARRANGEMENT_FIELDS_REQUIRED")
        route = item["route"]
        if route == "no_deploy":
            if item["criteria"] is not None or item["costs_cents"] is not None or any(
                item[k] is not None for k in ("current_available_cash_cents", "peak_cash_required_cents", "proposed_price_cents")
            ):
                raise ValueError("NO_DEPLOY_HAS_NO_IMAGINARY_COMMERCE")
            results.append({"route": route, "decision": "ADMISSIBLE_NO_DEPLOY", "unresolved": [], "hypothetical_margin_cents": None})
            continue
        criteria = item["criteria"]
        if not isinstance(criteria, dict) or set(criteria) != set(REQUIRED):
            raise ValueError("COMPLETE_MANDATORY_CRITERIA_REQUIRED")
        unresolved = sorted(k for k in REQUIRED if not _criterion(criteria[k], today))
        costs = item["costs_cents"]
        if not isinstance(costs, dict) or set(costs) != set(COSTS):
            raise ValueError("FULL_COST_CATEGORIES_REQUIRED")
        if any(v is not None and not _nonnegative(v) for v in costs.values()):
            raise ValueError("COST_MUST_BE_NONNEGATIVE_CENTS_OR_UNKNOWN")
        if any(v is None for v in costs.values()):
            unresolved.append("complete_costs_unknown")
        current = item["current_available_cash_cents"]
        peak = item["peak_cash_required_cents"]
        proposed = item["proposed_price_cents"]
        if any(v is not None and not _nonnegative(v) for v in (current, peak, proposed)):
            raise ValueError("MONEY_MUST_BE_NONNEGATIVE_CENTS_OR_UNKNOWN")
        if current is None or peak is None or current < peak:
            unresolved.append("working_capital_not_verified_sufficient")
        if proposed is None or proposed > opp["maximum_contract_value_cents"]:
            unresolved.append("proposed_price_unknown_or_exceeds_public_cap")
        margin = None
        if proposed is not None and all(v is not None for v in costs.values()):
            margin = proposed - sum(costs.values())
            if margin <= 0:
                unresolved.append("hypothetical_margin_nonpositive")
        if not timely:
            unresolved.append("official_source_stale_or_closed")
        if opp["kind"] == "RFI":
            unresolved.append("nonpurchase_request_for_information")
        results.append({
            "route": route,
            "decision": "HOLD_NO_BID" if unresolved else "READY_FOR_INDEPENDENT_REVIEW",
            "unresolved": sorted(set(unresolved)),
            "hypothetical_margin_cents": margin,
        })
    input_sha = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return {
        "schema": "agi-alpha/commercial-source-admission-result/v1",
        "input_sha256": input_sha,
        "evaluated_on": today.isoformat(),
        "opportunity_id": opp["id"],
        "buyer_observed_procurement_need": True,
        "external_collections_cents": 0,
        "contract_awards_observed": 0,
        "modeled_profit_cents": None,
        "actual_profit_cents": None,
        "operating_ledger_modified": False,
        "authorized_to_bid": False,
        "authorized_to_deploy": False,
        "arrangements": results,
        "scope": "PUBLIC_SOLICITATION_AND_UNVERIFIED_RESEARCH_GATE_NOT_PURCHASER_ACCEPTANCE",
    }

def load(path):
    path = Path(path).absolute()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError("BOUNDED_REGULAR_INPUT_REQUIRED")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--date", required=True)
    opts = parser.parse_args()
    print(json.dumps(evaluate(load(opts.input), on_date=opts.date), sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
