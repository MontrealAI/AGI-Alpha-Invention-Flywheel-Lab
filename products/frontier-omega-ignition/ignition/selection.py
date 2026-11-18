"""Prioritize finite proof experiments using the portfolio's frozen evidence and estimates."""
from urllib.parse import urlsplit

from .store import StateError


DEMAND = ("counterparty_acceptance", "published_reward", "reported_problem", "unconfirmed")
ACCESS = ("installed_offline", "public_sources", "external_permission", "unavailable")
FIT = ("core", "adjacent", "outside")
REUSE = ("repeatable", "single_recipient", "unknown")


def _range(value, maximum=None):
    if value is None:
        return
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) is not int or x < 0 for x in value) or value[0] > value[1]
            or (maximum is not None and value[1] > maximum)):
        raise StateError("Use an ordered nonnegative integer interval or null for unknown estimates")


def _net_bounds(profile):
    gross = profile["conditional_receipt_usd_cents"]
    chance = profile["collection_probability_bps"]
    cost = profile["full_expected_cost_usd_cents"]
    if any(x is None for x in (gross, chance, cost)):
        return None
    return [(gross[0] * chance[0]) // 10000 - cost[1],
            (gross[1] * chance[1] + 9999) // 10000 - cost[0]]


def assess(candidate):
    p = candidate.get("assessment")
    fields = {"proof_access", "requires_new_spending", "demand", "fit", "reuse", "rationale", "sources",
              "conditional_receipt_usd_cents", "collection_probability_bps", "full_expected_cost_usd_cents",
              "days_to_collection", "minutes_to_proof"}
    if not isinstance(p, dict) or set(p) != fields:
        raise StateError("Provide each economic assessment field; unknown estimates are null")
    for key, choices in (("demand", DEMAND), ("proof_access", ACCESS), ("fit", FIT), ("reuse", REUSE)):
        if p[key] not in choices:
            raise StateError("Unsupported economic assessment: " + key)
    if p["requires_new_spending"] is not None and type(p["requires_new_spending"]) is not bool:
        raise StateError("requires_new_spending must be true, false or null")
    if not isinstance(p["rationale"], str) or not p["rationale"].strip():
        raise StateError("Explain the estimate basis and downside")
    if not isinstance(p["sources"], list) or not p["sources"]:
        raise StateError("Cite the evidence for the economic assessment")
    for url in p["sources"]:
        if not isinstance(url, str):
            raise StateError("Provide HTTPS evidence sources")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise StateError("Provide public HTTPS evidence sources without credentials")
    for field in ("conditional_receipt_usd_cents", "collection_probability_bps", "full_expected_cost_usd_cents",
                  "days_to_collection", "minutes_to_proof"):
        _range(p[field], 10000 if field == "collection_probability_bps" else None)
    net = _net_bounds(p)
    reasons = []
    if p["fit"] == "outside":
        reasons.append("Outside the declared frontier objective")
    if p["requires_new_spending"] is not False:
        reasons.append("Proof requires new or unverified spending")
    if p["proof_access"] in ("external_permission", "unavailable"):
        reasons.append("Proof needs unavailable inputs or external permission")
    if net is not None and net[1] < 0:
        reasons.append("Even the upper estimated net return is negative")
    if not reasons and "brief" not in candidate:
        raise StateError("An eligible economic candidate needs an executable mission file")
    mission = candidate.get("brief", {}).get("mission", {})
    if "brief" in candidate and p["proof_access"] == "public_sources" and mission.get("authority", {}).get("public_sources") is not True:
        reasons.append("The mission has no public-source grant")
    return {"candidate": candidate["id"], "eligible": not reasons, "reasons": reasons,
            "estimated_net_usd_cents": net, "assessment": p}


def _time_order(interval):
    return (1, 0) if interval is None else (0, interval[1])


def _priority(row):
    p, net = row["assessment"], row["estimated_net_usd_cents"]
    positive_floor = net is not None and net[0] > 0
    return (not positive_floor, -net[0] if positive_floor else 0, DEMAND.index(p["demand"]),
            FIT.index(p["fit"]), _time_order(p["days_to_collection"]), ACCESS.index(p["proof_access"]),
            _time_order(p["minutes_to_proof"]), REUSE.index(p["reuse"]), row["candidate"])


def select(plan):
    rows = [assess(candidate) for candidate in plan["candidates"]]
    allowed = sorted((row for row in rows if row["eligible"]), key=_priority)
    excluded = sorted((row for row in rows if not row["eligible"]), key=lambda row: row["candidate"])
    return {"policy": plan["selection_policy"], "ranked": [row["candidate"] for row in allowed],
            "assessments": allowed + excluded}
