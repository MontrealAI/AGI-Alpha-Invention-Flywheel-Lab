"""Frozen-source, verifier-selected engineering generalization checks."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FREEZE_SHA256 = "fa2a87c8bc6a41c4444fea28b10d8d09e25971e06d1e61d0cbb84ba399e2a55c"
PROTOCOL_SHA256 = "027d44b1cc93defc82076ee5ac1a4f0012168ff6bcd70202273ba0e1f69e4950"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def fresh_tasks():
    selected_after_freeze = [
        ("artifact-publication", ["reserve", "manifest", "build", "publish", "complete"]),
        ("measurement-acquisition", ["reserve", "start", "work", "manifest", "complete"]),
        ("checkpoint-export", ["reserve", "start", "build", "publish", "complete"]),
        ("transaction-journal", ["reserve", "manifest", "work", "publish", "complete"]),
    ]
    tasks = []
    for family, phases in selected_after_freeze:
        dependencies = [list(edge) for edge in zip(phases, phases[1:])]
        for variant in ("ordered", "representation-permuted"):
            listed = phases if variant == "ordered" else list(reversed(phases))
            tasks.append({"id": family + "/" + variant, "phases": listed, "dependencies": dependencies,
                          "family_scope": "Abstract evidence protocol; no real domain delivery is claimed."})
    return tasks


def independent_valid(task, program):
    if not isinstance(program, dict) or set(program) != {"body", "protected_from"}:
        return False
    body, guard = program["body"], program["protected_from"]
    return (isinstance(body, list) and len(body) == len(task["phases"]) and len(set(body)) == len(body)
            and set(body) == set(task["phases"]) and body[0] == "reserve" and type(guard) is int
            and 0 <= guard <= len(body) and all(body.index(a) < body.index(b) for a, b in task["dependencies"]))


def conventional(task):
    remaining, ordered = set(task["phases"]), []
    while remaining:
        ready = sorted(p for p in remaining if all(a in ordered for a, b in task["dependencies"] if b == p))
        if not ready:
            raise ValueError("INFEASIBLE_TASK")
        phase = ready[0]
        ordered.append(phase)
        remaining.remove(phase)
    return {"body": ordered, "protected_from": 1}


def graph_checks(strategy):
    donor = {"id": "guarded-transaction", "nodes": [
        {"id": "g", "kind": "guard", "unit": "event"},
        {"id": "m", "kind": "effect", "unit": "event"},
        {"id": "a", "kind": "action", "unit": "event"}],
        "relations": [["g", "protects", "m"], ["m", "precedes", "a"]],
        "conditions": {"interrupt": "catchable"}}
    target = {"id": "fresh-measurement-scope", "nodes": [
        {"id": "receiver", "kind": "action", "unit": "event"},
        {"id": "cleanup", "kind": "guard", "unit": "event"},
        {"id": "capture", "kind": "effect", "unit": "event"}],
        "relations": [["cleanup", "protects", "capture"], ["capture", "precedes", "receiver"]],
        "conditions": {"interrupt": "catchable", "boundary": "measurement"},
        "changed_assumptions": ["Persistence after host loss is outside this target."]}
    cases = []
    for name, expected in (("different-labels-compatible", True), ("incompatible-unit", False),
                           ("reversed-causality", False), ("similar-labels-no-relation", False)):
        changed = json.loads(json.dumps(target))
        changed["id"] = name
        if name == "incompatible-unit":
            changed["nodes"][1]["unit"] = "joule"
        elif name == "reversed-causality":
            changed["relations"][0] = ["capture", "protects", "cleanup"]
        elif name == "similar-labels-no-relation":
            changed = json.loads(json.dumps(donor))
            changed["id"] = name
            changed["relations"] = []
        actual = strategy.discover([donor], changed)[0]
        cases.append({"name": name, "expected_applicable": expected, "actual": actual,
                      "passed": actual["applicable"] is expected})
    return cases


def evaluate(output):
    started, cpu = time.monotonic(), time.process_time()
    freeze_path, protocol_path = ROOT / "campaign/cycle-004/FREEZE.json", ROOT / "verification/cycle004_protocol.json"
    if digest(freeze_path) != FREEZE_SHA256 or digest(protocol_path) != PROTOCOL_SHA256:
        raise ValueError("FREEZE_OR_PROTOCOL_CHANGED")
    frozen = json.loads(freeze_path.read_text())
    for relative, expected in frozen["sources"].items():
        if (ROOT / relative).is_symlink() or digest(ROOT / relative) != expected:
            raise ValueError("FROZEN_SOURCE_CHANGED " + relative)
    output.mkdir(parents=True, exist_ok=False)
    write(output / "FREEZE_RECEIPT.json", {"freeze_sha256": FREEZE_SHA256, "protocol_sha256": PROTOCOL_SHA256,
          "verified_source_identities": frozen["sources"], "selected_cases_after_source_verification": True,
          "verifier_sha256": digest(__file__)})
    sys.path.insert(0, str(ROOT))
    from flywheel import strategy, sandbox, evidence_executor
    qualification = sandbox.qualify()
    write(output / "SANDBOX.json", qualification)
    if not qualification["qualified"]:
        raise ValueError("SANDBOX_UNQUALIFIED")
    tasks = fresh_tasks()
    write(output / "EXPOSED_TASKS.json", tasks)
    operator = {"operator": "protect_initialization", "language": "bounded-evidence/v1"}
    records = []
    for task_index, task in enumerate(tasks):
        arms = {}
        for name in ("inheritance", "ordinary_reuse", "reset", "operator_removed", "conventional_wrap_all"):
            arm_started = time.monotonic()
            if name == "conventional_wrap_all":
                built = {"status": "constructed", "program": conventional(task), "attempts": [], "rule": "independent topological sort plus wrap-all"}
            else:
                built = strategy.synthesize(task, [], max_candidates=64, inherited=operator if name in {"inheritance", "ordinary_reuse"} else None)
            program = built["program"]
            valid = independent_valid(task, program)
            checks = []
            if valid:
                for phase in program["body"][1:]:
                    run = sandbox.run(ROOT / "flywheel/strategy.py", "interpret",
                          {"task": task, "program": program, "interrupt_at": phase}, frozen["sources"]["flywheel/strategy.py"])
                    result = run.get("worker", {}).get("result", {})
                    destination = output / ("task-%02d-" % task_index + name + "-" + phase)
                    actual = evidence_executor.execute(task, program, destination, interrupt_at=phase)
                    snapshot = {p.name: digest(p) for p in destination.iterdir() if p.is_file()}
                    refused = False
                    try:
                        evidence_executor.execute(task, program, destination)
                    except FileExistsError:
                        refused = True
                    after = {p.name: digest(p) for p in destination.iterdir() if p.is_file()}
                    passed = (run["state"] == "COMPLETE" and result.get("interrupted_marker") is True
                              and actual.get("interrupted_marker") is True and "COMPLETE.json" not in snapshot
                              and "INTERRUPTED.json" in snapshot and refused and snapshot == after)
                    checks.append({"phase": phase, "passed": passed, "confined_interpreter": run,
                                   "actual_executor": actual, "files_sha256": snapshot,
                                   "replay_refused_unchanged": refused and snapshot == after})
                success_output = output / ("task-%02d-" % task_index + name + "-success")
                success = evidence_executor.execute(task, program, success_output)
                normal_passed = success["completed"] and (success_output / "COMPLETE.json").exists()
            else:
                normal_passed, success = False, None
            arms[name] = {"construction": built, "independently_valid": valid, "normal_execution": success,
                          "checks": checks, "passed": valid and normal_passed and all(c["passed"] for c in checks),
                          "wall_seconds": time.monotonic() - arm_started}
        records.append({"task": task, "arms": arms})
        if time.monotonic() - started > 120:
            raise RuntimeError("VERIFIER_WALL_ALLOCATION_EXHAUSTED")
    graph = graph_checks(strategy)
    scores = {name: sum(r["arms"][name]["passed"] for r in records) for name in records[0]["arms"]}
    report = {"schema": "agi-alpha-cycle004-independent-fresh-engineering/v1", "freeze_sha256": FREEZE_SHA256,
              "protocol_sha256": PROTOCOL_SHA256, "cases": records, "scores_out_of_8": scores,
              "structural_checks": graph, "all_structural_checks_passed": all(c["passed"] for c in graph),
              "ordinary_reuse_equivalent_outcomes": all(r["arms"]["inheritance"]["passed"] == r["arms"]["ordinary_reuse"]["passed"] for r in records),
              "resources": {"wall_seconds": time.monotonic()-started, "verifier_cpu_seconds": time.process_time()-cpu,
                            "complete_lifecycle_cost": None, "max_search_candidates": 64},
              "verdict": "Report every score; no superclass claim follows. Strong conventional and equivalent-content reuse may tie or outperform inheritance.",
              "confirmation_alpha_spent": 0,
              "limitations": ["Eight abstract evidence-protocol tasks from one supplied finite grammar, not eight consequential scientific domains.",
                              "No live model, physical test, buyer delivery, cost superiority, progressive discovery-policy learning, or earned-funded successor.",
                              "Procedural verifier separation only; same host, filesystem, libraries and model family."]}
    write(output / "REPORT.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.output.resolve())
    print(json.dumps({"scores_out_of_8": result["scores_out_of_8"], "structural_checks": result["all_structural_checks_passed"]}))
