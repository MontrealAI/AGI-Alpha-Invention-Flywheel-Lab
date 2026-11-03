"""Independent operating replay over the existing native financial history.

This is not another ledger: every cash observation comes from a prefix of the
native action tape, which ``audit_journal`` must independently replay first.
The operating audit derives demand, buyer selection, policy observations and
orders afresh. Rehashing a fabricated operating summary is not qualification.
No confirmation worlds are run or tuned by this module.
"""
from __future__ import annotations

import copy
from collections import defaultdict
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json
from .policy import POLICIES, decide, empty_stats
from .service import (NATIVE_FEE, check_delivery, contract_for as bound_contract,
                      delivery, terms_for, totals,
                      validate_contract)
from .world import (CHANNELS, USD, WORLDS, YEAR_HOURS, ContactRights, channel_quote,
                    contract_for, make_rule, settlement_outcome, validate_rule)

SCHEMA = "omega-savings/operating-audit/v1"
OPENING = 100_000 * USD
COST_CATEGORIES = {
    "production", "verification", "onboarding", "local_self_support",
    "storage_delivery", "maintenance_obligation", "qualification",
    "failure_retry_envelope", "payment_processing", "unpriced_cost_sensitivity",
}


def _require(condition, message):
    if not condition:
        raise ValueError("OPERATING_AUDIT:" + message)


def _same(actual, expected, message):
    # Canonical bytes distinguish booleans from integers, reject NaN, and make
    # extraneous fields observable. Python equality alone does not do this.
    _require(canonical(actual) == canonical(expected), message)


class _NativeEvidence:
    """Consume native effects in order; never recompute a cash balance."""

    def __init__(self, record):
        self.record, self.tape = record, record["ledger"]
        self.actions = self.tape["actions"]
        self.cursor = 0
        self.spends = {}
        for entry in record["connected_journal"]["entries"]:
            request = entry["request"]
            if request["operation"] == "spend":
                _require(entry["status"] == "COMPLETE", "UNCOMPLETED_RESOURCE")
                ident = request["id"]
                _require(ident not in self.spends, "DUPLICATE_RESOURCE")
                self.spends[ident] = entry
        self.used_spends = set()

    @property
    def summary(self):
        if self.cursor:
            return self.actions[self.cursor - 1]["after"]
        return self.actions[0]["before"] if self.actions else self.tape["summary"]

    def take(self, op, args, hour):
        _require(self.cursor < len(self.actions), "MISSING_NATIVE_ACTION:" + op)
        action = self.actions[self.cursor]
        _same({k: action[k] for k in ("seq", "day", "op", "args")},
              {"seq": self.cursor, "day": hour, "op": op, "args": args},
              "NATIVE_EFFECT_OR_ORDER_CHANGED:" + op)
        _same(action["before"], self.summary, "NATIVE_PREFIX_DISCONTINUITY")
        self.cursor += 1
        return action

    def spend(self, ident, kind, amount, hour, work, expected_net):
        _require(ident in self.spends and ident not in self.used_spends,
                 "MISSING_OR_DUPLICATE_RESOURCE:" + ident)
        entry = self.spends[ident]
        request = {"operation": "spend", "id": ident, "kind": kind,
                   "amount": amount, "day": hour, "work": work,
                   "expected_net": expected_net, "allow_seed": True}
        _same(entry["request"], request, "RESOURCE_REQUEST_CHANGED:" + ident)
        before = copy.deepcopy(self.summary)
        _require(before["available"] >= amount and not before["investmentStopped"],
                 "PRESENT_CASH_CANNOT_FUND_RESOURCE")
        earned = expected_net > 0 and min(before["available"], before["unrestrictedEarned"]) >= amount
        funding = "EARNED" if earned else "SEED"
        _same(entry["funding"], funding, "FUNDING_CLASS_CHANGED")
        if earned:
            plan = entry["plan"]
            proof = self.record["action_proofs"][plan["plan_id"]]["body"]
            self.take("reserve", {"id": plan["plan_id"], "amount": amount,
                "expected_net_value": expected_net, "intent_sha256": digest(proof)}, hour)
            self.take("finish", {"id": plan["plan_id"], "amount": amount,
                "artifact_sha256": digest({"work_artifact_sha256": digest(work),
                    "obligation_receipt_sha256": digest(entry["obligation_receipt"])})}, hour)
        else:
            seed_id = "connected014-seed-" + digest({"request": request,
                "source_sha256": self.record["connected_journal"]["source"]["sha256"]})[:32]
            self.take("cost", {"id": seed_id, "amount": amount}, hour)
        _same(entry["receipt"]["native_event_sequence"], self.cursor - 1,
              "RESOURCE_RECEIPT_PREFIX_CHANGED")
        _require(self.summary["expenses"] - before["expenses"] == amount
                 and self.summary["expensePaid"] - before["expensePaid"] == amount,
                 "RESOURCE_NOT_FULLY_INCURRED_AND_PAID")
        self.used_spends.add(ident)
        return funding


