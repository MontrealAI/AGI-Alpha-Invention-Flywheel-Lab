from itertools import product


METHOD = "ordinary-bounded-conformance-and-transaction-synthesis-v1"
K1_LESSONS = (
    "TIMEOUT admits both a lost request and a committed effect.",
    "Repeated tokens can duplicate effects; test the intended replay interval.",
    "ABSENT can be stale despite a committed effect.",
    "An authoritative fence can distinguish present and absent states.",
    "Test compensation after an effect, not only on an empty namespace.",
    "Prepared commits are idempotent within the public finite interface.",
    "Holds can expire while other providers operate; qualify the plan window.",
    "Reset-time replay conformance does not qualify later global-clock entry phases.",
    "Opaque non-idempotent irreversible providers can remain unresolved.",
)


def _op(name, **kwargs):
    return {"op": name, "token": "probe", **kwargs}


def _measured(rows, size):
    return len(rows) == size and all(
        type(row.get("effect_count")) is int
        and type(row.get("hold_count")) is int
        for row in rows
    )


class _Acquisition:
    def __init__(self, task, probe):
        self.probe = probe
        self.remaining = int(task["probe_budget_microUSD"])
        self.trace = []

    def ask(self, provider, sequence, purpose):
        expected = len(sequence) * provider["probe_unit_microUSD"]
        for attempt in range(2):
            if expected > self.remaining:
                self.trace.append({"event": "probe_declined", "provider": provider["id"],
                                   "purpose": purpose, "required_microUSD": expected,
                                   "remaining_microUSD": self.remaining})
                return []
            result = self.probe(provider["id"], sequence)
            charge = int(result.get("cost_microUSD", 0))
            self.remaining -= charge
            rows = result.get("observations", [])
            self.trace.append({"event": "conformance_probe", "provider": provider["id"],
                               "purpose": purpose, "attempt": attempt + 1,
                               "sequence": sequence, "observations": rows,
                               "cost_microUSD": charge})
            if _measured(rows, len(sequence)):
                return rows
            if not rows:
                return []
        return []


def _direct_profile(provider, acquisition):
    result = {"id": provider["id"], "call_microUSD": provider["call_microUSD"],
              "direct": None, "compensation": False, "prepared": False,
              "hypotheses": ["request_missing", "effect_without_ack", "neither"]}
    rows = acquisition.ask(provider, [
        _op("execute", fault="ack_lost"), _op("execute"), _op("cancel")
    ], "same_token_replay_and_effect_compensation")
    if rows:
        initial_effect = rows[0]["effect_count"] == 1
        replay = initial_effect and rows[1]["effect_count"] == 1 and rows[1]["response"] == "DONE"
        compensation = (rows[1]["effect_count"] >= 1 and rows[2]["effect_count"] == 0
                        and rows[2]["hold_count"] == 0 and rows[2]["response"] == "CANCELLED")
        result["compensation"] = compensation
        result["replay_observed_duplicate"] = rows[1]["effect_count"] > 1
        if replay:
            result["direct"] = "immediate_replay"
        elif compensation:
            result["direct"] = "compensate_before_retry"
    if result["direct"] is None:
        rows = acquisition.ask(provider, [
            _op("status"), _op("fence"), _op("execute", fault="ack_lost"),
            _op("status"), _op("fence"), _op("cancel")
        ], "present_absent_discrimination")
        if rows:
            present = rows[2]["effect_count"] == 1
            fence = (present and rows[1]["response"] == "ABSENT" and rows[1]["effect_count"] == 0
                     and rows[4]["response"] == "DONE" and rows[4]["effect_count"] == 1)
            status = (present and rows[0]["response"] == "ABSENT" and rows[0]["effect_count"] == 0
                      and rows[3]["response"] == "DONE" and rows[3]["effect_count"] == 1)
            compensation = (present and rows[5]["response"] == "CANCELLED"
                            and rows[5]["effect_count"] == 0 and rows[5]["hold_count"] == 0)
            result["compensation"] = result["compensation"] or compensation
            result["stale_absence_observed"] = present and rows[3]["response"] == "ABSENT"
            if fence:
                result["direct"] = "fence_reconciliation"
            elif compensation:
                result["direct"] = "compensate_before_retry"
            elif status:
                result["direct"] = "tested_status_reconciliation"
    if result["direct"] is None:
        rows = acquisition.ask(provider, [
            _op("status"), _op("execute", fault="ack_lost"), _op("wait", ticks=8),
            _op("status"), _op("cancel")
        ], "bounded_delayed_status_conformance")
        if rows:
            delayed = (rows[0]["response"] == "ABSENT" and rows[0]["effect_count"] == 0
                       and rows[1]["effect_count"] == 1 and rows[3]["response"] == "DONE"
                       and rows[3]["effect_count"] == 1)
            compensation = (rows[1]["effect_count"] == 1 and rows[4]["response"] == "CANCELLED"
                            and rows[4]["effect_count"] == 0 and rows[4]["hold_count"] == 0)
            result["compensation"] = result["compensation"] or compensation
            if delayed:
                result["direct"] = "bounded_delayed_status_reconciliation"
                result["qualified_status_wait_ticks"] = 8
            elif compensation:
                result["direct"] = "compensate_before_retry"
    return result


