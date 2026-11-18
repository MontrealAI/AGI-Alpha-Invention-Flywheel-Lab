"""Run a frozen shortlist through the existing mission worker and commercial journal."""
import hashlib
import os
import re
import tempfile
from datetime import date
from pathlib import Path

from . import commercial_handoff
from .store import Conflict, StateError, canonical, clean_mission, digest, strict_json, timestamp


def _slug(value):
    return isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value)


def read_shortlist(path):
    plan = strict_json(path.read_bytes())
    if not isinstance(plan, dict) or set(plan) != {"purpose", "selection_basis", "candidates"}:
        raise StateError("Supply a purpose, selection_basis and candidates")
    if not all(isinstance(plan[k], str) and plan[k].strip() for k in ("purpose", "selection_basis")):
        raise StateError("Describe the beneficiary objective and the selection assumptions")
    if not isinstance(plan["candidates"], list) or not plan["candidates"]:
        raise StateError("Provide a nonempty candidate list")
    seen = set()
    for candidate in plan["candidates"]:
        required = {"id", "mission_file", "counterparty", "problem", "current_alternative", "contact_route",
                    "source", "observed_on", "rights", "value_and_uncertainty", "proof_order"}
        if not isinstance(candidate, dict) or set(candidate) != required:
            raise StateError("Candidate fields differ from the registered shortlist format")
        if not all(isinstance(candidate[k], str) and candidate[k].strip() for k in required - {"proof_order"}):
            raise StateError("Every candidate needs its dated source, rights, outside option and economic uncertainty")
        if (not _slug(candidate["id"]) or candidate["id"] in seen or type(candidate["proof_order"]) is not int
                or candidate["proof_order"] < 1 or not candidate["source"].startswith("https://")):
            raise StateError("Use distinct candidate IDs, positive proof order and a primary HTTPS source")
        seen.add(candidate["id"])
        date.fromisoformat(candidate["observed_on"])
        name = candidate["mission_file"]
        if Path(name).name != name or not name.endswith(".json"):
            raise StateError("Reference a JSON mission in the shortlist directory")
        source = path.parent / name
        if source.is_symlink():
            raise StateError("Mission source must be a regular sibling file")
        doc = strict_json(source.read_bytes())
        if not isinstance(doc, dict) or "mission" not in doc:
            raise StateError("Candidate file must contain a mission")
        candidate["brief"] = {k: doc[k] for k in ("mission", "sources") if k in doc}
    return plan


