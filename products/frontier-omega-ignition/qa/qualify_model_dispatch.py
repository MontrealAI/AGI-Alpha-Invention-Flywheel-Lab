"""Qualify real local model selection, worker construction, portable replay and abstention.

Use fresh work and output paths outside the repository. The input is public archive
metadata. No paid service, remote model, scripted model answer or production data is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import resource
from statistics import median
import sys
import time

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))

from field_trials import observe
from ignition.construction import execute
from ignition.controller import Controller
from ignition.provider import LocalProvider
from ignition.store import Store
import qualify_live as qualification

INPUTS = PRODUCT / "action_study/qualification_choice/sources"
TRAIN = "django__django"
HOLDOUT = ("psf__requests", "pydata__xarray")


def evidence(name):
    path = INPUTS / (name + ".json")
    raw = path.read_bytes()
    packet = json.loads(raw)
    rows = []
    for values in packet["rows"]:
        source = dict(zip(packet["row_fields"], values, strict=True))
        prefix = packet["prefixes"][source["B_prefix_index"]]
        match = re.search(r'"resolved": (true|false)(?=[,}])', prefix)
        if match is None or type(source["A_resolved"]) is not bool:
            raise ValueError("Archive lacks a bounded resolution observation")
        rows.append({"task": source["id"], "first_run": source["A_resolved"],
                     "second_run": match.group(1) == "true"})
    return rows, hashlib.sha256(raw).hexdigest()


def labelled(rows):
    return {"input": {"rows": rows}, "expected": {"rows": [
        {"task": row["task"], "resolved": row["second_run"]} for row in rows]}}


def mission():
    sample, fingerprint = evidence(TRAIN)
    # Clean training rows from this publisher cannot distinguish the two runs.
    development = [next(row for row in sample if row["first_run"] == row["second_run"] == state)
                   for state in (True, False)]
    cases = []
    sources = {TRAIN: fingerprint}
    for repo in HOLDOUT:
        rows, sources[repo] = evidence(repo)
        if not any(row["first_run"] != row["second_run"] for row in rows):
            raise ValueError("A withheld archive must distinguish the two sources")
        cases.append({"name": repo, **labelled(rows)})
    purpose = "Build the release reviewer's index of results from the second recorded run."
    definition = {"input_fields": ["task", "first_run", "second_run"], "extra_fields": "reject",
                  "targets": [{"name": "task", "type": "text"}, {"name": "resolved", "type": "boolean"}],
                  "demonstrations": [labelled(development)]}
    contract = {"kind": "record_migration", "purpose": purpose, "definition": definition, "cases": cases}
    return {"purpose": purpose, "beneficiary": "MONTREAL.AI research release reviewer",
            "requirements": ["Copy task unchanged.", "For resolved use the second_run field."],
            "authority": {"local_model": True}, "resources": {"max_model_calls": 1, "max_repairs": 0},
            "construction_spec": contract}, sources


def compare(artifact, cases, incumbent):
    """Time the same in-memory public request and compare returned outputs."""
    rows = []
    for case in cases:
        argument = case["input"]
        samples = {"artifact": [], "incumbent": []}
        matches = True
        for turn in range(7):
            order = ("artifact", "incumbent") if turn % 2 == 0 else ("incumbent", "artifact")
            for name in order:
                start = time.perf_counter_ns()
                answer = execute(artifact, argument) if name == "artifact" else incumbent(argument)
                samples[name].append(time.perf_counter_ns() - start)
                matches = matches and answer == case["expected"]
        rows.append({"case": case["name"], "both_match_expected": matches, "pairs": 7,
                     "artifact_median_ns": median(samples["artifact"]),
                     "incumbent_median_ns": median(samples["incumbent"])})
    return rows


def project(argument):
    return {"rows": [{"task": row["task"], "resolved": row["second_run"]} for row in argument["rows"]]}


def exercise(folder, provider, record):
    brief, inputs = mission()
    store = Store(folder / "state")
    ctrl = Controller(store, provider_factory=lambda: provider)
    rid, revision = ctrl.create({"mission": brief, "request_id": "review-archive-second-run"})
    ctrl.advance(rid, revision)
    state = store.get(rid)
    calls = qualification.compact_calls(state)
    research = state.get("mapping_choice") or {}
    record.update(source_sha256=inputs, status=state["status"], error=state.get("error"),
                  candidate_ids=[c["id"] for c in research.get("candidates", [])],
                  resolution=state.get("mapping_resolution"), calls=calls,
                  contract_sha256=state.get("contract_sha256"),
                  artifact_sha256=(state.get("artifact") or {}).get("sha256"),
                  acceptance=(state.get("evaluation") or {}).get("status"),
                  ordinary_comparator=(state.get("evaluation") or {}).get("comparison"),
                  construction_attempts=state.get("construction_attempts"),
                  withheld_archives=[{"repository": c["name"], "records": len(c["input"]["rows"])}
                                     for c in brief["construction_spec"]["cases"]])
    portable = {}
    if state["status"] == "verified":
        archive = ctrl.deliver(rid, revision)
        portable = qualification.check_portable(archive, folder)
        record.update(bundle_sha256=hashlib.sha256(archive).hexdigest(), recipient=portable)
        (folder / "recipient.zip").write_bytes(archive)
    # A competent conventional reviewer can implement the requested column by name.
    # Rerun that direct extraction on every withheld archive in addition to the
    # controller's conventional example-based comparator. No stronger claim follows from a tie.
    direct_checks = (compare(state["artifact"], brief["construction_spec"]["cases"], project)
                     if state.get("artifact") else [])
    record["explicit_free_projection"] = direct_checks
    # The underdetermined mission goes through the ordinary controller. There
    # is intentionally no paid or local inference if evidence cannot distinguish
    # two inputs that agree on the public development sample.
    ambiguous, _ = mission()
    ambiguous["purpose"] = "Create a task-level research review index of recorded outcomes."
    ambiguous["construction_spec"]["purpose"] = ambiguous["purpose"]
    ambiguous["requirements"] = ["Copy task unchanged.", "Preserve the resolution outcome for each task."]
    ambiguous["resources"]["direct_method"] = "model_choice"
    aid, av = ctrl.create({"mission": ambiguous, "request_id": "review-archive-indeterminate"})
    ctrl.advance(aid, av)
    abstain = store.get(aid)
    record["abstention"] = {"status": abstain["status"], "model_calls": abstain.get("attempts", 0),
                            "artifact": bool(abstain.get("artifact")), "stage": abstain["stage"],
                            "last_event": abstain["events"][-1]["message"]}
    selected = record["resolution"] or {}
    valid = (state["status"] == "verified" and len(record["candidate_ids"]) > 1
             and selected.get("origin") == "model" and selected.get("choice") in record["candidate_ids"]
             and len(calls) == 1 and calls[0].get("stage") == "choose_hypothesis"
             and calls[0].get("mode") == "local" and calls[0].get("reported_model") == qualification.MODEL_ALIAS
             and calls[0].get("application_model_calls") == 1 and calls[0].get("status") == "completed"
             and record["acceptance"] == "pass" and direct_checks and all(c["both_match_expected"] for c in direct_checks)
             and portable.get("verified_exit") == portable.get("example_exit") == 0
             and abstain["status"] == "deferred" and abstain.get("attempts", 0) == 0 and not abstain.get("artifact"))
    return valid


def cpu_time():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + children.ru_utime + children.ru_stime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("work", "assets", "output"):
        parser.add_argument("--" + key, required=True, type=Path)
    parser.add_argument("--research", action="store_true", help="Run open discovery, critique and construction on the published archive")
    args = parser.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    if (work.exists() or output.exists() or work.is_relative_to(qualification.REPO)
            or output.is_relative_to(qualification.REPO) or output.is_relative_to(work)):
        parser.error("Use fresh private work and separate output paths outside the checkout.")
    work.mkdir(mode=0o700, parents=True)
    output.parent.mkdir(exist_ok=True, parents=True)
    record = {"protocol": "ignition.pinned-construction-selection.v1", "qualified": False,
              "started_at": qualification.stamp(), "hardware": observe.hardware(), "model": qualification.MODEL_ALIAS,
              "cash_collected_usd": 0, "economic_cost": None,
              "scope": "Bounded model selection from independently generated, content-identified mappings. "
                       "Public input, fresh execution. No general frontier discovery or commercial benefit inferred."}
    record["hardware"]["threads"] = min(4, record["hardware"]["threads"])
    if args.research:
        record.update(protocol="ignition.research-construction-selection.v1",
                      scope="Public instrument receipt. Real model discovery, selection and construction with "
                            "a supplied authorized contract. No purchased or deployed beneficiary infrastructure.")
    start, cpu = time.monotonic(), cpu_time()
    try:
        record["source_revision"] = qualification.checked_source()
        record["runtime_source_sha256"] = qualification.runtime_source()
        binary, weights = observe.prepare(args.assets.resolve(), work, record)
        with observe.server(binary, weights, work, record, "selection",
                            context_tokens=12288 if args.research else 6144) as port:
            model = LocalProvider("llama-cpp", qualification.MODEL_ALIAS, port, observe.PINS.MODEL_SHA,
                                  output_tokens=2048 if args.research else 128, timeout=600 if args.research else 120,
                                  streaming=True, schema_output=True)
            if args.research:
                from qa.qualify_research_dispatch import exercise as investigate
                passed = investigate(work, model, record)
            else:
                passed = exercise(work, model, record)
        record["qualified"] = bool(passed and qualification.checked_source() == record["source_revision"]
                                   and qualification.runtime_source() == record["runtime_source_sha256"])
    except (OSError, ValueError, RuntimeError, qualification.Blocked) as error:
        record["error_class"] = type(error).__name__
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
    finally:
        record.update(finished_at=qualification.stamp(), wall_seconds=round(time.monotonic() - start, 3),
                      cpu_seconds=round(cpu_time() - cpu, 3))
        observe.write(output, record)
    print(json.dumps({k: record.get(k) for k in ("source_revision", "qualified", "status", "abstention")}))
    return 0 if record["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