class _OperatingReplay:
    def __init__(self, supplied, record, rule, registration, root, manifest):
        self.supplied, self.record = supplied, record
        self.rule, self.reg = rule, registration
        self.native = _NativeEvidence(record)
        self.root = Path(root).resolve() if root is not None else None
        self.manifest = manifest
        self.matured, self.order_terms = set(), {}
        self.tax_assessed = 0
        self.artifacts_checked = 0
        self.s = {
            "schema": "omega-savings/native-case/v1", "case": copy.deepcopy(supplied["case"]),
            "built": False, "capability": 0, "stats": empty_stats(), "qualified_advanced": 0,
            "campaign_count": 0, "last_campaign_units": 0, "rights": None,
            "queue": [], "next_serial": 0, "next_order": 0, "pending": None,
            "decisions": [], "campaigns": {}, "lots": [], "orders": [], "costs": [],
            "taxes": [], "funded": [], "corrections": [], "claims": [], "processed": 0,
            "complete": False, "year_summary": None, "deferred_for_obligations": False, "human_minutes_actual": 0,
            "human_minutes_modeled_internal": 0, "founder_services": 0,
        }
        for day in range(0, 365, registration["decision_cadence_days"]):
            self.schedule({"kind": "decision", "hour": day * 24, "cycle": day // 30})
        self.schedule({"kind": "year_close", "hour": YEAR_HOURS - 1})
        self.schedule({"kind": "settlement_close", "hour": registration["settlement_end_hour"]})

    def schedule(self, event):
        row = copy.deepcopy(event)
        row["serial"] = self.s["next_serial"]
        self.s["next_serial"] += 1
        self.s["queue"].append(row)
        self.s["queue"].sort(key=lambda e: (e["hour"], e["serial"]))

    def advance(self, hour):
        # Native exports sort prospective_orders lexicographically by order_id.
        # This differs from numeric creation order once order-10 exists.
        # Advancing time is
        # permitted to release eligible protection, never to create income.
        for order in sorted(self.s["orders"], key=lambda row: row["order"]):
            ident = order["order"]
            terms = self.order_terms[ident]
            if (order.get("native_outcome") == "release" and ident not in self.matured
                    and hour > terms["maturity_day"]):
                before = copy.deepcopy(self.native.summary)
                self.native.take("mature", {"id": ident,
                    "event_id": "maturity:" + ident + ":" + digest(terms)[:20]}, hour)
                after = self.native.summary
                _require(all(before[k] == after[k] for k in ("cash", "revenue", "profit", "expenses")),
                         "MATURITY_CREATED_INCOME_OR_COST")
                self.matured.add(ident)

    def cost(self, ident, amount, hour, category):
        before = self.native.summary
        _require(before["available"] >= amount, "UNFUNDED_CURRENT_EXPENSE")
        action = self.native.take("cost", {"id": ident, "amount": amount}, hour)
        _require(action["after"]["expenses"] - action["before"]["expenses"] == amount
                 and action["after"]["expensePaid"] - action["before"]["expensePaid"] == amount,
                 "EXPENSE_NOT_FULLY_PAID")
        self.s["costs"].append({"id": ident, "amount": amount, "hour": hour, "category": category})
        return action

    def tax(self, ident, hour):
        # Assess increases in the positive pretax high-water mark. Previously
        # paid tax is added back exactly once; a later loss gives no refund.
        pretax = self.native.summary["profit"] + self.tax_assessed
        levy = max(0, max(0, pretax) // 4 - self.tax_assessed)
        if levy:
            action = self.cost("tax:" + ident, levy, hour, "modeled_tax")
            paid = action["after"]["expensePaid"] - action["before"]["expensePaid"]
            self.s["taxes"].append({"id": "tax:" + ident, "hour": hour,
                "expense": levy, "cash_payment": paid, "reserve_unpaid": levy - paid})
            _require(paid == levy, "IMMEDIATE_TAX_SCHEDULE_NOT_PAID")
            self.tax_assessed += levy

    def rights(self):
        return ContactRights(self.rule["seed"], self.rule["world"], self.s["rights"])

    def observation(self, hour):
        summary, rights = self.native.summary, self.rights()
        return {"hour": hour, "available": summary["available"],
            "unrestricted_earned": summary["unrestrictedEarned"], "payables": summary["payables"], "built": self.s["built"],
            "capability": self.s["capability"], "channel_stats": copy.deepcopy(self.s["stats"]),
            "campaign_count": self.s["campaign_count"], "last_campaign_units": self.s["last_campaign_units"],
            "qualified_advanced": self.s["qualified_advanced"], "cash_profit": summary["profit"],
            "fixed_fraction_bps": self.reg["fixed_fraction_bps"],
            "current_quotes": {c: channel_quote(c, 20, rights.state["cursors"][c],
                world=self.rule["world"]) for c in CHANNELS}}

    def decision(self, event):
        hour, s = event["hour"], self.s
        observation = self.observation(hour)
        action = decide(s["case"]["policy"], observation)
        if action["action"] == "campaign":
            rights = self.rights()
            fraction = observation["fixed_fraction_bps"] if s["case"]["policy"] == "fixed_split" else 2000
            while True:
                quote = channel_quote(action["channel"], action["units"],
                    rights.state["cursors"][action["channel"]], world=self.rule["world"])
                budget = observation["available"] if action["units"] <= 20 else observation["available"] * fraction // 10000
                if quote["price_microUSD"] + 40 * USD <= budget:
                    break
                if action["units"] <= 1:
                    action = {"action": "wait", "reason": "current_cash_cannot_buy_supplier_quote"}
                    break
                action["units"] //= 2
            if action["action"] == "campaign":
                history = observation["channel_stats"][action["channel"]]
                if history["purchased"] and action["reason"] != "costed_information_and_voluntary_sales_pilot":
                    while True:
                        forecast = (max(0, history["net_contribution"] + history["spent"]) * action["units"]
                            // history["purchased"] - quote["price_microUSD"] - 40 * USD)
                        if forecast > 0:
                            break
                        if action["units"] <= 20:
                            action = {"action": "wait", "reason": "quoted_marginal_acquisition_unprofitable"}
                            break
                        action["units"] //= 2
                        quote = channel_quote(action["channel"], action["units"],
                            rights.state["cursors"][action["channel"]], world=self.rule["world"])
                    if action["action"] == "campaign":
                        action["expected_net"] = forecast
                if action["action"] == "campaign":
                    action["quote"] = quote
        intent = {"event": event, "native_sequence_before": self.native.cursor,
                  "observation": observation, "action": action}
        index = len(s["decisions"])
        _require(index < len(self.supplied["decisions"]), "MISSING_REGISTERED_DECISION")
        _same(self.supplied["decisions"][index], intent,
              "DECISION_OR_HISTORICAL_INFORMATION_CHANGED:" + str(index))
        s["decisions"].append(copy.deepcopy(intent))
        if action["action"] == "wait" and action["reason"] == "unresolved_native_payables":
            s["deferred_for_obligations"] = True
        elif action["action"] in {"construct", "campaign"}:
            s["deferred_for_obligations"] = False
        if action["action"] == "construct":
            ident = "construct:c" + str(event["cycle"]) + ":a" + str(action["capability"])
            funding = self.native.spend(ident, "known_method_package", action["cost"], hour,
                {"capability": action["capability"], "independent_numerical_tests": True}, action["expected_net"])
            s["funded"].append({"id": ident, "category": "capability", "amount": action["cost"],
                                "hour": hour, "funding": funding})
            s["built"], s["capability"] = True, action["capability"]
            self.schedule({"kind": "decision", "hour": hour, "cycle": event["cycle"]})
        elif action["action"] == "campaign":
            ident = "campaign-" + str(s["campaign_count"])
            quote = action["quote"]
            self.cost("operating:" + ident, 40 * USD, hour, "subscription_infrastructure_admin_envelope")
            funding = self.native.spend(ident, "paid_contact_rights", quote["price_microUSD"], hour,
                {"quote": quote, "policy": s["case"]["policy"], "expiry_hours": quote["expiry_after_hours"]},
                action["expected_net"])
            rights = self.rights()
            bought = rights.purchase(ident, action["channel"], action["units"], hour,
                invoice=quote, paid_microUSD=quote["price_microUSD"])
            s["rights"] = rights.export()
            s["campaigns"][ident] = {"channel": action["channel"], "units": action["units"],
                "price_index": action["price_index"], "cycle": event["cycle"], "capability": s["capability"],
                "paid": quote["price_microUSD"], "hour": hour, "expiry": bought["expiry"]}
            stats = s["stats"][action["channel"]]
            expense = quote["price_microUSD"] + 40 * USD
            stats["spent"] += expense
            stats["net_contribution"] -= expense
            stats["campaigns"] += 1
            stats["purchased"] += action["units"]
            price_stats = stats["by_price"].setdefault(str(action["price_index"]), {"net": 0, "contacts": 0})
            price_stats["net"] -= expense
            price_stats["contacts"] += action["units"]
            s["funded"].append({"id": ident, "category": "acquisition", "amount": quote["price_microUSD"],
                                "hour": hour, "funding": funding})
            s["campaign_count"] += 1
            s["last_campaign_units"] = action["units"]
            self.schedule({"kind": "expose", "hour": bought["activation"], "campaign": ident})

    def expose(self, event):
        s, hour = self.s, event["hour"]
        campaign = s["campaigns"][event["campaign"]]
        rights = self.rights()
        exposure = rights.expose(event["campaign"], hour, self.rule, campaign=campaign["cycle"],
            capability=campaign["capability"], price_index=campaign["price_index"])
        s["rights"] = rights.export()
        campaign["exposure"] = copy.deepcopy(exposure)
        stats = s["stats"][campaign["channel"]]
        stats["contacted"] += exposure["fresh"]
        s["qualified_advanced"] += exposure.get("qualified_advanced", 0)
        for group in exposure["groups"]:
            self.schedule({"kind": "fulfill", "hour": hour, "campaign": event["campaign"],
                "cycle": campaign["cycle"], "profile": group["profile"], "members": group["members"],
                "price_index": campaign["price_index"], "capability": campaign["capability"],
                "expiry": campaign["expiry"]})

    def artifact(self, job_id):
        _require(self.root is not None and self.manifest is not None,
                 "ACTUAL_ARTIFACT_CONTEXT_REQUIRED")
        artifact = delivery(self.root, self.manifest, job_id)
        accepted = check_delivery(self.root, self.manifest, job_id, artifact)["accepted"]
        self.artifacts_checked += 1
        return artifact, accepted

    def fulfill(self, event):
        s, hour = self.s, event["hour"]
        if hour >= event["expiry"] or hour >= YEAR_HOURS:
            s["lots"].append({"hour": hour, "campaign": event["campaign"],
                              "expired_units": len(event["members"]), "selected_units": 0})
            return
        prefix = f"c{event['cycle']}t{event['profile']}p{event['price_index']}a{event['capability']}"
        probe = validate_contract(contract_for(self.rule, prefix + f"u1l{s['next_order']}"))
        backing = probe["price_microUSD"] + NATIVE_FEE + sum(probe["costs_microUSD"].values())
        available = self.native.summary["available"]
        selected = min(len(event["members"]), available // backing)
        # Hidden settlement values are queried only after the quantity AND
        # deterministic selected member prefix have been fixed from current cash.
        members = event["members"][:selected]
        partitions = defaultdict(list)
        for member in members:
            partitions[settlement_outcome(self.rule, member)].append(member)
        parts = []
        for offset, ((status, repair), group) in enumerate(sorted(partitions.items())):
            seq = s["next_order"] + offset
            parts.append({"job": prefix + f"u{len(group)}l{seq}", "order": "order-" + str(seq),
                "units": len(group), "status": status, "repair": repair, "members_sha256": digest(group)})
        lot = {"hour": hour, "campaign": event["campaign"], "profile": event["profile"],
            "selected_units": selected, "remaining_units": len(event["members"]) - selected,
            "unit_backing": backing, "available_before": available,
            "members_sha256": digest(members), "parts": copy.deepcopy(parts)}
        s["lots"].append(lot)
        for part in parts:
            contract = validate_contract(contract_for(self.rule, part["job"]))
            _same(sorted(contract["costs_microUSD"]), sorted(COST_CATEGORIES), "INCOMPLETE_COST_CATEGORIES")
            t, order = totals(contract), part["order"]
            self.cost("savings:" + order + ":complete_delivery", t["service_cost_microUSD"], hour, "complete_delivery")
            self.native.take("wallet", {"buyer": order + "-buyers", "amount": t["buyer_budget_microUSD"]}, hour)
            terms = terms_for(self.manifest, order, contract, hour)
            self.order_terms[order] = terms
            self.native.take("register_terms", {"id": order + ":terms", "terms": terms}, hour)
            self.native.take("offer", {"id": order, "buyer": order + "-buyers", "price": t["price_microUSD"],
                "job_id": part["job"], "deadline": hour + contract["deadline_hours"], "terms_id": order + ":terms"}, hour)
            for action in ("consent", "fund"):
                self.native.take("event", {"id": order, "action": action, "event_id": order + ":" + action}, hour)
            artifact, accepted = self.artifact(part["job"])
            if part["repair"]:
                from .verify import verify
                job, _ = bound_contract(self.root, self.manifest, part["job"])
                correction = strict_json((self.root / (job["output"] + ".correction.json")).read_bytes())
                _same(sorted(correction), sorted({"order", "failed_result", "failed_result_sha256", "rejected",
                    "repaired_result_sha256", "scope", "cost"}), "CORRECTION_RECEIPT_FIELDS_CHANGED")
                corrupt = correction["failed_result"]
                rejected = not verify(contract["request"], corrupt)["accepted"]
                _require(rejected, "INJECTED_ERROR_NOT_DETECTED")
                repaired_fault = copy.deepcopy(artifact["result"])
                repaired_fault["solutions"][0][0] += 1.0
                def semantic(value):
                    if isinstance(value, dict):
                        return {k: semantic(v) for k, v in value.items() if not k.endswith("wall_seconds")}
                    if isinstance(value, list):
                        return [semantic(v) for v in value]
                    return value
                _same(semantic(corrupt), semantic(repaired_fault), "DECLARED_INJECTED_FAULT_CHANGED")
                expected_correction = {"order": order, "failed_result_sha256": digest(corrupt),
                    "rejected": True, "repaired_result_sha256": digest(artifact["result"]),
                    "scope": "Injected output fault; independent rejection and actual known-constructor rerun, not naturally observed failure or novel repair discovery.",
                    "cost": contract["costs_microUSD"]["failure_retry_envelope"] * part["units"]}
                _same({k: v for k, v in correction.items() if k != "failed_result"}, expected_correction,
                      "CORRECTION_RECEIPT_OR_COST_CHANGED")
                s["corrections"].append(expected_correction)
            if not accepted:
                self.native.take("event", {"id": order, "action": "refund", "event_id": order + ":refund"}, hour)
                part["status"] = "verification_rejected"
            elif part["status"] != "refund":
                self.native.take("event", {"id": order, "action": "prepare", "event_id": order + ":prepare",
                    "artifact_sha256": digest(artifact)}, hour)
            due = hour + contract["collection_delay_hours"]
            s["orders"].append({**part, "campaign": event["campaign"], "profile": event["profile"],
                "hour": hour, "due": due, "price": t["price_microUSD"], "service_cost": t["service_cost_microUSD"],
                "budget": t["buyer_budget_microUSD"],
                "cost_categories": {k: v * part["units"] for k, v in contract["costs_microUSD"].items()},
                "mathematical_and_work_promise_accepted": accepted, "settled": False})
            stats = s["stats"][s["campaigns"][event["campaign"]]["channel"]]
            stats["net_contribution"] -= t["service_cost_microUSD"]
            stats["by_price"][str(event["price_index"])]["net"] -= t["service_cost_microUSD"]
            self.schedule({"kind": "settle", "hour": due, "order": order})
        s["next_order"] += len(parts)
        if selected < len(event["members"]):
            later = {k: copy.deepcopy(v) for k, v in event.items() if k != "serial"}
            later["members"] = event["members"][selected:]
            later["hour"] = hour + max(24, self.rule["world"]["collection_hours"])
            self.schedule(later)

    def settle(self, event):
        s, hour = self.s, event["hour"]
        order = next(o for o in s["orders"] if o["order"] == event["order"])
        action = "release" if order["status"] in {"collect", "late_claim"} and order["mathematical_and_work_promise_accepted"] else "refund"
        if order["status"] != "verification_rejected":
            self.native.take("event", {"id": order["order"], "action": action,
                "event_id": order["order"] + ":" + action}, hour)
        order["settled"], order["native_outcome"] = True, action
        if action == "release":
            campaign = s["campaigns"][order["campaign"]]
            stats = s["stats"][campaign["channel"]]
            stats["settled_units"] += order["units"]
            stats["net_contribution"] += order["price"]
            stats["by_price"][str(campaign["price_index"])]["net"] += order["price"]
            if order["status"] == "late_claim":
                self.schedule({"kind": "claim", "hour": hour + 168, "order": order["order"]})
        self.tax(order["order"], hour)

    def claim(self, event):
        order = next(o for o in self.s["orders"] if o["order"] == event["order"])
        ident, hour = order["order"] + ":compatibility-dispute", event["hour"]
        value = order["price"] // order["units"] // 10 * order["units"]
        action = self.native.take("claim", {"id": order["order"], "claim_id": ident,
            "amount": value, "kind": "disputed"}, hour)
        _require(action["after"]["expenses"] - action["before"]["expenses"] == value,
                 "POSTCOLLECTION_CLAIM_EXPENSE_OMITTED")
        _require(action["after"]["expensePaid"] == action["before"]["expensePaid"],
                 "CLAIM_ASSESSMENT_CONFUSED_WITH_PAYMENT")
        self.s["costs"].append({"id": ident, "amount": value, "hour": hour,
                                "category": "postcollection_disputes"})
        self.s["claims"].append({"id": ident, "order": order["order"], "amount": value,
            "hour": hour, "paid": 0, "resolution": None})
        campaign = self.s["campaigns"][order["campaign"]]
        stats = self.s["stats"][campaign["channel"]]
        stats["net_contribution"] -= value
        stats["by_price"][str(campaign["price_index"])]["net"] -= value
        self.schedule({"kind": "resolve_claim", "hour": hour + 48, "order": order["order"]})

    def resolve_claim(self, event):
        claim = next(c for c in self.s["claims"] if c["order"] == event["order"])
        action = self.native.take("resolve_claim", {"id": event["order"], "claim_id": claim["id"],
            "settlement_id": claim["id"] + ":settle", "resolution": "pay"}, event["hour"])
        _require(action["after"]["expenses"] == action["before"]["expenses"],
                 "CLAIM_PAYMENT_DOUBLE_COUNTED_AS_EXPENSE")
        paid = action["after"]["expensePaid"] - action["before"]["expensePaid"]
        _require(0 <= paid <= claim["amount"], "CLAIM_PAYMENT_OUT_OF_RANGE")
        claim["paid"], claim["resolution"] = paid, "paid" if paid == claim["amount"] else "partially_paid"
        native_claim = next(c for c in self.native.tape["prospective_claims"] if c["id"] == claim["id"])
        _same({"paid": int(native_claim["paid"]), "state": native_claim["state"]},
              {"paid": paid, "state": claim["resolution"]}, "NATIVE_CLAIM_SETTLEMENT_CHANGED")
        if self.s["deferred_for_obligations"] and not self.native.summary["payables"] and event["hour"] < 360 * 24:
            self.s["deferred_for_obligations"] = False
            self.schedule({"kind": "decision", "hour": event["hour"], "cycle": event["hour"] // 720})

    def run(self):
        while self.s["queue"]:
            event = self.s["queue"].pop(0)
            hour, kind = event["hour"], event["kind"]
            self.advance(hour)
            if kind == "decision":
                self.decision(event)
            elif kind == "expose":
                self.expose(event)
            elif kind == "fulfill":
                self.fulfill(event)
            elif kind == "settle":
                self.settle(event)
            elif kind == "claim":
                self.claim(event)
            elif kind == "resolve_claim":
                self.resolve_claim(event)
            elif kind == "year_close":
                self.tax("year-close", hour)
                self.cost("year-close-marker", 0, hour, "calendar")
                self.s["year_summary"] = copy.deepcopy(self.native.summary)
            elif kind == "settlement_close":
                self.tax("settlement-close", hour)
                self.cost("settlement-close-marker", 0, hour, "calendar")
                self.s["complete"] = True
            else:
                raise ValueError("OPERATING_AUDIT:UNREGISTERED_EVENT")
            self.s["processed"] += 1
        _require(self.native.cursor == len(self.native.actions), "UNEXPLAINED_NATIVE_EFFECTS")
        _same(sorted(self.native.used_spends), sorted(self.native.spends), "UNEXPLAINED_RESOURCE_SPEND")
        for field, expected in self.s.items():
            _same(self.supplied.get(field), expected, "OPERATING_FIELD_CHANGED:" + field)
        _same(sorted(self.supplied), sorted(self.s), "UNREGISTERED_OPERATING_FIELDS")
        _same(self.native.summary, self.native.tape["summary"], "FINAL_NATIVE_SUMMARY_CHANGED")
        return {"schema": SCHEMA, "accepted": True, "case_id": self.s["case"]["id"],
            "native_actions_covered": self.native.cursor, "operating_events_replayed": self.s["processed"],
            "decisions_replayed": len(self.s["decisions"]), "campaigns_replayed": len(self.s["campaigns"]),
            "actual_artifacts_rechecked": self.artifacts_checked, "orders_reconciled": len(self.s["orders"]),
            "tax_assessed_microUSD": self.tax_assessed, "tax_unpaid_reserve_microUSD": 0,
            "operating_hours": [0, YEAR_HOURS], "settlement_end_hour": self.reg["settlement_end_hour"],
            "scope": "Operating replay supplements required independent native audit; conditional authored demand, not observed customers."}


def operating_audit(state, public_account_record, rule, registration, *, root=None, manifest=None):
    """Refuse fabricated history even when an attacker recomputes public hashes.

    ``audit_journal`` is a mandatory companion: it validates native mathematics,
    conservation, protections and resource witnesses. Here native prefix cash is
    consumed as evidence, not reproduced by an alternative financial simulator.
    Complete runs only are accepted; owner recovery uses its signed checkpoint.
    Actual artifacts must be available for every purchased delivery, including
    refunded orders that never reached native prepare.
    """
    _require(isinstance(state, dict) and isinstance(registration, dict), "EXPLICIT_STATE_AND_REGISTRATION")
    _require(registration.get("schema") == "omega-savings/registration/v1", "REGISTRATION_SCHEMA")
    _same(registration.get("opening_microUSD"), OPENING, "EXACT_PRIMARY_OPENING_REQUIRED")
    _same(registration.get("operating_hours"), [0, YEAR_HOURS], "EXACT_TRAILING_YEAR_REQUIRED")
    _same(registration.get("settlement_end_hour"),
          YEAR_HOURS + max(w["collection_hours"] for w in WORLDS.values()) + 720 + 1,
          "SETTLEMENT_HORIZON_CHANGED")
    _require(registration.get("decision_cadence_days") in (7, 14, 30), "REGISTERED_CADENCE_REQUIRED")
    _require(registration.get("accounts_pooled") is False and registration.get("actual_commerce") is False,
             "INDEPENDENT_SIMULATION_ACCOUNT_REQUIRED")
    _require(state.get("complete") is True and state.get("pending") is None and state.get("queue") == [],
             "COMPLETE_SETTLED_OPERATING_RUN_REQUIRED")
    case = state.get("case")
    _require(isinstance(case, dict) and case.get("policy") in POLICIES, "EXACT_REGISTERED_CASE_REQUIRED")
    matches = [c for c in registration["cases"] if c["id"] == case.get("id")]
    _same(matches, [case], "EXACT_UNIQUE_REGISTERED_CASE_REQUIRED")
    validate_rule(rule)
    expected_rule = make_rule(case["seed"], case["world"], technical=registration["technical"],
        cost_surcharge=registration["cost_surcharge_microUSD_per_buyer"])
    _same(rule, expected_rule, "WORLD_OR_BUYER_BUDGET_ASSUMPTIONS_CHANGED")
    tape = public_account_record["ledger"]
    _same(tape["config"]["opening"], OPENING, "NATIVE_OPENING_CHANGED")
    _same(tape["config"]["working"], 0, "HIDDEN_WORKING_CAPITAL_CHANGED")
    _same(tape["config"]["contract"], "omega-saving-contracts-665b:" + case["id"], "ACCOUNT_IDENTITY_CHANGED")
    if root is None:
        root = Path(__file__).resolve().parents[1]
    if manifest is None:
        path = Path(root) / "omega_savings" / "deliveries" / case["id"] / "MANIFEST.json"
        if path.is_file():
            manifest = strict_json(path.read_bytes())
    if manifest is not None:
        _same(manifest.get("rule"), rule, "MANIFEST_RULE_CHANGED")
        _same(digest(manifest), tape["config"]["manifest_sha256"], "MANIFEST_IDENTITY_CHANGED")
    replay = _OperatingReplay(state, public_account_record, rule, registration, root, manifest)
    return replay.run()
