# SPDX-License-Identifier: Apache-2.0
"""Bounded strategy policies over the existing isolated workflow executor."""
from concurrent.futures import ThreadPoolExecutor
import copy
import secrets

from .adapters import BridgeError

PARENT_STRATEGIES = {"parallel-exploration", "adaptive"}


def call_limit(spec):
    roles = spec["roles"]
    # Each construction iteration can invoke every post-construction role once.
    return spec["max_iterations"] * (1 + sum(k in roles for k in ("critic", "adversary", "economist"))) + int("researcher" in roles)


def partition(total, count):
    base, remainder = divmod(total, count)
    return [base + int(i < remainder) for i in range(count)]


def plan(spec):
    from .workflows import require
    approaches = spec.get("approaches")
    require(isinstance(approaches, list) and 2 <= len(approaches) <= 4 and all(isinstance(x, str) and 0 < len(x.strip()) <= 4000 for x in approaches), "Exploration needs two to four distinct approach briefs.")
    require(len({x.strip().casefold() for x in approaches}) == len(approaches), "Exploration approach briefs must be distinct.")
    adaptive = spec["strategy"] == "adaptive"
    threshold = spec.get("adaptive_after_failures", 1)
    require(type(threshold) is int and threshold >= 1, "Adaptive failure threshold must be a positive integer.")
    count = len(approaches)
    require(spec["max_iterations"] >= count + (threshold if adaptive else 0), "The shared iteration limit must support each branch and the adaptive primary phase.")
    require(spec["max_actions"] >= count + int(adaptive), "The shared action limit must support each branch.")
    iterations = ([threshold] if adaptive else []) + partition(spec["max_iterations"] - (threshold if adaptive else 0), count)
    actions = partition(spec["max_actions"], count + int(adaptive))
    briefs = (["Use the strongest direct conventional approach first. Preserve failed checks; alternatives may be activated only if this approach fails."] if adaptive else []) + approaches
    result = []
    for index, (brief, rounds, acts) in enumerate(zip(briefs, iterations, actions)):
        child = copy.deepcopy(spec)
        for key in ("approaches", "adaptive_after_failures", "inherited_capability"):
            child.pop(key, None)
        child["strategy"] = "adversarial-review" if "adversary" in child["roles"] else "actor-critic" if "critic" in child["roles"] else "single-model"
        child["max_iterations"], child["max_actions"] = rounds, acts
        child["context"] = spec["context"] + "\n\nOPERATOR-ASSIGNED APPROACH (same objective, acceptance and permissions):\n" + brief.strip()
        require(len(child["context"].encode()) <= 262144, "Context plus the registered branch brief exceeds the context envelope.")
        result.append({"index": index, "label": "primary" if adaptive and index == 0 else "approach-" + str(index if adaptive else index + 1),
                       "approach": brief.strip(), "spec": child, "max_iterations": rounds, "max_actions": acts, "model_call_limit": call_limit(child)})
    return result


def initialize(service, state):
    from .workflows import require, digest
    planned = plan(state["spec"])
    state.setdefault("branch_runs", [])
    for branch in planned[len(state["branch_runs"]):]:
        # Reserve the identity and allowance in the parent before a child can
        # exist. Recovery reuses this identity, never reallocates the budget.
        state["branch_runs"].append({k: branch[k] for k in ("index", "label", "approach", "max_iterations", "max_actions", "model_call_limit")} | {"run_id": "wf_" + secrets.token_hex(12)})
        service._save(state)
    for branch, ref in zip(planned, state["branch_runs"]):
        if (service.root / ref["run_id"] / "state.json").exists():
            child = service._load(ref["run_id"])
            require(child.get("parent_run") == state["id"] and child.get("branch_index") == branch["index"] and child["spec_hash"] == digest(branch["spec"]), "Reserved branch differs from its frozen parent allocation.", "WORKFLOW_INTEGRITY")
            if child.get("branch_initialized"):
                continue
        else:
            service.create(branch["spec"], _reservation={"run_id": ref["run_id"], "index": branch["index"], "parent_run": state["id"]})
            child = service._load(ref["run_id"])
        # Reusable initial artifacts are common declared starting resources;
        # each branch gets its own immutable copy and must recheck acceptance.
        for name, meta in state["artifacts"].items():
            service._write(child, name, service._read_artifact(state, name).decode(), meta["kind"])
        service._event(child, "branch_created", {"parent": state["id"], "index": branch["index"], "approach": branch["approach"], "shared_budget_allocation": {k: branch[k] for k in ("max_iterations", "max_actions", "model_call_limit")}})
        child["branch_initialized"] = True
        service._save(child)
    state["model_call_limit"] = sum(b["model_call_limit"] for b in planned)
    state.setdefault("strategy_phase", "primary" if state["spec"]["strategy"] == "adaptive" else "exploration")
    state["phase"] = state["strategy_phase"]
    service._save(state)


