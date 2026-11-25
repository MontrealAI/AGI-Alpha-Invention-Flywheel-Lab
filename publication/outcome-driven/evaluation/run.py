# SPDX-License-Identifier: Apache-2.0
"""Run the matched local-model cohort against source-bound executor checkouts."""

from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
from inspect import signature
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter, sleep
from urllib.parse import urlsplit

from reference import REFERENCES


PREVIOUS_TOOLS = Path(__file__).resolve().parents[2] / "evidence-bound" / "evaluation"
sys.path.insert(0, str(PREVIOUS_TOOLS))
from run_missions import (ObservedTransport, approved_run, canonical, capture_usage, cpu_seconds, digest,
                          exact_row, reusable, save, source_identity, verified_json)


def context(case):
    return case["semantics"] + "\nSchema of the authorized tables: " + canonical(case["schema"]).decode()


def native_spec(case, expected, budget, provider, model):
    ident, data = case["dataset"], case["data"]
    fields = [[table, field] for table, columns in case["schema"].items() for field in columns]
    input_record = {"kind": "table", "origin": "AUTHORIZED_MISSION_INPUT", "version": case["version"],
                    "sha256": digest(canonical(data)), "facts": case["facts"]}
    claims = []
    for offset, (metric, unit, dimension) in enumerate(case["metrics"]):
        claim = {"id": metric, "dataset": ident, "tool": "run_table", "locator": ["rows", 0, offset],
                 "unit": unit, "dimension": dimension, "version": case["version"],
                 "requires": case["facts"], "required_fields": fields}
        if metric in expected["primary"]:
            claim["reference"] = {"value": expected["primary"][metric], "source": "Independent exact study reference"}
        claims.append(claim)
    return {"ambition": case["ambition"], "language": case["lang"], "provider": provider, "model": model,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "max_turns": budget["max_model_turns_each"], "max_output_tokens": budget["max_tokens_per_turn"],
            "max_actions": budget["max_tool_attempts"], "local_only": True,
            "tools": ["construct_table", "run_table", "read_artifact", "write_document"],
            "context": context(case), "requirements": {"approved_tables": {ident: data},
            "evidence": {"inputs": {ident: input_record}, "claims": claims}}}


def missing_exact(expected, texts):
    combined = "\n".join(texts).casefold()
    names = expected["missing"]
    for label, identity in zip(names, expected["identities"], strict=True):
        field = label.split(".")[-1].casefold()
        if label.casefold() not in combined and not (
                identity.casefold() in combined and (field in combined or re.search(r"durée|duration", combined))):
            return False
    return bool(names)


def contradiction(case, expected, texts):
    """Classify explicit assertions only. Retain original drafts for semantic review."""
    primary = expected["primary"]
    if primary.get("decision") == "ABSTAIN":
        numerical = re.compile(r"\b\d+(?:[.,/]\d+)?\s*(?:W|watts?)\b", flags=re.IGNORECASE)
        affirmative = re.compile(r"\b(?:has been (?:calculated|computed)|a été calculée?|nous avons calculé)\b", re.IGNORECASE)
        return any(numerical.search(text) or affirmative.search(text) for text in texts)
    for key, unit, _dimension in case["metrics"]:
        expression = re.compile(rf"\b{re.escape(key)}\b\s*[:=]\s*(-?\d+(?:[./]\d+)?)(?:\s*{re.escape(unit)})?",
                                flags=re.IGNORECASE)
        for text in texts:
            for match in expression.finditer(text):
                try:
                    if Fraction(match[1]) != Fraction(primary[key]):
                        return True
                except (ValueError, ZeroDivisionError):
                    return True
    return False


def numeric_correct(values, case, expected):
    return isinstance(values, dict) and set(values) == set(expected["primary"]) and exact_row(
        [[values.get(key) for key, _, _ in case["metrics"]]], case["metrics"], expected["primary"])


def retained_reuse(artifact, case, expected, reuse):
    if case["id"] not in reuse:
        return {"matched": False, "reason": "No numerical reuse case registered."}
    return reusable(artifact, {**case, "confirmation": reuse[case["id"]]}, expected["fresh_reuse"])