def _prepare_profile(provider, profile, acquisition, window):
    probe = [_op("reserve")]
    remaining = window
    while remaining:
        ticks = min(8, remaining)
        probe.append(_op("wait", ticks=ticks))
        remaining -= ticks
    probe.extend([_op("commit", fault="request_lost"), _op("commit"), _op("commit"), _op("cancel")])
    rows = acquisition.ask(provider, probe, "hold_survival_and_idempotent_commit")
    if not rows:
        return
    lost, completed, repeated, cancelled = rows[-4:]
    qualified = (rows[0]["response"] == "RESERVED" and rows[0]["hold_count"] == 1
                 and rows[0]["effect_count"] == 0 and lost["effect_count"] == 0
                 and completed["response"] == "DONE" and completed["effect_count"] == 1
                 and repeated["response"] == "DONE" and repeated["effect_count"] == 1
                 and repeated["hold_count"] == 0)
    profile["prepared"] = qualified
    profile["qualified_hold_window_ticks"] = window if qualified else None
    if qualified and cancelled["response"] == "CANCELLED" and cancelled["effect_count"] == 0:
        profile["compensation"] = True


class _Graph:
    def __init__(self, provider_ids):
        self.nodes = {
            "delivered": {"finish": "delivered", "obligations": []},
            "aborted": {"finish": "aborted", "obligations": []},
            "unresolved": {"finish": "unresolved", "obligations": list(provider_ids)},
        }
        self.counter = 0

    def call(self, operation, provider, branches, ticks=None):
        name = f"s{self.counter}"
        self.counter += 1
        self.nodes[name] = {"op": operation, "provider": provider, "token": "order",
                            "next": {"*": "unresolved", **branches}}
        if ticks is not None:
            self.nodes[name]["ticks"] = ticks
        return name

    def cleanup(self, provider_ids):
        target = "aborted"
        for provider in reversed(provider_ids):
            retry = self.call("cancel", provider, {"CANCELLED": target})
            target = self.call("cancel", provider, {"CANCELLED": target, "TIMEOUT": retry})
        return target

    def execute(self, profile, success, cleanup):
        provider, mode = profile["id"], profile["direct"]
        retry = self.call("execute", provider, {"DONE": success, "REFUSED": cleanup})
        if mode == "immediate_replay":
            resolution = retry
        elif mode == "compensate_before_retry":
            resolution = self.call("cancel", provider, {"CANCELLED": retry})
        elif mode in ("fence_reconciliation", "tested_status_reconciliation"):
            operation = "fence" if mode == "fence_reconciliation" else "status"
            resolution = self.call(operation, provider, {"DONE": success, "ABSENT": retry})
        elif mode == "bounded_delayed_status_reconciliation":
            query = self.call("status", provider, {"DONE": success, "ABSENT": retry})
            resolution = self.call("wait", provider, {"*": query}, ticks=8)
        else:
            raise ValueError("unqualified direct operation")
        return self.call("execute", provider, {"DONE": success, "REFUSED": cleanup, "TIMEOUT": resolution})

    def commit(self, profile, success, cleanup):
        retry = self.call("commit", profile["id"], {"DONE": success, "ABSENT": cleanup, "REFUSED": cleanup})
        return self.call("commit", profile["id"], {"DONE": success, "TIMEOUT": retry,
                                                    "ABSENT": cleanup, "REFUSED": cleanup})


