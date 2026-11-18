"""Private, evidence-bound annotations on a mission. No outbound or financial operations."""
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
    "delivered": "Await independent settlement evidence. This tool cannot reconcile receipts to cash.",
    "settlement_reported": "Reconcile through an authorized independent financial source. Paid remains unverified.",
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
    return {"mission_id": mission["id"], "version": mission["version"], "input_sha256": mission["input_sha256"],
            "technical_status": mission["status"], "operation_state": mission["operation"]["state"],
            "operation_sequence": mission["operation"]["sequence"],
            "commercial_state": "delivered" if stage == "settlement_reported"
            else (stage or "unassessed"), "next_action": ACTIONS[stage],
            "settlement": "pending_independent_reconciliation" if stage == "settlement_reported" else "unverified",
            "collected_revenue": None, "history": history,
            "attribution": "Private local observations. The reviewer is responsible for source authenticity, "
                           "authority and meaning. Digests identify reviewed bytes. No action is transmitted."}


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


def register_cli(subparsers):
    cmd = subparsers.add_parser("commercial", help="inspect a private commercial handoff or import reviewed evidence")
    cmd.add_argument("id")
    cmd.add_argument("--version", type=int, required=True)
    operation = cmd.add_mutually_exclusive_group()
    operation.add_argument("--template", choices=STAGES, help="prepare the next evidence record")
    operation.add_argument("--record", type=Path, help="import a completed record, without transmitting anything")
    cmd.add_argument("--evidence", action="append", default=[], metavar="KIND=PATH",
                     help="original or authorized redacted evidence for each required kind")


def dispatch_cli(args, controller):
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
