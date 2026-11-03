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


def event(label, receipt=0, outflow=0, financing=0, reserve=0):
    return {"label": label, "settled_receipt": receipt, "cash_outflow": outflow,
            "financing_received": financing, "reserve_after": reserve}


def funding_requirement(events):
    if not isinstance(events, (list, tuple)) or not events:
        raise ValueError("A finite ordered plan must include an explicit opening-reserve event")
    fields = {"label", "settled_receipt", "cash_outflow", "financing_received", "reserve_after"}
    receipts = outflows = financing = required = 0
    prefixes = []
    for index, row in enumerate(events):
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Every event must use the exact settled-flow and reserve schema")
        if not isinstance(row["label"], str) or not row["label"].strip():
            raise ValueError("Every event needs a nonempty label")
        for field in fields - {"label"}:
            integer(field, row[field])
        active_flows = sum(row[field] > 0 for field in ("settled_receipt", "cash_outflow", "financing_received"))
        if active_flows > 1:
            raise ValueError("Split receipts, outflows and financing into explicitly ordered events")
        if index == 0 and active_flows:
            raise ValueError("Event zero specifies opening reserves before any cash flow")
        receipts += row["settled_receipt"]
        outflows += row["cash_outflow"]
        financing += row["financing_received"]
        prefix_requirement = max(0, row["reserve_after"] + outflows - receipts - financing)
        required = max(required, prefix_requirement)
        prefixes.append({"event_index": index, **row, "cumulative_receipts": receipts,
                         "cumulative_outflows": outflows, "cumulative_financing_received": financing,
                         "opening_cash_required_at_prefix": prefix_requirement})
    return {"minimum_opening_cash": required, "ordered_prefixes": prefixes,
            "settled_receipts": receipts, "cash_outflows": outflows,
            "financing_received": financing, "terminal_reserve": events[-1]["reserve_after"],
            "net_nonfinancing_cash_flow": receipts - outflows,
            "terminal_cash_at_minimum_opening": required + receipts + financing - outflows}


def renewal_screen(opening_available, upfront_cost, settled_rate, qualification_delay, deadline):
    for name, number in (("opening_available", opening_available), ("upfront_cost", upfront_cost),
                         ("settled_rate", settled_rate), ("qualification_delay", qualification_delay),
                         ("deadline", deadline)):
        integer(name, number)
    shortfall = max(0, upfront_cost - opening_available)
    wait = Fraction(shortfall, settled_rate) if settled_rate else (Fraction(0) if not shortfall else None)
    earliest = wait + qualification_delay if wait is not None else None
    latest_start = deadline - qualification_delay
    minimum_opening = max(0, upfront_cost - settled_rate * latest_start) if latest_start >= 0 else None
    return {"opening_available_cash": opening_available, "upfront_successor_cost": upfront_cost,
            "net_unrestricted_settled_rate": settled_rate, "qualification_delay": qualification_delay,
            "deadline": deadline, "earliest_cash_ready_time": exact(wait) if wait is not None else None,
            "earliest_qualification_time": exact(earliest) if earliest is not None else None,
            "latest_start_time": latest_start,
            "minimum_opening_available_cash_for_deadline": minimum_opening,
            "can_qualify_by_deadline": earliest is not None and earliest <= deadline,
            "deadline_equality_is_accepted": True}


def renewal_examples():
    plans = {
        "settled_before_successor": [event("opening"), event("predecessor cost", outflow=100),
                                     event("predecessor accepted and invoiced"),
                                     event("predecessor collection", receipt=120),
                                     event("successor cost", outflow=110),
                                     event("accepted successor collection", receipt=145)],
        "reserve_fifteen": [event("opening"), event("predecessor cost", outflow=100),
                            event("predecessor accepted and collected; protect reserve", receipt=120, reserve=15),
                            event("successor cost", outflow=110, reserve=15),
                            event("accepted successor collection", receipt=145, reserve=15)],
        "delayed_collection_with_reserve": [event("opening"), event("predecessor cost", outflow=100),
                                           event("predecessor accepted; protect reserve", reserve=15),
                                           event("successor cost before predecessor collection", outflow=110, reserve=15),
                                           event("late predecessor collection", receipt=120, reserve=15),
                                           event("accepted successor collection", receipt=145, reserve=15)]
    }
    cases = {}
    for name, plan in plans.items():
        required = funding_requirement(plan)
        cases[name] = {**required, "recognized_revenue": 265, "recognized_expense": 210,
                       "recognized_profit": 55, "reference_opening_cash": 100,
                       "fundable_at_reference_opening": required["minimum_opening_cash"] <= 100,
                       "hypothetical_terminal_cash_at_reference_if_all_events_occur": 155}
    return {
        "funding": {
            "scope": "Minimum cash requirements of fixed authored event sequences; no executed accounts or received funding. Events are strictly ordered, with at most one positive cash-flow category per event. Event zero sets opening reserves. Financing counts only when actually received in the declared plan; a commitment or invoice is not a receipt.",
            "accounting": "The three cases retain stipulated recognized revenue 265 and expensed costs 210. Reserve 15 restricts cash without adding expense. In the 105-unit case, acceptance and settlement occur together before the reserve is required after that event; in the 225-unit case, acceptance requires the reserve before delayed collection. Positive hypothetical terminal cash is not evidence that an underfunded prefix can execute.",
            "cases": cases
        },
        "deadline": {
            "scope": "Conditional fixed-path renewal screen with constant net unrestricted settled surplus, no financing, an upfront construction cost and deterministic qualification delay. The predecessor continues without interference, and the successor is only a qualified-path hypothesis. Times beyond the deadline are arithmetic under the constant-rate assumption, not achieved continuation. No profit change is inferred from changing the assumed delay or available cash.",
            "cases": {
                "base_misses_deadline": renewal_screen(20, 60, 10, 3, 6),
                "ten_more_available_units": renewal_screen(30, 60, 10, 3, 6),
                "one_less_qualification_period": renewal_screen(20, 60, 10, 2, 6)
            }
        }
    }


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
    target_cases = {
        "baseline": arrangement(10, 30, 7, True, price=10, price_cap=10),
        "fixed_cost_ten": arrangement(10, 10, 7, True, price=10, price_cap=10),
        "variable_cost_five": arrangement(10, 30, 5, True, price=10, price_cap=10),
        "seventeen_buyers": arrangement(17, 30, 7, True, price=10, price_cap=10)
    }
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
        "construction_targets": {
            "scope": "A separate prospective price-10 scenario with desired profit 20. Each target changes one stated burden or cohort size, with all construction costs included. These are economic specifications, not achieved constructions or measured additional demand; incurred historical costs are unchanged.",
            "desired_profit": 20, "price_response_cap": 10, "buyer_value": 13,
            "baseline_complete_cost_gap": target_cases["baseline"]["complete_production_cost"] + 20 - 10 * 10,
            "cases": {name: {**row, "meets_desired_profit": row["forced_delivery_profit"] >= 20}
                      for name, row in target_cases.items()}
        },
        "funded_renewal": renewal_examples(),
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
