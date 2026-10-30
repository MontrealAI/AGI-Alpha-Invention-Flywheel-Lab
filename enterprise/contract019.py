"""Prospective priced finite-exposure terms with native residual reservations.

This is a simulation contract, not legal finality, insurance placement, or a
claim about counterparty solvency.  It extends PR24's finite-contract state
machine without changing the permanent-contract baseline or old histories.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile

from commercial.ledger import canonical, digest
from commercial.single_writer import SingleWriterExchange, _acquire
from enterprise.contract012 import (
    FINAL_STATE,
    FiniteTapeExchange,
    _terms,
)

SCHEMA = "agi-alpha/capital-recycling019-risk-contract/v1"
RISK_SOURCE_PATHS = (
    "enterprise/contract019.py",
    "enterprise/contract012.py",
    "commercial/ledger.py",
    "commercial/persistence.py",
    "commercial/single_writer.py",
    "commercial/tape_lease.py",
    "experiments/commerce006.py",
    "vendor/alpha_claim/protected_exchange.py",
    "vendor/alpha_claim/contracts.py",
)


def risk_source_hashes(root):
    out = {}
    for name in RISK_SOURCE_PATHS:
        path = Path(root) / name
        if path.is_symlink() or any(part.is_symlink() for part in path.parents):
            raise ValueError("RISK_CONTRACT_SOURCE_SYMLINK")
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def risk_terms(value):
    fields = {
        "premium_per_order", "buyer_friction", "cover_bps", "deductible_bps",
        "exclusion_bps", "payout_gap_bps", "provider_default_severity_bps",
        "correlated_dispute_bps", "residual_ticks",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("EXACT_RISK_TERMS_REQUIRED")
    for key in fields:
        if type(value[key]) is not int or value[key] < 0:
            raise ValueError("NONNEGATIVE_INTEGER_RISK_TERM:" + key)
    for key in fields - {"premium_per_order", "buyer_friction", "residual_ticks"}:
        if value[key] > 10_000:
            raise ValueError("RISK_BASIS_POINTS_REQUIRED:" + key)
    if not 1 <= value["residual_ticks"] <= 87_600:
        raise ValueError("BOUNDED_RESIDUAL_WINDOW_REQUIRED")
    return {
        **copy.deepcopy(value),
        "scope": "Authored prospective simulated terms; no real insurer, legal finality, or solvency claim.",
        "reserve_rule": "Uninsured gaps plus modeled cover default and correlated loss stay natively reserved.",
    }


def residual_cap(tail, terms):
    """Conservative modeled gap; 100% default/correlation leaves full tail."""
    if type(tail) is not int or tail <= 0:
        raise ValueError("POSITIVE_TAIL_REQUIRED")
    base_gap_bps = min(
        10_000,
        terms["deductible_bps"] + terms["exclusion_bps"] + terms["payout_gap_bps"],
    )
    base_gap = (tail * base_gap_bps + 9_999) // 10_000
    covered = (tail * terms["cover_bps"]) // 10_000
    default_gap = (covered * terms["provider_default_severity_bps"] + 9_999) // 10_000
    correlated = (tail * terms["correlated_dispute_bps"] + 9_999) // 10_000
    return min(tail, base_gap + default_gap + correlated)


class RiskFiniteTapeExchange(FiniteTapeExchange):
    def __init__(self, path, *, risk, _contract_already_bound=False, **kwargs):
        self.risk = risk_terms(risk)
        contract = kwargs["contract"]
        if not _contract_already_bound:
            kwargs["contract"] = contract + "/risk019/" + digest(self.risk)
        super().__init__(path, **kwargs)

    def _coverage(self, ident):
        row = self.ex.db.execute(
            "SELECT raw FROM events WHERE id=? AND order_id=?",
            ("risk-cover:" + ident, ident),
        ).fetchone()
        if row is None:
            raise ValueError("PRICED_RISK_COVER_REQUIRED")
        value = json.loads(row["raw"])
        if value.get("risk_terms_sha256") != digest(self.risk):
            raise ValueError("RISK_TERMS_CHANGED")
        return value

    def _bind_cover(self, ident, funding_event_id, event_id, tick):
        if not all(isinstance(x, str) and x for x in (ident, funding_event_id, event_id)):
            raise ValueError("RISK_COVER_ID_REQUIRED")
        if event_id != "risk-cover:" + ident:
            raise ValueError("CANONICAL_RISK_COVER_ID_REQUIRED")
        paid = self.ex.db.execute("SELECT raw FROM events WHERE id=?", (funding_event_id,)).fetchone()
        if paid is None:
            raise ValueError("RISK_PREMIUM_FUNDING_EVENT_REQUIRED")
        evidence = json.loads(paid["raw"])
        funded = evidence.get("cost", evidence.get("consumed"))
        if type(funded) is not int or funded < self.risk["premium_per_order"]:
            raise ValueError("RISK_PREMIUM_NOT_FUNDED")
        payload = {
            "funding_event_id": funding_event_id,
            "premium_per_order": self.risk["premium_per_order"],
            "risk_terms_sha256": digest(self.risk),
            "now": tick,
        }
        raw = canonical(payload).decode()
        self.ex.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.ex.db.execute("SELECT order_id,raw FROM events WHERE id=?", (event_id,)).fetchone()
            if prior:
                if prior["order_id"] != ident or prior["raw"] != raw:
                    raise ValueError("RISK_COVER_EVENT_REBOUND")
            else:
                self.ex.db.execute("INSERT INTO events VALUES(?,?,?)", (event_id, ident, raw))
            self.ex.db.execute("COMMIT")
        except BaseException:
            self.ex.db.execute("ROLLBACK")
            raise

    def _risk_mature(self, ident, event_id, tick):
        if not all(isinstance(x, str) and x for x in (ident, event_id)):
            raise ValueError("RISK_MATURITY_ID_REQUIRED")
        cover = self._coverage(ident)
        self.ex.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.ex.db.execute("SELECT order_id,raw FROM events WHERE id=?", (event_id,)).fetchone()
            if prior:
                value = json.loads(prior["raw"])
                if prior["order_id"] != ident or value.get("action") != "risk_mature":
                    raise ValueError("RISK_MATURITY_EVENT_REBOUND")
                self.ex.db.execute("COMMIT")
                return
            row = self.ex.order(ident)
            if row["state"] != "released" or row["custody"] or int(row["refund_due"]) or int(row["compensation_due"]):
                raise ValueError("RISK_MATURITY_REQUIRES_RELEASED_UNDISPUTED_ORDER")
            history = [json.loads(x[0]) for x in self.ex.db.execute(
                "SELECT raw FROM events WHERE order_id=?", (ident,)
            )]
            releases = [x["now"] for x in history if x.get("action") == "release"]
            if len(releases) != 1 or tick < releases[0] + self.terms["liability_ticks"]:
                raise ValueError("FINITE_LIABILITY_NOT_MATURE")
            before = self.ex.snapshot()
            tail = int(row["price"]) + 200_000
            cap = residual_cap(tail, self.risk)
            self.ex.db.execute("UPDATE trades SET state=? WHERE id=?", (FINAL_STATE, ident))
            after_release = self.ex.snapshot()
            if cap and after_release["unrestrictedEarned"] < cap:
                raise ValueError("EARNED_RESIDUAL_RESERVE_UNAVAILABLE")
            reserve_id = "risk-residual:" + ident
            if cap:
                self.ex.db.execute(
                    "INSERT INTO investments(id,cap,state) VALUES(?,?,'reserved')",
                    (reserve_id, str(cap)),
                )
                witness = {
                    "before": before,
                    "after_full_tail_release": after_release,
                    "cap": cap,
                    "tail": tail,
                    "funding": "native unrestricted earned cash after full-tail release",
                    "risk_terms_sha256": digest(self.risk),
                    "cover": cover,
                }
                self.ex.db.execute(
                    "INSERT INTO investment_events(investment_id,action,witness) VALUES(?,'reserve',?)",
                    (reserve_id, canonical(witness).decode()),
                )
            payload = {
                "action": "risk_mature",
                "risk_terms_sha256": digest(self.risk),
                "tail": tail,
                "residual_cap": cap,
                "residual_expiry_tick": tick + self.risk["residual_ticks"],
            }
            self.ex.db.execute(
                "INSERT INTO events VALUES(?,?,?)",
                (event_id, ident, canonical(payload).decode()),
            )
            self.ex.db.execute("COMMIT")
        except BaseException:
            self.ex.db.execute("ROLLBACK")
            raise

    def _maturity_record(self, ident):
        rows = self.ex.db.execute(
            "SELECT raw FROM events WHERE order_id=?", (ident,)
        ).fetchall()
        values = [json.loads(x[0]) for x in rows]
        found = [x for x in values if x.get("action") == "risk_mature"]
        if len(found) != 1:
            raise ValueError("UNIQUE_RISK_MATURITY_REQUIRED")
        return found[0]

    def execute(self, op, args, day, *, record=True):
        custom = {
            "cover": {"id", "funding_event_id", "event_id"},
            "risk_mature": {"id", "event_id"},
            "risk_claim": {"id", "amount", "claim_sha256"},
            "risk_expire": {"id"},
        }
        if op not in custom:
            return super().execute(op, args, day, record=record)
        if self.persistence and (self.persistence.failed or not record):
            raise ValueError("DURABLE_ACTION_RECORD_REQUIRED")
        if type(day) is not int or day < self.last_day or day < 0:
            raise ValueError("EVENT_TIME_REGRESSION")
        if not isinstance(args, dict) or set(args) != custom[op]:
            raise ValueError("EXACT_RISK_ACTION_REQUIRED")
        before = self.ex.snapshot()
        if op == "cover":
            self._bind_cover(args["id"], args["funding_event_id"], args["event_id"], day)
        elif op == "risk_mature":
            self._risk_mature(args["id"], args["event_id"], day)
        else:
            maturity = self._maturity_record(args["id"])
            reserve_id = "risk-residual:" + args["id"]
            if day > maturity["residual_expiry_tick"] and op == "risk_claim":
                raise ValueError("RISK_CLAIM_WINDOW_EXPIRED")
            if day < maturity["residual_expiry_tick"] and op == "risk_expire":
                raise ValueError("RESIDUAL_EXPOSURE_NOT_EXPIRED")
            if maturity["residual_cap"] == 0:
                if op == "risk_claim" and args["amount"]:
                    raise ValueError("CLAIM_EXCEEDS_ZERO_RESIDUAL")
            elif op == "risk_claim":
                if type(args["amount"]) is not int or not 0 <= args["amount"] <= maturity["residual_cap"]:
                    raise ValueError("CLAIM_EXCEEDS_RESIDUAL")
                self.ex.finish_investment(reserve_id, args["amount"], args["claim_sha256"])
            else:
                self.ex.cancel_investment(reserve_id)
        after = self.ex.snapshot()
        self.last_day = day
        self.assert_conservation()
        event = {
            "seq": len(self.actions), "day": day, "op": op,
            "args": copy.deepcopy(args), "before": before, "after": after,
        }
        if self.persistence and not self._restoring:
            self.persistence.append(event)
        self.actions.append(event)
        return after

    def export(self):
        result = super().export()
        result["risk_contract"] = {
            "schema": SCHEMA,
            "terms": self.risk,
            "terms_sha256": digest(self.risk),
            "source_hashes": risk_source_hashes(self.root),
            "limitations": [
                "simulated prospective terms only",
                "no legal finality or real insurer",
                "provider failure and correlated loss are bounded authored severities",
            ],
        }
        return result


class OwnedRiskFiniteExchange(SingleWriterExchange):
    def __init__(self, path, **kwargs):
        self.lease = _acquire(path)
        self._closed, self._exchange = False, None
        try:
            self._exchange = RiskFiniteTapeExchange(path, **kwargs)
        except BaseException:
            self.close()
            raise

    def download(self, ident, buyer):
        self.lease.assert_owner()
        return self._exchange.download(ident, buyer)


def audit_contract019(tape, *, root, manifest, expected_actions_sha256=None):
    if not isinstance(tape, dict) or not isinstance(tape.get("risk_contract"), dict):
        raise ValueError("RISK_CONTRACT_TAPE_REQUIRED")
    rc = tape["risk_contract"]
    terms = risk_terms({k: rc["terms"][k] for k in (
        "premium_per_order", "buyer_friction", "cover_bps", "deductible_bps",
        "exclusion_bps", "payout_gap_bps", "provider_default_severity_bps",
        "correlated_dispute_bps", "residual_ticks",
    )})
    if (
        rc.get("schema") != SCHEMA
        or rc.get("terms") != terms
        or rc.get("terms_sha256") != digest(terms)
        or rc.get("source_hashes") != risk_source_hashes(root)
    ):
        raise ValueError("RISK_CONTRACT_IDENTITY_CHANGED")
    if digest(tape.get("actions")) != tape.get("actions_sha256"):
        raise ValueError("ACTION_TAPE_IDENTITY_MISMATCH")
    if expected_actions_sha256 is not None and tape["actions_sha256"] != expected_actions_sha256:
        raise ValueError("EXTERNAL_ACTION_IDENTITY_MISMATCH")
    config = tape.get("config")
    base_terms = config["terms"]
    with tempfile.TemporaryDirectory(prefix="contract019-audit-") as tmp:
        replay = RiskFiniteTapeExchange(
            Path(tmp) / "replay.sqlite", root=root, manifest=manifest,
            opening=config["opening"], working=config["working"],
            contract=config["contract"], _contract_already_bound=True,
            liability_ticks=base_terms["liability_ticks"],
            time_unit=base_terms["time_unit"],
            arrangement_cost=base_terms["arrangement_cost"],
            risk={k: terms[k] for k in (
                "premium_per_order", "buyer_friction", "cover_bps", "deductible_bps",
                "exclusion_bps", "payout_gap_bps", "provider_default_severity_bps",
                "correlated_dispute_bps", "residual_ticks",
            )},
            durable=False,
        )
        try:
            for seq, event in enumerate(tape["actions"]):
                if event.get("seq") != seq or event.get("before") != replay.ex.snapshot():
                    raise ValueError("EVENT_SEQUENCE_OR_OPENING_STATE_MISMATCH")
                if replay.execute(event["op"], event["args"], event["day"]) != event.get("after"):
                    raise ValueError("EVENT_DERIVED_BALANCE_MISMATCH")
            rebuilt = replay.export()
        finally:
            replay.close()
    for key in (
        "config", "summary", "journal", "orders", "investments",
        "investment_witnesses", "invoices", "receivables", "risk_contract",
    ):
        if rebuilt[key] != tape.get(key):
            raise ValueError("DERIVED_" + key.upper() + "_MISMATCH")
    return {
        "accepted": True,
        "scope": "prospective simulated risk contract",
        "actions_sha256": tape["actions_sha256"],
        "summary": rebuilt["summary"],
        "risk_contract": rebuilt["risk_contract"],
    }
