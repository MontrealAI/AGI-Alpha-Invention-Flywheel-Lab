"""Read-only counterexample gate for declared partner payoffs and seller transfers.

Not supplier consent evidence, an executed contract, a native admission or profit.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from enterprise078.transactional_admission.choice import (
    money, quote, registered_rows, registered_bundles, subset_key,
)
from enterprise078.transactional_admission.offer import COSTS
from enterprise078.transactional_admission.planning import plan

PINNED = {
    "enterprise078/transactional_admission/choice.py": "ceff4afbfc4c680ade86f9fc536d99e4a64f730a",
    "enterprise078/transactional_admission/planning.py": "537bb71dae621962f6787c16d69d51a8f12c7f46",
}
FIELDS = frozenset(("quote", "compensation", "own_cost", "outside_surplus", "seller_cost_category"))


def pin_source(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    for relative, expected in PINNED.items():
        path = root / relative
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError("PINNED_REGULAR_PARTNER_REVIEW_SOURCE_REQUIRED")
        raw = path.read_bytes()
        observed = hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest()
        if observed != expected:
            raise ValueError("PARTNER_REVIEW_INCUMBENT_SOURCE_CHANGED:" + relative)
    return dict(PINNED)


def exact_quote(given, expected):
    if not isinstance(given, dict) or set(given) != set(expected):
        return False
    for ident, entry in given.items():
        if not isinstance(entry, dict) or set(entry) != {"price", "terms_id"}:
            return False
        try:
            money(entry["price"])
        except ValueError:
            return False
        if not isinstance(entry["terms_id"], str) or not entry["terms_id"]:
            return False
    return given == expected


def review(rows, bundles, *, wallets, available, earned, sunk_acquisition,
           decision_time, scenarios, partner_economics):
    """Add necessary partner rationality and seller-transfer checks to fixed plan.

    Every scenario is a declared *predecision assumption*, not a collected
    partner consent. Each partner must strictly prefer its disclosed contractual
    payoff over its explicit outside option; supplier costs and contingent risks
    belong in own_cost, and all compensation must be provided for inside the
    seller's original complete package costs. Never revise the native ledger.
    """
    source = pin_source()
    rows = list(rows)
    by_id = registered_rows(rows, wallets)
    packages = registered_bundles(bundles, by_id)
    base = plan(rows, packages, wallets=wallets, available=available, earned=earned,
                sunk_acquisition=sunk_acquisition, decision_time=decision_time,
                scenarios=scenarios)
    if not isinstance(partner_economics, dict) or set(partner_economics) != set(scenarios):
        raise ValueError("ALL_REGISTERED_PARTNER_SCENARIOS_REQUIRED")
    outcomes = []
    for out in base["outcomes"]:
        ids = out["bundle"]
        reasons = set(out["reasons"])
        records = {}
        if ids:
            selected = [by_id[ident] for ident in ids]
            groups = {}
            for row in selected:
                if row.get("partner") is not None:
                    groups.setdefault(row["partner"], []).append(row)
            for name, scenario in sorted(scenarios.items()):
                declarations = partner_economics[name]
                if not isinstance(declarations, dict) or set(declarations) != set(groups):
                    reasons.add("PARTNER_ECONOMICS_COVERAGE_UNESTABLISHED:" + name)
                    continue
                seller_costs = scenario["costs"].get(subset_key(ids))
                provision = {}
                details = {}
                for partner, group in sorted(groups.items()):
                    key = subset_key(row["id"] for row in group)
                    entry = declarations.get(partner, {}).get(key) if isinstance(declarations.get(partner), dict) else None
                    if not isinstance(entry, dict) or set(entry) != FIELDS:
                        reasons.add("PARTNER_ECONOMICS_UNESTABLISHED:" + name + ":" + partner)
                        continue
                    if not exact_quote(entry["quote"], quote(group)):
                        reasons.add("PARTNER_PAYOFF_QUOTE_CHANGED:" + name + ":" + partner)
                        continue
                    category = entry["seller_cost_category"]
                    if category not in COSTS:
                        reasons.add("PARTNER_COST_CATEGORY_UNREGISTERED:" + name + ":" + partner)
                        continue
                    try:
                        paid = money(entry["compensation"])
                        own = money(entry["own_cost"])
                        outside = money(entry["outside_surplus"])
                    except ValueError:
                        reasons.add("PARTNER_PAYOFF_NOT_ESTABLISHED:" + name + ":" + partner)
                        continue
                    if paid <= own + outside:
                        reasons.add("PARTNER_OUTSIDE_OPTION_WINS_OR_TIES:" + name + ":" + partner)
                    provision[category] = provision.get(category, 0) + paid
                    details[partner] = {"partner_residual_microUSD": paid - own - outside,
                                        "seller_category": category, "transfer_microUSD": paid}
                if provision:
                    for category, promised in provision.items():
                        recognized = seller_costs.get(category) if isinstance(seller_costs, dict) else None
                        if type(recognized) is not int or recognized < promised:
                            reasons.add("PARTNER_PAYMENT_NOT_IN_SELLER_COSTS:" + name + ":" + category)
                records[name] = details
        outcomes.append({
            "bundle": list(ids), "feasible": out["feasible"] and not reasons,
            "reasons": sorted(reasons), "partner_payoffs": records,
            "worst_case_net_microUSD": out["worst_case_net_microUSD"],
        })
    winner = outcomes[0]
    for out in outcomes[1:]:
        if (out["feasible"] and out["worst_case_net_microUSD"] is not None
                and out["worst_case_net_microUSD"] > winner["worst_case_net_microUSD"]):
            winner = out
    return {
        "incumbent_predecision_selected_bundle": base["selected_bundle"],
        "review_selected_bundle": list(winner["bundle"]),
        "review_worst_case_net_microUSD": winner["worst_case_net_microUSD"],
        "outcomes": outcomes,
        "source_blobs": source,
        "native_catalog_admitted": False, "native_mutations": 0,
        "partner_contracts_executed": False, "observed_partner_evidence": False,
        "observed_buyers": False, "forecast_expected_net": None,
        "scope": "authored partner incentive and transfer-coverage counterexample; read-only conditional review, not supplier consent, native profit or deployment",
    }