def native(case, expected, reuse, runtime, directory, provider, model, treatment, budget):
    from bridge.universal_missions import UniversalMissionService

    spec = native_spec(case, expected, budget, provider, model)
    save(directory / "authorized-spec.json", spec)
    keywords = {"schema_delivery": treatment[0], "outcome_assembly": treatment[1]}
    parameters = signature(UniversalMissionService).parameters
    if not set(keywords) <= set(parameters):
        if any(treatment):
            raise ValueError("Candidate executor lacks registered treatment controls.")
        keywords = {}
    service = UniversalMissionService(runtime, directory / "workspace", **keywords)
    try:
        run_id = service.submit(spec)["id"]
        service.start(run_id)
        stop = perf_counter() + budget["task_deadline_s"]
        while True:
            view = service.get(run_id)
            if not view["worker_active"] and view["status"] not in {"ready", "running"}:
                break
            if perf_counter() >= stop:
                raise TimeoutError("The registered whole-case deadline expired.")
            sleep(.2)
        archive = service.export(run_id)
    finally:
        service.close()
    save(directory / "executed-archive.json", archive)
    state, files = archive["state"], archive["files"]
    events = [e for e in state["events"] if e["kind"] == "tool_completed"]
    summaries = [e["detail"]["summary"] for e in state["events"] if e["kind"] == "route_proposed"]
    documents = [raw for name, raw in files.items() if name.endswith((".md", ".txt"))]
    refusals = [{"kind": e["kind"], **e["detail"]} for e in state["events"]
                if e["kind"] in {"tool_refused", "response_refused", "model_error", "claim_refused"}]
    evidence = view.get("evidence", {})
    projection = view.get("outcome", {})
    if treatment[1] and not projection:
        raise ValueError("Treatment B ran without its public outcome projection.")
    bad_draft = contradiction(case, expected, documents + summaries)
    options = {"raw_drafts": documents + summaries, "raw_explicit_contradiction": bad_draft,
               "outcome_surface": projection, "evidence": evidence}
    primary = expected["primary"]
    if primary.get("decision") == "ABSTAIN":
        if treatment[1]:
            unresolved = [item for item in projection.get("unresolved", []) if item.get("reason") == "REQUIRED_FIELD_MISSING"]
            precise = missing_exact(primary, [json.dumps(unresolved, ensure_ascii=False)])
            typed_missing = projection.get("status") == "ABSTAIN" and bool(unresolved)
            exposed = bool(projection.get("conclusions"))
        else:
            precise = missing_exact(primary, documents + summaries)
            typed_missing = evidence.get("status") == "ABSTAIN"
            exposed = bad_draft
        exact_abstention = precise and typed_missing and not exposed
        options.update(verdict="ACCEPT" if exact_abstention else "FAIL", precise_missing_cell=precise,
                       withheld_total=typed_missing, false_user_facing_acceptance=exposed)
    else:
        reports = projection.get("conclusions", []) if treatment[1] else evidence.get("claims", [])
        metric_ids = {key for key, _, _ in case["metrics"]}
        values = {x["id"]: x.get("value") for x in reports if x["status"] == "VERIFIED"}
        verified = numeric_correct(values, case, expected)
        bound_events = {x.get("event_sha256") for x in reports if x.get("id") in metric_ids and x["status"] == "VERIFIED"}
        scored_actions = []
        for event in events:
            if not approved_run(event, case):
                continue
            out = event["detail"]["outcome"]
            name = out["artifact"]
            attached = name in files and state["artifacts"][name]["sha256"] == out["artifact_sha256"]
            correct = exact_row(out["rows"], case["metrics"], primary)
            is_bound = event["sha256"] in bound_events
            reused = retained_reuse(files[name].encode(), case, expected, reuse) if attached and correct and is_bound else {"matched":False}
            scored_actions.append({"artifact": name, "bound": is_bound, "primary_exact": correct,
                                   "held_reuse": reused, "rows": out["rows"]})
        correct_reuse = any(a["held_reuse"]["matched"] for a in scored_actions)
        exposed = bool(values) and not verified or (bad_draft and not treatment[1])
        complete = verified and correct_reuse and not exposed
        options.update(verdict="ACCEPT" if complete else "FAIL", verified_primary=verified,
                       reusable_on_withheld=correct_reuse, approved_runs=scored_actions, false_user_facing_acceptance=exposed)
    return {**options, "mission_id": run_id, "workflow_status": view["status"], "refusals": refusals,
            "action_attempts": view["actions"], "actual_tool_events": len(events), "archive_sha256": archive["sha256"],
            "tool_input_origins": sorted({e["detail"]["outcome"]["input_origin"] for e in events
                                            if "input_origin" in e["detail"]["outcome"]})}


DIRECT_SCHEMA = {"type": "object", "properties": {
    "decision": {"enum": ["CONTINUE", "ANSWER", "ABSTAIN"]},
    "queries": {"type": "array", "maxItems": 4, "items": {"type": "string", "maxLength": 6000}},
    "result": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 100}},
    "missing": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 160}},
    "explanation": {"type": "string", "maxLength": 900}},
    "required": ["decision", "queries", "result", "missing", "explanation"], "additionalProperties": False}


