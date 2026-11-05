"""Authored commercial environment, kept outside the seller information set.

No balance is held here. Every actual modeled financial action uses the native
JournalAccount. A channel sells expiring contact rights, never sales. Population
indices have no market ceiling; numerical chunks only limit temporary memory.
All demand, bills, effort, prices and probabilities below are assumptions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict

USD = 1_000_000
YEAR_HOURS = 8760
SCHEMA = "omega-savings/world-rule/v1"
CHANNELS = ("search", "community", "partner")
PROFILES = (
    {"id": 0, "family": "rhs", "budget": 500, "bill": 1800,
     "self_setup": 420, "rival": 550, "buyer_effort": 30},
    {"id": 1, "family": "low_rank", "budget": 2000, "bill": 8000,
     "self_setup": 1250, "rival": 1600, "buyer_effort": 60},
    {"id": 2, "family": "dense_change", "budget": 600, "bill": 1600,
     "self_setup": 180, "rival": 400, "buyer_effort": 30},
    {"id": 3, "family": "successor_low_rank", "budget": 12000, "bill": 36000,
     "self_setup": 3200, "rival": 4200, "buyer_effort": 120},
)

# These are an explicit uncertainty grid, not estimated market probabilities.
WORLDS = {
    "positive": dict(qualified_bps=[3800, 5000, 4400], bill_bps=10000,
        effort_bps=10000, rival_bps=10000, cost_bps=10000,
        collection_hours=48, default_bps=150, refund_bps=150, late_claim_bps=100,
        correction_bps=400, avoidable_bps=10000, deterioration_bps=1600,
        saturation_contacts=100000, overlap_bps=2000),
    "weak": dict(qualified_bps=[800, 1000, 1200], bill_bps=3500,
        effort_bps=3500, rival_bps=7000, cost_bps=10000,
        collection_hours=168, default_bps=400, refund_bps=400, late_claim_bps=200,
        correction_bps=700, avoidable_bps=10000, deterioration_bps=2000,
        saturation_contacts=20000, overlap_bps=4000),
    "parity": dict(qualified_bps=[3800, 5000, 4400], bill_bps=10000,
        effort_bps=600, rival_bps=600, cost_bps=10000,
        collection_hours=48, default_bps=100, refund_bps=100, late_claim_bps=50,
        correction_bps=300, avoidable_bps=10000, deterioration_bps=5000,
        saturation_contacts=100000, overlap_bps=2000),
    "adverse": dict(qualified_bps=[1600, 2400, 1800], bill_bps=6000,
        effort_bps=8000, rival_bps=6500, cost_bps=40000,
        collection_hours=504, default_bps=2000, refund_bps=1200, late_claim_bps=700,
        correction_bps=2000, avoidable_bps=10000, deterioration_bps=4000,
        saturation_contacts=20000, overlap_bps=5000),
    "fixed_hardware": dict(qualified_bps=[3800, 5000, 4400], bill_bps=10000,
        effort_bps=10000, rival_bps=10000, cost_bps=10000,
        collection_hours=48, default_bps=150, refund_bps=150, late_claim_bps=100,
        correction_bps=400, avoidable_bps=0, deterioration_bps=1600,
        saturation_contacts=100000, overlap_bps=2000),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


def integer(value, name, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError("EXACT_NONNEGATIVE_INTEGER_REQUIRED:" + name)
    return value


def bps(value, name):
    integer(value, name)
    if value > 10000:
        raise ValueError("PROBABILITY_OUT_OF_RANGE:" + name)
    return value


def validate_rule(rule):
    if not isinstance(rule, dict) or set(rule) != {"schema", "seed", "world", "technical", "cost_surcharge"} or rule["schema"] != SCHEMA:
        raise ValueError("EXACT_SAVINGS_WORLD_RULE_REQUIRED")
    integer(rule["seed"], "seed"); integer(rule["cost_surcharge"], "cost_surcharge")
    world = rule["world"]
    if set(world) != set(WORLDS["positive"]):
        raise ValueError("EXACT_WORLD_FIELDS_REQUIRED")
    if not isinstance(world["qualified_bps"], list) or len(world["qualified_bps"]) != 3:
        raise ValueError("THREE_CHANNEL_PROBABILITIES_REQUIRED")
    for i, value in enumerate(world["qualified_bps"]): bps(value, "qualified_" + str(i))
    for key in ("default_bps", "refund_bps", "late_claim_bps", "correction_bps", "avoidable_bps", "deterioration_bps", "overlap_bps"):
        bps(world[key], key)
    if world["default_bps"] + world["refund_bps"] + world["late_claim_bps"] > 10000:
        raise ValueError("SETTLEMENT_PROBABILITIES_EXCEED_ONE")
    for key in ("bill_bps", "effort_bps", "rival_bps", "cost_bps", "collection_hours", "saturation_contacts"):
        integer(world[key], key, positive=key in {"cost_bps", "saturation_contacts"})
    if not isinstance(rule["technical"], dict) or set(rule["technical"]) != {"base", "extended"}:
        raise ValueError("TECHNICAL_QUALIFICATION_REQUIRED")
    for tier in rule["technical"].values():
        if set(tier) != {str(i) for i in range(len(PROFILES))}: raise ValueError("ALL_PROFILE_ECONOMICS_REQUIRED")
        for row in tier.values():
            if set(row) != {"saved_bps", "method", "accepted", "proxy_note"} or type(row["accepted"]) is not bool:
                raise ValueError("BOUND_TECHNICAL_ECONOMICS_REQUIRED")
            bps(row["saved_bps"], "saved_bps")
            if row["method"] not in {"direct", "reuse", "woodbury"}: raise ValueError("KNOWN_METHOD_REQUIRED")
    return rule


def make_rule(seed, world="positive", *, technical=None, cost_surcharge=0):
    if world not in WORLDS: raise ValueError("UNKNOWN_REGISTERED_WORLD")
    if technical is None: technical = technical_qualification()
    return validate_rule(dict(schema=SCHEMA, seed=seed, world=copy.deepcopy(WORLDS[world]),
        technical=copy.deepcopy(technical), cost_surcharge=cost_surcharge))


def technical_qualification():
    """Development-only applicability facts; no confirmation seed is inspected."""
    from .kernel import build_request, construct, execute, retained_assets
    from .verify import verify
    result = {}
    for tier, methods in (("base", ["direct", "reuse"]), ("extended", ["direct", "reuse", "woodbury"])):
        result[tier] = {}
        for p in PROFILES:
            request = build_request(11 + p["id"], p["family"], n=32, cases=8, rank=2)
            plan = construct(request, "adaptive", retained_assets(methods))
            artifact = execute(request, plan)
            accepted = verify(request, artifact)["accepted"]
            counts = artifact["count_model"]
            baseline = counts["direct_complete_proxy_units"]
            saved = max(0, baseline - counts["candidate_complete_proxy_units"])
            result[tier][str(p["id"])] = {"saved_bps": min(10000, saved * 10000 // baseline) if accepted else 0,
                "method": plan["method"] if plan["method"] in {"direct", "reuse", "woodbury"} else "direct",
                "accepted": accepted, "proxy_note": "Declared equal-unit scalar-work economics; not measured cloud cash savings."}
    return result


def profile_terms(rule, profile, campaign, capability):
    validate_rule(rule)
    if profile not in range(len(PROFILES)) or capability not in (0, 1): raise ValueError("PROFILE_OR_CAPABILITY_INVALID")
    integer(campaign, "campaign")
    p, w = PROFILES[profile], rule["world"]
    tech = rule["technical"]["extended" if capability else "base"][str(profile)]
    bill = p["bill"] * USD * w["bill_bps"] // 10000
    savings = bill * tech["saved_bps"] // 10000 * w["avoidable_bps"] // 10000
    # Rival response depends on elapsed time and observed public delivery volume
    # only through this predeclared calendar response; never on future demand.
    rival_scale = max(1000, 10000 - w["deterioration_bps"] * min(campaign, 12) // 12)
    rival = p["rival"] * USD * w["rival_bps"] // 10000 * rival_scale // 10000
    return {"budget_microUSD": p["budget"] * USD,
            "declared_avoidable_savings_microUSD": savings,
            "buyer_effort_microUSD": p["buyer_effort"] * USD,
            "self_setup_microUSD": p["self_setup"] * USD * w["effort_bps"] // 10000,
            "rival_microUSD": rival, "method": tech["method"], "accepted": tech["accepted"],
            "minimum_saved_bps": tech["saved_bps"]}


def quote_price(terms, price_index):
    if price_index == 0: return 299 * USD
    if price_index not in (1, 2): raise ValueError("PRICE_ACTION_OUTSIDE_REGISTERED_MENU")
    share = 2000 if price_index == 1 else 3500
    return max(USD, terms["declared_avoidable_savings_microUSD"] * share // 10000)


JOB_RE = re.compile(r"^c(\d+)t([0-3])p([0-2])a([01])u([1-9]\d*)l(\d+)$")


def contract_for(rule, job_id):
    validate_rule(rule)
    match = JOB_RE.fullmatch(job_id)
    if not match: raise ValueError("PROCEDURAL_JOB_ID_REQUIRED")
    campaign, profile, price_index, capability, units, lot = map(int, match.groups())
    from .kernel import build_request
    seed = int(digest([rule["seed"], campaign, profile, lot])[:12], 16)
    request = build_request(seed, PROFILES[profile]["family"], n=32, cases=8, rank=2)
    terms = profile_terms(rule, profile, campaign, capability)
    price = quote_price(terms, price_index)
    multiplier = rule["world"]["cost_bps"]
    costs = {"production": 3 * USD, "verification": 5 * USD,
             "onboarding": 8 * USD, "local_self_support": 5 * USD,
             "storage_delivery": USD, "maintenance_obligation": 3 * USD,
             "qualification": 4 * USD, "failure_retry_envelope": 2 * USD}
    costs = {k: v * multiplier // 10000 for k, v in costs.items()}
    costs["payment_processing"] = (price * 290 + 9999) // 10000 + 100_000
    costs["unpriced_cost_sensitivity"] = rule["cost_surcharge"]
    return {"id": job_id, "request": request, "price_microUSD": price,
            "budget_microUSD": terms["budget_microUSD"], "costs_microUSD": costs,
            "units": units, "method": terms["method"], "claim_window_hours": 720,
            "minimum_saved_bps": terms["minimum_saved_bps"],
            "residual_bps": 100, "collection_delay_hours": rule["world"]["collection_hours"],
            "deadline_hours": rule["world"]["collection_hours"] + 72}


def channel_quote(channel, units, cumulative_contacts, *, world):
    if channel not in CHANNELS: raise ValueError("UNKNOWN_CHANNEL")
    integer(units, "units", positive=True); integer(cumulative_contacts, "contacts")
    base = {"search": 6 * USD, "community": 3 * USD, "partner": 4 * USD}[channel]
    scale = world["saturation_contacts"]
    # Increasing marginal supplier prices, no fixed customer maximum.
    variable = base * (units + (2 * cumulative_contacts * units + units * units) // (2 * scale))
    return {"price_microUSD": variable + 15 * USD, "units": units,
            "unit_reference_microUSD": base, "channel": channel,
            "expiry_after_hours": 24 * 21, "lead_hours": 24,
            "source": "authored increasing-cost, finite-expiry supplier terms"}


def _uniform(seed, namespace, index, stage):
    raw = json.dumps([seed, namespace, index, stage], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % 10000


class ContactRights:
    """Compact disjoint indexed populations and cross-channel shared identities.

    Cursors bind purchased slots, not a fixed population. Shared identities have
    the same eligibility and private preference draws in every channel. Buying
    overlapping or expired rights never creates a second fresh prospect.
    """
    def __init__(self, seed, world, state=None):
        self.seed, self.world = integer(seed, "seed"), copy.deepcopy(world)
        self.state = copy.deepcopy(state) if state else {"cursors": {c: 0 for c in CHANNELS}, "campaigns": {}}

    def purchase(self, ident, channel, units, hour, *, invoice, paid_microUSD):
        integer(hour, "hour")
        request = {"channel": channel, "units": units, "hour": hour, "invoice": invoice}
        old = self.state["campaigns"].get(ident)
        if old:
            if old["request"] != request or paid_microUSD != old["request"]["invoice"]["price_microUSD"]:
                raise ValueError("CHANNEL_DUPLICATE_PAYLOAD_CHANGED")
            return copy.deepcopy(old)
        expected = channel_quote(channel, units, self.state["cursors"][channel], world=self.world)
        if invoice != expected or paid_microUSD != expected["price_microUSD"]:
            raise ValueError("ACTUAL_FUNDED_CHANNEL_INVOICE_REQUIRED")
        start = self.state["cursors"][channel]
        row = {"request": request, "start": start, "other_cursors": dict(self.state["cursors"]),
               "activation": hour + invoice["lead_hours"],
               "expiry": hour + invoice["lead_hours"] + invoice["expiry_after_hours"], "consumed": False}
        self.state["cursors"][channel] += units
        self.state["campaigns"][ident] = row
        return copy.deepcopy(row)

    def expose(self, ident, hour, rule, *, campaign, capability, price_index):
        row = self.state["campaigns"][ident]
        if row["consumed"]: return {"groups": [], "fresh": 0, "qualified": 0, "overlap": 0, "expired": 0}
        if hour < row["activation"]: raise ValueError("UNACTIVATED_CONTACT_RIGHTS")
        row["consumed"] = True
        units, channel = row["request"]["units"], row["request"]["channel"]
        if hour >= row["expiry"]:
            return {"groups": [], "fresh": 0, "qualified": 0, "overlap": 0, "expired": units}
        return self._exposure(row, rule, campaign=campaign, capability=capability, price_index=price_index)

    def _exposure(self, row, rule, *, campaign, capability, price_index):
        channel = row["request"]["channel"]
        groups = defaultdict(list)
        fresh = qualified = overlap = advanced = 0
        base_qbps = self.world["qualified_bps"][CHANNELS.index(channel)]
        for index in range(row["start"], row["start"] + row["request"]["units"]):
            shared = _uniform(self.seed, "shared", index, "membership") < self.world["overlap_bps"]
            if shared and any(cursor > index for c, cursor in row["other_cursors"].items() if c != channel):
                overlap += 1; continue
            namespace = "shared" if shared else channel
            fresh += 1
            # Per-index deterioration preserves grouping invariance. Splitting
            # the same slots into smaller engineering batches creates no leads.
            qbps = base_qbps * self.world["saturation_contacts"] // (self.world["saturation_contacts"] + index)
            if _uniform(self.seed, namespace, index, "qualified") >= qbps: continue
            qualified += 1
            z = _uniform(self.seed, namespace, index, "profile")
            profile = 0 if z < 4000 else 1 if z < 7000 else 2 if z < 9000 else 3
            if profile in (1, 3): advanced += 1
            terms = profile_terms(rule, profile, campaign, capability)
            price = quote_price(terms, price_index)
            # Hidden preferences and permissions are evaluator-only.
            effort_factor = 6000 + _uniform(self.seed, namespace, index, "setup-effort")
            self_setup = terms["self_setup_microUSD"] * effort_factor // 10000
            if _uniform(self.seed, namespace, index, "data-permission") < 500: continue
            savings = terms["declared_avoidable_savings_microUSD"]
            buyer_cost = price + terms["buyer_effort_microUSD"]
            outside_cost = min(savings, self_setup, terms["rival_microUSD"])
            if not terms["accepted"] or price > terms["budget_microUSD"] or buyer_cost >= outside_cost: continue
            groups[profile].append({"namespace": namespace, "index": index})
        return {"groups": [{"profile": p, "units": len(members), "members": members} for p, members in sorted(groups.items())],
                "fresh": fresh, "qualified": qualified, "qualified_advanced": advanced,
                "overlap": overlap, "expired": 0}

    def export(self): return copy.deepcopy(self.state)


def settlement_outcome(rule, member):
    """Evaluator-only, called after a cash-feasible lot is selected and bound."""
    fate = _uniform(rule["seed"], member["namespace"], member["index"], "settlement")
    w = rule["world"]
    status = "default" if fate < w["default_bps"] else "refund" if fate < w["default_bps"] + w["refund_bps"] else "collect"
    if status == "collect" and fate < w["default_bps"] + w["refund_bps"] + w["late_claim_bps"]:
        status = "late_claim"
    repair = _uniform(rule["seed"], member["namespace"], member["index"], "correction") < w["correction_bps"]
    return status, repair


def candidate_campaign_sizes(available, *, maximum_fraction_bps=2000):
    """Policy action menu expands geometrically with actual current cash."""
    integer(available, "available"); bps(maximum_fraction_bps, "fraction")
    affordable_contacts = available * maximum_fraction_bps // 10000 // (3 * USD)
    values = [20]
    while values[-1] * 2 <= max(20, affordable_contacts): values.append(values[-1] * 2)
    return values
