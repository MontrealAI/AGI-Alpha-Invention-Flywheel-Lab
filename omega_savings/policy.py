"""Seller decisions from permitted, historical observations only.

The proposed and ordinary adaptive policies intentionally share a competent
known decision rule. A tie is evidence against a special invention advantage.
This finite action comparison claims no global or game-theoretic optimum.
"""
from __future__ import annotations

import math
from .world import USD, CHANNELS, candidate_campaign_sizes, bps, integer

POLICIES = ("adaptive", "ordinary", "fixed299", "fixed_split", "capability_only", "no_entry")
OBSERVATION_FIELDS = {"hour", "available", "unrestricted_earned", "payables", "built", "capability",
    "channel_stats", "campaign_count", "last_campaign_units", "qualified_advanced",
    "current_quotes", "cash_profit", "fixed_fraction_bps"}


def validate_prior(prior):
    if not isinstance(prior, dict) or set(prior) != {"alpha", "beta"}:
        raise ValueError("EXACT_PRIOR_REQUIRED")
    for value in prior.values():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("POSITIVE_FINITE_PRIOR_PARAMETERS_REQUIRED")
    return prior


def validate_observation(o):
    if not isinstance(o, dict) or set(o) != OBSERVATION_FIELDS:
        raise ValueError("EXACT_PERMITTED_OBSERVATIONS_REQUIRED")
    for key in ("hour", "available", "unrestricted_earned", "payables", "campaign_count", "last_campaign_units", "qualified_advanced"):
        integer(o[key], key)
    if type(o["cash_profit"]) is not int: raise ValueError("EXACT_PROFIT_REQUIRED")
    if type(o["built"]) is not bool or o["capability"] not in (0, 1):
        raise ValueError("EXPLICIT_CURRENT_CAPABILITY_REQUIRED")
    bps(o["fixed_fraction_bps"], "fixed_fraction")
    if set(o["channel_stats"]) != set(CHANNELS) or set(o["current_quotes"]) != set(CHANNELS):
        raise ValueError("PUBLIC_CHANNEL_MENU_REQUIRED")
    # An evaluator world, future draw, buyer value or seed cannot be smuggled in.
    for row in o["channel_stats"].values():
        if set(row) != {"contacted", "purchased", "settled_units", "net_contribution", "spent", "campaigns", "by_price"}:
            raise ValueError("HISTORICAL_CHANNEL_OBSERVATIONS_ONLY")
    return o


def decide(policy, observation, *, prior=None):
    if policy not in POLICIES: raise ValueError("REGISTERED_POLICY_REQUIRED")
    o = validate_observation(observation)
    prior = validate_prior({"alpha": 1.0, "beta": 9.0} if prior is None else prior)
    if policy == "no_entry": return {"action": "wait", "reason": "registered_no_entry"}
    # The qualified native resolution interface requires current incurred
    # invoices to be resolved before a new earned-funded commitment completes.
    # Preserve that invariant; protected-but-unpaid is not already serviced.
    if o["payables"]:
        return {"action": "wait", "reason": "unresolved_native_payables"}
    if not o["built"]:
        cost = 800 * USD if policy in {"fixed299", "fixed_split", "capability_only"} else 300 * USD
        return {"action": "construct", "capability": 1 if cost == 800 * USD else 0,
                "cost": cost, "expected_net": 0,
                "reason": "finite_exploratory_package_no_positive_value_claim"} if o["available"] >= cost else {"action": "wait", "reason": "current_cash"}
    if policy == "capability_only": return {"action": "wait", "reason": "registered_capability_without_commerce"}
    if policy in {"adaptive", "ordinary"} and not o["capability"] and o["qualified_advanced"] >= 3 and o["available"] >= 500 * USD:
        successes = sum(s["settled_units"] for s in o["channel_stats"].values())
        contribution = sum(s["net_contribution"] + s["spent"] for s in o["channel_stats"].values())
        # Explicit transfer forecast: observed unit contribution and a declared
        # 10% conversion prior applied to observed advanced requests. This can
        # be wrong; it is never collected income or a funding source.
        forecast = int(max(0, contribution) / max(1, successes) * o["qualified_advanced"] * prior["alpha"] / (prior["alpha"] + prior["beta"])) - 500 * USD
        if forecast > 0:
            return {"action": "construct", "capability": 1, "cost": 500 * USD, "expected_net": forecast,
                    "reason": "declared_transfer_forecast_from_observed_requests_and_contribution"}
    if o["hour"] >= 360 * 24:
        return {"action": "wait", "reason": "remaining_sale_and_settlement_time_below_campaign_window"}
    stats = o["channel_stats"]
    if policy == "fixed299":
        channel, price = "search", 0
    elif policy == "fixed_split":
        channel, price = "community", 1
    else:
        # A small first campaign in each unobserved channel buys actual rights
        # and informative outcomes, rather than charging a compulsory R&D bill.
        unseen = [c for c in CHANNELS if stats[c]["campaigns"] == 0]
        if unseen:
            channel = min(unseen, key=lambda c: (o["current_quotes"][c]["unit_reference_microUSD"], c))
            return {"action": "campaign", "channel": channel, "price_index": 1,
                    "units": 20, "expected_net": 0, "reason": "costed_information_and_voluntary_sales_pilot"}
        scores = {}
        for c, s in stats.items():
            n = s["purchased"]
            # Conservative contribution observation; no latent buyer values.
            mean = s["net_contribution"] / max(1, n)
            scores[c] = mean
        channel = max(CHANNELS, key=lambda c: (scores[c], c))
        if scores[channel] <= 0:
            return {"action": "wait", "reason": "observed_acquisition_unprofitable_all_tested_channels"}
        by_price = stats[channel]["by_price"]
        untried = [p for p in (0, 1, 2) if str(p) not in by_price]
        price = untried[0] if untried else max((0, 1, 2), key=lambda p: (
            by_price[str(p)]["net"] / max(1, by_price[str(p)]["contacts"]), -p))
    s = stats[channel]
    if s["campaigns"] >= 2 and s["net_contribution"] <= 0:
        return {"action": "wait", "reason": "fixed_policy_loss_stop"}
    fraction = o["fixed_fraction_bps"] if policy == "fixed_split" else 2000
    sizes = candidate_campaign_sizes(o["available"], maximum_fraction_bps=fraction)
    # Policy sizes/timing are registered choices; the environment has no cap.
    units = sizes[-1] if s["settled_units"] else 20
    return {"action": "campaign", "channel": channel, "price_index": price,
            "units": units,
            "expected_net": max(0, (s["net_contribution"] + s["spent"]) * units // max(1, s["purchased"]))
                - o["current_quotes"][channel]["unit_reference_microUSD"] * units - 55 * USD if s["purchased"] else 0,
            "reason": "current_cash_finances_observed_positive_acquisition" if units > 20 else "finite_commercial_pilot"}


def empty_stats():
    return {c: {"contacted": 0, "purchased": 0, "settled_units": 0, "net_contribution": 0,
                "spent": 0, "campaigns": 0, "by_price": {}} for c in CHANNELS}
