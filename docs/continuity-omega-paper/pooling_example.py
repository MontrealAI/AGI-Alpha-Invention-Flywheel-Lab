#!/usr/bin/env python3
"""Exact arithmetic for the paper's authored fixed-period pooling illustration."""
import json
from fractions import Fraction


def illustration():
    common_cost, cost_per_buyer, fee_ceiling = 900, 100, 400
    capacity, quantity = 2000, 750
    ratio = Fraction(common_cost, fee_ceiling - cost_per_buyer)
    minimum = -(-ratio.numerator // ratio.denominator)
    maximum = capacity // quantity
    # Independent direct enumeration of every physically admitted buyer count.
    rows = []
    for buyers in range(1, maximum + 1):
        receipts = buyers * fee_ceiling
        costs = common_cost + buyers * cost_per_buyer
        rows.append({"buyers": buyers, "receipts": receipts, "cost": costs,
                     "contribution": receipts - costs,
                     "required_capacity": buyers * quantity})
    feasible = [r["buyers"] for r in rows if r["contribution"] >= 0]
    if bool(feasible) != (minimum <= maximum):
        raise ValueError("Direct enumeration and algebra disagree")
    return {
        "scope": "Authored fixed-period all-activation illustration; not prices, demand, a scheduler, or commerce.",
        "inputs": {"common_cost": common_cost, "cost_per_buyer": cost_per_buyer,
                   "fee_ceiling": fee_ceiling, "capacity_units": capacity,
                   "quantity_per_buyer": quantity},
        "minimum_buyers_for_nonnegative_contribution": minimum,
        "maximum_buyers_for_simultaneous_capacity": maximum,
        "all_capacity_admissible_counts": rows,
        "feasible_counts": feasible,
        "three_buyers": {"contribution": 3 * (fee_ceiling - cost_per_buyer) - common_cost,
                         "required_capacity": 3 * quantity, "capacity_admissible": False},
    }


if __name__ == "__main__":
    print(json.dumps(illustration(), indent=2, sort_keys=True))
