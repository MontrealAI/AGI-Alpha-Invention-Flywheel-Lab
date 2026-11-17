"""FRONTIER Ω ignition decisions: evidence and cash gates, not unauthorized execution.

All external observations and economic inputs remain assertions until receipts
are separately audited. This module neither calls models nor spends money.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .__main__ import COST_CATEGORIES, InventoryError, assess_one, rank, read_json, validate


def _nonnegative(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise InventoryError(name + " must be a finite nonnegative number")
    return float(value)


def _complete_cost(costs):
    if not isinstance(costs, dict) or set(costs) != set(COST_CATEGORIES):
        raise InventoryError("Cost envelope must include every full-lifecycle category")
    return round(sum(_nonnegative(costs[k], k) for k in COST_CATEGORIES), 2)


def result(o, decision, why, *, reported_metrics=None, next_action=None):
    return {
        "opportunity_id": o["id"],
        "engine": o["engine"],
        "title": o["title"],
        "decision": decision,
        "reason": why,
        "next_action": next_action or o["first_discriminating_test"],
        "status": "READ_ONLY_RECOMMENDATION_NOT_EXECUTION_OR_EVIDENCE_CERTIFICATION",
        "reported_metrics": reported_metrics or {},
    }


def ignition(o, evidence=None):
    """Choose the earliest defensible action; fail closed on unknown obligations.

    Evidence and booleans are caller-reported, not authenticated by this
    classifier. A reported crossing never upgrades itself to audited truth.
    """
    if evidence is None:
        return result(o, "PROBE_CANDIDATE", "No matched pre/post benchmark or paid-demand evidence exists.")
    if type(evidence) is not dict:
        raise InventoryError("Evidence must be an object")
    if evidence.get("synthetic") is True:
        return result(o, "SYNTHETIC_REHEARSAL", "Synthetic evidence cannot ignite real production.")
    if evidence.get("synthetic") is not False:
        raise InventoryError("Synthetic flag must be explicit")
    if evidence.get("source_access_confirmed") is not True:
        return result(o, "VERIFY_SOURCE_ACCESS", "Announcement is not proof of usable capability.")
    if evidence.get("test_authorized") is not True:
        return result(o, "AWAIT_TEST_AUTHORIZATION", "Testing rights and scope have not been established.")
    if "matched_test" not in evidence:
        return result(o, "RUN_MATCHED_CROSSING_TEST", "No comparable historical and current test.")
    test = dict(evidence["matched_test"])
    # An outer nonsynthetic declaration cannot erase a nested rehearsal flag.
    # Preserve any pre-bound evidence identity rather than laundering it
    # into a different opportunity's acceptance threshold.
    if "opportunity_id" in test and test["opportunity_id"] != o["id"]:
        raise InventoryError("Nested benchmark opportunity ID mismatch")
    if "synthetic" in test and type(test["synthetic"]) is not bool:
        raise InventoryError("Nested benchmark synthetic flag must be Boolean")
    if test.get("synthetic") is True:
        return result(o, "SYNTHETIC_REHEARSAL",
                      "A synthetic matched benchmark cannot support a real pilot.")
    test.setdefault("opportunity_id", o["id"])
    test.setdefault("synthetic", False)
    finding = assess_one(o, test)
    tech = finding["stage"]
    if tech in {"BLOCKED_CURRENT_BELOW_ACCEPTANCE_COST_OR_TIME_GATE",
                "UNINDEPENDENT_CROSSING_REPORT_NEEDS_VERIFIER"}:
        return result(o, "RETEST_OR_REDESIGN", "The current benchmark does not independently meet every scoped crossing gate.",
                      reported_metrics={"technical_stage": tech})
    if tech == "QUALIFIED_BUT_NO_NEW_FIVE_WEEK_CROSSING":
        recent = False
    elif tech in {"REPORTED_NEW_TECHNICAL_CROSSING_AUDIT_REQUIRED",
                  "REPORTED_PAID_OUTCOME_AUDIT_REQUIRED"}:
        recent = True
    else:
        return result(o, "HOLD_UNRESOLVED_TECHNICAL_EVIDENCE", "Technical status cannot be promoted.",
                      reported_metrics={"technical_stage": tech})
    if evidence.get("external_receipt_audit") is not True:
        return result(o, "INDEPENDENT_AUDIT_REQUIRED", "A self-reported benchmark and a URL cannot certify a crossing.",
                      reported_metrics={"technical_stage": tech, "new_five_week_crossing_reported": recent})
    if evidence.get("strongest_complete_alternative_tested") is not True:
        return result(o, "COMPARE_STRONG_ALTERNATIVE",
                      "A new solution must be evaluated against a capable, fully costed incumbent.",
                      reported_metrics={"new_five_week_crossing_reported": recent})
    if evidence.get("buyer_contact_authorized") is not True:
        return result(o, "AWAIT_MARKET_AUTHORIZATION",
                      "No outreach or buyer-data access without explicit permission.")
    pilot = evidence.get("pilot")
    if not isinstance(pilot, dict) or pilot.get("signed_order") is not True:
        return result(o, "VERIFY_PAID_DEMAND",
                      "A proposed quote or market-size estimate is not buyer willingness to pay.")
    for key in ("contract_price_usd", "liquid_unrestricted_cash_usd", "remaining_obligations_reserved_usd"):
        if key not in pilot:
            raise InventoryError("Missing actual contract / liquidity boundary: " + key)
    price = _nonnegative(pilot["contract_price_usd"], "contract_price_usd")
    cash = _nonnegative(pilot["liquid_unrestricted_cash_usd"], "liquid_unrestricted_cash_usd")
    residual_reserve = _nonnegative(pilot["remaining_obligations_reserved_usd"], "remaining_obligations_reserved_usd")
    complete_upper = _complete_cost(pilot.get("upper_complete_costs_usd"))
    # Tail cash reserves are liquidity protection, not an additional expense.
    # The complete-cost envelope already contains residual_obligations.
    if residual_reserve > _nonnegative(pilot["upper_complete_costs_usd"]["residual_obligations"], "residual_obligations"):
        raise InventoryError("Reserved tail obligations exceed the costed tail; expand the full-cost envelope")
    gross_surplus_floor = round(price - complete_upper, 2)
    envelope = {
        "new_five_week_crossing_reported": recent,
        "contract_price_usd_reported": price,
        "pessimistic_complete_cost_usd": complete_upper,
        "tail_cash_reserved_within_complete_cost_usd": residual_reserve,
        "contracted_surplus_floor_usd_not_profit": gross_surplus_floor,
        "unrestricted_cash_usd_reported": cash,
        "break_even_unit_cost_usd": price,
    }
    if pilot.get("customer_rights_confirmed") is not True:
        return result(o, "AWAIT_CUSTOMER_DATA_RIGHTS",
                      "A signed order does not grant rights to process every dataset or tool.",
                      reported_metrics=envelope)
    if gross_surplus_floor <= 0:
        return result(o, "WAIT_FOR_COST_OR_PRICE_CROSSING",
                      "Complete pessimistic delivery cost (including tail exposure) meets or exceeds contract value.",
                      reported_metrics=envelope,
                      next_action="Reduce measured all-in cost, improve contracted customer value, or redesign the deliverable.")
    if cash < complete_upper:
        return result(o, "AWAIT_FUNDED_EXECUTION",
                      "The projected signed order cannot be prefunded using reported unrestricted cash.",
                      reported_metrics=envelope,
                      next_action="Secure real unrestricted funding or stage a smaller qualifying deliverable. Never spend future profit.")
    if pilot.get("outside_option_beaten") is not True:
        return result(o, "COMPARE_BUYER_OUTSIDE_OPTION",
                      "A cheaper producer is not necessarily a better buyer offer; confirm the real buyer prefers the full outcome.",
                      reported_metrics=envelope)
    sales = evidence.get("sales") or {}
    if type(sales) is not dict:
        raise InventoryError("Sales evidence must be an object")
    settled = sales.get("accepted_and_collected_count", 0)
    if type(settled) is not int or settled < 0:
        raise InventoryError("Invalid paid-delivery count")
    if settled >= 2 and sales.get("native_account_audited") is True and sales.get("repeat_customer_documented") is True:
        return result(o, "SCALE_CANDIDATE_AUDIT_REQUIRED",
                      "Repeat receipts are reported, but the planner cannot certify native journals or future margins.",
                      reported_metrics={**envelope, "claimed_accepted_and_collected_count": settled},
                      next_action="Independently reconcile paid receipts, tail reserves, acquisition and marginal scale costs.")
    return result(o, "IGNITE_PILOT_REVIEW_REQUIRED",
                  "Reported technical, buyer-value and conservative prefunding gates align; no action is authorized by this decision.",
                  reported_metrics=envelope,
                  next_action="Obtain approved pilot execution authority, then deliver, independently accept and collect.")


def portfolio_decisions(opportunities, evidence_by_id=None, limit=20):
    """Rank the candidate probes; never treat ordinal scores as expected returns."""
    if evidence_by_id is None:
        evidence_by_id = {}
    if not isinstance(evidence_by_id, dict):
        raise InventoryError("Evidence root must map opportunity IDs to observations")
    known = {o["id"] for o in opportunities}
    unknown = set(evidence_by_id) - known
    if unknown:
        raise InventoryError("Unknown opportunity IDs: " + ",".join(sorted(unknown)))
    if type(limit) is not int or limit < 1:
        raise InventoryError("limit must be a positive integer")
    rows = [ignition(o, evidence_by_id.get(o["id"])) for o in rank(opportunities)]
    return {
        "schema": "frontier-omega-ignition-decisions/v1",
        "qualification": "READ_ONLY_CLAIM_BOUNDED_RECOMMENDATIONS",
        "count": len(opportunities),
        "candidates": rows[:limit],
        "actual_ignitions_executed": 0,
        "actual_revenue_certified": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="FRONTIER Ω ignition: choose the next evidence-gated action; no purchases or execution.")
    parser.add_argument("--evidence", type=Path, help="Optional JSON object keyed by opportunity ID; assertions not authenticated")
    parser.add_argument("--limit", type=int, default=15)
    options = parser.parse_args(argv)
    opportunities, _ = validate()
    evidence = read_json(options.evidence) if options.evidence else {}
    print(json.dumps(portfolio_decisions(opportunities, evidence, options.limit), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (InventoryError, KeyError, TypeError, OSError) as exc:
        raise SystemExit("FRONTIER Ω ignition refused: " + str(exc))