def _freeze(store, key, plan, reuse_from):
    if not _slug(key):
        raise StateError("Choose a stable 1–80 character pursuit ID")
    if reuse_from is not None:
        if not _slug(reuse_from) or reuse_from == key:
            raise StateError("Select a distinct prior local pursuit ID for reuse")
        plan = dict(plan, reuse_from=reuse_from)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS ignition_pursuits
                   (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, plan TEXT NOT NULL, created_at TEXT NOT NULL)""")
        previous = db.execute("SELECT sha256 FROM ignition_pursuits WHERE id=?", (key,)).fetchone()
        fingerprint = digest(plan)
        if previous and previous[0] != fingerprint:
            raise Conflict("Pursuit ID already binds a different shortlist or mission input")
        if not previous:
            db.execute("INSERT INTO ignition_pursuits VALUES(?,?,?,?)", (key, fingerprint, canonical(plan), timestamp()))
    return fingerprint


def _run_key(pursuit_id, candidate_id):
    return "pursue-" + digest([pursuit_id, candidate_id])


def _negative_quantum_evidence(ctrl, db, prior_id, plan, candidate):
    """Validate the prior decision, archived recipient, and grants without repeating the experiment."""
    from . import quantum_specialist as quantum
    old = db.execute("SELECT sha256,plan FROM ignition_pursuits WHERE id=?", (prior_id,)).fetchone()
    if not old:
        return None
    prior = strict_json(old[1])
    if (digest(prior) != old[0] or prior["purpose"] != plan["purpose"] or
            prior["selection_basis"] != plan["selection_basis"] or candidate not in prior["candidates"]):
        return None
    source = db.execute("SELECT id,version FROM requests WHERE key=?", (_run_key(prior_id, candidate["id"]),)).fetchone()
    if not source:
        return None
    state = ctrl.store._get(db, source[0])
    brief = candidate["brief"]
    preset = strict_json(quantum.PRESET.read_bytes())["mission"]
    if (brief["mission"] != preset or brief.get("sources", []) or state["version"] != source[1] or
            state["status"] != "verified" or state["operation"]["state"] != "active" or ctrl.obsolete(state) or
            state["mission"] != clean_mission(brief["mission"]) or
            state["mission"]["authority"].get("allow_program_reuse") is not True):
        return None

    # Match the installed public experiment and the independent truth-table evidence it requires.
    result = state.get("quantum_result")
    frozen = strict_json((quantum.SOURCE / "RECEIPT.json").read_bytes())
    frozen.pop("published_sdk")  # Optional upstream SDK report, outside the local recipient protocol.
    circuit = frozen["circuits"]["flexible_on_stronger_order.kmx"]
    independent = {"circuit_sha256": circuit["sha256"], "gates": circuit["gates_checked"],
                   "exhaustive_input_pairs_at_zero_target": 4096**2, "arbitrary_target_identity_proved": True,
                   "assignments_covered": circuit["assignments_covered"]}
    if result != dict(frozen, independent_truth_table=independent, beneficiary_acceptance=None, payment_received=None):
        return None
    package, contract = quantum._package(state)
    report_hash = digest(result)
    decision = quantum._decision(result)
    if (decision["disposition"] != "withhold" or state.get("field_decision") != decision or
            state["contract"] != contract or state["contract_sha256"] != digest(contract) or
            state["artifact"] != {"kind": quantum.KIND, "sha256": contract["package_sha256"]} or
            state["evaluation"] != {"status": "pass", "scope": quantum.SCOPE, "receipt_sha256": report_hash}):
        return None
    sha = contract["package_sha256"]
    filename = f"{source[0]}-v{source[1]}-{sha}.zip"
    recipient = ctrl.store.root / "recipients" / filename
    if recipient.parent.is_symlink() or recipient.is_symlink() or not recipient.is_file():
        return None
    if recipient.stat().st_size != len(package) or recipient.read_bytes() != package:
        return None

    history = commercial_handoff._history(db, state)
    if len(history) != 2:
        return None
    first, held = (item["event"] for item in history)
    if (first["stage"] != "identified" or held["stage"] != "withheld" or
            any(e["counterparty"] != candidate["counterparty"] for e in (first, held)) or
            held["reviewer"] != "IGNITION registered shortlist" or
            held["details"] != {"reason": decision["reason"], "reopen_condition": decision["next_action"]} or
            held["evidence"] != {"decision_basis": {"source": "Source-bound mission evaluation", "sha256": digest(decision)}}):
        return None
    return {"pursuit_id": prior_id, "mission_id": source[0], "version": source[1],
            "prior_shortlist_sha256": old[0], "candidate_sha256": digest(candidate), "counterparty": candidate["counterparty"],
            "observed_on": candidate["observed_on"], "operation_sequence": state["operation"]["sequence"],
            "input_sha256": state["input_sha256"], "source_sha256": state["specialist_source"], "receipt_sha256": report_hash,
            "recipient_file": filename, "recipient_sha256": sha, "withheld_event_sha256": history[-1]["sha256"],
            "decision": decision}


def _select_reuse(ctrl, pursuit_id, prior_id, plan, candidate):
    mission = candidate["brief"]["mission"]
    if (not prior_id or not isinstance(mission, dict) or
            "quantum_multiplier" not in mission.get("resources", {}) or
            mission.get("authority", {}).get("allow_program_reuse") is not True):
        return None
    # This method's conclusion only applies to this sponsor's scoring objective.
    if (candidate["source"] != "https://opensource.googleblog.com/2026/10/announcing-verifiable-quantum-circuit-compilation-competition-on-kaggle.html"
            or candidate["counterparty"] != "Google Quantum AI (competition sponsor)"):
        return None
    with ctrl.store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS ignition_pursuit_reuse
                   (pursuit TEXT, candidate TEXT, receipt TEXT NOT NULL, fresh INTEGER NOT NULL,
                    PRIMARY KEY(pursuit,candidate))""")
        key = (pursuit_id, candidate["id"])
        selected = db.execute("SELECT receipt,fresh FROM ignition_pursuit_reuse WHERE pursuit=? AND candidate=?", key).fetchone()
        if selected and selected[1]:
            return None
        try:
            evidence = _negative_quantum_evidence(ctrl, db, prior_id, plan, candidate)
        except (OSError, ValueError, KeyError, TypeError):
            evidence = None
        serialized = canonical(evidence)
        if not selected:
            db.execute("INSERT INTO ignition_pursuit_reuse VALUES(?,?,?,?)", (*key, serialized, int(evidence is None)))
        elif selected[0] != serialized:
            # A changed grant or receipt commits this successor to fresh execution on every retry.
            db.execute("UPDATE ignition_pursuit_reuse SET fresh=1 WHERE pursuit=? AND candidate=?", key)
            return None
        return evidence


def _observe(ctrl, run_id, rev, candidate, stage, evidence, details, observed):
    try:
        return _commit_observation(ctrl, run_id, rev, candidate, stage, evidence, details)
    except Conflict:
        latest = commercial_handoff.status(ctrl.store, run_id, rev)
        if latest["history"] == observed["history"]:
            raise
        return latest


