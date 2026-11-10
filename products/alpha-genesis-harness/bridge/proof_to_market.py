# SPDX-License-Identifier: Apache-2.0
"""Non-transactional development/acceptance planning; never a financial ledger."""
from __future__ import annotations

import copy
from .adapters import BridgeError
from .workflows import digest, encoded

CATEGORIES = {"inference", "tools", "compute", "construction", "verification", "maintenance",
              "failed-experiments", "coordination", "financing", "support", "other"}
STAGES = ("forecast", "interest", "commitment", "invoiced", "collected", "earned")


def require(ok, message):
    if not ok:
        raise BridgeError("MARKET_PLAN", message)


def text(value, name, maximum=2000):
    require(isinstance(value, str) and 0 < len(value) <= maximum, name + " must be bounded nonempty text.")
    return value


def money(value, name):
    require(type(value) is int and 0 <= value <= 9_007_199_254_740_991,
            name + " must be a nonnegative exact integer in currency minor units.")
    return value


def rows(value, name):
    require(isinstance(value, list) and len(value) <= 1000, name + " must be a bounded list.")
    require(all(isinstance(row, dict) for row in value), name + " must contain objects.")
    ids = [text(row.get("id"), name + " ID", 100) for row in value]
    require(len(ids) == len(set(ids)), name + " IDs must be unique.")
    return value