def direct(case, expected, reuse, runtime, directory, provider, model, budget):
    from bridge.adapters import BridgeError, strict_json
    from bridge.mission_tools import _artifact, _replay

    public = {key: case[key] for key in ("ambition", "semantics", "lang", "dataset", "schema", "facts", "metrics", "data")}
    instruction = ("Solve the actual user task exactly. Use ordinary read-only SQLite with the supplied table schema and rows. "
        "Candidate SQL must be SELECT or WITH and return all registered values as exact integers or rational text. "
        "SQL may concatenate exact integer numerator and denominator with '||' and '/'. Use the user's language for explanation. "
        "Reuse the same query on other rows of these tables. On missing required observations, output ABSTAIN, pinpoint the cell, and "
        "return an empty result. A complete numeric result requires the same approved rows, executed query, and exact metric keys. "
        "Output one JSON object with decision, queries, result, missing and explanation. Tool checks report reference agreement separately.")
    observations, attempts, responses = [], 0, []
    scored = []
    end = perf_counter() + budget["task_deadline_s"]
    for turn in range(budget["max_model_turns_each"]):
        if perf_counter() >= end:
            break
        prompt = instruction + "\n" + canonical({"task": public, "previous": observations}).decode()
        try:
            response = strict_json(runtime.generate({"provider": provider, "model": model,
                "run_id": f"outcome-{case['id']}-direct-{turn+1}", "prompt": prompt, "max_output_tokens": budget["max_tokens_per_turn"],
                "json_mode": True, "json_schema": DIRECT_SCHEMA})["text"])
        except (BridgeError, ValueError) as error:
            observations.append({"error":getattr(error,"code",type(error).__name__)})
            break
        responses.append(response)
        observed = []
        for query in response["queries"]:
            if attempts >= budget["max_tool_attempts"]:
                break
            attempts += 1
            try:
                artifact = canonical(_artifact(case["schema"], query))
                got = _replay(artifact, case["data"])
            except ValueError as error:
                observed.append({"query": query, "refused": str(error)})
                continue
            agrees = "decision" not in expected["primary"] and exact_row(got["rows"], case["metrics"], expected["primary"])
            observed.append({"query": query, "rows": got["rows"], "reference_agreement": agrees,
                             "input_sha256": got["input_sha256"], "output_sha256": got["output_sha256"]})
            reuse_result = retained_reuse(artifact, case, expected, reuse) if agrees else {"matched":False}
            scored.append({"query": query, "primary_exact": agrees, "held_reuse": reuse_result})
        observations.append({"proposal": response, "tool_feedback": observed})
        if response["decision"] == "ABSTAIN" or response["decision"] == "ANSWER" and any(x["primary_exact"] for x in scored):
            break
    save(directory / "direct-tool-journal.json", observations)
    last = responses[-1] if responses else {"decision":"CONTINUE","result":{},"missing":[],"explanation":""}
    bad = contradiction(case, expected, [last["explanation"]])
    if expected["primary"].get("decision") == "ABSTAIN":
        precise = missing_exact(expected["primary"], last["missing"] + [last["explanation"]])
        exposed = bool(last["result"]) or last["decision"] == "ANSWER" or bad
        return {"verdict": "ACCEPT" if last["decision"] == "ABSTAIN" and precise and not exposed else "FAIL",
                "precise_missing_cell": precise, "false_user_facing_acceptance": exposed, "action_attempts": attempts,
                "final_response": last, "actual_tool_events": len(scored)}
    reported = numeric_correct(last["result"], case, expected)
    reused = any(a["held_reuse"]["matched"] for a in scored)
    exposed = last["decision"] == "ANSWER" and (not reported or not any(a["primary_exact"] for a in scored) or bad)
    return {"verdict": "ACCEPT" if last["decision"] == "ANSWER" and reported and reused and not exposed else "FAIL",
            "approved_runs": scored, "verified_primary": reported, "reusable_on_withheld": reused,
            "false_user_facing_acceptance": exposed, "final_response": last, "action_attempts": attempts,
            "actual_tool_events": len(scored)}


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("repo", "cases", "reuse", "oracle", "registration", "config", "result"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--phase", choices=("initial", "candidate", "conventional"), required=True)
    parser.add_argument("--provider", default="llama-cpp")
    parser.add_argument("--model", default="qwen3-8b-q4_k_m")
    args = parser.parse_args()
    study = verified_json(args.registration, args.registration_sha256)
    cohort = verified_json(args.cases, study["authorized_cases_sha256"])
    reuse = verified_json(args.reuse, study["withheld_reuse_sha256"])
    gold = verified_json(args.oracle, study["independent_oracle_sha256"])
    if digest(Path(__file__).with_name("reference.py").read_bytes()) != study["independent_reference_source_sha256"]:
        raise ValueError("The independent reference source changed.")
    ids = study["cohort"]["ordered_cases"]
    if ids != [c["id"] for c in cohort] or set(ids) != set(gold):
        raise ValueError("The exact registered denominator changed.")
    cases = {x["id"]: x for x in cohort}
    conventional = {}
    for ident, case in cases.items():
        before = perf_counter()
        reference = REFERENCES[case["oracle"]]
        got = {"primary": reference(case["data"])}
        if ident in reuse:
            got["fresh_reuse"] = reference(reuse[ident])
        if got != gold[ident]:
            raise ValueError("A registered exact expected result did not recompute.")
        conventional[ident] = {"verdict": "ACCEPT", "task_elapsed_seconds": perf_counter()-before, **got}
    args.result.mkdir(parents=True, exist_ok=False, mode=0o700)
    if args.phase == "conventional":
        save(args.result / "report.json", {"cases": conventional, "active_model_dispatches": 0,
                                            "independent_reference_sha256": study["independent_reference_source_sha256"]})
        return
    config = json.loads(args.config.read_bytes())
    provider = config["providers"][args.provider]
    if config.get("local_only") is not True or config.get("allow_paid_requests") is not False or config.get("session_budget_usd") != 0 or (
            urlsplit(provider["base_url"]).hostname not in {"127.0.0.1", "::1"} or provider.get("key_env")):
        raise ValueError("The matched campaign requires credential-free loopback, local-only execution and zero paid requests.")
    budget = study["budget"]
    frozen = source_identity(args.repo)
    checkout = subprocess.run(["git", "-C", str(args.repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    source_revision = checkout.stdout.strip() or (study["source_baseline"] if args.phase == "initial" else None)
    sys.path.insert(0, str(args.repo.resolve() / "products/alpha-genesis-harness"))
    from bridge.adapters import Runtime, transport

    dispatch = study["execution_order"][args.phase]
    records = []
    save(args.result / "installation.json", {"phase": args.phase, "source_revision": source_revision or None,
        "source_sha256": digest(canonical(frozen)), "source_files": frozen, "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "case_registration_sha256": args.registration_sha256, "config_sha256":digest(args.config.read_bytes()),
        "model":args.model,"provider":args.provider,"order":dispatch,"actual_config":config})
    for ident, arm in dispatch:
        directory = args.result / f"{ident}-{arm}"
        directory.mkdir(mode=0o700)
        observer = ObservedTransport(transport, directory)

        def deterministic(url, headers, body=None, timeout=60):
            return observer(url, headers, {**body, "temperature": budget["provider_temperature"], "seed": budget["provider_seed"]}, timeout)

        runtime = Runtime(config, sender=deterministic)
        case = cases[ident]
        print("BEGIN", ident, arm, flush=True)
        begin, cpu0 = perf_counter(), cpu_seconds()
        try:
            if arm == "direct":
                scored = direct(case, gold[ident], reuse, runtime, directory, args.provider, args.model, budget)
            else:
                scored = native(case, gold[ident], reuse, runtime, directory, args.provider, args.model,
                                study["treatments"][arm], budget)
        except TimeoutError as error:
            scored = {"verdict": "INTERRUPTED", "reason": str(error), "false_user_facing_acceptance": None}
        measured = {"case":ident,"arm":arm,**scored,"task_elapsed_seconds":perf_counter()-begin,
                    "orchestrator_cpu_seconds":cpu_seconds()-cpu0,"observed_provider_dispatches":len(observer.records),
                    "observed_usage":capture_usage(observer.records),"operator_actions_after_case_start":0,
                    "operator_preparation_and_review_seconds":None,"complete_economic_cost_known":False,"paid_requests":0,
                    "provider_elapsed_seconds":sum(x["transport_seconds"] for x in observer.records)}
        save(directory / "result.json", measured)
        records.append(measured)
        print("END", ident, arm, measured["verdict"], measured["observed_provider_dispatches"], flush=True)
    if source_identity(args.repo) != frozen:
        raise ValueError("The executor checkout changed during the registered run.")
    save(args.result / "report.json", {"cases":records, "active_model_dispatches":sum(x["observed_provider_dispatches"] for x in records)})


if __name__ == "__main__":
    main()
