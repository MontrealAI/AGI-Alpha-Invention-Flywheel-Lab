import argparse
import json
from fractions import Fraction
from pathlib import Path


def integer(name, value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def exact(value):
    value = Fraction(value)
    return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def cost(n, fixed, variable, pooled):
    for name, value in (("buyers", n), ("fixed", fixed), ("variable", variable)):
        integer(name, value)
    if type(pooled) is not bool:
        raise ValueError("pooled must be Boolean")
    return (fixed if pooled else n * fixed) + n * variable if n else 0


def arrangement(n, fixed, variable, pooled, price=12, value=13, accepted=True, price_cap=None):
    for name, number in (("price", price), ("value", value)):
        integer(name, number)
    if type(accepted) is not bool:
        raise ValueError("accepted must be Boolean")
    if price_cap is not None:
        integer("price_cap", price_cap)
    total = cost(n, fixed, variable, pooled)
    willing = n > 0 and price < value
    response_permits = price_cap is None or price <= price_cap
    revenue = n * price if accepted and willing and response_permits else 0
    surplus = n * (value - price) if accepted and willing and response_permits else 0
    margin = revenue - total
    upper_profit = n * value - total
    response_bound = n * min(value, price_cap if price_cap is not None else value) - total
    return {"buyers": n, "fixed_cost": fixed, "variable_cost": variable,
            "pooled": pooled, "offered_price": price, "buyer_value": value,
            "accepted": accepted, "strict_buyer_participation": willing,
            "price_response_cap": price_cap, "price_response_permits_offer": response_permits,
            "complete_production_cost": total, "conditional_recognized_revenue": revenue,
            "forced_delivery_profit": margin, "buyer_surplus_if_accepted": surplus,
            "profitable_voluntary_price_exists": accepted and n > 0 and response_bound > 0,
            "profit_supremum_at_open_value_bound": upper_profit if accepted else -total,
            "profit_upper_bound_under_response": response_bound if accepted else -total,
            "break_even_unit_price": exact(Fraction(total, n)) if n else None,
            "best_of_this_offer_and_non_entry": max(0, margin),
            "execute_this_offer": accepted and willing and response_permits and margin > 0}


def quantities(initial, recognized, collected, paid, reserve=0):
    for name, number in (("initial", initial), ("recognized", recognized),
                         ("collected", collected), ("paid", paid), ("reserve", reserve)):
        integer(name, number)
    if collected > recognized:
        raise ValueError("This illustration has no prepayments or excess collections")
    cash = initial + collected - paid
    if cash < reserve:
        raise ValueError("This illustration requires cash sufficient for paid costs and reserves")
    return {"initial_cash": initial, "recognized_revenue": recognized,
            "collected_revenue": collected, "costs_expensed_and_paid": paid,
            "recognized_profit": recognized - paid, "cash": cash,
            "uncollected_receivable": recognized - collected,
            "protected_reserve": reserve, "available_cash": cash - reserve}


def admission(available, needed):
    integer("available", available)
    integer("needed", needed)
    return {"available_cash": available, "required_before_collection": needed,
            "fundable": available >= needed}


def evaluate():
    arms = []
    for name, fixed, variable in (("ordinary", 20, 12), ("new", 30, 7)):
        for pooled in (False, True):
            arms.append({"production": name, "arrangement": "pooled" if pooled else "individual",
                         **arrangement(10, fixed, variable, pooled)})
    predecessor = quantities(100, 120, 120, 100)
    delayed = quantities(100, 120, 0, 100)
    protected = quantities(100, 120, 120, 100, reserve=15)
    failed = quantities(100, 0, 0, 100)
    candidate = arrangement(10, 30, 7, True)
    ordinary_constructor = arrangement(10, 30, 7, True)
    policy_assets = [{"procedure": policy, "inherited_artifact": inherited,
                     "continuation_cost": 24 if inherited else 40,
                     "earlier_asset_construction": 16 if inherited else 0,
                     "complete_history_cost": 40}
                    for policy in ("reference", "revised") for inherited in (False, True)]
    return {
        "schema_version": 1,
        "kind": "authored_exact_analytical_illustration",
        "units": "abstract_units_not_dollars",
        "scope": "Pure explanatory arithmetic; no market observations, physical production, native accounts, live transactions, autonomous discovery result or scale-profit evidence.",
        "assumptions": {
            "costs": "Stipulated complete costs within this finite model. All are expensed and paid immediately. Taxes, financing, maintenance, liability, further coordination costs and all unlisted burdens are zero by definition, not empirical estimates.",
            "participation": "Homogeneous buyers purchase only when price is strictly below value and the contracted output is accepted; equality does not force purchase.",
            "pricing": "Price 12 is a selected illustrative offer, not an optimized price, equilibrium or observed willingness to pay. Value 13 is an open upper price bound; reported upper profit is a supremum, not attained under strict participation.",
            "alternatives": "Production ablations restrict components for causal explanation. An unrestricted conventional constructor can choose the entire same route and ties. Rival and candidate are alternative worlds; their ten buyers are not counted twice.",
            "arrangement_table": "Loss entries are conditional forced-production comparisons. Non-entry is available at zero. No account is funded or charged by the table.",
            "liquidity": "Initial cash 100 pays the predecessor's 100-unit cost before any invoice or collection. Reserves restrict availability without being expensed twice. No further financing is available for the successor comparisons.",
            "imitation": "Conditional post-entry identical-product price game with common variable cost 7 and ample capacity. This imposes a price response after setup, not a solved dynamic entry equilibrium.",
            "discovery_control": "The crossed policy/assets costs are authored negative-control quantities, not measured discovery runs. Real process claims need fresh executed tasks and independent controls."
        },
        "arrangements": arms,
        "accepted_predecessor": predecessor,
        "failure_cases": {
            "buyer_value_nine": arrangement(10, 30, 7, True, price=8, value=9),
            "only_five_buyers": arrangement(5, 30, 7, True),
            "late_collection": {"quantities": delayed, "successor": admission(delayed["available_cash"], 110)},
            "protected_cash": {"quantities": protected, "successor": admission(protected["available_cash"], 110)},
            "imitation_price_seven": arrangement(10, 30, 7, True, price=7, price_cap=7),
            "acceptance_failed": {"offer": arrangement(10, 30, 7, True, accepted=False), "quantities": failed}
        },
        "strong_complete_alternative": {
            "candidate": candidate, "ordinary_constructor": ordinary_constructor,
            "complete_cost_difference": candidate["complete_production_cost"] - ordinary_constructor["complete_production_cost"],
            "profit_difference": candidate["forced_delivery_profit"] - ordinary_constructor["forced_delivery_profit"],
            "unique_inventor_advantage_established": False
        },
        "capability_successor": {
            "without_inherited_means": admission(120, 130),
            "with_inherited_means": admission(120, 110),
            "initial_funds_with_inherited_means": admission(100, 110),
            "conditional_accepted_receipt": 145,
            "accepted_complete_history": quantities(100, 120 + 145, 120 + 145, 100 + 110),
            "expanded_conventional_alternative": admission(120, 110),
            "scope": "Enablement holds only for the declared alternatives and funding path. Adding a 110-unit ordinary alternative defeats claimed necessity. A conventional constructor retaining the same means ties the whole history."
        },
        "mere_financing_successor": {
            "without_inherited_means": admission(120, 115),
            "with_inherited_means": admission(120, 115),
            "initial_funds": admission(100, 115),
            "conditional_accepted_receipt": 130,
            "accepted_complete_history": quantities(100, 120 + 130, 120 + 130, 100 + 115),
            "technical_asset_effect": 0
        },
        "crossed_discovery_negative_control": {
            "cells": policy_assets, "asset_continuation_saving": 16,
            "procedure_saving_without_artifact": 0, "procedure_saving_with_artifact": 0,
            "complete_history_saving": 0, "improved_inventor_established": False
        },
        "qualification": {"illustration_computes": True, "real_demand_observed": False,
                          "physical_product_validated": False, "discovery_advantage_established": False,
                          "native_simulation_profit_claimed": False, "super_alpha_demonstrated": False}
    }


def main():
    parser = argparse.ArgumentParser(description="Reproduce exact authored SUPER ALPHA illustrations; no network or business account access.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(evaluate(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