def assess(plan):
    """Recompute supplied assumptions; user-entered receipts cannot certify commerce.

    Member payments are transfers, never revenue. Funding is prospective. Repeated
    pipeline stages are separate amounts for the same opportunity, never additive.
    Costs and funding form a finite planning projection, not spendable cash.
    """
    require(isinstance(plan, dict) and len(encoded(plan)) <= 1_048_576, "Plan must be a bounded object.")
    allowed = {"desired_result", "acceptance", "currency", "missing_capabilities", "participants",
               "costs", "funding", "milestones", "alternatives", "commercial_records"}
    require(not set(plan) - allowed, "Unsupported plan fields; this planner has no transaction or contract execution tool.")
    title = text(plan.get("desired_result"), "Desired result")
    acceptance = text(plan.get("acceptance"), "Customer acceptance")
    currency = plan.get("currency")
    require(isinstance(currency, str) and len(currency) == 3 and currency.isascii() and currency.isupper(), "Use a three-letter currency code.")
    missing = plan.get("missing_capabilities", [])
    require(isinstance(missing, list) and len(missing) <= 100 and all(isinstance(x, str) and 0 < len(x) <= 200 for x in missing), "Missing capabilities must be a bounded text list.")
    costs = rows(plan.get("costs", []), "Costs")
    funding = rows(plan.get("funding", []), "Funding")
    milestones = rows(plan.get("milestones", []), "Milestones")
    participants = rows(plan.get("participants", []), "Participants")
    alternatives = rows(plan.get("alternatives", []), "Alternatives")
    records = rows(plan.get("commercial_records", []), "Commercial records")
    issues, total, costs_by_period, funding_by_period = [], 0, {}, {}
    unknown_costs = []
    categories = set()
    for row in costs:
        category = row.get("category")
        require(category in CATEGORIES, "Unknown cost category.")
        categories.add(category)
        period = money(row.get("period", 0), "Cost period")
        amount = row.get("amount_minor")
        text(row.get("basis"), "Cost basis")
        if amount is None:
            unknown_costs.append(row["id"])
            continue
        amount = money(amount, "Cost amount")
        total += amount
        costs_by_period[period] = costs_by_period.get(period, 0) + amount
    for row in funding:
        money(row.get("amount_minor"), "Prospective funding")
        period = money(row.get("period", 0), "Funding period")
        require(row.get("kind") in {"owner", "customer", "grant", "debt", "equity"}, "Choose an explicit funding kind.")
        text(row.get("terms"), "Financing terms, obligations and cost basis")
        funding_by_period[period] = funding_by_period.get(period, 0) + row["amount_minor"]
    projection, balance, peak_gap = [], 0, 0
    for period in sorted(set(costs_by_period) | set(funding_by_period)):
        balance += funding_by_period.get(period, 0) - costs_by_period.get(period, 0)
        peak_gap = max(peak_gap, -balance)
        projection.append({"period": period, "prospective_funding_minor": funding_by_period.get(period, 0),
                           "known_cost_minor": costs_by_period.get(period, 0), "conditional_balance_minor": balance})
    participation = []
    for row in participants:
        text(row.get("role"), "Participant role")
        benefit = money(row.get("benefit_minor"), "Participant benefit")
        contribution = money(row.get("contribution_minor"), "Participant contribution")
        outside = money(row.get("outside_option_minor"), "Participant outside option")
        surplus = benefit - contribution - outside
        participation.append({"id": row["id"], "conditional_surplus_minor": surplus,
                              "individually_rational_under_assumptions": surplus >= 0, "consent": "NOT_ESTABLISHED"})
        if surplus < 0:
            issues.append("Participant " + row["id"] + " prefers its declared outside option.")
    milestone_views = []
    for row in milestones:
        text(row.get("deliverable"), "Milestone deliverable")
        text(row.get("acceptance"), "Milestone acceptance")
        status = row.get("status", "proposed")
        require(status in {"proposed", "constructed", "submitted", "accepted", "rejected"}, "Unknown milestone status.")
        evidence = row.get("evidence", [])
        require(isinstance(evidence, list) and len(evidence) <= 100 and all(isinstance(e, str) and len(e) <= 2000 for e in evidence), "Milestone evidence must be bounded references.")
        if status in {"accepted", "rejected"}:
            require(bool(evidence), "Acceptance/rejection records require an evidence reference.")
        milestone_views.append({"id": row["id"], "recorded_status": status, "evidence": evidence,
                                "verification": "OPERATOR_RECORDED_NOT_INDEPENDENTLY_VALIDATED"})
    comparisons = []
    for row in alternatives:
        text(row.get("description"), "Alternative description")
        require(row.get("route") in {"independent", "purchase", "shared", "commissioned", "no-build"}, "Unknown alternative route.")
        require(type(row.get("feasible")) is bool, "Alternative feasibility must be explicitly declared.")
        amount = row.get("total_cost_minor")
        if amount is not None:
            money(amount, "Alternative cost")
        comparisons.append(copy.deepcopy(row))
    pipeline = {stage: 0 for stage in STAGES}
    for row in records:
        stage = row.get("stage")
        require(stage in STAGES, "Commercial stage must distinguish forecast, interest, commitment, invoice, collection and earned revenue.")
        amount = money(row.get("amount_minor"), "Recorded commercial amount")
        reference = row.get("evidence_reference")
        if stage != "forecast":
            text(reference, "Commercial evidence reference")
        pipeline[stage] += amount
    uncovered = sorted(CATEGORIES - categories)
    if unknown_costs or uncovered:
        issues.append("Complete costs remain unknown.")
    if peak_gap:
        issues.append("Prospective funding arrives too late or is insufficient for declared costs.")
    if not milestones:
        issues.append("No delivery milestones supplied.")
    if not participants:
        issues.append("No participants or outside options supplied.")
    if not alternatives:
        issues.append("No competent alternatives supplied.")
    return {"schema": "genesis-proof-to-market/v1", "plan_sha256": digest(plan),
            "desired_result": title, "acceptance": acceptance, "currency": currency,
            "missing_capabilities": missing, "technical_feasibility": "REQUIRES_INDEPENDENT_TEST",
            "economic_feasibility": "CONDITIONAL_ON_DECLARED_ASSUMPTIONS" if not issues else "UNRESOLVED",
            "commercial_validation": "NOT_ESTABLISHED", "known_cost_minor": total,
            "unknown_cost_ids": unknown_costs, "uncovered_cost_categories": uncovered,
            "prospective_funding_minor": sum(funding_by_period.values()), "peak_funding_gap_minor": peak_gap,
            "cash_flow_projection": projection, "participants": participation,
            "milestones": milestone_views, "alternatives": comparisons,
            "operator_recorded_pipeline_minor": pipeline, "verified_earned_revenue_minor": None,
            "verified_complete_cost_profit_minor": None, "available_reinvestable_surplus_minor": None,
            "issues": issues, "scope": "Non-transactional planning and operator-recorded evidence. Pipeline stages must not be summed as revenue. No contract, consent, verified payment, financial account, spendable balance or successful market is created."}
