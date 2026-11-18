"""Private mission observations and an optional, explicitly invoked read-only Stripe reconciliation."""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

from .store import Conflict, StateError, canonical, digest, require_active, strict_json, timestamp


# One counterparty and one full-price offer per mission revision. Each observed external
# action needs its own type of source. A local assessment or technical pass cannot advance it.
STAGES = {
    "identified": (("problem", "current_alternative", "contact_route"), ("public_need",)),
    "validated": (("acceptance_criteria", "willingness_basis", "funding_basis", "rights"),
                  ("counterparty_requirements", "funding_and_demand", "rights_basis")),
    "offered": (("offer_id", "recipient", "amount", "currency", "terms", "acceptance_criteria", "artifact_sha256"),
                ("owner_authorization", "transmitted_offer")),
    "accepted": (("offer_sha256", "recipient", "decision_reference"), ("counterparty_acceptance",)),
    "delivered": (("offer_sha256", "recipient", "artifact_sha256", "accepted_outcome"),
                  ("recipient_acknowledgment",)),
    "settlement_reported": (("offer_sha256", "recipient", "amount", "currency", "statement_reference"),
                            ("settlement_observation",)),
    "withheld": (("reason", "reopen_condition"), ("decision_basis",)),
}
NEXT = {None: "identified", "identified": "validated", "validated": "offered", "offered": "accepted",
        "accepted": "delivered", "delivered": "settlement_reported"}
