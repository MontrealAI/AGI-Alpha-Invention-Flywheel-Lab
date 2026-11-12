# SPDX-License-Identifier: Apache-2.0
"""Matched construction-method study for the existing workshop qualification runner."""
from __future__ import annotations

from time import monotonic

from bridge.instruments import strict_portable_json
from bridge.workflows import digest

BASELINE = "List the output contract. Derive the simplest formulas. Check edge conditions before finishing."

# These trial contracts and their independently computed cases are fixed before
# obtaining a candidate procedure. The procedure proposer receives neither.
TASKS = {
    "dispatch": {
        "ambition": "Find the earliest authorized completion window for a service dispatch.",
        "contract": "Inputs earliest, deadline, busyUntil, duration are integer minutes. authorized is boolean. "
                    'Return exactly {"feasible":boolean,"start":number or null}. '
                    "Choose the larger of earliest and busyUntil. That start is feasible if authorized, duration is positive, "
                    "and start plus duration is at most deadline. Return null for an infeasible start.",
        "rows": [
            (10, 30, 12, 18, True), (10, 30, 13, 18, True), (10, 30, 5, 5, False),
            (10, 30, 12, 0, True), (12, 80, 5, 15, True), (20, 50, 35, 15, True),
            (20, 49, 35, 15, True), (3, 7, 2, 3, True), (3, 7, 8, 1, True),
        ],
    },
    "handover": {
        "ambition": "Route a service handover to a safe status based on record freshness and authority.",
        "contract": "Inputs allowed, logged, repairable are booleans. age and limit are integer minutes. "
                    'Return exactly {"decision":string}. If allowed is false, return blocked. Otherwise, '
                    "if logged is false, age is negative or age exceeds limit, return inspect if repairable and stop otherwise. "
                    "With a valid record, return proceed.",
        "rows": [
            (False, True, True, 0, 7), (True, True, False, 7, 7), (True, True, True, 8, 7),
            (True, False, False, 4, 7), (True, False, True, 4, 7), (True, True, False, -1, 7),
            (True, True, False, 8, 7), (True, True, True, 0, 0), (False, False, False, 9, 7),
        ],
    },
}


def dispatch(row):
    earliest, deadline, busy_until, duration, authorized = row
    start = max(earliest, busy_until)
    feasible = authorized and duration > 0 and start + duration <= deadline
    return {"feasible": feasible, "start": start if feasible else None}


def handover(row):
    allowed, logged, repairable, age, limit = row
    if not allowed:
        return {"decision": "blocked"}
    if not logged or age < 0 or age > limit:
        return {"decision": "inspect" if repairable else "stop"}
    return {"decision": "proceed"}


def cases(name):
    fields, oracle = (
        (("earliest", "deadline", "busyUntil", "duration", "authorized"), dispatch) if name == "dispatch"
        else (("allowed", "logged", "repairable", "age", "limit"), handover)
    )
    return [{"input": dict(zip(fields, row)), "expected": oracle(row)} for row in TASKS[name]["rows"]]


def run(api, generate, trial, output):
    initial = output / "foundry" / "instrument.json"
    if not initial.is_file():
        return {"status": "NOT_TESTED", "reason": "No initial accepted construction to compare."}
    frozen = {name: {"contract": TASKS[name]["contract"], "cases_sha256": digest(cases(name))} for name in TASKS}
    start = monotonic()
    proposal = generate(
        "Propose one compact reusable method for a builder that turns a public input/output contract into "
        "a bounded formula instrument. Draw a lesson from the calibration example: verify the support conditions "
        "before inferring a decision from ambiguous readings. Consider what an ordinary engineer would do. "
        'Return JSON with exactly {"guidance":"text under 600 characters"}. This advice grants no permissions.'
    )
    discovery_seconds = monotonic() - start
    info = {key: proposal.get(key) for key in ("provider", "model", "reported_model", "usage", "cost")}
    info["response_sha256"] = digest(proposal["text"])
    try:
        data = strict_portable_json(proposal["text"])
        guidance = data["guidance"]
        if set(data) != {"guidance"} or not isinstance(guidance, str) or not 0 < len(guidance) <= 600:
            raise ValueError("Invalid bounded guidance.")
    except (ValueError, KeyError, TypeError):
        return {"status": "REJECTED_PROCEDURE", "frozen_tasks": frozen, "discovery": info}
    artifact = initial.read_text(encoding="utf-8")
    material = {
        "ordinary": BASELINE,
        "retained_method": guidance,
        "equal_content": guidance,
        "artifact_only": "Prior calibration artifact, provided as an example of a format and no evidence for this task:\n" + artifact,
        "no_inheritance": "",
    }
    results = []
    for name, task in TASKS.items():
        for arm, context in material.items():
            result = trial(api, output, "custom", task["ambition"], trial_name=f"study-{name}-{arm}",
                           context=task["contract"] + "\n" + context, cases=cases(name))
            results.append({"task": name, "arm": arm, "context_sha256": digest(context), "result": result})
    return {
        "status": "MEASURED", "frozen_tasks": frozen, "baseline_guidance": BASELINE, "candidate_guidance": guidance,
        "discovery": info, "discovery_seconds": discovery_seconds, "results": results,
        "scope": "Each arm uses the same model, cases, tool permissions, attempt budget and output cap. "
                 "The retained and ordinary equal-content arms receive identical guidance. The separate imperative "
                 "references generate acceptance labels. Human engineering, inference economics and downstream operating "
                 "costs remain unknown. Two finite tasks cannot establish general method superiority.",
    }