def summaries(service, state):
    result = []
    for ref in state.get("branch_runs", []):
        if not (service.root / ref["run_id"] / "state.json").exists():
            result.append({**ref, "status": "uninitialized", "model_calls": 0, "actions": 0, "iteration": 0,
                           "verification": {"passed": False, "checks": []}, "artifacts": {}, "roles": state["spec"]["roles"], "events_count": 0})
            continue
        child = service._load(ref["run_id"])
        result.append({**ref, "status": child["status"], "model_calls": child["model_calls"], "actions": child["actions"], "iteration": child["iteration"],
                       "verification": child["verification"], "artifacts": child["artifacts"], "roles": child["spec"]["roles"], "events_count": len(child["events"])})
    return result


def aggregate(service, state):
    rows = summaries(service, state)
    state["model_calls"] = sum(r["model_calls"] for r in rows)
    state["actions"] = sum(r["actions"] for r in rows)
    state["iteration"] = sum(r["iteration"] for r in rows)
    from .workflows import require
    require(state["model_calls"] <= state["model_call_limit"] and state["actions"] <= state["spec"]["max_actions"] and state["iteration"] <= state["spec"]["max_iterations"], "A branch exceeded its shared parent budget.", "WORKFLOW_INTEGRITY")
    return rows


def _select(service, state, candidates):
    if not candidates:
        state["status"] = "exhausted"
        service._event(state, "exploration_rejected", {"reason": "No branch completed the frozen acceptance and required review.", "candidate_count": len(state["branch_runs"])})
        return
    winner = min(candidates, key=lambda row: (row["actions"], row["model_calls"], row["index"]))
    child = service._load(winner["run_id"])
    for name, meta in child["artifacts"].items():
        service._write(state, name, service._read_artifact(child, name).decode(), meta["kind"])
    state["adversarial_cases"] = copy.deepcopy(child.get("adversarial_cases", []))
    state["selected_branch"] = winner["run_id"]
    service._event(state, "branch_selected", {"run_id": winner["run_id"], "index": winner["index"], "rule": "Among completed accepted branches: fewest tool actions, then model calls, then registered branch order. This is not economic optimality.", "accepted_branches": [c["run_id"] for c in candidates], "all_launched_work_settled": True})
    service._finish(state)


