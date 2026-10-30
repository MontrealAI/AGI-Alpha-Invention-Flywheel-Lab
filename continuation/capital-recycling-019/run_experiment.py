from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from commercial.ledger import audit as audit_native, digest
from commercial.single_writer import SingleWriterExchange
from enterprise.contract019 import (
    OwnedRiskFiniteExchange,
    audit_contract019,
    residual_cap,
    risk_terms,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "continuation/capital-recycling-019"
MANIFEST = json.loads((OUT / "enterprise-services/MANIFEST.json").read_text())
ADAPTIVE_MANIFEST = json.loads((OUT / "services/MANIFEST.json").read_text())
CATALOGUE = json.loads((ROOT / "portfolio_scale/universe.json").read_text())
BUNDLES = json.loads((ROOT / "portfolio_scale/reference_bundles.json").read_text())
JOB = next(x["id"] for x in MANIFEST["jobs"] if x["accepted"])

MICRO = 1_000_000
OPENING = 500 * MICRO
WORKING = 100 * MICRO
PRICE = 200 * MICRO
PRODUCTION = 40 * MICRO
ARRANGEMENT = 5 * MICRO
OPPORTUNITIES = [
    {"id": i, "utility_margin": (i % 5 + 1) * 5 * MICRO,
     "nonpayment": i % 7 == 6, "refund": i % 11 == 10,
     "late_claim": i % 13 == 12}
    for i in range(20)
]


def basic_terms(**updates):
    value = {
        "premium_per_order": 1 * MICRO,
        "buyer_friction": 2 * MICRO,
        "cover_bps": 8_000,
        "deductible_bps": 500,
        "exclusion_bps": 250,
        "payout_gap_bps": 250,
        "provider_default_severity_bps": 500,
        "correlated_dispute_bps": 500,
        "residual_ticks": 3,
    }
    value.update(updates)
    return value


def fund_delivery(ex, index, tick, amount):
    state = ex.snapshot()
    ident = f"delivery-{index}"
    artifact = hashlib.sha256(ident.encode()).hexdigest()
    if index == 0:
        event = "seed-delivery-0"
        ex.execute("cost", {"id": event, "amount": amount}, tick)
        return {"funding": "SEED_OR_REMAINING_LIQUIDITY", "event": event,
                "before": state, "amount": amount}
    if state["unrestrictedEarned"] < amount:
        return None
    intent = hashlib.sha256(("intent:" + ident).encode()).hexdigest()
    ex.execute("reserve", {"id": ident, "amount": amount,
                           "expected_net_value": PRICE - amount,
                           "intent_sha256": intent}, tick)
    reserved = ex.snapshot()
    ex.execute("finish", {"id": ident, "amount": amount,
                          "artifact_sha256": artifact}, tick)
    return {"funding": "PRIOR_UNRESTRICTED_EARNINGS",
            "event": "investment-" + ident, "before": state,
            "reserved": reserved, "after": ex.snapshot(), "amount": amount}


def deliver(ex, index, tick, funding, risk=None, opportunity=None):
    oid = f"order-{index}"
    buyer = f"buyer-{index}"
    ex.execute("wallet", {"buyer": buyer, "amount": PRICE}, tick)
    ex.execute("offer", {"id": oid, "buyer": buyer, "price": PRICE,
                         "job_id": JOB, "deadline": tick + 100}, tick)
    if risk is not None:
        ex.execute("cover", {"id": oid, "funding_event_id": funding["event"],
                             "event_id": "risk-cover:" + oid}, tick)
    ex.execute("event", {"id": oid, "action": "consent",
                         "event_id": oid + "-consent"}, tick)
    ex.execute("event", {"id": oid, "action": "fund",
                         "event_id": oid + "-fund"}, tick)
    ex.execute("event", {"id": oid, "action": "prepare",
                         "event_id": oid + "-prepare"}, tick + 1)
    if opportunity["refund"]:
        ex.execute("event", {"id": oid, "action": "refund",
                             "event_id": oid + "-refund"}, tick + 2)
        return {"outcome": "REFUNDED", "next_tick": tick + 3}
    ex.execute("event", {"id": oid, "action": "release",
                         "event_id": oid + "-release"}, tick + 2)
    if risk is None:
        return {"outcome": "SETTLED_PERMANENT", "next_tick": tick + 6}
    ex.execute("risk_mature", {"id": oid, "event_id": oid + "-risk-mature"}, tick + 4)
    maturity = ex.snapshot()
    cap = next(
        (int(x["cap"]) for x in ex.export()["investments"]
         if x["id"] == "risk-residual:" + oid), 0
    )
    if opportunity["late_claim"] and cap:
        claim = cap // 2
        ex.execute("risk_claim", {
            "id": oid, "amount": claim,
            "claim_sha256": hashlib.sha256((oid + ":claim").encode()).hexdigest(),
        }, tick + 5)
        outcome = "SETTLED_THEN_LATE_CLAIM"
    else:
        ex.execute("risk_expire", {"id": oid}, tick + 7)
        claim = 0
        outcome = "SETTLED_RISK_RESIDUAL_EXPIRED"
    return {"outcome": outcome, "next_tick": tick + 8,
            "residual_cap": cap, "claim": claim, "maturity": maturity}


def run_arm(destination, *, prospective, terms=None):
    contract = "capital-recycling019"
    common = dict(root=ROOT, manifest=MANIFEST, opening=OPENING,
                  working=WORKING, contract=contract, durable=True)
    if prospective:
        ex = OwnedRiskFiniteExchange(
            destination, liability_ticks=2, time_unit="hours",
            arrangement_cost=ARRANGEMENT, risk=terms, **common
        )
    else:
        ex = SingleWriterExchange(destination, **common)
    lineage, outcomes = [], []
    stopped = None
    tick = 0
    try:
        if prospective:
            ex.execute("arrange", {}, tick)
        for opportunity in OPPORTUNITIES:
            friction = terms["buyer_friction"] if prospective else 0
            if opportunity["utility_margin"] < friction:
                outcomes.append({"id": opportunity["id"], "outcome": "VOLUNTARY_NO_PURCHASE"})
                continue
            if opportunity["nonpayment"]:
                outcomes.append({"id": opportunity["id"], "outcome": "NONPAYMENT_NO_COMMITMENT"})
                continue
            amount = PRODUCTION + (terms["premium_per_order"] if prospective else 0)
            funding = fund_delivery(ex, opportunity["id"], tick, amount)
            if funding is None:
                stopped = {"reason": "NO_AUDITED_UNRESTRICTED_EARNINGS",
                           "opportunity": opportunity["id"],
                           "snapshot": ex.snapshot()}
                break
            try:
                result = deliver(ex, opportunity["id"], tick, funding,
                                 risk=terms if prospective else None,
                                 opportunity=opportunity)
            except ValueError as exc:
                stopped = {"reason": str(exc), "opportunity": opportunity["id"],
                           "snapshot": ex.snapshot()}
                break
            lineage.append({
                "opportunity": opportunity["id"], "funding": funding,
                "accepted_output_job_id": JOB, "settlement": result,
            })
            outcomes.append({"id": opportunity["id"], "outcome": result["outcome"]})
            tick = result["next_tick"]
        tape = ex.export()
        audit = (
            audit_contract019(tape, root=ROOT, manifest=MANIFEST)
            if prospective else audit_native(tape, root=ROOT, manifest=MANIFEST)
        )
        assert audit["accepted"] is True
        return {
            "prospective": prospective,
            "terms": terms,
            "summary": tape["summary"],
            "accepted_settled": sum(x["outcome"].startswith("SETTLED") for x in outcomes),
            "refunded": sum(x["outcome"] == "REFUNDED" for x in outcomes),
            "voluntary_no_purchase": sum(x["outcome"] == "VOLUNTARY_NO_PURCHASE" for x in outcomes),
            "nonpayment": sum(x["outcome"] == "NONPAYMENT_NO_COMMITMENT" for x in outcomes),
            "prior_earned_funded": sum(
                x["funding"]["funding"] == "PRIOR_UNRESTRICTED_EARNINGS" for x in lineage
            ),
            "stopped": stopped,
            "funding_lineage": lineage,
            "actions_sha256": tape["actions_sha256"],
            "audit_accepted": True,
        }
    finally:
        ex.close()


def account_boundary_negative(tmp):
    path = Path(tmp) / "adaptive-risk.sqlite"
    before = list(Path(tmp).iterdir())
    try:
        OwnedRiskFiniteExchange(
            path, root=ROOT, manifest=ADAPTIVE_MANIFEST,
            opening=OPENING, working=WORKING, contract="must-refuse",
            liability_ticks=2, time_unit="hours", arrangement_cost=ARRANGEMENT,
            risk=basic_terms(), durable=True,
        )
    except ValueError as exc:
        return {
            "refused": "MANDATORY_WRITER_ACCOUNT_FACADE" in str(exc),
            "error": str(exc),
            "before_files": [x.name for x in before],
            "after_files": sorted(x.name for x in Path(tmp).iterdir()),
            "meaning": "PR24-derived exchange is not the current mandatory Account path.",
        }
    raise AssertionError("adaptive manifest unexpectedly bypassed Account")


def restart_and_writer_probe(tmp):
    path = Path(tmp) / "restart-risk.sqlite"
    kwargs = dict(
        root=ROOT, manifest=MANIFEST, opening=OPENING, working=WORKING,
        contract="restart-probe", liability_ticks=2, time_unit="hours",
        arrangement_cost=ARRANGEMENT, risk=basic_terms(), durable=True,
    )
    with OwnedRiskFiniteExchange(path, **kwargs) as ex:
        ex.execute("arrange", {}, 0)
        funding = fund_delivery(ex, 0, 0, PRODUCTION + basic_terms()["premium_per_order"])
        deliver(ex, 0, 0, funding, risk=basic_terms(), opportunity=OPPORTUNITIES[0])
        before = ex.export()
        try:
            OwnedRiskFiniteExchange(path, **kwargs)
        except Exception as exc:
            concurrent = {"refused": True, "error": str(exc)}
        else:
            raise AssertionError("concurrent writer unexpectedly admitted")
    with OwnedRiskFiniteExchange(path, **kwargs) as reopened:
        after = reopened.export()
        receipt = audit_contract019(after, root=ROOT, manifest=MANIFEST)
    return {
        "same_actions_sha256": before["actions_sha256"] == after["actions_sha256"],
        "same_summary": before["summary"] == after["summary"],
        "audit_accepted": receipt["accepted"],
        "concurrent_writer": concurrent,
    }


def main():
    scenarios = {
        "central": basic_terms(),
        "high_premium": basic_terms(premium_per_order=80 * MICRO),
        "high_friction": basic_terms(buyer_friction=30 * MICRO),
        "full_provider_default": basic_terms(provider_default_severity_bps=10_000),
        "fully_correlated_dispute": basic_terms(correlated_dispute_bps=10_000),
    }
    with tempfile.TemporaryDirectory(prefix="capital019-") as tmp:
        tmp = Path(tmp)
        boundary = account_boundary_negative(tmp)
        assert boundary["refused"]
        recovery = restart_and_writer_probe(tmp)
        assert recovery["same_actions_sha256"] and recovery["same_summary"]
        assert recovery["audit_accepted"] and recovery["concurrent_writer"]["refused"]
        permanent = run_arm(tmp / "permanent.sqlite", prospective=False)
        results = {}
        for name, terms in scenarios.items():
            results[name] = run_arm(tmp / (name + ".sqlite"), prospective=True, terms=terms)
    central = results["central"]
    assertion = {
        "same_seed": OPENING,
        "same_working": WORKING,
        "same_opportunities_sha256": digest(OPPORTUNITIES),
        "same_accepted_output_job": JOB,
        "permanent_settled": permanent["accepted_settled"],
        "prospective_settled": central["accepted_settled"],
        "incremental_settled": central["accepted_settled"] - permanent["accepted_settled"],
        "permanent_profit": permanent["summary"]["profit"],
        "prospective_profit": central["summary"]["profit"],
        "incremental_profit": central["summary"]["profit"] - permanent["summary"]["profit"],
        "prospective_prior_earned_funded": central["prior_earned_funded"],
    }
    assert central["accepted_settled"] > permanent["accepted_settled"]
    assert central["prior_earned_funded"] > permanent["prior_earned_funded"]
    assert all(
        item["funding"]["reserved"]["reservedInvestment"] >= item["funding"]["amount"]
        for item in central["funding_lineage"]
        if item["funding"]["funding"] == "PRIOR_UNRESTRICTED_EARNINGS"
    )
    result = {
        "schema": "agi-alpha/capital-recycling019-result/v1",
        "source_support_commit": "ee6742725c68bf7bea5bb3cb2ed91c4fd5a1164e",
        "pr24_input": "97c790ae681779deca53e8ddc8c6dc3b6841bfc6",
        "observed_pr28_head": "d1a7b41779ae4ee2f00402bef11e5ae931200ba6",
        "scope": "Authored positive-demand native-ledger exploration; not current Account qualification, external commerce, insurer evidence, or C/K factorial.",
        "predeclared": {
            "opening": OPENING, "working": WORKING, "price": PRICE,
            "production_cost": PRODUCTION, "opportunities": len(OPPORTUNITIES),
            "liability_hours": 2, "central_terms": scenarios["central"],
        },
        "catalogue": {
            "jobs": len(CATALOGUE["jobs"]),
            "families": len({x["family"] for x in CATALOGUE["jobs"]}),
            "reference_bundles": len(BUNDLES["sample_enterprise_programs"]),
            "actual_catalogue_jobs_performed": 0,
            "accepted_synthetic_service_job": JOB,
        },
        "permanent": permanent,
        "prospective": results,
        "matched_central_assertion": assertion,
        "account_boundary": boundary,
        "restart_and_writer_probe": recovery,
        "adoption": "DECLINE_AS_OPERATIONAL_CURRENT_ACCOUNT_MECHANISM",
        "adoption_reason": "Economic effect appears in the PR24-derived ledger exploration, but mandatory adaptive Account ownership/audit refuses this wrapper. Integration would otherwise create an unaudited parallel operating path.",
        "unknown_costs": ["host billing", "model billing (no paid/model call occurred)", "real buyer demand", "legal enforceability", "provider solvency"],
    }
    (OUT / "RESULT.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "central": assertion,
        "account_boundary": boundary,
        "failures": {k: {"settled": v["accepted_settled"],
                          "profit": v["summary"]["profit"],
                          "stop": v["stopped"]}
                     for k, v in results.items()},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
