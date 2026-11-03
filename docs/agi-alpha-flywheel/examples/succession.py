import argparse
import json
from pathlib import Path


def quantities(initial, recognized, collected, cost, held=0, reserve=0):
    cash = initial + collected - cost
    return {"initial_cash": initial, "recognized_revenue": recognized,
            "collected_revenue": collected, "complete_cost_paid": cost,
            "profit": recognized - cost, "cash": cash,
            "receivable": recognized - collected, "held_earnings": held,
            "protection_reserve": reserve, "available_cash": cash - held - reserve}


def example():
    base, earned, ordinary, tool = 10, 6, 18, 15
    predecessor = quantities(base, 14, 14, 8)
    cells = []
    for instrument in (False, True):
        for earnings in (False, True):
            available = base + int(earnings) * earned
            required = tool if instrument else ordinary
            cells.append({"instrument_available": instrument, "earnings_available": earnings,
                          "available_cash": available, "required_cash": required,
                          "funded_admission": available >= required,
                          "held_earnings": 0 if earnings else earned,
                          "predecessor_profit": predecessor["profit"]})
    held = quantities(base, 14, 14, 8, held=earned)
    delayed = quantities(base, 14, 0, 8)
    protected = quantities(base, 14, 14, 8, reserve=2)
    accepted = quantities(base, 14 + 20, 14 + 20, 8 + tool)
    failed = quantities(base, 14, 14, 8 + tool)
    return {
        "kind": "constructed_pedagogical_counterfactual",
        "units": "exact_integer_abstract_units",
        "scope": "Static arithmetic, not an enterprise account, empirical experiment or revenue forecast.",
        "assumptions": {"financing_available": False, "omitted_cost_categories": "Taxes, support, maintenance, refunds and financing costs are zero by definition in this abstract model, not empirical estimates.",
                        "predecessor_tool_cost": "Included once in predecessor complete cost of 8.",
                        "acceptance": "Assumed for the accepted case, refused for the failed case.",
                        "alternatives": "Two declared successor methods; no claim of global minimum cost."},
        "parameters": {"b": base, "e": earned, "c_without_tool": ordinary, "c_with_tool": tool},
        "predecessor": predecessor,
        "four_cells": cells,
        "admission_interaction": int(cells[3]["funded_admission"]) - int(cells[2]["funded_admission"])
                                 - int(cells[1]["funded_admission"]) + int(cells[0]["funded_admission"]),
        "accepted_whole_sequence": {"successor_cost": tool, "successor_collection": 20,
                                    "successor_profit": 20 - tool, "totals": accepted},
        "positive_profit_insufficient_liquidity": {
            "held_earnings": {"quantities": held, "investment_cost": tool, "defer": held["available_cash"] < tool},
            "delayed_receivable": {"quantities": delayed, "investment_cost": tool, "defer": delayed["available_cash"] < tool},
            "protection_reserve": {"quantities": protected, "investment_cost": tool, "defer": protected["available_cash"] < tool}},
        "failed_successor_acceptance": {"funded_admission": predecessor["available_cash"] >= tool,
                                        "accepted": False, "successor_cost_retained": tool,
                                        "successor_collection": 0, "successor_profit": -tool, "totals": failed},
        "conventional_without_inherited_tool": {"instrument_available": False, "available_cash": 16,
                                               "required_cash": 15, "funded_admission": True,
                                               "totals": dict(accepted), "instrument_necessity_established": False,
                                               "interpretation": "An expanded alternative set has c_without_tool=15; the threshold hypothesis no longer holds."},
        "strong_conventional_same_tool": {"candidate": accepted, "ordinary_reuse": dict(accepted),
                                          "profit_difference": 0, "discovery_advantage_established": False}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(result):
    require(result["kind"] == "constructed_pedagogical_counterfactual", "Incorrect evidence label")
    p = result["parameters"]
    require((p["b"], p["e"], p["c_without_tool"], p["c_with_tool"]) == (10, 6, 18, 15), "Example parameters changed")
    expected = {(False, False): (10, 18, False, 6), (False, True): (16, 18, False, 0),
                (True, False): (10, 15, False, 6), (True, True): (16, 15, True, 0)}
    seen = set()
    for row in result["four_cells"]:
        key = (row["instrument_available"], row["earnings_available"])
        require(key not in seen and key in expected, "Missing or duplicate intervention")
        seen.add(key)
        actual = (row["available_cash"], row["required_cash"], row["funded_admission"], row["held_earnings"])
        require(actual == expected[key], "Incorrect counterfactual funding result")
        require(row["predecessor_profit"] == 6, "Withholding earnings erased recognized profit")
        require(row["available_cash"] + row["held_earnings"] == 16, "Withholding destroyed cash")
    require(seen == set(expected), "Four interventions are required")
    require(result["admission_interaction"] == 1, "Incorrect threshold interaction")
    records = [result["predecessor"], result["accepted_whole_sequence"]["totals"],
               result["failed_successor_acceptance"]["totals"],
               *[x["quantities"] for x in result["positive_profit_insufficient_liquidity"].values()],
               result["strong_conventional_same_tool"]["candidate"], result["strong_conventional_same_tool"]["ordinary_reuse"],
               result["conventional_without_inherited_tool"]["totals"]]
    for r in records:
        require(all(type(v) is int for v in r.values()), "Arithmetic must use exact integers")
        require(r["initial_cash"] + r["collected_revenue"] == r["cash"] + r["complete_cost_paid"], "Cash does not conserve")
        require(r["recognized_revenue"] == r["profit"] + r["complete_cost_paid"], "Profit does not reconcile")
        require(r["recognized_revenue"] == r["collected_revenue"] + r["receivable"], "Receivable does not reconcile")
        require(r["cash"] == r["available_cash"] + r["held_earnings"] + r["protection_reserve"], "Protected cash was spent or double counted")
        require(r["cash"] >= 0 and r["available_cash"] >= 0, "Negative available cash")
    seq = result["accepted_whole_sequence"]
    require((seq["totals"]["cash"], seq["totals"]["profit"], seq["totals"]["complete_cost_paid"]) == (21, 11, 23), "Incorrect whole-sequence totals")
    require((seq["successor_cost"], seq["successor_collection"], seq["successor_profit"]) == (15, 20, 5), "Incorrect successor result")
    for name, cash, receivable in (("held_earnings", 10, 0), ("delayed_receivable", 2, 14), ("protection_reserve", 14, 0)):
        row = result["positive_profit_insufficient_liquidity"][name]
        require(row["quantities"]["profit"] == 6 and row["investment_cost"] == 15 and row["defer"] is True, "Profitable but unaffordable investment must defer")
        require((row["quantities"]["available_cash"], row["quantities"]["receivable"]) == (cash, receivable), "Incorrect liquidity counterexample")
    failure = result["failed_successor_acceptance"]
    require(failure["funded_admission"] is True and failure["accepted"] is False, "Funding must not imply acceptance")
    require((failure["successor_cost_retained"], failure["successor_collection"], failure["successor_profit"]) == (15, 0, -15), "Refusal erased sunk cost or invented revenue")
    require((failure["totals"]["cash"], failure["totals"]["profit"], failure["totals"]["complete_cost_paid"]) == (1, -9, 23), "Failed sequence does not reconcile")
    alternative = result["conventional_without_inherited_tool"]
    require(alternative["instrument_available"] is False and alternative["funded_admission"] is True, "A sufficient ordinary alternative invalidates tool necessity")
    require((alternative["available_cash"], alternative["required_cash"], alternative["totals"]["cash"], alternative["totals"]["profit"]) == (16, 15, 21, 11), "Incorrect ordinary-alternative result")
    require(alternative["instrument_necessity_established"] is False, "The instrument cannot be called necessary after admitting a sufficient alternative")
    tie = result["strong_conventional_same_tool"]
    require(tie["candidate"] == tie["ordinary_reuse"] and tie["profit_difference"] == 0, "Equal-content ordinary method must tie")
    require(tie["discovery_advantage_established"] is False, "Arithmetic cannot establish discovery advantage")


def main():
    parser = argparse.ArgumentParser(description="Exact pedagogical counterfactuals; no network or enterprise accounts.")
    parser.add_argument("--check", action="store_true", help="Verify conservation and the documented cases; compare saved output.")
    args = parser.parse_args()
    result = example()
    if args.check:
        check(result)
        saved = Path(__file__).with_name("example-results.json")
        require(saved.exists(), "Saved example-results.json is missing")
        recorded = json.loads(saved.read_text(encoding="utf-8"))
        check(recorded)
        require(recorded == result, "Saved output differs from this source")
        print("PASS: exact arithmetic, conservation, liquidity, failure and conventional-reuse cases.")
    else:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
