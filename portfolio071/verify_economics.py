"""Read-only independent arithmetic and native replay of exported campaigns.

No account is opened for writing, no signing key is read, and this module never
constructs economic offers or injects funds. This is an audit of conditional
simulation records, not certification of external demand or actual revenue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from commercial.ledger import strict_json
from connected_enterprise.finance import audit_journal


def load(path):
    return strict_json(Path(path).read_bytes())


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def money_state(state, opening):
    require(state["profit"] == state["revenue"] + state["recoveryIncome"] - state["expenses"],
            "Recognized profit identity violated")
    require(state["cash"] == opening + state["collections"] + state["recoveryIncome"] - state["expensePaid"],
            "Opening equity plus actual cash flows does not reconcile")
    reserve = sum(state[k] for k in ("custodyReserve", "tailReserve", "workingCapital", "reservedInvestment", "payables"))
    require(state["cash"] >= reserve, "Cash is below native protections and incurred payables")
    require(state["available"] == state["cash"] - reserve, "Available cash differs from native protections")


def event_facts(actions, opening, tax_bps):
    orders, released, refunded = {}, {}, {}
    tax_paid, pending_tax_payment = 0, None
    protected = ("cash", "collections", "revenue", "profit", "expenses", "available")
    for i, action in enumerate(actions):
        args, op = action["args"], action["op"]
        money_state(action["before"], opening)
        money_state(action["after"], opening)
        if pending_tax_payment is not None:
            ident, due, hour = pending_tax_payment
            require(op == "cost" and args["id"] == "tax-" + ident and args["amount"] == due and action["day"] == hour,
                    "Incurred scenario tax was not settled immediately after collection")
            tax_paid += due
            pending_tax_payment = None
        elif op == "cost" and args["id"].startswith("tax-"):
            raise AssertionError("Tax expense has no preceding collection obligation")
        if op == "wallet":
            require(all(action["before"][k] == action["after"][k] for k in protected),
                    "Buyer wallet provisioning changed company cash or income")
        if op == "offer":
            require(args["id"] not in orders, "Duplicate modeled license order")
            orders[args["id"]] = args["price"]
        if op == "event" and args["action"] in ("release", "refund"):
            ident = args["id"]
            require(ident in orders and ident not in released and ident not in refunded,
                    "Collection/refund is missing an offer or is counted twice")
            if args["action"] == "release":
                released[ident] = action["day"]
                require(action["after"]["collections"] - action["before"]["collections"] == orders[ident],
                        "Collection does not equal accepted modeled price")
                require(action["after"]["revenue"] - action["before"]["revenue"] == orders[ident],
                        "Revenue differs from accepted release")
                pretax = action["after"]["profit"] + tax_paid
                due = max(0, pretax * tax_bps // 10000 - tax_paid)
                if due:
                    pending_tax_payment = (ident, due, action["day"])
            else:
                refunded[ident] = action["day"]
                require(action["after"]["revenue"] == action["before"]["revenue"] and
                        action["after"]["collections"] == action["before"]["collections"],
                        "Escrow cancellation improperly became company revenue")
    require(pending_tax_payment is None, "Unsettled tax at the end of the exported action tape")
    return {"orders": orders, "releases": released, "refunds": refunded, "tax_paid": tax_paid}


def daily_commitments(trajectory, actions):
    pending, cursor = {}, 0
    state = actions[0]["before"]
    rate = trajectory["world"]["tax_bps"]
    for expected_day, row in enumerate(trajectory["daily"]):
        require(row["day"] == expected_day, "Missing or repeated operating day")
        while cursor < len(actions) and actions[cursor]["day"] < (expected_day + 1) * 24:
            action = actions[cursor]
            args = action["args"]
            if action["op"] == "offer":
                pending[args["id"]] = args["price"]
            if action["op"] == "event" and args["action"] in ("release", "refund"):
                pending.pop(args["id"])
            state = action["after"]
            cursor += 1
        bound = sum((price * rate + 9999) // 10000 for price in pending.values())
        require(row["pending_tax_commitment_microUSD"] == bound,
                "Controller tax memo does not equal independent pending gross-price bound")
        require(state["available"] >= bound and row["tax_commitments_covered"] is True,
                "Pending scenario tax is not covered by discretionary cash")
        require(row["cash_microUSD"] == state["cash"] and row["available_microUSD"] == state["available"],
                "Daily economic summary does not match native actions")
    return len(trajectory["daily"])


def audit_arm(root, directory, expected_hours=43800):
    directory = Path(directory)
    trajectory = load(directory / "trajectory.json")
    manifest = load(directory / "manifest.json")
    horizon, drained = (load(directory / name) for name in ("native-at-horizon.json", "native-after-drain.json"))
    for filename, field in (("manifest.json", "manifest_sha256"),
                            ("native-at-horizon.json", "native_export_sha256"),
                            ("native-after-drain.json", "drain_export_sha256")):
        require(hashlib.sha256((directory / filename).read_bytes()).hexdigest() == trajectory[field],
                "Export file identity differs from trajectory")
    # This reuses the mandatory native replay, then independently checks the
    # economic interpretation without constructing a second financial ledger.
    replay_at_horizon = audit_journal(horizon, root=Path(root), manifest=manifest)
    replay_after_drain = audit_journal(drained, root=Path(root), manifest=manifest)
    require(replay_at_horizon["accepted"] and replay_after_drain["accepted"], "Native replay did not accept")
    actions = horizon["ledger"]["actions"]
    all_actions = drained["ledger"]["actions"]
    require(all_actions[:len(actions)] == actions, "Drain revised the historical operating prefix")
    require(actions[-1]["day"] == expected_hours - 1, "Operating endpoint was shortened or extended")
    require(all(a["day"] < expected_hours for a in actions), "Post-horizon event entered operating export")
    require(all(a["day"] >= expected_hours for a in all_actions[len(actions):]), "Drain contains an operating-period action")
    require(trajectory["operating_complete"] is True, "Incomplete registered operating horizon")
    opening = trajectory["capital_usd"] * 1000000
    require(actions[0]["before"]["cash"] == opening and actions[0]["before"]["profit"] == 0,
            "Fresh account opening is not the stated equity-only counterfactual")
    facts = event_facts(all_actions, opening, trajectory["world"]["tax_bps"])
    days = daily_commitments(trajectory, actions)
    require(days * 24 == expected_hours, "Daily operating history is incomplete")
    start = expected_hours - 8760
    exact = sum(a["after"]["profit"] - a["before"]["profit"]
                for a in actions if start <= a["day"] < expected_hours)
    rolling = trajectory["rolling_profit"]
    require(rolling["interval"]["start_hour_inclusive"] == start and
            rolling["interval"]["end_hour_exclusive"] == expected_hours,
            "Wrong exact trailing-year interval")
    require(exact == rolling["trailing_365_day_profit_microUSD"],
            "Reported trailing profit differs from independent signed hourly sum")
    final = drained["ledger"]["summary"]
    require(final == trajectory["post_horizon_drain_endpoint"], "Drained endpoint mismatch")
    require(horizon["ledger"]["summary"] == trajectory["operating_endpoint"], "Operating endpoint mismatch")
    require(final["payables"] == 0 and final["custodyReserve"] == 0, "Unresolved payable or custody after drainage")
    require(facts["tax_paid"] == trajectory["total_tax_after_drain_microUSD"], "Total tax does not reconcile")
    before = sum(hour < expected_hours for hour in facts["releases"].values())
    after = len(facts["releases"]) - before
    require(before == trajectory["modeled_licenses"] and after == trajectory["post_horizon_collected_licenses"],
            "Modeled license count does not equal unique releases")
    require(trajectory["external_financing_received_usd"] == trajectory["external_revenue_usd"] == trajectory["installed_physical_sites"] == 0,
            "Simulation was promoted to external funding, revenue or installation")
    require(trajectory["actual_scientific_artifacts"] == len(manifest["jobs"]) == 2,
            "License reuse was counted as new scientific production")
    require(trajectory["milestone_1b"] == (exact >= 1000000000 * 1000000) and
            trajectory["milestone_3b"] == (exact >= 3000000000 * 1000000), "Profit milestone flag mismatch")
    return {"accepted": True, "arm": directory.name, "id": trajectory["id"],
            "world": trajectory["world"]["name"], "capital_usd": trajectory["capital_usd"],
            "native_replay_at_horizon": replay_at_horizon["accepted"],
            "native_replay_after_drain": replay_after_drain["accepted"],
            "operating_days": days, "operating_actions": len(actions), "drain_actions": len(all_actions) - len(actions),
            "independent_trailing_profit_microUSD": exact, "released_modeled_licenses": before,
            "post_horizon_releases": after, "escrow_cancellations": len(facts["refunds"]),
            "pending_tax_coverage_every_day": True, "immediate_tax_after_release": True,
            "tax_paid_after_drain_microUSD": facts["tax_paid"],
            "cash_reconciles_at_every_action": True, "buyer_wallet_isolation": True,
            "unresolved_payables_after_drain": final["payables"],
            "residual_tail_reserve_after_drain_microUSD": final["tailReserve"],
            "scope": "Conditional native accounting accepted; authored demand and costs remain unvalidated."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.process_time()
    campaign = load(args.campaign / "campaign.json")
    rows = []
    directories = sorted(args.campaign.glob("arm-*"))
    require(len(directories) == campaign["registered_arms"] == campaign["completed_arms"] == 24,
            "Registered 24-arm denominator was not completed")
    for directory in directories:
        try:
            rows.append(audit_arm(args.root, directory))
        except Exception as error:
            rows.append({"accepted": False, "arm": directory.name, "failure": type(error).__name__ + ": " + str(error)})
        print(json.dumps(rows[-1]), flush=True)
    report = {"schema": "portfolio071/independent-economic-audit/v1", "registered_arms": 24,
              "accepted": all(row["accepted"] for row in rows), "arms": rows,
              "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "process_cpu_seconds": time.process_time() - started,
              "source_review": "Separate verifier reviewed full service, arrangement, economics and native dispatch. Prospective fixes cover tax liquidity, cash-aware price choice, prior collected renewal, same-budget outside options and prepaid retirement.",
              "limits": ["Replaying an existing exact native engine is not external institutional certification.",
                         "No demand calibration, realized customer consent, external financing, physical installation or actual commerce is established.",
                         "Pending-tax protection is a controller policy under the mandatory single writer, not a native reserve.",
                         "Conventional equal-capability entrepreneurship is an admissible competitor; unique discovery superiority is not established."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if not report["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
