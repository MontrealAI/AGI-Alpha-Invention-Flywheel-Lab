"""Post-freeze whole-path engineering verification; no evaluator-supplied operator."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import resource
import shutil
import sys
import tempfile
import time

FREEZE_SHA256 = "b14c94567111814a5dc10e7ce97bcfcff1041bcc7cb1f8118622c2d508b060ea"
PROTOCOL_SHA256 = "2435ffbfa46cbba96f5184d0eb0606bb20b4a97c883475d4b6758e0a6c7bfe64"
ADDENDUM_SHA256 = "5baef3b9f8fd827dac1f9d6459615d6ec9af028fafc4361945e7bae0bb3b0f24"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write("\n")


def snapshot(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob("*") if p.is_file()} if path.exists() else {}


def graph(task):
    return {"id": task["id"], "nodes": [{"id": p["id"], "event": p["id"], "kind": p["kind"], "unit": p["unit"]} for p in task["phases"]],
            "relations": [[d, "precedes", p["id"]] for p in task["phases"] for d in p["deps"]], "conditions": copy.deepcopy(task["conditions"])}


def task(index, shuffled=True):
    rng = random.Random(int(FREEZE_SHA256[:16], 16) + 1009*index)
    ids = ["v%02d-%08x" % (index, rng.getrandbits(32)) for _ in range(4)]
    phases = [{"id": identity, "kind": kind, "unit": "event", "deps": [] if i == 0 else [ids[i-1]]}
              for i, (identity, kind) in enumerate(zip(ids, ("reserve", "capture", "compute", "commit")))]
    if index % 2:
        phases[2]["deps"].append(ids[0])
    if index % 3 == 0:
        phases[3]["deps"].append(ids[0])
    if shuffled:
        rng.shuffle(phases)
    return {"id": "verifier-005-target-%02d" % index, "phases": phases,
            "conditions": {"failure": "catchable_exception", "effects": "exclusive_local_output", "target_boundary": "bounded-%d" % (index % 3)}}


def source_donor():
    return {"id": "independent-supplied-transaction-fragment", "nodes": [
        {"id": role, "kind": kind, "unit": "event"} for role, kind in
        (("custody", "reserve"), ("first_mutation", "capture"), ("productive_action", "compute"), ("terminal_publication", "commit"))],
        "relations": [["custody", "precedes", "first_mutation"], ["first_mutation", "precedes", "productive_action"], ["productive_action", "precedes", "terminal_publication"]],
        "conditions": {"failure": "catchable_exception", "effects": "exclusive_local_output"},
        "obligations": [{"kind": "protect", "role_ids": ["first_mutation"]}],
        "provenance": "Verifier supplies a disclosed partial source mechanism; matcher chooses the target role correspondence. No complete repair or operator is supplied."}


def independent_accept(task_value, program, verification, check_root, executor):
    errors = []
    if program is None:
        return {"passed": False, "errors": ["NO_EXECUTABLE_PROGRAM"], "refused": True}
    nodes = {p["id"]: p for p in task_value["phases"]}
    order = program.get("order", [])
    if len(order) != len(nodes) or len(set(order)) != len(order) or set(order) != set(nodes):
        return {"passed": False, "errors": ["PHASE_IDENTITY_MISMATCH"]}
    if nodes[order[0]]["kind"] != "reserve" or nodes[order[-1]]["kind"] != "commit" or any(order.index(d) >= order.index(p) for p in order for d in nodes[p]["deps"]):
        errors.append("CAUSAL_OR_TERMINAL_ORDER")
    normal = check_root / "normal"
    try:
        completed = json.loads((normal / "COMPLETE.json").read_text())
        if completed != {"phase": order[-1], "kind": "commit", "task": task_value["id"]}:
            errors.append("NORMAL_COMPLETION_IDENTITY")
        for index, phase in enumerate(order[1:-1], 1):
            actual = json.loads((normal / ("phase-%03d.json" % index)).read_text())
            if actual != {"phase": phase, "kind": nodes[phase]["kind"], "task": task_value["id"]}:
                errors.append("NORMAL_EFFECT_IDENTITY")
    except (OSError, ValueError):
        errors.append("NORMAL_OUTPUT_UNAVAILABLE")
    by_phase = {row["phase"]: row for row in verification.get("checks", [])}
    for index, phase in enumerate(order):
        actual_root = check_root / ("failure-%03d" % index)
        row = by_phase.get(phase, {})
        if nodes[phase]["kind"] == "reserve":
            if actual_root.exists():
                errors.append("RESERVATION_INTERRUPTION_CREATED_OUTPUT")
            continue
        files = snapshot(actual_root)
        if "COMPLETE.json" in files or "INTERRUPTED.json" not in files:
            errors.append("UNSAFE_INTERRUPTION:" + phase)
        else:
            marker = json.loads((actual_root / "INTERRUPTED.json").read_text())
            if marker.get("failure_at") != phase or marker.get("state") != "INCOMPLETE":
                errors.append("WRONG_INTERRUPTION_IDENTITY:" + phase)
        if files != row.get("actual", {}).get("files_sha256"):
            errors.append("ACTUAL_FILE_HASH_MISMATCH:" + phase)
        confined = row.get("confined", {})
        observed = confined.get("worker", {}).get("result", {})
        if confined.get("state") != "COMPLETE" or observed.get("failure_at") != phase or observed.get("interrupted_marker") is not True or observed.get("complete_exists") is not False:
            errors.append("CONFINED_INTERPRETER_FAILED:" + phase)
        before = snapshot(actual_root)
        refused = False
        try:
            executor.execute(task_value, program, actual_root)
        except FileExistsError:
            refused = True
        if not refused or snapshot(actual_root) != before:
            errors.append("REPLAY_NOT_REFUSED_UNCHANGED:" + phase)
    return {"passed": not errors, "errors": errors, "program_sha256": digest(program), "raw_check_root": str(check_root)}


def evaluate(root, output):
    started, cpu = time.monotonic(), time.process_time()
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)
    frozen_path = root / "campaign/cycle-005/FREEZE.json"
    pins = {frozen_path: FREEZE_SHA256, root / "verification/cycle005_protocol.json": PROTOCOL_SHA256,
            root / "verification/cycle005_protocol_addendum.json": ADDENDUM_SHA256}
    if any(sha(path) != expected for path, expected in pins.items()):
        raise ValueError("VERIFIER_FREEZE_OR_PROTOCOL_MISMATCH")
    frozen = json.loads(frozen_path.read_text())
    for relative, expected in frozen["sources"].items():
        if (root / relative).is_symlink() or sha(root / relative) != expected:
            raise ValueError("BUILDER_SOURCE_CHANGED " + relative)
    output.mkdir(parents=True, exist_ok=False)
    write(output / "FREEZE_RECEIPT.json", {"source_freeze_sha256": FREEZE_SHA256, "protocol_sha256": PROTOCOL_SHA256,
          "addendum_sha256": ADDENDUM_SHA256, "sources": frozen["sources"], "verifier_sha256": sha(__file__),
          "selection": "Exact fresh cases selected after checking this final source freeze; now exposed engineering regressions."})
    sys.path.insert(0, str(root))
    from mechanisms import pipeline, mapping, memory, construct, criticism, executor
    from flywheel import sandbox, retention
    qualified = sandbox.qualify()
    write(output / "SANDBOX.json", qualified)
    if not qualified["qualified"]:
        raise ValueError("SANDBOX_UNQUALIFIED")
    development = task(90, False)
    development["conditions"].pop("target_boundary")
    donors = [source_donor()]
    memory_root = output / "acquired-memory"
    developed = pipeline.develop(development, donors, graph(development), output / "development", memory_root)
    dev_check = json.loads((output / "development/after-check/VERIFICATION.json").read_text())
    dev_accepted = independent_accept(development, developed["after"]["program"], dev_check, output / "development/after-check", executor)
    retained = developed.get("retained")
    lineage = bool(retained) and developed["before_passed"] is False and dev_accepted["passed"]
    if retained:
        record = json.loads((memory_root / (retained["id"] + ".json")).read_text())
        lineage = lineage and digest(record) == retained["id"] and record["provenance"]["origin"] == "derived-from-verified-before-after-delta" and bool(record["generative_operator"]["program"]["role_deltas"])
    else:
        record = None
    fresh = [task(index) for index in range(8)]
    write(output / "EXPOSED_TASKS.json", {"development": development, "donors": donors, "fresh_successors": fresh})
    cases = []
    for index, target in enumerate(fresh):
        arms = {}
        for mode in ("inheritance", "ordinary", "removed", "conventional", "reset"):
            location = output / ("fresh-%02d-" % index + mode)
            result = pipeline.reuse(target, donors, graph(target), location, memory_root, mode)
            accepted = independent_accept(target, result["construction"].get("program"), result["verification"], location / "checks", executor)
            instantiation = result["construction"].get("memory_instantiation", {})
            inherited_link = mode not in ("inheritance", "ordinary") or (instantiation.get("fresh_target") is True and instantiation.get("record_sha256") == retained["id"] and instantiation.get("learned_role_delta_count", 0) > 0)
            arms[mode] = {"reported_passed": result["passed"], "independent": accepted, "actual_retained_lineage": inherited_link,
                          "receipt": str(location.relative_to(output) / "RESULT.json"), "receipt_sha256": sha(location / "RESULT.json")}
        cases.append({"task": target, "arms": arms})
    scores = {mode: sum(case["arms"][mode]["independent"]["passed"] for case in cases) for mode in cases[0]["arms"]}
    no_mapping = pipeline.develop(development, donors, graph(development), output / "no-mapping", output / "no-mapping-memory", use_mapping=False)
    no_critic = pipeline.develop(development, donors, graph(development), output / "no-critic", output / "no-critic-memory", use_critic=False)
    alternate_donors = copy.deepcopy(donors)
    alternate_donors[0]["obligations"][0]["role_ids"] = ["productive_action"]
    alternate = pipeline.develop(development, alternate_donors, graph(development), output / "different-mapped-role", output / "different-role-memory")
    role_effect = developed["before"]["program"]["protected"] != alternate["before"]["program"]["protected"]
    critic_record = json.loads((output / "development/CRITICISM.json").read_text())
    established = [row for row in critic_record["adjudications"] if row["status"] == "established"]
    witnessed_locations = sorted({row["objection"]["reproduction"]["interrupt_at"] for row in established})
    location_sensitive = len(witnessed_locations) >= 2 and all(set(rule["phase_ids"]) <= set(witnessed_locations) for rule in developed["obligations"])
    empty = pipeline.reuse(fresh[0], donors, graph(fresh[0]), output / "empty-memory", output / "no-records-present", "inheritance")
    incompatible = copy.deepcopy(fresh[0]); incompatible["conditions"]["failure"] = "power_loss"
    refused_scope = pipeline.reuse(incompatible, donors, graph(incompatible), output / "incompatible-memory-scope", memory_root, "inheritance")
    bad_units = graph(development); bad_units["nodes"][1]["unit"] = "joule"
    refused_mapping = pipeline.develop(development, donors, bad_units, output / "incompatible-mapping", output / "incompatible-mapping-memory")
    controls = {"no_mapping": {"status": no_mapping["status"], "retained": no_mapping.get("retained"), "scope": "Explicit structural-lineage admission gate; not a measured necessity of mapping for every useful solution."},
                "no_critic": {"after_passed": no_critic.get("after_passed"), "retained": no_critic.get("retained")},
                "changed_role_changes_actual_construction": role_effect, "critic_constraints_follow_multiple_witness_locations": location_sensitive,
                "witness_locations": witnessed_locations, "empty_memory_refuses_without_default_operator": empty["construction"].get("program") is None,
                "incompatible_memory_scope_refused": refused_scope["construction"].get("program") is None,
                "incompatible_mapping_refused": refused_mapping["status"] == "refused"}
    if record:
        initial = snapshot(memory_root)
        duplicate = retention.store(memory_root, record)
        controls["duplicate_immutable"] = duplicate == retained["id"] and snapshot(memory_root) == initial
        wrong_receipt = copy.deepcopy(developed["verification_receipt"]); wrong_receipt["after_sha256"] = "0"*64
        try:
            memory.acquire(development, developed["mapping"], developed["before"]["program"], developed["after"]["program"], developed["obligations"], wrong_receipt, root)
            controls["wrong_hash_acquisition_refused"] = False
        except ValueError:
            controls["wrong_hash_acquisition_refused"] = True
        with tempfile.TemporaryDirectory(prefix="cycle005-source-negative-") as temporary:
            damaged = Path(temporary)
            dependencies = {record["instrument"]["path"], *record["provenance"]["dependency_sha256"]}
            for relative in dependencies:
                target = damaged / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(root / relative, target)
            leaf = damaged / record["instrument"]["path"]; leaf.write_bytes(leaf.read_bytes() + b"\n# corruption test\n")
            corrupted = memory.generate(memory_root, fresh[0], donors, damaged, 64)
            controls["corrupted_source_refused"] = corrupted.get("program") is None
            write(output / "CORRUPTED_SOURCE_CONTROL.json", corrupted)
    bundle_target = task(71)
    bundle_target["conditions"].pop("target_boundary")
    combined = pipeline.combinations(development, donors, graph(development), output / "bundles", output / "bundle-memory", successor_task=bundle_target)
    bundle_scores = {}
    for mode, arm in combined["arms"].items():
        checked = []
        for index, item in enumerate(arm["checks"]):
            accepted = independent_accept(bundle_target, item["construction"].get("program"), item["verification"], output / "bundles" / (mode + "-bundle-%d" % index), executor)
            checked.append({"record_count": item["construction"]["memory_bundle"]["record_count"], "record_ids": item["construction"]["memory_bundle"]["record_ids"], "independent": accepted})
        bundle_scores[mode] = checked
    policies = []
    for index, target in enumerate(fresh):
        nonreserve = [p["id"] for p in target["phases"] if p["kind"] != "reserve"]
        commits = [p["id"] for p in target["phases"] if p["kind"] == "commit"]
        required = [{"kind": "protect", "phase_ids": nonreserve}, {"kind": "atomic_publish", "phase_ids": commits}]
        cells = {}
        for policy in ("old", "new"):
            for toolbox, capabilities in (("old", ["protect"]), ("new", ["protect", "atomic_publish"])):
                built = construct.evaluate_policy(target, policy, capabilities, required, max_candidates=64)
                location = output / ("policy-%02d-%s-%s" % (index, policy, toolbox))
                checked = pipeline.verify(target, built.get("program"), location)
                accepted = independent_accept(target, built.get("program"), checked, location, executor)
                cells[policy + "/" + toolbox] = {"construction": built, "independent": accepted}
        policies.append({"task_id": target["id"], "cells": cells})
    policy_scores = {key: sum(row["cells"][key]["independent"]["passed"] for row in policies) for key in policies[0]["cells"]}
    write(output / "POLICY_CROSS.json", {"cases": policies, "scores_out_of_8": policy_scores,
          "scope": "Developer-authored policy comparison and supplied capabilities, not learned discovery-policy improvement. Same explicit objective, candidate allowance and independent final checks."})
    enabling = pipeline.archive_enabling(output / "archive-enabling")
    objective = enabling["reframing"]["objective"]
    reframe_gate = (enabling["passed"] is True and enabling["missing_instrument_specification"]["built"] is False
                    and enabling["constructed_instrument"]["built"] is True and enabling["reframing"]["objective_sha256"] == digest(objective)
                    and enabling["reframing"]["snapshot_receipt_supported"] is True
                    and any(row["representation"] == "verified_snapshot" and row["status"] == "admitted" and row["objective"] == objective for row in enabling["reframing"]["alternatives"]))
    child_end = resource.getrusage(resource.RUSAGE_CHILDREN)
    gates = {"actual_development_acquisition": bool(lineage), "all_inherited_fresh_cases": scores["inheritance"] == 8,
             "actual_inherited_source_checked_lineage": all(case["arms"][mode]["actual_retained_lineage"] for case in cases for mode in ("inheritance", "ordinary")),
             "equivalent_reuse_and_strong_controls": scores["ordinary"] == 8 and scores["conventional"] == 8,
             "operator_removed_has_no_hidden_repair": scores["removed"] == 0,
             "role_sensitive_mapping": role_effect, "location_sensitive_critic": location_sensitive,
             "bundle_complementarity_actual": all([row["independent"]["passed"] for row in rows] == [False, False, False, True] for rows in bundle_scores.values()),
             "objective_preserving_actual_archive_enabling": reframe_gate,
             "negative_integrity_controls": all(controls.get(key) is True for key in ("empty_memory_refuses_without_default_operator", "incompatible_memory_scope_refused", "incompatible_mapping_refused", "duplicate_immutable", "wrong_hash_acquisition_refused", "corrupted_source_refused"))}
    report = {"schema": "agi-alpha-cycle005-independent-wholepath/v1", "freeze_sha256": FREEZE_SHA256,
              "protocol_sha256": PROTOCOL_SHA256, "addendum_sha256": ADDENDUM_SHA256,
              "development_independent": dev_accepted, "acquired_record_id": retained["id"] if retained else None,
              "fresh_cases": cases, "scores_out_of_8": scores, "controls": controls, "bundle_scores": bundle_scores,
              "policy_cross_scores_out_of_8": policy_scores, "enabling_receipt_sha256": sha(output / "archive-enabling/ENABLING.json"),
              "engineering_gates": gates, "all_engineering_gates_passed": all(gates.values()),
              "resources": {"wall_seconds": time.monotonic()-started, "verifier_cpu_seconds": time.process_time()-cpu,
                            "child_cpu_seconds": child_end.ru_utime+child_end.ru_stime-child_start.ru_utime-child_start.ru_stime,
                            "complete_lifecycle_cost": None},
              "confirmation_alpha_spent": 0,
              "limits": ["Eight fresh label/order/extra-edge variants of one declared typed local-evidence family; no consequential scientific generalization.",
                         "Donor and grammar are supplied. The acquired role operator is actually constructed, stored, retrieved and instantiated; no literal evaluator operator is injected.",
                         "Equivalent ordinary reuse and competent conventional controls may tie. No complete-cost, learned discovery-policy, physical, buyer-demand or commercial-success claim.",
                         "Receipt hashes authenticate identity, not truth; acquisition relies on trusted pipeline-produced actual verifier artifacts, rechecked here from raw files.",
                         "Procedural separation only, sharing host, filesystem, models and libraries. Cases become exposed regressions on publication."]}
    write(output / "REPORT.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.root.resolve(), args.output.resolve())
    print(json.dumps({"all_engineering_gates_passed": result["all_engineering_gates_passed"], "scores_out_of_8": result["scores_out_of_8"], "policy_cross": result["policy_cross_scores_out_of_8"]}))
    raise SystemExit(0 if result["all_engineering_gates_passed"] else 1)
