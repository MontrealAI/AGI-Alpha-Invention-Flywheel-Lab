"""Prospective public-input qualification through the signed-in blank Studio path.

Only the intake goes to the proposer. The two confirmation cases and recipient
checks are owned by this simulated operator and declared before inference.
The trusted operator never repairs a draft, chooses a candidate or supplies
an artifact. A decline, timeout or invalid proposal is an observable outcome.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
import subprocess
import sys
import time

import qualify_live as q

PURPOSE = "Turn the cost center names from our flat export into labels our bookkeeping importer accepts."
SOURCE_URL = "https://github.blog/changelog/2026-11-03-look-up-a-resources-cost-center-with-the-github-rest-api/"
SOURCE_TEXT = ("GitHub announced a per-resource cost center lookup on November 3, 2026. "
               "Previously an authorized user listed all cost centers and searched their resources. "
               "The lookup returns the center ID and name when a membership exists.")
# The date of the observation is fixed, not refreshed when someone reruns the study.
SOURCE = {"url": SOURCE_URL, "publisher": "GitHub", "title": "Resource cost center lookup announcement",
          "text": SOURCE_TEXT, "rights": "Operator-authored summary of the public GitHub Changelog for local study.",
          "published_at": "2026-11-03", "event_at": "2026-11-03", "retrieved_at": "2026-11-18T22:33:00Z"}
CALL_CAP = 8
CALL_SECONDS = 300

# Fresh test-only labels, intentionally absent from the mission and evidence.
CONFIRMATION_INPUTS = (
    {"rows": [{"name": "Équipe 71 — Montréal"}, {"name": " North / 008 "}]},
    {"rows": [{"name": "R24", "unmapped": "private note"}]},
)
RECIPIENT_INPUTS = (
    {"rows": [{"name": "A-010"}, {"name": "Cellule 028"}, {"name": "A-010"}]},
    {"rows": [{"name": 309}]},
    {"rows": [{"unknown": "unmapped"}]},
)


def intake():
    mission = {"purpose": PURPOSE, "beneficiary": "Internal bookkeeping import reviewer (simulated)",
               "requirements": ["Convert a batch of flat rows with one text field named name into rows "
                                "whose only field is cost_center. Preserve spelling, spacing, order and repeats exactly.",
                                "Reject a batch containing a row with a missing name, an extra field or a non-text name."],
               "authority": {"local_model": True, "public_sources": False},
               "resources": {"execution_strategy": "research", "max_initial_candidates": 2,
                             "max_model_calls": CALL_CAP, "max_repairs": 1,
                             "assets": "An authorized user already supplies flat name rows. Compare the whole offline "
                                       "import step with a conventional field projection. No paid or remote access."}}
    return {"request_id": "blank-studio-public-label-import", "mission": mission, "sources": [SOURCE]}


def reference(payload):
    """Conventional independent projection, implemented without the engine interpreter."""
    if not isinstance(payload, dict) or set(payload) != {"rows"} or not isinstance(payload["rows"], list):
        return {"error": "invalid_input"}
    out = []
    for row in payload["rows"]:
        if not isinstance(row, dict) or "name" not in row:
            return {"error": "missing_field"}
        if set(row) != {"name"}:
            return {"error": "extra_field"}
        if not isinstance(row["name"], str):
            return {"error": "invalid_value"}
        out.append({"cost_center": row["name"]})
    return {"expected": {"rows": out}}


def held_out_cases():
    return [{"name": name, "input": payload, **reference(payload)}
            for name, payload in zip(("Independent ordered labels", "Independent undeclared field"),
                                     CONFIRMATION_INPUTS, strict=True)]


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def review(spec):
    """Approve either supported representation of the requested import after checking its semantics."""
    if not isinstance(spec, dict) or spec.get("kind") != "record_migration" or spec.get("purpose") != PURPOSE:
        return "Proposed purpose or artifact family differs from the intake"
    definition = spec["definition"]
    if definition.get("extra_fields") != "reject" or definition.get("input_fields", ["name"]) != ["name"]:
        return "Proposed field admission policy differs from the recipient workflow"
    if "demonstrations" in definition:
        if definition.get("targets") != [{"name": "cost_center", "type": "text"}]:
            return "Proposed target shape differs from the importer"
    elif definition.get("columns") != [{"source": "name", "target": "cost_center", "type": "text"}]:
        return "Proposed transformation differs from the importer"
    withheld = {digest(row) for sample in (*CONFIRMATION_INPUTS, *RECIPIENT_INPUTS) for row in sample["rows"]}
    for example in [*spec["cases"], *definition.get("demonstrations", [])]:
        answer = reference(example["input"])
        actual = {k: example[k] for k in ("expected", "error") if k in example}
        if actual != answer:
            return "A proposed example disagrees with the independent reference"
        rows = example["input"].get("rows") if isinstance(example["input"], dict) else None
        if isinstance(rows, list) and any(digest(row) in withheld for row in rows):
            return "A reserved input appeared in the proposal"
    return None


def wait_for_stage(call, endpoint, state, deadline):
    while state["status"] in {"running", "queued"} and time.monotonic() < deadline:
        time.sleep(0.4)
        state = call(endpoint)
    return state


def snapshot(record, state, evidence):
    research = state.get("research") or {}
    record.update(status=state["status"], stage=state["stage"], error=state.get("error"),
                  candidate_ids=[r["id"] for r in research.get("candidates", [])],
                  research_decision=research.get("decision"), research_reason=research.get("decision_reason"),
                  original_requirement_fit=research.get("fit"), selected=research.get("selected"),
                  route=(state.get("routing") or {}).get("route"), events=[e["stage"] for e in state["events"]],
                  attempts=state["attempts"], construction_attempts=state.get("construction_attempts"),
                  artifact=evidence["artifact"], usage=(evidence.get("economics") or {}).get("usage"),
                  acceptance_origin=evidence.get("acceptance_origin"), contract_sha256=evidence.get("contract_sha256"),
                  acceptance=(evidence.get("evaluation") or {}).get("status"),
                  modular_comparison=(evidence.get("evaluation") or {}).get("comparison"))


def replay_recipient(work):
    checks = []
    for payload in RECIPIENT_INPUTS:
        start = time.perf_counter_ns()
        expected = reference(payload)
        reference_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        completed = subprocess.run([sys.executable, "-IB", str(work/"delivery/run.py"), "run"],
                                   cwd=work/"delivery", env={"LANG": "C.UTF-8", "PATH": os.defpath},
                                   input=json.dumps(payload).encode(), capture_output=True, timeout=15)
        wall_ns = time.perf_counter_ns() - start
        if completed.returncode == 0:
            observed = {"expected": json.loads(completed.stdout)}
        elif completed.returncode == 2:
            observed = {"error": json.loads(completed.stderr).get("error")}
        else:
            observed = {"unexpected_exit": completed.returncode}
        checks.append({"input": payload, "reference": expected, "received": observed,
                       "matched": observed == expected, "reference_in_process_ns": reference_ns,
                       "recipient_cold_process_ns": wall_ns})
    return checks


def run(work, call, record):
    request = intake()
    confirmations = held_out_cases()
    record.update(public_source=SOURCE, intake=request, independent_confirmation_sha256=digest(confirmations),
                  independent_recipient_inputs_sha256=digest(RECIPIENT_INPUTS), approval_submitted=False,
                  approval_authority="Automated simulated operator, solely for this prospective public qualification. "
                                     "No customer participation, financial authority or external effects.",
                  comparison_scope="Synthetic flat export to importer rows. No live billing account, measured demand "
                                   "or counterfactual claim that projection recently became possible.",
                  limits={"per_call_seconds": CALL_SECONDS, "max_calls": CALL_CAP, "max_initial_candidates": 2})
    if (record.get("unauthenticated_status") != 401 or record["authentication"] != {
            "authenticated": True, "environment": "staging"} or record["readiness"] != {
            "status": "ok", "revision": record["source_revision"]}
            or record["configuration"]["declared_model_sha256"] != q.pinned.MODEL_SHA
            or record["configuration"]["timeout_seconds"] != CALL_SECONDS):
        record["protocol_outcome"] = "Staging identity, access or model preflight failed"
        return False
    deadline = time.monotonic() + CALL_CAP * CALL_SECONDS + 60
    initial = call("/api/runs", request)
    endpoint = "/api/runs/" + initial["id"]
    state = wait_for_stage(call, endpoint, initial, deadline)
    snapshot(record, state, call(endpoint + "/evidence?version=1"))
    if state["status"] != "awaiting_contract":
        record["protocol_outcome"] = "No contract offered for operator review within the run budget"
        return False
    spec = state["proposed_contract"]["spec"]
    record.update(proposed_spec=spec, proposed_contract_sha256=state["contract_sha256"])
    reason = review(spec)
    if reason:
        record["protocol_outcome"] = reason
        return False
    accepted = call(endpoint + "/approve", {"version": 1, "contract_sha256": state["contract_sha256"],
                                            "confirmations": confirmations})
    record["approval_submitted"] = True
    state = wait_for_stage(call, endpoint, accepted, deadline)
    snapshot(record, state, call(endpoint + "/evidence?version=1"))
    if state["status"] != "verified":
        record["protocol_outcome"] = "Approved contract did not yield a verified construction"
        return False
    bundle = call(endpoint + "/bundle?version=1")
    (work / "recipient.zip").write_bytes(bundle)
    record.update(bundle_sha256=sha256(bundle).hexdigest(), receiver=q.check_portable(bundle, work))
    context = json.loads((work / "delivery/context.json").read_bytes())
    successful = context["model_calls"]
    receipts = q.compact_calls({"calls": dict(enumerate(successful)), "unsuccessful_calls": []})
    record["completed_model_receipts"] = sorted(receipts, key=lambda receipt: receipt["recorded_at"])
    record["independent_recipient_replay"] = replay_recipient(work)
    calls = (record.get("usage") or {}).get("recorded_application_model_calls")
    passed = (record["route"] == "research" and record["research_decision"] == "build"
              and record["acceptance"] == "pass" and "construct" in record["events"]
              and type(calls) is int and 4 <= calls <= CALL_CAP
              and {"discover", "challenge", "specification", "construct"} <= {r.get("stage") for r in receipts}
              and all(r.get("mode") == "local" and r.get("reported_model") == q.MODEL_ALIAS
                      and r.get("response_sha256") and r.get("application_model_calls") == 1 for r in receipts)
              and (record["acceptance_origin"] or {}).get("operator_supplemental_cases") == len(confirmations)
              and record["receiver"]["verified_exit"] == record["receiver"]["example_exit"] == 0
              and all(row["matched"] for row in record["independent_recipient_replay"]))
    record["protocol_outcome"] = ("Verified and replayed at the recipient" if passed
                                  else "Construction or recipient evidence did not meet the predeclared checks")
    return passed