def _commit_observation(ctrl, run_id, rev, candidate, stage, evidence, details):
    event = commercial_handoff.template(ctrl.store, run_id, rev, stage)
    kind, = event["evidence"]
    data = canonical(evidence).encode()
    reference = ("MONTREAL.AI research note citing " + candidate["source"]
                 if stage == "identified" else "Source-bound mission evaluation")
    event.update(counterparty=candidate["counterparty"], reviewer="IGNITION registered shortlist", details=details)
    event["evidence"][kind] = {"source": reference, "sha256": hashlib.sha256(data).hexdigest()}
    # Keep the input reachable in the frozen shortlist or mission. No external action is performed.
    with tempfile.NamedTemporaryFile(dir=ctrl.store.root) as file:
        file.write(data)
        file.flush()
        return commercial_handoff.record(ctrl, run_id, rev, event, {kind: file.name})


def _keep_recipient(ctrl, state, directory):
    """Only expose a complete revision-bound export; retries can reuse identical bytes."""
    run_id, rev = state["id"], state["version"]
    data = ctrl.deliver(run_id, rev)
    sha = hashlib.sha256(data).hexdigest()
    path = directory / f"{run_id}-v{rev}-{sha}.zip"
    with tempfile.NamedTemporaryFile(dir=directory, prefix=".recipient-") as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        with ctrl.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = ctrl.store._get(db, run_id)
            if current["version"] != rev or current["operation"] != state["operation"] or current["operation"]["state"] != "active":
                raise Conflict("Mission control or revision changed before export")
            try:
                os.link(tmp.name, path)
            except FileExistsError:
                if path.is_symlink() or not path.is_file():
                    raise Conflict("Previously prepared recipient is no longer a regular file")
                with path.open("rb") as previous:
                    if hashlib.file_digest(previous, "sha256").hexdigest() != sha:
                        raise Conflict("Previously prepared recipient differs from this export")
    return {"file": path.name, "bytes": len(data), "sha256": sha}


def pursue(ctrl, plan_file, request_id, *, reuse_from=None):
    plan = read_shortlist(Path(plan_file))
    receipt = {"id": request_id, "shortlist_sha256": _freeze(ctrl.store, request_id, plan, reuse_from),
               "purpose": plan["purpose"], "selection_basis": plan["selection_basis"],
               "attempts": [], "result": "shortlist_exhausted", "collected_revenue": None}
    directory = ctrl.store.root / "recipients"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise StateError("Use a private recipient directory inside the mission workspace")
    for candidate in sorted(plan["candidates"], key=lambda c: (c["proof_order"], c["id"])):
        reused = _select_reuse(ctrl, request_id, reuse_from, plan, candidate)
        if reused:
            receipt["attempts"].append({"candidate": candidate["id"], "technical_status": "reused_previous_negative",
                                        "new_measurement": False, "reused_from": reused, "commercial_state": "unassessed",
                                        "field_decision": reused["decision"], "next_action": reused["decision"]["next_action"]})
            continue
        run_key = _run_key(request_id, candidate["id"])
        run_id, rev = ctrl.create(dict(candidate["brief"], request_id=run_key))
        state = ctrl.view(run_id)
        attempt = {"candidate": candidate["id"], "mission_id": run_id, "version": rev}
        receipt["attempts"].append(attempt)
        if state["version"] != rev or state["status"] == "stale" or state["operation"]["state"] != "active":
            receipt["result"] = "operator_control_or_revision_changed"
            attempt["next_action"] = "Inspect the existing mission and its controls before continuing."
            break
        commercial = commercial_handoff.status(ctrl.store, run_id, rev)
        if not commercial["history"]:
            note = {k: v for k, v in candidate.items() if k != "brief"}
            fields = {k: candidate[k] for k in ("problem", "current_alternative", "contact_route")}
            commercial = _observe(ctrl, run_id, rev, candidate, "identified", note, fields, commercial)
        state = ctrl.advance(run_id, rev)
        attempt["technical_status"] = state["status"]
        decision = state.get("field_decision")
        if state["status"] == "verified":
            attempt["recipient"] = _keep_recipient(ctrl, state, directory)
        commercial = commercial_handoff.status(ctrl.store, run_id, rev)
        if state["status"] == "verified" and decision and decision["disposition"] == "withhold" and commercial["commercial_state"] == "identified":
            commercial = _observe(ctrl, run_id, rev, candidate, "withheld", decision,
                                  {"reason": decision["reason"], "reopen_condition": decision["next_action"]}, commercial)
        commercial = commercial_handoff.status(ctrl.store, run_id, rev)
        attempt["field_decision"] = decision
        attempt["commercial_state"] = commercial["commercial_state"]
        attempt["next_action"] = (decision or {}).get("next_action") or state.get("error") or commercial["next_action"]
        if commercial["commercial_state"] == "withheld":
            attempt["next_action"] = commercial["history"][-1]["event"]["details"]["reopen_condition"]
        if commercial["commercial_state"] not in ("identified", "withheld"):
            receipt["result"] = "existing_commercial_engagement"
            break
        if state["status"] == "verified" and decision and decision["disposition"] == "ready_for_beneficiary_review" and commercial["commercial_state"] != "withheld":
            receipt["result"] = "beneficiary_review_required"
            break
        if state["status"].startswith("awaiting_"):
            receipt["result"] = state["status"]
            break
    return receipt