def step(service, ident):
    from .workflows import require, TERMINAL
    with service._lock(ident):
        state = service._load(ident)
        require(ident not in service._inflight, "A strategy wave is already running.", "WORKFLOW_BUSY")
        require(state["status"] not in TERMINAL | {"paused"}, "Resume the parent strategy before dispatch.", "WORKFLOW_STATE")
        initialize(service, state)
        refs = state["branch_runs"][:1] if state["strategy_phase"] == "primary" else state["branch_runs"][1:] if state["spec"]["strategy"] == "adaptive" else state["branch_runs"]
        active = []
        for ref in refs:
            child = service._load(ref["run_id"])
            if child["status"] == "ready" and child["inflight"] is None:
                active.append(ref["run_id"])
            elif child["status"] == "running" or child["inflight"] is not None:
                raise BridgeError("WORKFLOW_STATE", "Interrupted branch requests require explicit parent resume.")
        epoch = state["epoch"]
        state["status"], state["phase"] = "running", state["strategy_phase"]
        service._inflight[ident] = ident + "_strategy"
        service._event(state, "strategy_wave_started", {"phase": state["strategy_phase"], "branches": active, "shared_action_limit": state["spec"]["max_actions"], "shared_model_call_limit": state["model_call_limit"]})
        service._save(state)
    errors = []
    # Wait for every launched branch, including failures. No winner hides a
    # sibling's unresolved request, consumed allowance, or refusal evidence.
    with ThreadPoolExecutor(max_workers=max(1, min(len(active), getattr(service.runtime, "max_concurrent", 2)))) as pool:
        futures = {pool.submit(service.step, child, _parent=ident): child for child in active}
        for future, child in futures.items():
            try:
                future.result()
            except Exception as error:
                errors.append({"branch": child, "code": getattr(error, "code", "BRANCH_ERROR"), "message": "Branch failed safely; inspect its own history."})
    with service._lock(ident):
        state = service._load(ident)
        service._inflight.pop(ident, None)
        rows = aggregate(service, state)
        service._event(state, "strategy_wave_completed", {"phase": state["strategy_phase"], "branches": [{k: row[k] for k in ("run_id", "index", "status", "model_calls", "actions", "iteration")} for row in rows], "errors": errors})
        if state["epoch"] != epoch or state["status"] in {"paused", "cancelled"}:
            service._save(state)
            return service._view(state)
        relevant = rows[:1] if state["strategy_phase"] == "primary" else rows[1:] if state["spec"]["strategy"] == "adaptive" else rows
        accepted = [row for row in relevant if row["status"] == "complete" and row["verification"]["passed"]]
        if errors or any(row["status"] == "paused" for row in relevant):
            state["status"] = "paused"
        elif state["strategy_phase"] == "primary" and relevant[0]["status"] in TERMINAL:
            if accepted:
                _select(service, state, accepted)
            else:
                primary = service._load(relevant[0]["run_id"])
                failures = [event for event in primary["events"] if event["kind"] in {"tool_refused", "response_refused"} or event["kind"] == "verification" and not event["detail"]["passed"]]
                if failures:
                    state["strategy_phase"], state["phase"], state["status"] = "exploration", "exploration", "ready"
                    service._event(state, "strategy_switched", {"from": "primary", "to": "parallel-exploration", "failure_run": primary["id"], "evidence": [{"event_index": event["index"], "event_sha256": event["sha256"], "kind": event["kind"]} for event in failures], "reason": "The direct construction exhausted its registered allocation with recorded rejected work. Use the pre-authorized distinct approaches and remaining fixed allocations.", "providers_changed": False, "permissions_changed": False, "acceptance_changed": False})
                else:
                    state["status"] = "needs_review"
                    service._event(state, "adaptive_not_switched", {"reason": "No adjudicated or executable failure justifies the registered switch."})
        elif all(row["status"] in TERMINAL for row in relevant):
            _select(service, state, accepted)
        else:
            state["status"] = "ready"
        service._save(state)
        return service._view(state)


def interrupt_children(service, state, status):
    for ref in state.get("branch_runs", []):
        if (service.root / ref["run_id"] / "state.json").exists():
            service._interrupt(ref["run_id"], status)


def resume_children(service, state):
    from .workflows import TERMINAL
    for ref in state.get("branch_runs", []):
        child = service._load(ref["run_id"])
        if child["status"] not in TERMINAL:
            service.resume(ref["run_id"], background=False, _parent=state["id"])


def validate_branch_exports(service, archive):
    """Validate every imported child against the parent's exact frozen plan."""
    from .workflows import require, encoded
    state = archive["state"]
    branches = archive.get("branch_exports")
    planned = plan(state["spec"])
    require(isinstance(branches, list) and len(branches) == len(planned), "Parent export must include every registered branch.")
    for expected, child in zip(planned, branches):
        require(isinstance(child, dict) and "branch_exports" not in child, "Nested strategy branches are not permitted.")
        service._validate_import(child)
        require(encoded(child["state"]["spec"]) == encoded(expected["spec"]), "Imported branch changed its parent-frozen acceptance, roles, permissions, approach or budget.", "WORKFLOW_INTEGRITY")
    return branches


def restore_branches(service, state, archives):
    for ref, archive in zip(state["branch_runs"], archives):
        child = service._load(ref["run_id"])
        service._restore_import_files(child, archive)
        service._save(child)
    state["strategy_phase"] = "primary" if state["spec"]["strategy"] == "adaptive" else "exploration"
    state["selected_branch"] = None