ACTIONS = {
    None: "Identify the counterparty and its published need.",
    "identified": "Obtain attributable evidence of requirements, rights, funding and willingness to pay.",
    "validated": "Obtain owner authorization before an external offer. Record only an offer actually transmitted.",
    "offered": "Await counterparty acceptance of the exact offer.",
    "accepted": "Await recipient acknowledgment of the verified package and its outcome.",
    "delivered": "Await independent settlement evidence. An enrolled Stripe offer supports an authorized read-only check.",
    "settlement_reported": "Await independent settlement reconciliation through the supported enrolled rail.",
    "paid": "Historical observation of available Stripe funds. Reversals, bank payout and profit require separate evidence.",
    "withheld": "Review the recorded reopening condition. Open a new revision if the decision changes.",
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = {"mission_id", "version", "input_sha256", "operation_sequence", "previous_sha256", "stage", "counterparty",
          "reviewer", "details", "evidence"}
TABLE = """CREATE TABLE IF NOT EXISTS ignition_commercial_events (
    mission_id TEXT NOT NULL, version INTEGER NOT NULL, sequence INTEGER NOT NULL,
    sha256 TEXT NOT NULL, observed_at TEXT NOT NULL, event TEXT NOT NULL,
    PRIMARY KEY (mission_id, version, sequence), UNIQUE(mission_id, version, sha256))"""


def _history(db, mission):
    db.execute(TABLE)
    history = []
    rows = db.execute("SELECT sequence,sha256,observed_at,event FROM ignition_commercial_events "
                      "WHERE mission_id=? AND version=? ORDER BY sequence", (mission["id"], mission["version"]))
    for sequence, fingerprint, observed_at, raw in rows:
        event = strict_json(raw)
        previous = history[-1]["sha256"] if history else None
        if (sequence != len(history) + 1 or digest(event) != fingerprint or event["previous_sha256"] != previous
                or (event["mission_id"], event["version"], event["input_sha256"]) !=
                (mission["id"], mission["version"], mission["input_sha256"])):
            raise Conflict("Commercial history does not match this mission or its preceding evidence.")
        history.append({"sha256": fingerprint, "recorded_at": observed_at, "event": event})
    return history


def _offer(history):
    return next((item for item in history if item["event"]["stage"] == "offered"), None)


def _summary(mission, history):
    stage = history[-1]["event"]["stage"] if history else None
    paid = history[-1]["event"]["details"] if stage == "paid" else None
    return {"mission_id": mission["id"], "version": mission["version"], "input_sha256": mission["input_sha256"],
            "technical_status": mission["status"], "operation_state": mission["operation"]["state"],
            "operation_sequence": mission["operation"]["sequence"],
            "commercial_state": "delivered" if stage == "settlement_reported"
            else (stage or "unassessed"), "next_action": ACTIONS[stage],
            "settlement": ("stripe_balance_available_at_observation" if paid else
                           "pending_independent_reconciliation" if stage == "settlement_reported" else "unverified"),
            "collected_revenue": ({**paid, "observed_at": history[-1]["recorded_at"]} if paid else None), "history": history,
            "attribution": "Private local observations. The reviewer is responsible for source authenticity, "
                           "authority and meaning. A paid event requires an authenticated provider read. No funds are moved."}


def status(store, run_id, version):
    with store.connection() as db:
        mission = store._get(db, run_id, version)
        return _summary(mission, _history(db, mission))


def _allowed(stage, previous):
    return (stage in STAGES and (stage == NEXT.get(previous) or
            (stage == "withheld" and previous in (None, "identified", "validated"))))


def template(store, run_id, version, stage):
    s = status(store, run_id, version)
    history = s["history"]
    last = history[-1] if history else None
    if not _allowed(stage, last["event"]["stage"] if last else None):
        raise Conflict("This transition does not follow the current commercial state.")
    fields, kinds = STAGES[stage]
    details = dict.fromkeys(fields, "")
    offer = _offer(history)
    if offer:
        prior = offer["event"]["details"]
        details.update({key: prior[key] for key in details.keys() & prior.keys()})
        details["offer_sha256"] = offer["sha256"]
    if stage == "offered":
        details["acceptance_criteria"] = last["event"]["details"]["acceptance_criteria"]
    return {"mission_id": run_id, "version": version, "input_sha256": s["input_sha256"],
            "previous_sha256": last["sha256"] if last else None, "operation_sequence": s["operation_sequence"],
            "stage": stage,
            "counterparty": last["event"]["counterparty"] if last else "", "reviewer": "", "details": details,
            "evidence": {kind: {"source": "", "sha256": ""} for kind in kinds}}


def _text(value):
    return isinstance(value, str) and value.strip() == value and 0 < len(value) <= 4000


def _file_digest(path):
    # Do not ingest private evidence into the mission journal or follow a link to a device.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or not info.st_size:
            raise StateError("Provide a nonempty regular evidence file.")
        hashed = hashlib.sha256()
        for chunk in iter(lambda: f.read(1 << 20), b""):
            hashed.update(chunk)
        final = os.fstat(f.fileno())
        if (final.st_mtime_ns, final.st_size) != (info.st_mtime_ns, info.st_size):
            raise Conflict("Evidence changed while being read.")
        return hashed.hexdigest()


def _check_evidence(event, paths):
    stage = event["stage"]
    fields, kinds = STAGES[stage]
    details, evidence = event["details"], event["evidence"]
    if stage == "offered" and isinstance(details, dict) and "stripe_parties_sha256" in details:
        if not isinstance(details["stripe_parties_sha256"], str) or not HASH.fullmatch(details["stripe_parties_sha256"]):
            raise StateError("Invalid enrolled Stripe parties digest.")
        fields = (*fields, "stripe_parties_sha256")
    if (not isinstance(details, dict) or set(details) != set(fields) or not all(map(_text, details.values()))
            or not _text(event["counterparty"]) or not _text(event["reviewer"])):
        raise StateError("Provide the counterparty, named reviewer and every required stage detail.")
    if not isinstance(evidence, dict) or set(evidence) != set(kinds) or set(paths) != set(kinds):
        raise StateError("Provide each required source and its corresponding local evidence file.")
    for kind in kinds:
        source = evidence[kind]
        if (not isinstance(source, dict) or set(source) != {"source", "sha256"} or not _text(source["source"])
                or not isinstance(source["sha256"], str) or not HASH.fullmatch(source["sha256"])
                or _file_digest(paths[kind]) != source["sha256"]):
            raise StateError(f"Missing source or evidence digest mismatch for {kind}.")


def record(controller, run_id, version, event, paths):
    """Import a local operator's reviewed observation. No model or remote endpoint can call this."""
    if not isinstance(event, dict) or set(event) != FIELDS or not isinstance(event["stage"], str):
        raise StateError("Use the revision-bound event template.")
    stage = event["stage"]
    if stage not in STAGES:
        raise StateError("Unsupported stage. A local record cannot establish paid status.")
    if type(version) is not int or type(event["version"]) is not int or (
            event["mission_id"], event["version"]) != (run_id, version):
        raise Conflict("Observation belongs to another mission or revision.")
    store = controller.store
    snapshot = store.get(run_id)
    if snapshot["version"] != version or event["input_sha256"] != snapshot["input_sha256"]:
        raise Conflict("Current mission revision and input must match the observation.")
    require_active(snapshot["operation"])
    if type(event["operation_sequence"]) is not int or event["operation_sequence"] != snapshot["operation"]["sequence"]:
        raise Conflict("Commercial template predates an operator control change. Generate a fresh template.")
    _check_evidence(event, paths)
    fingerprint = digest(event)
    # Export outside the write transaction so a slow qualification cannot prevent a pause.
    if stage in {"offered", "delivered"}:
        if hashlib.sha256(controller.deliver(run_id, version)).hexdigest() != event["details"]["artifact_sha256"]:
            raise Conflict("The observed artifact does not match this verified mission export.")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        mission = store._get(db, run_id)
        if mission["version"] != version or event["input_sha256"] != mission["input_sha256"]:
            raise Conflict("Current mission revision and input must match the observation.")
        require_active(mission["operation"])
        if mission["operation"]["sequence"] != snapshot["operation"]["sequence"]:
            raise Conflict("Operator control changed while recording the observation.")
        history = _history(db, mission)
        if any(h["sha256"] == fingerprint for h in history):
            return _summary(mission, history)
        last = history[-1] if history else None
        if (event["previous_sha256"] != (last["sha256"] if last else None) or
                not _allowed(stage, last["event"]["stage"] if last else None)):
            raise Conflict("Stale observation or commercial transition out of order.")
        if last and event["counterparty"] != last["event"]["counterparty"]:
            raise Conflict("Observation belongs to another counterparty.")
        details = event["details"]
        if stage == "offered":
            if (not re.fullmatch(r"[A-Z]{3}", details["currency"]) or
                    not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", details["amount"]) or
                    not re.search(r"[1-9]", details["amount"])):
                raise StateError("Provide a positive decimal offer price and a three-letter currency.")
            if details["acceptance_criteria"] != last["event"]["details"]["acceptance_criteria"]:
                raise Conflict("Offer criteria differ from the counterparty's validated criteria.")
        if stage in {"accepted", "delivered", "settlement_reported"}:
            offer = _offer(history)
            terms = offer["event"]["details"]
            if (details["offer_sha256"] != offer["sha256"] or
                    any(details[k] != terms[k] for k in details.keys() & terms.keys())):
                raise Conflict("Recipient, price, currency or artifact differs from the exact offer.")
        now = timestamp()
        db.execute("INSERT INTO ignition_commercial_events VALUES(?,?,?,?,?,?)",
                   (run_id, version, len(history) + 1, fingerprint, now, canonical(event)))
        history.append({"sha256": fingerprint, "recorded_at": now, "event": event})
        return _summary(mission, history)


def _stripe_offer(history):
    from . import stripe_readonly as stripe
    offer = _offer(history)
    if not offer or not offer["event"]["details"].get("stripe_parties_sha256"):
        raise StateError("This offer has no prospective Stripe merchant and customer enrollment.")
    terms = offer["event"]["details"]
    stripe.minor_amount(terms["amount"], terms["currency"])
    return offer


def reconcile_stripe(controller, run_id, version, request, key_fd, sequence):
    """Perform only owner-requested authenticated reads; never accept provider objects from caller input."""
    from . import stripe_readonly as stripe
    if not isinstance(request, dict) or set(request) != {"merchant", "customer", "payment_intent", "charge"}:
        raise StateError("Specify exact private merchant, customer, PaymentIntent and charge references.")
    store = controller.store

    def authorize_read():
        state = store.get(run_id)
        require_active(state["operation"])
        if state["version"] != version or type(sequence) is not int or state["operation"]["sequence"] != sequence:
            raise Conflict("Mission or control generation changed. Review current status before reconciliation.")
    authorize_read()
    state = status(store, run_id, version)
    old = state["history"]
    offer = _stripe_offer(old)
    if stripe.parties(request) != offer["event"]["details"]["stripe_parties_sha256"]:
        raise Conflict("Expected Stripe parties differ from the enrolled offer.")
    charge_tag = digest(["stripe-direct-charge/1", request["merchant"], request["charge"]])
    if old[-1]["event"]["stage"] == "paid":
        if state["collected_revenue"]["charge_fingerprint"] != charge_tag:
            raise Conflict("A different payment already closed this offer.")
        return state
    if old[-1]["event"]["stage"] not in {"delivered", "settlement_reported"}:
        raise Conflict("Recipient delivery acknowledgment is required for this settlement transition.")
    charge, traces = stripe.observe(request, key_fd, authorize_read)
    details = stripe.reconcile_charge(charge, request, offer)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        mission = store._get(db, run_id)
        require_active(mission["operation"])
        if mission["version"] != version or mission["operation"]["sequence"] != sequence:
            raise Conflict("Mission changed during the authorized provider read.")
        history = _history(db, mission)
        if history[-1]["event"]["stage"] == "paid" and history[-1]["event"]["details"]["charge_fingerprint"] == charge_tag:
            return _summary(mission, history)
        if history[-1]["sha256"] != old[-1]["sha256"]:
            raise Conflict("Commercial history changed during the provider read.")
        db.execute("""CREATE TABLE IF NOT EXISTS ignition_stripe_claims (
                   charge_sha256 TEXT PRIMARY KEY, transaction_sha256 TEXT NOT NULL UNIQUE)""")
        if db.execute("SELECT 1 FROM ignition_stripe_claims WHERE charge_sha256=? OR transaction_sha256=?",
                      (charge_tag, details["balance_transaction_fingerprint"])).fetchone():
            raise Conflict("Provider settlement was already attributed in this workspace.")
        now = timestamp()
        event = {"mission_id":run_id, "version":version, "input_sha256":mission["input_sha256"],
                 "operation_sequence":sequence, "previous_sha256":history[-1]["sha256"], "stage":"paid",
                 "offer_sha256": offer["sha256"], "details": details, "provider_request_fingerprints": traces,
                 "observed_at": now}
        fingerprint = digest(event)
        db.execute("INSERT INTO ignition_stripe_claims VALUES(?,?)", (charge_tag, details["balance_transaction_fingerprint"]))
        db.execute("INSERT INTO ignition_commercial_events VALUES(?,?,?,?,?,?)",
                   (run_id, version, len(history) + 1, fingerprint, now, canonical(event)))
        history.append({"sha256":fingerprint, "recorded_at": now, "event":event})
        return _summary(mission, history)


def register_cli(subparsers):
    cmd = subparsers.add_parser("commercial", help="inspect a private commercial handoff or import reviewed evidence")
    cmd.add_argument("id")
    cmd.add_argument("--version", type=int, required=True)
    operation = cmd.add_mutually_exclusive_group()
    operation.add_argument("--template", choices=STAGES, help="prepare the next evidence record")
    operation.add_argument("--record", type=Path, help="import a completed record, without transmitting anything")
    operation.add_argument("--stripe-offer", type=Path, metavar="PARTIES.json",
                           help="prepare an offer bound to verified merchant, customer and precreated PaymentIntent IDs")
    operation.add_argument("--stripe-metadata", action="store_true",
                           help="show the opaque metadata binding for an enrolled offer")
    operation.add_argument("--stripe-reconcile", type=Path, metavar="PRIVATE.json",
                           help="read a specified live Stripe charge and its available balance transaction")
    cmd.add_argument("--stripe-key-fd", type=int, help="descriptor for an owner-supplied live restricted read key")
    cmd.add_argument("--control-sequence", type=int, help="current operator generation for a Stripe read")
    cmd.add_argument("--evidence", action="append", default=[], metavar="KIND=PATH",
                     help="original or authorized redacted evidence for each required kind")


def dispatch_cli(args, controller):
    from . import stripe_readonly as stripe
    if args.stripe_reconcile:
        if args.evidence or args.stripe_key_fd is None or args.control_sequence is None:
            raise StateError("Reconciliation requires --stripe-key-fd and --control-sequence only.")
        return reconcile_stripe(controller, args.id, args.version, strict_json(args.stripe_reconcile.read_bytes()),
                                args.stripe_key_fd, args.control_sequence)
    if args.stripe_key_fd is not None or args.control_sequence is not None:
        raise StateError("Provider key and control generation options require --stripe-reconcile.")
    if args.stripe_offer or args.stripe_metadata:
        if args.evidence:
            raise StateError("--evidence requires --record.")
        if args.stripe_offer:
            request = strict_json(args.stripe_offer.read_bytes())
            if not isinstance(request, dict) or set(request) != {"merchant", "customer", "payment_intent"}:
                raise StateError("Provide exactly the expected merchant, customer and precreated PaymentIntent.")
            event = template(controller.store, args.id, args.version, "offered")
            event["details"]["stripe_parties_sha256"] = stripe.parties(request)
            return event
        offer = _stripe_offer(status(controller.store, args.id, args.version)["history"])
        return {stripe.BINDING_KEY: offer["sha256"]}
    if args.record is None:
        if args.evidence:
            raise StateError("--evidence requires --record")
        if args.template:
            return template(controller.store, args.id, args.version, args.template)
        return status(controller.store, args.id, args.version)
    paths = {}
    for entry in args.evidence:
        kind, separator, path = entry.partition("=")
        if not separator or not path or kind in paths:
            raise StateError("Use one --evidence KIND=PATH per requested kind.")
        paths[kind] = Path(path)
    return record(controller, args.id, args.version, strict_json(args.record.read_bytes()), paths)
