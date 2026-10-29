"""Acquire an inert repair operator from adjudicated construction evidence."""
from __future__ import annotations

import copy
import hashlib
import itertools
from pathlib import Path
import time

from flywheel.retention import canonical, compatible, retrieve, store, validate


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _source(source_root):
    root = Path(source_root).resolve(strict=True)
    path = root / "mechanisms/construct.py"
    if path.is_symlink() or not path.is_file():
        raise ValueError("CONSTRUCTOR_SOURCE_UNAVAILABLE")
    return {"path": "mechanisms/construct.py", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _dependency_hashes(source_root):
    root = Path(source_root)
    result = {}
    for name in ("mechanisms/memory.py", "mechanisms/mapping.py", "flywheel/retention.py"):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("DEPENDENCY_SOURCE_UNAVAILABLE " + name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _conditions(task):
    conditions = task.get("conditions", {})
    if not conditions:
        raise ValueError("TASK_APPLICABILITY_REQUIRED")
    return copy.deepcopy(conditions)


def _established(obligation):
    provenance = obligation.get("provenance", {})
    return obligation.get("status") == "established" or provenance.get("status") == "established" or provenance.get("adjudication") == "established"


def acquire(task, mapping, before, after, obligations, verification_receipt, source_root):
    """Derive role-parameterized added protections; no target event IDs survive."""
    started = time.process_time()
    if before.get("language") != "event-plan/v1" or after.get("language") != "event-plan/v1":
        raise ValueError("CONSTRUCTION_LANGUAGE_MISMATCH")
    receipt = verification_receipt
    if receipt.get("before_sha256") != digest(before) or receipt.get("after_sha256") != digest(after):
        raise ValueError("VERIFICATION_IDENTITY_MISMATCH")
    if receipt.get("before_passed") is not False or receipt.get("after_passed") is not True:
        raise ValueError("VERIFIED_REPAIR_TRANSITION_REQUIRED")
    phases = {phase["id"]: phase for phase in task["phases"]}
    target_events = mapping.get("target_events")
    source_graph = mapping.get("source_graph", mapping.get("donor_graph"))
    if not isinstance(target_events, dict) or not source_graph:
        raise ValueError("MAPPING_LINEAGE_REQUIRED")
    inverse = {}
    for role, event in target_events.items():
        inverse.setdefault(event, []).append(role)
    base_role_obligations, role_deltas = [], []
    for field, kind in (("protected", "protect"), ("atomic", "atomic_publish")):
        old, new = set(before.get(field, [])), set(after.get(field, []))
        if old - new:
            raise ValueError("REMOVED_OBLIGATION_UNSUPPORTED")
        for event in sorted(old):
            if event not in phases or len(inverse.get(event, [])) != 1:
                raise ValueError("UNRESOLVED_BASE_ROLE")
            base_role_obligations.append({"kind": kind, "role_ids": inverse[event]})
        for event in sorted(new - old):
            if event not in phases or len(inverse.get(event, [])) != 1:
                raise ValueError("UNRESOLVED_REPAIR_ROLE")
            supporting = [item for item in obligations if item.get("kind") == kind and event in item.get("phase_ids", []) and _established(item)]
            if not supporting:
                raise ValueError("UNADJUDICATED_REPAIR_DELTA")
            role_deltas.append({"kind": kind, "role_ids": inverse[event]})
    if not role_deltas:
        raise ValueError("NO_ACQUIRED_REPAIR_DELTA")
    graph = copy.deepcopy(source_graph)
    if before.get("compensations") != after.get("compensations") or before.get("compensations"):
        raise ValueError("COMPENSATION_ACQUISITION_NOT_SUPPORTED")
    graph["obligations"] = base_role_obligations + role_deltas
    graph.pop("strategy_recipe", None)
    record = {"instrument": _source(source_root),
        "applicability": {"schema_version": 1, "conditions": _conditions(task),
            "assumptions": ["Typed relation-preserving unique mapping", "Construction language and exact dependency hashes unchanged", "New task requires its own verification"],
            "uncertainty": "Learned from one adjudicated repair; transfer and lifecycle advantage remain unproved", "failures": []},
        "generative_operator": {"language": "event-plan-rewrite-v1", "program": {"source_graph": graph, "base_role_obligations": base_role_obligations, "role_deltas": role_deltas, "max_matches": 32}},
        "provenance": {"origin": "derived-from-verified-before-after-delta", "task_id": task["id"], "task_sha256": digest(task), "mapping_sha256": digest(mapping),
            "before_sha256": digest(before), "after_sha256": digest(after), "obligations_sha256": digest(obligations), "dependency_sha256": _dependency_hashes(source_root),
            "verification_scope": copy.deepcopy(receipt.get("objective_scope", {"scope": "receipt-bound development repair; no separately named subcontract"})),
            "acquisition": "Before behavior and actual added protected/atomic events separately inverted through discovered structural role mapping; target event identifiers not retained in recipe"},
        "verification": {"status": "verified-in-scope", "receipt_sha256": digest(receipt)},
        "costs": {"acquisition_cpu_seconds": time.process_time() - started, "development_trace_costs": receipt.get("costs"), "complete_cost_usd": None},
        "exposure": [task["id"]], "supersedes": []}
    validate(record)
    return record


def retain(root, task, mapping, before, after, obligations, verification_receipt, source_root):
    record = acquire(task, mapping, before, after, obligations, verification_receipt, source_root)
    return {"id": store(root, record), "record": record}


def failed_transfer(root, task, mapping, reason, source_root, costs=None):
    """Retain a scoped failure without inventing a successful capability."""
    record = {"instrument": _source(source_root),
        "applicability": {"schema_version": 1, "conditions": _conditions(task), "assumptions": [], "uncertainty": "Failure is scoped to the observed mapping and conditions",
            "failures": [{"conditions": _conditions(task), "reason": str(reason)}]},
        "generative_operator": {"language": "event-plan-rewrite-v1", "program": {"source_graph": mapping.get("source_graph", mapping.get("donor_graph", {})), "role_deltas": [], "max_matches": 0}},
        "provenance": {"task_id": task["id"], "mapping_sha256": digest(mapping), "failure_reason": str(reason)},
        "verification": {"status": "failed", "receipt_sha256": digest({"mapping": mapping, "reason": str(reason)})},
        "costs": costs or {"complete_cost_usd": None}, "exposure": [task["id"]], "supersedes": []}
    return {"id": store(root, record), "record": record}


def _source_check(record, source_root):
    root = Path(source_root).resolve(strict=True)
    for name, expected in {record["instrument"]["path"]: record["instrument"]["sha256"], **record["provenance"].get("dependency_sha256", {})}.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("MEMORY_DEPENDENCY_MISMATCH " + name)


def _bound(budget):
    value = budget.get("max_candidates", 64) if isinstance(budget, dict) else budget
    if type(value) is not int or not 1 <= value <= 256:
        raise ValueError("SEARCH_BOUND")
    return value


def _instantiate(record, target, source_root, budget, prepare_only=False):
    validate(record)
    _source_check(record, source_root)
    if record["verification"]["status"] != "verified-in-scope":
        raise ValueError("UNVERIFIED_MEMORY")
    observed = _conditions(target)
    if any(key not in observed or type(observed[key]) is not type(value) or observed[key] != value for key, value in record["applicability"]["conditions"].items()):
        raise ValueError("INAPPLICABLE_MEMORY")
    for failure in record["applicability"]["failures"]:
        if all(key in observed and type(observed[key]) is type(value) and observed[key] == value for key, value in failure["conditions"].items()):
            raise ValueError("SCOPED_COUNTEREXAMPLE")
    program = record["generative_operator"]["program"]
    if record["generative_operator"]["language"] != "event-plan-rewrite-v1" or type(program.get("role_deltas")) is not list or type(program.get("base_role_obligations", [])) is not list:
        raise ValueError("GENERATIVE_OPERATOR_SCHEMA")
    from mechanisms.construct import construct
    from mechanisms.mapping import discover, compile_mapping, target_from_task
    donor = copy.deepcopy(program["source_graph"])
    combined = program.get("base_role_obligations", []) + program["role_deltas"]
    donor["obligations"] = combined
    graph = target_from_task(target)
    reports = discover([donor], graph)
    viable = [item for item in reports if item.get("status") == "unique" and len(item.get("correspondences", [])) == 1]
    if len(viable) != 1:
        raise ValueError("FRESH_MAPPING_NOT_UNIQUE")
    mapped = compile_mapping(donor, graph, viable[0]["correspondences"][0])
    phases = {phase["id"]: phase for phase in target["phases"]}
    rules = []
    for delta in combined:
        for role in delta["role_ids"]:
            event = mapped["target_events"][role]
            phase = phases[event]
            rules.append({"match": {"kind": phase["kind"], "unit": phase.get("unit", "event"), "phase_ids": [event]}, "emit": {"kind": delta["kind"], "phase_ids": ["$match"]}})
    operator = {"language": "event-plan-rewrite/v1", "rules": rules, "max_matches": program["max_matches"]}
    trace = {"source_graph_id": donor["id"], "mapping": mapped, "operator": operator, "record_sha256": digest(record), "fresh_target": target["id"] not in record["exposure"],
        "base_role_obligation_count": len(program.get("base_role_obligations", [])), "learned_role_delta_count": len(program["role_deltas"])}
    if prepare_only:
        return {"operator": operator, "memory_instantiation": trace}
    result = construct(target, obligations=[], max_candidates=_bound(budget), operator=operator)
    result["memory_instantiation"] = trace
    return result


def generate(root, target, donors, source_root, budget):
    started = time.process_time()
    report = retrieve(root, {"schema_version": 1, "conditions": _conditions(target)}, source_root)
    attempts = []
    for item in report["records"]:
        try:
            result = _instantiate(item["record"], target, source_root, budget)
            result["memory"] = {"id": item["id"], "retrieval": report, "cpu_seconds": time.process_time() - started, "donor_context_sha256": digest(donors)}
            return result
        except (ValueError, KeyError) as error:
            attempts.append({"id": item["id"], "reason": str(error)})
    return {"status": "refused", "program": None, "attempts": [], "memory": {"retrieval": report, "instantiation_refusals": attempts, "cpu_seconds": time.process_time() - started}}


def ordinary_generate(record, target, donors, source_root, budget):
    """Equivalent JSON content gets the same constructor without a memory index."""
    started = time.process_time()
    result = _instantiate(copy.deepcopy(record), target, source_root, budget)
    result["ordinary_reuse"] = {"equivalent_content_sha256": digest(record), "cpu_seconds": time.process_time() - started, "donor_context_sha256": digest(donors)}
    return result


def _bundle_limits(budget):
    values = budget if isinstance(budget, dict) else {"max_candidates": budget}
    limits = {"max_candidates": _bound(budget), "max_combinations": values.get("max_combinations", 16),
        "max_bundle_size": values.get("max_bundle_size", 3), "max_records": values.get("max_records", 16)}
    for key, ceiling in (("max_combinations", 256), ("max_bundle_size", 8), ("max_records", 32)):
        if type(limits[key]) is not int or not 1 <= limits[key] <= ceiling:
            raise ValueError("BUNDLE_BOUND " + key)
    return limits


def _bundles(entries, target, donors, source_root, budget):
    """Enumerate bounded unions. Only an external unchanged judge may select one."""
    started = time.process_time()
    limits = _bundle_limits(budget)
    unique_entries = {item["id"]: item for item in entries}
    ordered = sorted(unique_entries.values(), key=lambda item: item["id"])
    prepared, refused, candidates = [], [], []
    for item in ordered[:limits["max_records"]]:
        try:
            prepared.append({**item, **_instantiate(item["record"], target, source_root, budget, prepare_only=True)})
        except (ValueError, KeyError) as error:
            refused.append({"record_ids": [item["id"]], "reason": str(error)})
    from mechanisms.construct import construct
    combination_count, candidate_count = 0, 0
    exhausted = False
    for size in range(0, min(len(prepared), limits["max_bundle_size"]) + 1):
        for bundle in itertools.combinations(prepared, size):
            if combination_count >= limits["max_combinations"] or candidate_count >= limits["max_candidates"]:
                exhausted = True
                break
            combination_count += 1
            identities = [item["id"] for item in bundle]
            if not compatible([item["record"] for item in bundle]):
                refused.append({"record_ids": identities, "reason": "INCOMPATIBLE_COMPOSITION"})
                continue
            unique_rules = {digest(rule): rule for item in bundle for rule in item["operator"]["rules"]}
            rules = [unique_rules[key] for key in sorted(unique_rules)]
            operator = {"language": "event-plan-rewrite/v1", "rules": rules, "max_matches": max(1, sum(item["operator"]["max_matches"] for item in bundle))}
            candidate_started = time.process_time()
            try:
                result = construct(target, obligations=[], max_candidates=limits["max_candidates"] - candidate_count, operator=operator)
            except (ValueError, KeyError) as error:
                refused.append({"record_ids": identities, "reason": str(error), "cpu_seconds": time.process_time() - candidate_started})
                continue
            evaluated = len(result.get("attempts", []))
            candidate_count += evaluated
            result["memory_bundle"] = {"record_ids": identities, "record_count": len(bundle), "instantiations": [item["memory_instantiation"] for item in bundle],
                "operator": operator, "evaluated_candidates": evaluated, "cpu_seconds": time.process_time() - candidate_started,
                "verification_scopes": [item["record"]["provenance"].get("verification_scope") for item in bundle]}
            candidates.append(result)
        if exhausted:
            break
    return {"status": "exhausted" if exhausted else ("generated" if candidates else "refused"), "program": None, "candidates": candidates,
        "memory": {"limits": limits, "available_records": len(ordered), "duplicate_records_ignored": len(entries) - len(ordered), "prepared_records": len(prepared), "records_deferred": max(0, len(ordered) - limits["max_records"]),
            "combinations_considered": combination_count, "evaluated_candidates": candidate_count, "refused": refused, "cpu_seconds": time.process_time() - started,
            "donor_context_sha256": digest(donors), "selection": "No acceptance-based selection; every generated singleton and compatible bundle is returned to the external judge",
            "complete_cost_usd": None, "acquisition_costs": [{"id": item["id"], "costs": item["record"]["costs"]} for item in ordered]}}


def generate_bundle(root, target, donors, source_root, budget):
    started = time.process_time()
    report = retrieve(root, {"schema_version": 1, "conditions": _conditions(target)}, source_root)
    result = _bundles(report["records"], target, donors, source_root, budget)
    result["memory"]["retrieval"] = report
    result["memory"]["cpu_seconds"] = time.process_time() - started
    return result


def ordinary_bundle(records, target, donors, source_root, budget):
    """Same JSON instruments and bundle budget, supplied without a memory index."""
    entries = []
    for item in records:
        record = copy.deepcopy(item.get("record", item))
        entries.append({"id": digest(record), "record": record})
    result = _bundles(entries, target, donors, source_root, budget)
    result["memory"]["ordinary_equivalent_content_sha256"] = [item["id"] for item in sorted(entries, key=lambda item: item["id"])]
    return result
