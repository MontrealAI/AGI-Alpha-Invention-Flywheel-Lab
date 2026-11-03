"""One source-frozen, restartable native enterprise per registered comparison.

The commercial environment is conditional; actual numerical packages execute.
All money and obligations belong to JournalAccount, never this operating state.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
from collections import defaultdict

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, audit_journal, SOURCE_PATHS as FINANCE_PATHS
from connected_enterprise.scale import trailing_profit
from .policy import decide, empty_stats, POLICIES
from .world import (USD, YEAR_HOURS, CHANNELS, WORLDS, ContactRights, make_rule,
    channel_quote, contract_for as generated_contract, settlement_outcome, technical_qualification)
from .service import (prepare_manifest, contract_for, totals, cost_rows, terms_for,
    produce, check_delivery, SOURCE_PATHS as SERVICE_PATHS)

OPENING = 100_000 * USD
ROOT = Path(__file__).resolve().parents[1]
CASE_SCHEMA = "omega-savings/native-case/v1"
CODE_FOLDERS = ("omega_savings", "connected_enterprise", "adaptive_enterprise", "commercial", "enterprise",
                "vendor", "portfolio25", "mechanisms", "mechanism_harness", "flywheel", "flywheel_wheel")


def save(path, value):
    atomic_bytes(Path(path), canonical(value) + b"\n")


def source_files(root):
    names = set(FINANCE_PATHS) | set(SERVICE_PATHS)
    for folder in CODE_FOLDERS:
        names.update(str(p.relative_to(root)) for p in (root / folder).rglob("*.py") if "__pycache__" not in p.parts)
    names.add("experiments/commerce006.py")
    names.update({"requirements-commercial010.txt", "requirements-omega-savings.txt", "AGENTS.md"})
    return sorted(names)


def freeze(root, output, registration):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists(): raise FileExistsError("FRESH_REGISTERED_OUTPUT_REQUIRED")
    output.mkdir(parents=True)
    source = output / "source"
    files = {}
    for name in source_files(root):
        p = root / name
        if not p.is_file() or p.is_symlink(): raise ValueError("COMPLETE_SOURCE_REQUIRED:" + name)
        target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
        files[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    record = {"schema": "omega-savings/source-freeze/v1", "files": files, "sha256": digest(files),
              "git_commit": git.stdout.strip() if git.returncode == 0 else None,
              "registration_sha256": digest(registration)}
    save(output / "SOURCE.json", record); save(output / "REGISTRATION.json", registration)
    save(output / "PROGRESS.json", {"complete": False, "completed": [], "registered_cases": len(registration["cases"])})
    return record


def check_source(output):
    output = Path(output).resolve()
    frozen = strict_json((output / "SOURCE.json").read_bytes())
    source = output / "source"
    if set(frozen["files"]) != set(source_files(source)) or digest(frozen["files"]) != frozen["sha256"]:
        raise ValueError("COMPLETE_FROZEN_SOURCE_REQUIRED")
    for name, sha in frozen["files"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != sha:
            raise ValueError("FROZEN_SOURCE_CHANGED:" + name)
    registration = strict_json((output / "REGISTRATION.json").read_bytes())
    if digest(registration) != frozen["registration_sha256"]: raise ValueError("REGISTRATION_CHANGED")
    if Path(__file__).resolve() != source / "omega_savings/runner.py":
        raise ValueError("EXECUTE_FROM_FROZEN_SOURCE_REQUIRED")
    return source, registration, frozen


def registration(*, role="confirmation", seeds=(701, 702), worlds=None, policies=None, fixed_fraction=1500, cadence_days=14, cost_surcharge=0, variant="primary"):
    worlds = list(WORLDS if worlds is None else worlds)
    policies = list(POLICIES if policies is None else policies)
    if not worlds or not policies or not seeds or len(set(worlds)) != len(worlds) or len(set(policies)) != len(policies) or len(set(seeds)) != len(seeds):
        raise ValueError("NONEMPTY_UNIQUE_REGISTRATION_AXES_REQUIRED")
    if any(type(s) is not int or s < 0 for s in seeds) or cadence_days not in (7, 14, 30):
        raise ValueError("REGISTERED_SEEDS_AND_CADENCE_REQUIRED")
    if role not in {"development", "confirmation", "reproduction"}: raise ValueError("EXPLICIT_EVIDENCE_ROLE_REQUIRED")
    if type(cost_surcharge) is not int or cost_surcharge < 0 or type(fixed_fraction) is not int or not 0 <= fixed_fraction <= 10000:
        raise ValueError("EXPLICIT_NONNEGATIVE_COST_AND_VALID_ALLOCATION_REQUIRED")
    if not isinstance(variant, str) or not variant or len(variant) > 30 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in variant):
        raise ValueError("EXPLICIT_SAFE_EXPERIMENT_VARIANT_REQUIRED")
    suffix = "" if variant == "primary" else "-" + variant
    if any(w not in WORLDS for w in worlds) or any(p not in POLICIES for p in policies): raise ValueError("REGISTERED_WORLD_AND_POLICY_REQUIRED")
    if role == "confirmation" and set(seeds).intersection({11, 12, 13, 14}): raise ValueError("DEVELOPMENT_SEED_IN_CONFIRMATION")
    return {"schema": "omega-savings/registration/v1", "role": role, "opening_microUSD": OPENING,
        "operating_hours": [0, YEAR_HOURS], "settlement_end_hour": YEAR_HOURS + max(w["collection_hours"] for w in WORLDS.values()) + 720 + 1,
        "technical": technical_qualification(), "technical_confirmation_seeds": [701, 702, 703],
        "variant": variant,
        "primary": ("positive-adaptive-701" if "positive" in worlds and "adaptive" in policies and 701 in seeds else f"{worlds[0]}-{policies[0]}-{seeds[0]}") + suffix,
        "accounts_pooled": False, "actual_commerce": False, "fixed_fraction_bps": fixed_fraction,
        "decision_cadence_days": cadence_days, "cost_surcharge_microUSD_per_buyer": cost_surcharge,
        "tax_policy": "Immediate nonrefundable25percent levy on increases of positive cumulative pretax profit highwater; assessment and payment distinct native fields at same event; reserve0after full payment; not tax advice or actual jurisdiction law.",
        "scale_semantics": "Each native order is an exactly homogeneous cohort of independently budgeted buyers receiving the same reusable package. Partial cohorts selected from current cash before hidden settlement outcomes. One enterprise account; no cross-account money.",
        "cost_scope": "Declared model complete; prices, demand, bills, effort and cash avoidability authored. Work-unit savings never asserted as measured cloud dollars. Actual host/model billing unknown.",
        "stopping": "Finish every fixed world/policy/seed through365days and the longest collection plus720hour claim window and one inclusive-boundary hour; preserve errors and resume same accounts. No result-based retuning of confirmation; one separate diagnostic may investigate an identified failure.",
        "cases": [{"id": f"{w}-{p}-{s}" + suffix, "world": w, "policy": p, "seed": int(s)}
                  for w in worlds for p in policies for s in seeds]}


def _schedule(state, event):
    event = copy.deepcopy(event)
    event["serial"] = state["next_serial"]; state["next_serial"] += 1
    state["queue"].append(event)
    state["queue"].sort(key=lambda e: (e["hour"], e["serial"]))


def _initial(case, registration):
    s = {"schema": CASE_SCHEMA, "case": case, "built": False, "capability": 0,
         "stats": empty_stats(), "qualified_advanced": 0, "campaign_count": 0,
         "last_campaign_units": 0, "rights": None, "queue": [], "next_serial": 0,
         "next_order": 0, "pending": None, "decisions": [], "campaigns": {}, "lots": [],
         "orders": [], "costs": [], "taxes": [], "funded": [], "corrections": [], "claims": [],
         "processed": 0, "complete": False, "year_summary": None, "deferred_for_obligations": False,
         "human_minutes_actual": 0, "human_minutes_modeled_internal": 0,
         "founder_services": 0}
    for day in range(0, 365, registration["decision_cadence_days"]):
        _schedule(s, {"kind": "decision", "hour": day * 24, "cycle": day // 30})
    _schedule(s, {"kind": "year_close", "hour": YEAR_HOURS - 1})
    _schedule(s, {"kind": "settlement_close", "hour": registration["settlement_end_hour"]})
    return s


def _cost(account, state, ident, value, hour, category):
    account.cost(ident, value, hour)
    if not any(r["id"] == ident for r in state["costs"]):
        state["costs"].append({"id": ident, "amount": value, "hour": hour, "category": category})


def _tax(account, state, ident, hour):
    tape = account.export()["ledger"]
    paid = sum(a["args"]["amount"] for a in tape["actions"] if a["op"] == "cost" and a["args"]["id"].startswith("tax:"))
    existing = next((a for a in tape["actions"] if a["op"] == "cost" and a["args"]["id"] == "tax:" + ident), None)
    levy = existing["args"]["amount"] if existing else max(0, max(0, tape["summary"]["profit"] + paid) // 4 - paid)
    if levy:
        _cost(account, state, "tax:" + ident, levy, hour, "modeled_tax")
        row = next(a for a in account.export()["ledger"]["actions"] if a["op"] == "cost" and a["args"]["id"] == "tax:" + ident)
        if not any(r["id"] == "tax:" + ident for r in state["taxes"]):
            state["taxes"].append({"id": "tax:" + ident, "hour": hour, "expense": levy,
                "cash_payment": row["after"]["expensePaid"] - row["before"]["expensePaid"],
                "reserve_unpaid": levy - (row["after"]["expensePaid"] - row["before"]["expensePaid"])})


def _public_observation(account, state, rule, hour, registration):
    summary = account.snapshot()["summary"]
    rights = ContactRights(rule["seed"], rule["world"], state["rights"])
    return {"hour": hour, "available": summary["available"], "unrestricted_earned": summary["unrestrictedEarned"], "payables": summary["payables"],
        "built": state["built"], "capability": state["capability"], "channel_stats": copy.deepcopy(state["stats"]),
        "campaign_count": state["campaign_count"], "last_campaign_units": state["last_campaign_units"],
        "qualified_advanced": state["qualified_advanced"], "cash_profit": summary["profit"],
        "fixed_fraction_bps": registration["fixed_fraction_bps"],
        "current_quotes": {c: channel_quote(c, 20, rights.state["cursors"][c], world=rule["world"]) for c in CHANNELS}}


def _prepare_intent(account, state, event, rule, registration):
    hour = event["hour"]
    account.advance_financial(hour)
    intent = {"event": event, "native_sequence_before": len(account.export()["ledger"]["actions"])}
    if event["kind"] == "decision":
        observation = _public_observation(account, state, rule, hour, registration)
        action = decide(state["case"]["policy"], observation)
        # A decision buys at most currently available rights. Marginal saturation
        # can make a proposed size unaffordable; shrink before committing money.
        if action["action"] == "campaign":
            rights = ContactRights(rule["seed"], rule["world"], state["rights"])
            fraction = observation["fixed_fraction_bps"] if state["case"]["policy"] == "fixed_split" else 2000
            while True:
                quote = channel_quote(action["channel"], action["units"], rights.state["cursors"][action["channel"]], world=rule["world"])
                # The exploratory20-contact pilot is separately costed. Larger
                # campaigns obey the allocation fraction at their actual quote.
                budget = observation["available"] if action["units"] <= 20 else observation["available"] * fraction // 10000
                if quote["price_microUSD"] + 40 * USD <= budget: break
                if action["units"] <= 1:
                    action = {"action": "wait", "reason": "current_cash_cannot_buy_supplier_quote"}; break
                action["units"] //= 2
            if action["action"] == "campaign":
                history = observation["channel_stats"][action["channel"]]
                if history["purchased"] and action["reason"] != "costed_information_and_voluntary_sales_pilot":
                    # Quote and quantity are final. Historical contribution is
                    # a forecast, never future income or funding authority.
                    while True:
                        forecast = max(0, history["net_contribution"] + history["spent"]) * action["units"] // history["purchased"] - quote["price_microUSD"] - 40 * USD
                        if forecast > 0: break
                        if action["units"] <= 20:
                            action = {"action": "wait", "reason": "quoted_marginal_acquisition_unprofitable"}; break
                        action["units"] //= 2
                        quote = channel_quote(action["channel"], action["units"], rights.state["cursors"][action["channel"]], world=rule["world"])
                    if action["action"] == "campaign": action["expected_net"] = forecast
                if action["action"] == "campaign": action["quote"] = quote
        intent.update(observation=observation, action=action)
    elif event["kind"] == "fulfill":
        # Select quantity BEFORE consulting future settlement outcomes.
        probe_id = f"c{event['cycle']}t{event['profile']}p{event['price_index']}a{event['capability']}u1l{state['next_order']}"
        c = generated_contract(rule, probe_id)
        backing = c["price_microUSD"] + 200_000 + sum(c["costs_microUSD"].values())
        n = min(len(event["members"]), account.snapshot()["summary"]["available"] // backing)
        intent.update(selected_units=n, unit_backing=backing, available_before=account.snapshot()["summary"]["available"])
        partitions = defaultdict(list)
        for member in event["members"][:n]:
            partitions[settlement_outcome(rule, member)].append(member)
        parts = []
        for offset, ((status, repair), members) in enumerate(sorted(partitions.items())):
            seq = state["next_order"] + offset
            job = f"c{event['cycle']}t{event['profile']}p{event['price_index']}a{event['capability']}u{len(members)}l{seq}"
            parts.append({"job": job, "order": f"order-{seq}", "units": len(members),
                          "status": status, "repair": repair, "members_sha256": digest(members)})
        intent["parts"] = parts
    return intent


def _apply_intent(account, state, intent, root, manifest, rule, registration):
    event, hour = intent["event"], intent["event"]["hour"]
    kind = event["kind"]
    if kind == "decision":
        action = intent["action"]
        state["decisions"].append(copy.deepcopy(intent))
        if action["action"] == "wait" and action["reason"] == "unresolved_native_payables":
            state["deferred_for_obligations"] = True
        elif action["action"] in {"construct", "campaign"}:
            state["deferred_for_obligations"] = False
        if action["action"] == "construct":
            ident = "construct:c" + str(event["cycle"]) + ":a" + str(action["capability"])
            receipt = account.spend(ident, "known_method_package", action["cost"], hour,
                {"capability": action["capability"], "independent_numerical_tests": True},
                expected_net=action["expected_net"], allow_seed=True)
            if receipt is None: raise ValueError("PREDECIDED_CONSTRUCTION_NOT_FUNDED")
            state["funded"].append({"id": ident, "category": "capability", "amount": action["cost"], "hour": hour, "funding": receipt["funding"]})
            state["built"], state["capability"] = True, action["capability"]
            # Reobserve after the build: same-day affordable next action allowed.
            _schedule(state, {"kind": "decision", "hour": hour, "cycle": event["cycle"]})
        elif action["action"] == "campaign":
            ident = f"campaign-{state['campaign_count']}"
            quote = action["quote"]
            _cost(account, state, "operating:" + ident, 40 * USD, hour, "subscription_infrastructure_admin_envelope")
            receipt = account.spend(ident, "paid_contact_rights", quote["price_microUSD"], hour,
                {"quote": quote, "policy": state["case"]["policy"], "expiry_hours": quote["expiry_after_hours"]},
                expected_net=action["expected_net"], allow_seed=True)
            if receipt is None: raise ValueError("PREDECIDED_CAMPAIGN_NOT_FUNDED")
            rights = ContactRights(rule["seed"], rule["world"], state["rights"])
            row = rights.purchase(ident, action["channel"], action["units"], hour,
                invoice=quote, paid_microUSD=quote["price_microUSD"])
            state["rights"] = rights.export()
            state["campaigns"][ident] = {"channel": action["channel"], "units": action["units"],
                "price_index": action["price_index"], "cycle": event["cycle"], "capability": state["capability"],
                "paid": quote["price_microUSD"], "hour": hour, "expiry": row["expiry"]}
            s = state["stats"][action["channel"]]
            s["spent"] += quote["price_microUSD"] + 40 * USD; s["net_contribution"] -= quote["price_microUSD"] + 40 * USD
            s["campaigns"] += 1
            s["purchased"] += action["units"]
            bp = s["by_price"].setdefault(str(action["price_index"]), {"net": 0, "contacts": 0})
            bp["net"] -= quote["price_microUSD"] + 40 * USD
            bp["contacts"] += action["units"]  # Paid slots, including overlaps/nonconversions.
            state["funded"].append({"id": ident, "category": "acquisition", "amount": quote["price_microUSD"], "hour": hour, "funding": receipt["funding"]})
            state["campaign_count"] += 1; state["last_campaign_units"] = action["units"]
            _schedule(state, {"kind": "expose", "hour": row["activation"], "campaign": ident})
    elif kind == "expose":
        campaign = state["campaigns"][event["campaign"]]
        rights = ContactRights(rule["seed"], rule["world"], state["rights"])
        exposure = rights.expose(event["campaign"], hour, rule, campaign=campaign["cycle"],
            capability=campaign["capability"], price_index=campaign["price_index"])
        state["rights"] = rights.export()
        campaign["exposure"] = copy.deepcopy(exposure)
        stats = state["stats"][campaign["channel"]]
        stats["contacted"] += exposure["fresh"]
        state["qualified_advanced"] += exposure.get("qualified_advanced", 0)
        for group in exposure["groups"]:
            _schedule(state, {"kind": "fulfill", "hour": hour, "campaign": event["campaign"],
                "cycle": campaign["cycle"], "profile": group["profile"], "members": group["members"],
                "price_index": campaign["price_index"], "capability": campaign["capability"], "expiry": campaign["expiry"]})
    elif kind == "fulfill":
        if hour >= event["expiry"] or hour >= YEAR_HOURS:
            state["lots"].append({"hour": hour, "campaign": event["campaign"], "expired_units": len(event["members"]), "selected_units": 0})
            return
        n = intent["selected_units"]
        state["lots"].append({"hour": hour, "campaign": event["campaign"], "profile": event["profile"],
            "selected_units": n, "remaining_units": len(event["members"]) - n,
            "unit_backing": intent["unit_backing"], "available_before": intent["available_before"],
            "members_sha256": digest(event["members"][:n]), "parts": copy.deepcopy(intent["parts"])})
        for part in intent["parts"]:
            job, contract = contract_for(root, manifest, part["job"])
            t = totals(contract); order = part["order"]
            for ident, amount in cost_rows(job, order, contract):
                _cost(account, state, ident, amount, hour, ident.split(":")[-1])
            account.execute("wallet", {"buyer": order + "-buyers", "amount": t["buyer_budget_microUSD"]}, hour)
            account.execute("register_terms", {"id": order + ":terms", "terms": terms_for(manifest, order, contract, hour)}, hour)
            account.execute("offer", {"id": order, "buyer": order + "-buyers", "price": t["price_microUSD"],
                "job_id": part["job"], "deadline": hour + contract["deadline_hours"], "terms_id": order + ":terms"}, hour)
            for action in ("consent", "fund"):
                account.execute("event", {"id": order, "action": action, "event_id": order + ":" + action}, hour)
            if part["repair"]:
                # A grounded critic detects a real corrupted result; repair is
                # the already available checked constructor, not human labor.
                from .verify import verify
                from .kernel import solve
                correction_path = root / (job["output"] + ".correction.json")
                if correction_path.exists():
                    correction = strict_json(correction_path.read_bytes())
                    artifact = produce(root, manifest, part["job"])
                else:
                    original = solve(contract["request"], method=contract["method"])
                    corrupt = copy.deepcopy(original)
                    if corrupt.get("solutions"): corrupt["solutions"][0][0] += 1.0
                    rejected = not verify(contract["request"], corrupt)["accepted"]
                    if not rejected: raise ValueError("CORRECTION_COUNTEREXAMPLE_NOT_DETECTED")
                    repaired = solve(contract["request"], method=contract["method"])
                    if not verify(contract["request"], repaired)["accepted"]:
                        raise ValueError("TESTED_RECONSTRUCTION_FAILED")
                    # If an interrupted event already materialized the correct
                    # delivery, preserve those exact bytes and authority.
                    artifact = produce(root, manifest, part["job"]) if (root / job["output"]).exists() else produce(root, manifest, part["job"], result=repaired)
                    correction = {"order": order, "failed_result": corrupt, "failed_result_sha256": digest(corrupt), "rejected": True,
                        "repaired_result_sha256": digest(artifact["result"]),
                        "scope": "Injected output fault; independent rejection and actual known-constructor rerun, not naturally observed failure or novel repair discovery.",
                        "cost": contract["costs_microUSD"]["failure_retry_envelope"] * part["units"]}
                    save(correction_path, correction)
                state["corrections"].append({k: v for k, v in correction.items() if k != "failed_result"})
            else:
                artifact = produce(root, manifest, part["job"])
            accepted = check_delivery(root, manifest, part["job"], artifact)["accepted"]
            if not accepted:
                account.execute("event", {"id": order, "action": "refund", "event_id": order + ":refund"}, hour)
                part["status"] = "verification_rejected"
            elif part["status"] != "refund":
                account.execute("event", {"id": order, "action": "prepare", "event_id": order + ":prepare",
                    "artifact_sha256": digest(artifact)}, hour)
            due = hour + contract["collection_delay_hours"]
            state["orders"].append({**part, "campaign": event["campaign"], "profile": event["profile"],
                "hour": hour, "due": due, "price": t["price_microUSD"],
                "service_cost": t["service_cost_microUSD"], "budget": t["buyer_budget_microUSD"],
                "cost_categories": {k: v * part["units"] for k, v in contract["costs_microUSD"].items()},
                "mathematical_and_work_promise_accepted": accepted, "settled": False})
            s = state["stats"][state["campaigns"][event["campaign"]]["channel"]]
            s["net_contribution"] -= t["service_cost_microUSD"]
            s["by_price"][str(event["price_index"])]["net"] -= t["service_cost_microUSD"]
            _schedule(state, {"kind": "settle", "hour": due, "order": order})
        state["next_order"] += len(intent["parts"])
        if n < len(event["members"]):
            later = copy.deepcopy(event); later.pop("serial", None)
            later["members"] = event["members"][n:]
            later["hour"] = hour + max(24, rule["world"]["collection_hours"])
            _schedule(state, later)
    elif kind == "settle":
        order = next(o for o in state["orders"] if o["order"] == event["order"])
        action = "release" if order["status"] in {"collect", "late_claim"} and order["mathematical_and_work_promise_accepted"] else "refund"
        if order["status"] != "verification_rejected":
            account.execute("event", {"id": order["order"], "action": action, "event_id": order["order"] + ":" + action}, hour)
        order["settled"] = True; order["native_outcome"] = action
        if action == "release":
            campaign = state["campaigns"][order["campaign"]]
            stats = state["stats"][campaign["channel"]]
            stats["settled_units"] += order["units"]; stats["net_contribution"] += order["price"]
            stats["by_price"][str(campaign["price_index"])]["net"] += order["price"]
            if order["status"] == "late_claim":
                _schedule(state, {"kind": "claim", "hour": hour + 168, "order": order["order"]})
        _tax(account, state, order["order"], hour)
    elif kind == "claim":
        order = next(o for o in state["orders"] if o["order"] == event["order"])
        ident = order["order"] + ":compatibility-dispute"
        value = order["price"] // order["units"] // 10 * order["units"]
        account.execute("claim", {"id": order["order"], "claim_id": ident,
            "amount": value, "kind": "disputed"}, hour)
        state["costs"].append({"id": ident, "amount": value, "hour": hour, "category": "postcollection_disputes"})
        state["claims"].append({"id": ident, "order": order["order"], "amount": value,
            "hour": hour, "paid": 0, "resolution": None})
        campaign = state["campaigns"][order["campaign"]]
        stats = state["stats"][campaign["channel"]]
        stats["net_contribution"] -= value
        stats["by_price"][str(campaign["price_index"])]["net"] -= value
        _schedule(state, {"kind": "resolve_claim", "hour": hour + 48, "order": order["order"]})
    elif kind == "resolve_claim":
        claim = next(c for c in state["claims"] if c["order"] == event["order"])
        account.execute("resolve_claim", {"id": event["order"], "claim_id": claim["id"],
            "settlement_id": claim["id"] + ":settle", "resolution": "pay"}, hour)
        row = next(c for c in account.export()["ledger"]["prospective_claims"] if c["id"] == claim["id"])
        claim["paid"], claim["resolution"] = int(row["paid"]), row["state"]
        if state["deferred_for_obligations"] and not account.snapshot()["summary"]["payables"] and hour < 360 * 24:
            state["deferred_for_obligations"] = False
            _schedule(state, {"kind": "decision", "hour": hour, "cycle": hour // 720})
    elif kind == "year_close":
        _tax(account, state, "year-close", hour)
        _cost(account, state, "year-close-marker", 0, hour, "calendar")
        state["year_summary"] = copy.deepcopy(account.snapshot()["summary"])
    elif kind == "settlement_close":
        _tax(account, state, "settlement-close", hour)
        _cost(account, state, "settlement-close-marker", 0, hour, "calendar")
        state["complete"] = True
    else: raise ValueError("UNREGISTERED_OPERATING_EVENT")


def operate_case(output, case_id, *, max_events=None):
    source, reg, freeze_record = check_source(output)
    case = next((c for c in reg["cases"] if c["id"] == case_id), None)
    if case is None: raise ValueError("UNREGISTERED_CASE")
    folder = Path(output).resolve() / "cases" / case_id
    folder.mkdir(parents=True, exist_ok=True)
    rule = make_rule(case["seed"], case["world"], technical=reg["technical"], cost_surcharge=reg["cost_surcharge_microUSD_per_buyer"])
    manifest_path = folder / "MANIFEST.json"
    if manifest_path.exists():
        manifest = strict_json(manifest_path.read_bytes())
        if manifest.get("rule") != rule: raise ValueError("EXACT_CASE_RULE_CHANGED")
    else:
        manifest = prepare_manifest(source, f"omega_savings/deliveries/{case_id}", rule=rule)
        save(manifest_path, manifest)
    checkpoint = folder / "private" / "STATE.json"
    started = time.perf_counter(); cpu_start = time.process_time()
    with JournalAccount(source, manifest, folder / "private/account.sqlite", opening=OPENING,
                        working=0, contract="omega-saving-contracts-665b:" + case_id) as account:
        state = account.verify_checkpoint(strict_json(checkpoint.read_bytes())) if checkpoint.exists() else _initial(case, reg)
        steps = 0
        while state["pending"] is not None or state["queue"]:
            if max_events is not None and steps >= max_events: break
            if state["pending"] is None:
                event = state["queue"].pop(0)
                state["pending"] = _prepare_intent(account, state, event, rule, reg)
                save(checkpoint, account.seal_checkpoint(state))
            intent = copy.deepcopy(state["pending"])
            _apply_intent(account, state, intent, source, manifest, rule, reg)
            state["pending"] = None; state["processed"] += 1; steps += 1
            save(checkpoint, account.seal_checkpoint(state))
        public = account.export()
        audit = account.audit()
        if not audit["accepted"]: raise ValueError("NATIVE_AUDIT_REJECTED")
        if state["complete"]:
            result = result_from(state, public, reg, freeze_record)
            result["execution_telemetry"] = {"wall_seconds_this_invocation": time.perf_counter() - started,
                "cpu_seconds_this_invocation": time.process_time() - cpu_start,
                "peak_rss_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "actual_model_host_bill_microUSD": None}
            save(folder / "RESULT.json", result)
            save(folder / "OPERATING.json", state)
            with gzip.open(folder / "ACCOUNT.json.gz", "wb") as stream: stream.write(canonical(public))
            save(folder / "AUDIT.json", audit)
            return result
        save(folder / "PAUSED.json", {"case": case_id, "processed": state["processed"], "complete": False,
            "native_sequence": len(public["ledger"]["actions"]), "audit_accepted": True})
        return {"case_id": case_id, "complete": False}


def result_from(state, public, reg, frozen):
    tape = public["ledger"]
    year = state["year_summary"]
    year_prefix = [a for a in tape["actions"] if a["day"] < YEAR_HOURS]
    if not year_prefix or year_prefix[-1]["after"] != year:
        raise ValueError("YEAR_SUMMARY_MUST_MATCH_COMPLETE_OPERATING_PREFIX")
    settled = tape["summary"]
    released = [o for o in state["orders"] if o.get("native_outcome") == "release"]
    within = [o for o in released if o["due"] < YEAR_HOURS]
    costs = defaultdict(int)
    for c in state["costs"]:
        if c["hour"] < YEAR_HOURS and c["category"] != "complete_delivery": costs[c["category"]] += c["amount"]
    for o in state["orders"]:
        if o["hour"] < YEAR_HOURS:
            for k, value in o["cost_categories"].items(): costs[k] += value
    for c in state["funded"]:
        if c["hour"] < YEAR_HOURS: costs[c["category"]] += c["amount"]
    if sum(costs.values()) != year["expenses"]: raise ValueError("COMPLETE_COST_RECONCILIATION_FAILED")
    expanded = any(c["units"] > 20 for c in state["campaigns"].values())
    earned_campaign = sum(c["amount"] for c in state["funded"] if c["category"] == "acquisition" and c["funding"] == "EARNED")
    earned_expansion_receipts = [{"id": c["id"], "units": state["campaigns"][c["id"]]["units"],
        "amount_microUSD": c["amount"], "hour": c["hour"]} for c in state["funded"]
        if c["category"] == "acquisition" and c["funding"] == "EARNED" and state["campaigns"][c["id"]]["units"] > 20]
    total_tax = sum(t["expense"] for t in state["taxes"] if t["hour"] < YEAR_HOURS)
    return {"schema": "omega-savings/result/v1", "case_id": state["case"]["id"], "complete": state["complete"],
        "role": reg["role"], "source_sha256": frozen["sha256"], "registration_sha256": digest(reg),
        "account_config": tape["config"], "account_actions_sha256": tape["actions_sha256"],
        "primary_seed_microUSD": OPENING, "year_hours": [0, YEAR_HOURS], "settlement_end_hour": reg["settlement_end_hour"],
        "annual_native_observer": trailing_profit(tape, operating_end_hour=YEAR_HOURS, operating_complete=True),
        "year": year, "settlement": settled, "annual_cost_categories": dict(costs),
        "tax": {"expense_microUSD": total_tax, "cash_payment_microUSD": sum(t["cash_payment"] for t in state["taxes"] if t["hour"] < YEAR_HOURS),
                "unpaid_reserve_microUSD": sum(t["reserve_unpaid"] for t in state["taxes"] if t["hour"] < YEAR_HOURS), "schedule": reg["tax_policy"]},
        "contacts_purchased": sum(c["units"] for c in state["campaigns"].values()),
        "fresh_contacts": sum(c.get("exposure", {}).get("fresh", 0) for c in state["campaigns"].values()),
        "accepted_collected_units": sum(o["units"] for o in within), "native_cohort_orders": len(within),
        "refund_or_default_units": sum(o["units"] for o in state["orders"] if o.get("native_outcome") == "refund"),
        "postcollection_dispute_units": sum(o["units"] for o in state["orders"] if o.get("status") == "late_claim" and o.get("native_outcome") == "release"),
        "postcollection_claims": state["claims"],
        "correction_events": len(state["corrections"]), "capability": state["capability"],
        "reach_expanded": expanded, "funded_expansion": bool(earned_expansion_receipts),
        "earned_expansion_receipts": earned_expansion_receipts, "earned_acquisition_microUSD": earned_campaign,
        "commerce": "CONDITIONAL_PROFITABLE" if year["profit"] > 0 and within else "NOT_PROFITABLE_IN_THIS_WORLD",
        "buyer_capability": "ACTUAL_VERIFIED_NUMERICAL_PACKAGES" if within else "NO_COLLECTED_DELIVERY",
        "invention_advantage": "NOT_ESTABLISHED_KNOWN_METHODS_STRONG_ORDINARY_CONTROL",
        "three_billion": year["profit"] >= 3_000_000_000 * USD,
        "human_involvement": {"actual_internal_minutes": 0, "modeled_internal_minutes": 0,
            "necessary_unexecuted": "Real installation/customer validation/market evidence not performed; unknown, not assumed zero.",
            "buyer_effort": "Explicit separate opportunity-cost terms in world profiles", "optional_founder_services": 0},
        "financial_scope": "Native complete-cost conditional simulation; not observed customers, cloud bills, forecast, public release or global optimum."}


def audit_case(output, case_id):
    source, reg, frozen = check_source(output)
    folder = Path(output).resolve() / "cases" / case_id
    manifest = strict_json((folder / "MANIFEST.json").read_bytes())
    state = strict_json((folder / "OPERATING.json").read_bytes())
    result = strict_json((folder / "RESULT.json").read_bytes())
    with gzip.open(folder / "ACCOUNT.json.gz", "rb") as stream: public = strict_json(stream.read())
    checked = audit_journal(public, root=source, manifest=manifest)
    rebuilt = result_from(state, public, reg, frozen)
    if {k: v for k, v in result.items() if k != "execution_telemetry"} != rebuilt:
        raise ValueError("NATIVE_RESULT_OR_COSTS_CHANGED")
    expected_case = next(c for c in reg["cases"] if c["id"] == case_id)
    if state["case"] != expected_case or manifest["rule"] != make_rule(expected_case["seed"], expected_case["world"], technical=reg["technical"], cost_surcharge=reg["cost_surcharge_microUSD_per_buyer"]):
        raise ValueError("REGISTERED_CASE_CHANGED")
    from .audit import operating_audit
    operating = operating_audit(state, public, manifest["rule"], reg, root=source, manifest=manifest)
    return {"case_id": case_id, "accepted": checked["accepted"] and operating["accepted"],
        "source_sha256": frozen["sha256"], "native_actions_sha256": public["ledger"]["actions_sha256"],
        "operating": operating}


def summarize(output):
    output = Path(output)
    reg = strict_json((output / "REGISTRATION.json").read_bytes())
    rows, missing = [], []
    for c in reg["cases"]:
        p = output / "cases" / c["id"] / "RESULT.json"
        if not p.exists(): missing.append(c["id"]); continue
        r = strict_json(p.read_bytes())
        rows.append({"case_id": c["id"], "world": c["world"], "policy": c["policy"], "seed": c["seed"],
            "profit_microUSD": r["year"]["profit"], "revenue_microUSD": r["year"]["revenue"],
            "cash_microUSD": r["year"]["cash"], "available_microUSD": r["year"]["available"],
            "cost_microUSD": r["year"]["expenses"], "accepted_units": r["accepted_collected_units"],
            "funded_expansion": r["funded_expansion"], "earned_acquisition_microUSD": r["earned_acquisition_microUSD"],
            "three_billion": r["three_billion"]})
    summary = {"schema": "omega-savings/comparison/v1", "complete": not missing, "registered": len(reg["cases"]),
        "completed": len(rows), "missing": missing, "primary": reg["primary"], "rows": rows,
        "distribution_note": "Unweighted scenario grid; no invented probabilities or selected favorable seed. Accounts independent, never pooled."}
    save(output / "COMPARISON.json", summary)
    save(output / "PROGRESS.json", {"complete": not missing, "completed": [r["case_id"] for r in rows], "registered_cases": len(reg["cases"])})
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("register", "operate", "audit", "summary"))
    p.add_argument("--output", required=True); p.add_argument("--root", default=str(ROOT))
    p.add_argument("--case"); p.add_argument("--role", default="confirmation")
    p.add_argument("--seeds", default="701,702"); p.add_argument("--worlds"); p.add_argument("--policies")
    p.add_argument("--fixed-fraction", type=int, default=1500); p.add_argument("--max-events", type=int)
    p.add_argument("--cadence-days", type=int, default=14)
    p.add_argument("--cost-surcharge", type=int, default=0, help="Explicit additional microUSD operating cost per buyer")
    p.add_argument("--variant", default="primary")
    args = p.parse_args()
    if args.action == "register":
        reg = registration(role=args.role, seeds=tuple(map(int, args.seeds.split(","))),
            worlds=args.worlds.split(",") if args.worlds else None,
            policies=args.policies.split(",") if args.policies else None, fixed_fraction=args.fixed_fraction, cadence_days=args.cadence_days, cost_surcharge=args.cost_surcharge, variant=args.variant)
        result = freeze(Path(args.root).resolve(), args.output, reg)
    elif args.action == "operate":
        if not args.case: raise ValueError("EXPLICIT_REGISTERED_CASE_REQUIRED")
        result = operate_case(args.output, args.case, max_events=args.max_events)
    elif args.action == "audit":
        if not args.case: raise ValueError("EXPLICIT_REGISTERED_CASE_REQUIRED")
        result = audit_case(args.output, args.case)
    else: result = summarize(args.output)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__": main()