def _candidate_assignments(profiles, max_steps):
    choices = []
    for profile in profiles:
        options = []
        if profile["direct"]:
            options.append("direct")
        if profile["prepared"]:
            options.append("prepared")
        if not options:
            return []
        choices.append(options)
    candidates = []
    for roles in product(*choices):
        irreversible = [p for p, role in zip(profiles, roles) if role == "direct" and not p["compensation"]]
        if len(irreversible) > 1:
            continue
        counts = [3 if role == "prepared" else
                  2 if p["direct"] == "immediate_replay" else
                  4 if p["direct"] == "bounded_delayed_status_reconciliation" else 3
                  for p, role in zip(profiles, roles)]
        calls = sum(counts) + 2 * len(profiles)
        if calls > max_steps:
            continue
        cost = sum((count + 2) * p["call_microUSD"] for p, count in zip(profiles, counts))
        candidates.append({"roles": roles, "worst_call_bound": calls, "worst_cost_bound_microUSD": cost})
    return sorted(candidates, key=lambda c: (c["worst_cost_bound_microUSD"], c["worst_call_bound"], c["roles"]))


def _replay_entry_phases(profiles, roles):
    selected = list(zip(profiles, roles))
    prepared = [p for p, role in selected if role == "prepared"]
    reversible = [p for p, role in selected if role == "direct" and p["compensation"]]
    irreversible = [p for p, role in selected if role == "direct" and not p["compensation"]]
    phases = {len(prepared)}
    result = []
    durations = {"immediate_replay": (1, 2), "compensate_before_retry": (1, 3),
                 "fence_reconciliation": (1, 2, 3), "tested_status_reconciliation": (1, 2, 3),
                 "bounded_delayed_status_reconciliation": (1, 10, 11)}
    for profile in reversible + irreversible:
        if profile["direct"] == "immediate_replay":
            result.append((profile, sorted(phases)))
        phases = {start + duration for start in phases for duration in durations[profile["direct"]]}
    return result


def _qualify_replay_phase(provider, phase, acquisition):
    sequence = []
    remaining = phase
    while remaining:
        ticks = min(8, remaining)
        sequence.append(_op("wait", ticks=ticks))
        remaining -= ticks
    sequence.extend([_op("execute", fault="ack_lost"), _op("execute")])
    if len(sequence) > 16:
        return False
    rows = acquisition.ask(provider, sequence, f"replay_at_global_entry_tick_{phase}")
    return bool(rows and rows[-2]["effect_count"] == 1 and rows[-1]["effect_count"] == 1
                and rows[-1]["response"] == "DONE" and rows[-1]["hold_count"] == 0)


def _replace_unqualified_replay(provider, profile, acquisition):
    if profile["compensation"]:
        profile["direct"] = "compensate_before_retry"
        return
    profile["direct"] = None
    rows = acquisition.ask(provider, [
        _op("status"), _op("fence"), _op("execute", fault="ack_lost"),
        _op("status"), _op("fence"), _op("cancel")
    ], "alternative_resolver_after_phase_replay_rejection")
    if not rows:
        return
    present = rows[2]["effect_count"] == 1
    compensation = (present and rows[5]["response"] == "CANCELLED"
                    and rows[5]["effect_count"] == 0 and rows[5]["hold_count"] == 0)
    fence = (present and rows[1]["response"] == "ABSENT" and rows[1]["effect_count"] == 0
             and rows[4]["response"] == "DONE" and rows[4]["effect_count"] == 1)
    status = (present and rows[0]["response"] == "ABSENT" and rows[0]["effect_count"] == 0
              and rows[3]["response"] == "DONE" and rows[3]["effect_count"] == 1)
    profile["compensation"] = compensation
    if fence:
        profile["direct"] = "fence_reconciliation"
    elif compensation:
        profile["direct"] = "compensate_before_retry"
    elif status:
        profile["direct"] = "tested_status_reconciliation"


