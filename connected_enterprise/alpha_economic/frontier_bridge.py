"""FRONTIER Ω -> ALPHA Economic Engine: proof-gated commercial-intake bridge.

Runs the existing bounded host checker on actual historical/current candidate
instruments before accepting a *separately buyer-signed* ALPHA work request.
Even when all gates pass, matching published model release dates is NOT proof
that the outcome was historically impossible or is commercially profitable.

No customer keys are manufactured, no Stripe charge is issued here, and this
module never creates a ledger or grants new financial/deployment authority.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import time

from frontier_omega.core import COSTS, Reservoir
from . import checker
from .core import (
    authenticate, canonical, contract, digest, filehash, harness,
    identifier, immutable, safe, worst_cost
)


BUNDLE_SCHEMA = "alpha-frontier/conversion-request/v1"
REPLAY_SCHEMA = "alpha-frontier/host-replay/v1"
LINK_SCHEMA = "alpha-frontier/qualified-intake/v1"
SCOPE = "MATCHED_HOST_REPLAY_AND_REGISTERED_BUYER_REQUEST_NOT_LIVE_COMMERCE"

_CHECKER_SOURCE = filehash(checker.__file__)
_EVALUATOR = harness("instruments")
_EVALUATOR_SOURCE = filehash(_EVALUATOR.__file__)


def _identity():
    # Detect source changing on disk while already-loaded Python remains old.
    current = (filehash(checker.__file__), filehash(_EVALUATOR.__file__))
    if current != (_CHECKER_SOURCE, _EVALUATOR_SOURCE):
        raise ValueError("CHECKER_SOURCE_CHANGED_RESTART_REQUIRED")
    return {
        "checker_sha256": current[0],
        "bounded_evaluator_sha256": current[1],
        "protocol": "alpha-economic/bounded-json-instrument/v1"
    }


def _acceptance_sha(c):
    return digest({
        "training": c["training"],
        "confirmation": c["confirmation"],
        "max_operations": c["max_operations"]
    })


def _protocol_sha():
    return digest(_identity())


def _replay_sha(c, problem_id, frontier_id, instrument, result):
    return digest({
        "schema": REPLAY_SCHEMA,
        "contract_sha256": digest(c),
        "problem_id": problem_id,
        "frontier_id": frontier_id,
        "instrument_sha256": digest(instrument),
        "host_check_sha256": digest(result),
        "identity": _identity()
    })


def _scope(scope):
    if scope not in ("AUTHORED_SCENARIO", "OPERATOR_REPORTED_UNVERIFIED"):
        raise ValueError("NO_SELF_CERTIFIED_EXTERNAL_VERIFICATION")
    return scope


def make_trial(c, problem_id, frontier_id, trial_id, instrument, *,
               run_on, costs_microUSD, acceptance_probability_bps,
               scope="AUTHORED_SCENARIO", expected_loss_microUSD=0):
    """Create an actual host-checker technical record, NOT a paid buyer receipt.

    Costs and willingness-to-pay probabilities remain reported estimates.
    Never use an authored scenario to authorize an external engine.
    """
    from frontier_omega.core import (
        TRIAL_SCHEMA, validate_trial, identifier as frontier_id_check
    )
    c = contract(c)
    for value in (problem_id, frontier_id, trial_id):
        frontier_id_check(value)
    if date.fromisoformat(run_on).isoformat() != run_on:
        raise ValueError("EXACT_TRIAL_DAY_REQUIRED")
    _scope(scope)
    if type(costs_microUSD) is not dict or set(costs_microUSD) != set(COSTS):
        raise ValueError("COMPLETE_DECLARED_COST_ENVELOPE_REQUIRED")
    if any(type(v) is not int or v < 0 for v in costs_microUSD.values()):
        raise ValueError("NONNEGATIVE_COST_IN_MICROUSD_REQUIRED")
    if type(expected_loss_microUSD) is not int or expected_loss_microUSD < 0:
        raise ValueError("NONNEGATIVE_LOSS_REQUIRED")
    if type(acceptance_probability_bps) is not int or not 0 <= acceptance_probability_bps <= 10000:
        raise ValueError("BASIS_POINT_PROBABILITY_REQUIRED")

    observed = checker.check(c, instrument)
    ordinary = checker.check(c, c["ordinary"])
    value = {
        "schema": TRIAL_SCHEMA,
        "id": trial_id,
        "problem_id": problem_id,
        "frontier_id": frontier_id,
        "run_on": run_on,
        "terms_sha256": digest(c),
        "acceptance_sha256": _acceptance_sha(c),
        "protocol_sha256": _protocol_sha(),
        "evidence_sha256": _replay_sha(c, problem_id, frontier_id,
                                      instrument, observed),
        "scope": scope,
        "passed": observed["accepted"],
        "independent_check": True,  # Host code, separate from model proposal.
        "price_microUSD": c["price_microUSD"],
        "acceptance_probability_bps": acceptance_probability_bps,
        "costs_microUSD": dict(costs_microUSD),
        "expected_loss_microUSD": expected_loss_microUSD,
        "alternative": {
            "name": "Qualified ordinary bounded instrument",
            "qualified": ordinary["accepted"],
            "complete_cost_microUSD": None
        }
    }
    return validate_trial(value)


def bundle_shape(problem_id, before_id, after_id, buyer_envelope,
                 historical_instrument, current_instrument):
    """Construct an exact submission envelope. Does NOT sign for the buyer."""
    return {
        "schema": BUNDLE_SCHEMA,
        "problem_id": problem_id,
        "before_id": before_id,
        "after_id": after_id,
        "buyer_envelope": buyer_envelope,
        "historical_instrument": historical_instrument,
        "current_instrument": current_instrument
    }


def _bundle(value):
    fields = {"schema", "problem_id", "before_id", "after_id", "buyer_envelope",
              "historical_instrument", "current_instrument"}
    if type(value) is not dict or set(value) != fields or value["schema"] != BUNDLE_SCHEMA:
        raise ValueError("EXACT_CROSSING_TO_ORDER_BUNDLE_REQUIRED")
    for name in ("problem_id", "before_id", "after_id"):
        from frontier_omega.core import identifier as frontier_id_check
        frontier_id_check(value[name])
    if value["before_id"] == value["after_id"]:
        raise ValueError("DISTINCT_CAPABILITY_OBSERVATIONS_REQUIRED")
    if type(value["historical_instrument"]) is not dict or type(value["current_instrument"]) is not dict:
        raise ValueError("BOUNDED_INSTRUMENTS_REQUIRED")
    if len(canonical(value)) > 2_000_000:
        raise ValueError("BOUNDED_COMMERCIAL_INTAKE_REQUIRED")
    return value


def _trial_pair(reservoir, before, after, report):
    trials = {x["id"]: x for x in reservoir.rows("trials")}
    ids = report.get("trial_ids", [])
    if type(ids) is not list or len(ids) != 2 or any(t not in trials for t in ids):
        raise ValueError("MATCHED_REPORTED_CROSSING_REQUIRED")
    old, new = (trials[t] for t in ids)
    if (old["frontier_id"] != before or new["frontier_id"] != after or
        old["scope"] != new["scope"]):
        raise ValueError("COMPARED_SOURCE_OR_SCOPE_MISMATCH")
    _scope(old["scope"])
    return old, new


def admission_preflight(reservoir, bundle, buyer_keys, *, now=None):
    """Host-execute bounded technical replay + authenticate *existing buyer*.

    Returns a preflight receipt; it does not create a job, collect money or
    claim that a technical comparison establishes independent real demand.
    """
    if not isinstance(reservoir, Reservoir):
        raise TypeError("FRONTIER_RESERVOIR_REQUIRED")
    bundle = _bundle(bundle)
    now = int(time.time()) if now is None else now
    if type(now) is not int or now < 0:
        raise ValueError("EXPLICIT_UNIX_TIME_REQUIRED")
    if type(buyer_keys) is not dict:
        raise ValueError("REGISTERED_BUYER_KEYS_REQUIRED")
    envelope = bundle["buyer_envelope"]
    raw = envelope.get("body") if type(envelope) is dict else None
    buyer = raw.get("buyer") if type(raw) is dict else None
    key = buyer_keys.get(buyer)
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("REGISTERED_EXTERNAL_BUYER_KEY_REQUIRED")
    body = authenticate(envelope, key, kind="request", now=now)
    if set(body) != {"kind", "buyer", "expires_at", "contract"}:
        raise ValueError("EXACT_CUSTOMER_REQUEST_REQUIRED")
    c = contract(body["contract"])
    if c["buyer"] != buyer or body["expires_at"] != c["expires_at"]:
        raise ValueError("CUSTOMER_CONTRACT_IDENTITY_OR_EXPIRY_CHANGED")
    if (c["price_microUSD"] > c["buyer_budget_microUSD"]
        or c["price_microUSD"] >= c["outside_option_microUSD"]):
        raise ValueError("CUSTOMER_REPORTED_BUDGET_OR_OUTSIDE_OPTION_LOSES")

    # The hash check must precede consumption of the reservoir's economic
    # claims: a modified local trial may not become a payment justification.
    reservoir.audit()
    problems = {p["id"]: p for p in reservoir.rows("problems")}
    frontiers = {f["id"]: f for f in reservoir.rows("frontiers")}
    problem_id, before, after = (
        bundle["problem_id"], bundle["before_id"], bundle["after_id"])
    if problem_id not in problems or before not in frontiers or after not in frontiers:
        raise ValueError("UNKNOWN_FRONTIER_PROBLEM_OR_OBSERVATION")
    p = problems[problem_id]
    if c["scope_key"] != p["id"] or c["purpose"] != p["outcome"]:
        raise ValueError("BUYER_CONTRACT_NOT_BOUND_TO_EXACT_PROBLEM_OUTCOME")
    if not set(p["tags"]).intersection(frontiers[after]["tags"]):
        raise ValueError("UNRELATED_FRONTIER_OBSERVATION")

    demand = p["demand"]
    ceiling = demand["ceiling_microUSD"]
    if ceiling is not None and c["price_microUSD"] > ceiling:
        raise ValueError("REPORTED_BUYER_PRICE_CEILING_EXCEEDED")
    if demand["deadline"] is not None:
        exp_day = datetime.fromtimestamp(c["expires_at"], timezone.utc).date().isoformat()
        if exp_day > demand["deadline"]:
            raise ValueError("BUYER_CONTRACT_AFTER_REPORTED_DEADLINE")

    comparison = reservoir.compare(problem_id, before, after)
    if not comparison.get("reported_crossing"):
        raise ValueError("MATCHED_REPORTED_CROSSING_REQUIRED")
    old, new = _trial_pair(reservoir, before, after, comparison)
    # A recorded host replay cannot precede its claimed capability observation
    # or arrive from the future relative to this authenticated intake. These
    # bounds check chronology, not whether an authored run really happened.
    submit_day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    if (old["run_on"] < frontiers[before]["observed_on"]
        or new["run_on"] < frontiers[after]["observed_on"]
        or old["run_on"] > submit_day
        or new["run_on"] > submit_day):
        raise ValueError("TRIAL_CHRONOLOGY_INVALID")
    if (old["problem_id"] != problem_id or new["problem_id"] != problem_id
        or old["terms_sha256"] != digest(c)
        or new["terms_sha256"] != digest(c)
        or old["acceptance_sha256"] != _acceptance_sha(c)
        or new["acceptance_sha256"] != _acceptance_sha(c)
        or old["protocol_sha256"] != _protocol_sha()
        or new["protocol_sha256"] != _protocol_sha()
        or old["price_microUSD"] != c["price_microUSD"]
        or new["price_microUSD"] != c["price_microUSD"]):
        raise ValueError("MATCHED_REPORTED_CROSSING_REQUIRED")

    # The authoritative checker is independent of the proposed instrument.
    # It is *not* an external third-party certification or general proof.
    ordinary = checker.check(c, c["ordinary"])
    if not ordinary["accepted"]:
        raise ValueError("COMPETENT_ORDINARY_CONTROL_MUST_PASS")
    historical = checker.check(c, bundle["historical_instrument"])
    current = checker.check(c, bundle["current_instrument"])
    if (old["evidence_sha256"] != _replay_sha(
            c, problem_id, before, bundle["historical_instrument"], historical)
        or new["evidence_sha256"] != _replay_sha(
            c, problem_id, after, bundle["current_instrument"], current)):
        raise ValueError("EVIDENCE_HASH_OR_CHECKER_MISMATCH")
    if (old["passed"] is not historical["accepted"]
        or new["passed"] is not current["accepted"]
        or old["independent_check"] is not True
        or new["independent_check"] is not True):
        raise ValueError("REPORTED_TRIAL_AND_HOST_VERDICT_DISAGREE")
    if not current["accepted"]:
        raise ValueError("CURRENT_FINITE_CASES_NOT_ACCEPTED")

    cost_floor = worst_cost(c)
    cost_scenario = sum(new["costs_microUSD"].values()) + new["expected_loss_microUSD"]
    if cost_scenario < cost_floor:
        raise ValueError("REPORTED_FULL_COST_UNDERSTATES_NATIVE_RISK_ENVELOPE")
    if new["alternative"]["qualified"] is not True:
        raise ValueError("STRONG_CURRENT_ALTERNATIVE_MUST_BE_COMPARED")
    mode = ("TECHNICAL_UNBLOCKING_OBSERVED_FINITE_CASES" if not historical["accepted"]
            else "ECONOMIC_UNBLOCKING_REPORTED_COSTS")
    return {
        "schema": "alpha-frontier/commercial-preflight/v1",
        "contract_sha256": digest(c),
        "order_id": identifier(c),
        "problem_id": problem_id,
        "frontier_before": before,
        "frontier_after": after,
        "reported_trial_ids": comparison["trial_ids"],
        "crossing_mechanism": mode,
        "technical_scope": "HOST_REPLAYED_FINITE_CASES",
        "reported_economic_margin_numerator": comparison["after_margin_numerator"],
        "native_declared_cost_floor_microUSD": cost_floor,
        "reported_cost_envelope_microUSD": cost_scenario,
        "actual_costs_reconciled": False,
        "reported_source_scope": old["scope"],
        "buyer_request_scope": "REGISTERED_SIGNER_AUTHENTICATED_NOT_BUYER_INDEPENDENCE_PROVEN",
        "current_strong_alternative_checked": True,
        "external_superiority_established": False,
        "independent_historical_frontier_causality_established": False,
        "economic_crossing_established": False,
        "actual_customer_established": False,
        "earned_revenue_established": False,
        "conversion_status": "AUTHENTICATED_READY_FOR_ENGINE_INTAKE",
        "operating_scope": SCOPE,
        "current_evidence_sha256": new["evidence_sha256"],
        "historical_evidence_sha256": old["evidence_sha256"],
        "checker_identity": _identity()
    }


def submit_qualified(engine, reservoir, bundle, *, buyer_keys=None, now=None):
    """Gated intake into the EXISTING ALPHA Engine; money authority is unchanged.

    A successful return is a signed order **submission**, not an accepted
    delivery, a reconciled Stripe payment or an earned-dollar claim.
    """
    mode = getattr(engine, "policy", {}).get("scope")
    if mode not in ("SIMULATED", "EXTERNAL_TEST", "EXTERNAL_LIVE"):
        raise ValueError("EXISTING_ALPHA_ENGINE_POLICY_REQUIRED")
    # No fabricated fixture is allowed to represent an external transaction.
    if mode != "SIMULATED":
        problem_id = _bundle(bundle)["problem_id"]
        before, after = bundle["before_id"], bundle["after_id"]
        arms = [t for t in reservoir.rows("trials") if t["problem_id"] == problem_id
                and t["frontier_id"] in (before, after)]
        if any(x["scope"] == "AUTHORED_SCENARIO" for x in arms):
            raise PermissionError("SCENARIO_NOT_LIVE_COMMERCIAL_EVIDENCE")
        if not hasattr(engine, "stripe") or not hasattr(engine, "treasury"):
            raise PermissionError("LIVE_PAYMENT_AND_TREASURY_INTEGRATION_REQUIRED")
    keys = getattr(engine, "keys", None) if buyer_keys is None else buyer_keys
    report = admission_preflight(reservoir, bundle, keys, now=now)
    if not callable(getattr(engine, "submit", None)):
        raise ValueError("ENGINE_HAS_NO_AUTHENTICATED_INTAKE")
    root = safe(engine.root)
    links = root / "frontier-links"
    links.mkdir(mode=0o700, exist_ok=True)
    if links.stat().st_mode & 0o077:
        raise ValueError("PRIVATE_FRONTIER_LINKS_REQUIRED")

    # Commit only an immutable, nonfinancial intake proof before admitting the
    # order. A killed process can safely replay it under the same contract.
    receipt = {
        "schema": LINK_SCHEMA,
        "preflight": report,
        "request_envelope_sha256": digest(bundle["buyer_envelope"]),
        "admission_intent": "INTAKE_ONLY_NO_PAYMENT_OR_PRODUCTION_AUTHORITY_ADDED",
        "payment_status": "NOT_RECONCILED",
        "external_customer_status": "NOT_INDEPENDENTLY_VERIFIED",
        "financial_account": "UNCHANGED_EXISTING_ALPHA_ACCOUNT"
    }
    target = links / (report["order_id"] + ".json")
    immutable(target, receipt)
    job = engine.submit(bundle["buyer_envelope"])
    if job != report["order_id"]:
        raise ValueError("ALPHA_ADMITTED_WRONG_CUSTOMER_CONTRACT")
    return {
        "job": job,
        "frontier_link_receipt": target,
        "status": "SIGNED_ORDER_ADMITTED_NO_PAYMENT_CLAIM",
        "economic_crossing_established": False,
        "actual_paid_customer_established": False
    }