def construct(task, probe):
    providers = task["providers"]
    acquisition = _Acquisition(task, probe)
    profiles = [_direct_profile(provider, acquisition) for provider in providers]
    risky = sum(bool(p["direct"]) and not p["compensation"] for p in profiles)
    delayed = sum(p["direct"] == "bounded_delayed_status_reconciliation" for p in profiles)
    window = max(4, 4 * len(providers) + 8 * delayed)
    for provider, profile in zip(providers, profiles):
        if profile["direct"] is None or (risky > 1 and not profile["compensation"]):
            _prepare_profile(provider, profile, acquisition, window)
    phase_cache = {profile["id"]: {0: True} for profile in profiles}
    provider_by_id = {provider["id"]: provider for provider in providers}
    candidates = []
    for refinement in range(len(providers) + 1):
        candidates = _candidate_assignments(profiles, int(task["max_steps"]))
        if not candidates:
            break
        failure = None
        for profile, phases in _replay_entry_phases(profiles, candidates[0]["roles"]):
            for phase in phases:
                cached = phase_cache[profile["id"]]
                if phase not in cached:
                    cached[phase] = _qualify_replay_phase(provider_by_id[profile["id"]], phase, acquisition)
                if not cached[phase]:
                    failure = (profile, phase)
                    break
            if failure:
                break
        if not failure:
            acquisition.trace.append({"event": "global_phase_replay_qualification", "phases": phase_cache})
            break
        profile, phase = failure
        acquisition.trace.append({"event": "replay_scope_rejected", "provider": profile["id"],
                                   "entry_phase": phase, "refinement": refinement,
                                   "reason": "phase conformance failed or remained unaffordable/unmeasured"})
        provider = provider_by_id[profile["id"]]
        _replace_unqualified_replay(provider, profile, acquisition)
        if profile["direct"] is None and not profile["prepared"]:
            _prepare_profile(provider, profile, acquisition, window)
        if refinement == len(providers):
            candidates = []
    ids = [p["id"] for p in profiles]
    graph = _Graph(ids)
    if not candidates:
        entry = "aborted"
        decision = {"event": "no_deploy", "reason": "no_qualified_complete_protocol_within_budget"}
    else:
        selected = candidates[0]
        selected_roles = list(zip(profiles, selected["roles"]))
        prepared = [p for p, role in selected_roles if role == "prepared"]
        reversible = [p for p, role in selected_roles if role == "direct" and p["compensation"]]
        irreversible = [p for p, role in selected_roles if role == "direct" and not p["compensation"]]
        cleanup = graph.cleanup(ids)
        entry = "delivered"
        for profile in reversed(prepared):
            entry = graph.commit(profile, entry, cleanup)
        for profile in reversed(reversible + irreversible):
            entry = graph.execute(profile, entry, cleanup)
        for profile in reversed(prepared):
            entry = graph.call("reserve", profile["id"], {"RESERVED": entry, "REFUSED": cleanup})
        decision = {"event": "select_conventional_protocol", "selected": selected,
                    "candidate_count": len(candidates), "all_candidates": candidates,
                    "rule": "minimum worst call cost among qualified finite role assignments"}
    if len(graph.nodes) > int(task.get("maximum_program_nodes", 256)):
        raise ValueError("constructed graph exceeds public node envelope")
    acquisition.trace.extend([{"event": "observed_profiles", "profiles": profiles}, decision])
    return {"program": {"entry": entry, "nodes": graph.nodes}, "trace": acquisition.trace,
            "retained": {"method": METHOD, "source": "model_agent_authored_conventional_procedure",
                         "K1_lessons": list(K1_LESSONS), "new_model_calls_during_confirmation": 0,
                         "scope": "bounded tested semantics; not full automata-learning or global optimality"}}
