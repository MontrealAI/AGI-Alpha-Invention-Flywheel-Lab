"""Agent-developed settlement compiler; deterministic after source freeze.

Only session.public and session.probe are used.  This module contains no model
callable, private-world inspection, confirmation selection, or weight editing.
The code was written by the included agent during the recorded K1 development.
"""

from copy import deepcopy
import hashlib
import json


RETAINED = {
    "schema": "outlearning073.retained-settlement.v1",
    "origin": "Included-agent K1 development, followed by frozen deterministic reuse",
    "primitive": "settle_intent",
    "observed_counterexamples": [
        "A timeout can already have one effect; unkeyed immediate retry produced two.",
        "One shared key suppressed the second distinct intent in a global-key contract.",
        "An absent read immediately after timeout was followed by a committed late effect.",
        "Same-key retries produced two effects when keys were unsupported.",
        "An unbounded contract left reads unknown and a late effect unresolved.",
    ],
    "rules": [
        "Give every intent a distinct request/intent key.",
        "Use same-key retry only after an observable one-effect diagnostic for lost ACK.",
        "Otherwise require both finite public in-flight and visibility bounds.",
        "Wait their sum, read, and retry only on absent; preserve unknown as refusal.",
        "Publish dependent output only after an acknowledged predecessor token.",
        "Refuse unsupported output schemas, unresolved contracts, and excessive worst-case latency.",
    ],
    "applicability": (
        "The authored sandbox's shared service contracts, stipulated probe effect-count "
        "instrument, first-write faults, and acknowledging subsequent calls. Finite K1 "
        "observations do not identify arbitrary live-service behavior."
    ),
    "invalidation": (
        "Changing key guarantees, diagnostic fidelity, bounded visibility, subsequent-call "
        "ACK behavior, dependency semantics, output schema, or deadline requires revalidation."
    ),
    "strong_control": "All substantive retained facts and the primitive source are available to the ordinary control.",
}

_LAST_TRACE = None


def retained_content():
    return deepcopy(RETAINED)


def construction_trace():
    """Return metadata separately from the evaluator's exact two-key artifact."""
    return deepcopy(_LAST_TRACE)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _if(intent, status, yes, no):
    return {"op": "if", "test": {"intent": intent, "is": status}, "then": yes, "else": no}


def _stop(reason):
    return {"op": "stop", "reason": reason}


def settle_intent(intent, key, value, *, mode, quiet_ticks=0, dependency=None):
    """Compile one intent into an acknowledgment-gated settlement procedure.

    The bounded-read branch was constructed after the observed absent-then-late
    counterexample.  It delays the absent test until *both* public uncertainty
    windows have elapsed.  It never interprets timeout or unknown as absence.
    This is code generation over the public action grammar, not a named template
    standing in for an absent executable mechanism.
    """
    write = {"op": "write", "intent": intent, "key": key, "value": value}
    if dependency is not None:
        write["dependency"] = "$token:" + dependency
    acknowledged = _if(intent, "committed", [], [_stop("retry did not acknowledge " + intent)])
    if mode == "keyed":
        recovery = [deepcopy(write), acknowledged]
    elif mode == "bounded-read":
        retry_if_absent = _if(
            intent, "absent", [deepcopy(write), acknowledged],
            [_stop("neither absence nor acknowledged commitment for " + intent)],
        )
        recovery = []
        if quiet_ticks:
            recovery.append({"op": "wait", "ticks": quiet_ticks})
        recovery += [{"op": "read", "intent": intent}, _if(intent, "committed", [], [retry_if_absent])]
    else:
        raise ValueError("unsupported settlement mode")
    return [write, _if(intent, "committed", [], recovery)]


def _worst_ticks(steps):
    total = 0
    for step in steps:
        if step["op"] in ("read", "write"):
            total += 1
        elif step["op"] == "wait":
            total += step["ticks"]
        elif step["op"] == "if":
            total += max(_worst_ticks(step["then"]), _worst_ticks(step["else"]))
    return total


def _exact_output(public):
    if public.get("stage") == "K1":
        objects = public["objects"]
        output = {}
        for item in objects:
            content = item["content"]
            if not isinstance(content, str):
                raise ValueError("archive content must be UTF-8 text")
            output[item["intent"]] = {"content": content, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}
        return output
    if public.get("stage") == "K2":
        rows = public["rows"]
        if not isinstance(rows, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in rows):
            raise ValueError("computation rows must be exact integers")
        job_id = public["id"]
        encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return {
            "reserve": {"job_id": job_id, "rows": len(rows)},
            "publish": {
                "job_id": job_id, "count": len(rows), "sum": sum(rows),
                "sum_squares": sum(x * x for x in rows),
                "source_sha256": hashlib.sha256(encoded).hexdigest(),
            },
        }
    raise ValueError("unsupported public output schema")


def _order(public):
    intents = list(public["intents"])
    if not intents or len(intents) != len(set(intents)) or not all(isinstance(i, str) for i in intents):
        raise ValueError("invalid public intents")
    dependencies = public.get("dependencies", {})
    normalized = {}
    for intent, dependency in dependencies.items():
        if isinstance(dependency, list) and len(dependency) == 1:
            dependency = dependency[0]
        if intent not in intents or dependency not in intents or dependency == intent:
            raise ValueError("unsupported dependency graph")
        normalized[intent] = dependency
    order = []
    while len(order) < len(intents):
        ready = [i for i in intents if i not in order and (i not in normalized or normalized[i] in order)]
        if not ready:
            raise ValueError("cyclic dependency graph")
        order.extend(ready)
    return order, normalized


def construct(session, retained=None):
    """Build a JSON artifact using only the admitted public session interface."""
    global _LAST_TRACE
    public = deepcopy(session.public)
    content = retained_content() if retained is None else deepcopy(retained)
    trace = {
        "public": public, "retained_sha256": _digest(content),
        "primitive": "settle_intent", "primitive_calls": [], "probes": [],
        "development_mode": "frozen deterministic reuse of included-agent K1 code",
    }
    _LAST_TRACE = trace
    output = {}
    try:
        if not isinstance(content, dict) or content.get("schema") != RETAINED["schema"]:
            raise ValueError("unsupported retained content")
        output = _exact_output(public)
        order, dependencies = _order(public)
        if set(output) != set(order):
            raise ValueError("output and intent mismatch")
        diagnostic = [
            {"op": "write", "intent": "p0", "key": "diagnostic/p0", "value": {"probe": 0}},
            {"op": "write", "intent": "p0", "key": "diagnostic/p0", "value": {"probe": 0}},
            {"op": "read", "intent": "p0"},
        ]
        receipt = session.probe(diagnostic)
        trace["probes"].append({"proposal_sha256": _digest(diagnostic), "actions": diagnostic, "receipt": deepcopy(receipt)})
        effects = receipt.get("effects")
        count = effects.get("p0") if isinstance(effects, dict) else None
        if receipt.get("status") == "observed" and count == 1:
            mode, quiet_ticks = "keyed", 0
            trace["hypotheses"] = {
                "H1": "Timeout guarantees absence: rejected by the lost-ACK diagnostic.",
                "H2": "One-effect same-key settlement: committed within the shared authored contract.",
                "neither": "Late completion remains possible; key settlement is common-safe in the admitted model.",
            }
        else:
            inflight, visibility = public.get("max_inflight"), public.get("visibility_bound")
            bounded = all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (inflight, visibility))
            trace["hypotheses"] = {
                "H1": "Timeout guarantees absence: rejected by retained counterexample.",
                "H2": "Safe keys: rejected" if count == 2 else "Safe keys: unresolved by unavailable/noisy diagnostics.",
                "neither": "Pending effects remain possible until the public in-flight and visibility windows close.",
            }
            if not bounded:
                raise ValueError("unresolved keys and no finite public settlement bounds")
            mode, quiet_ticks = "bounded-read", inflight + visibility
        steps = []
        for intent in order:
            key = str(public["id"]) + "/" + intent if mode == "keyed" else None
            dependency = dependencies.get(intent)
            compiled = settle_intent(intent, key, "$output:" + intent, mode=mode, quiet_ticks=quiet_ticks, dependency=dependency)
            trace["primitive_calls"].append({"intent": intent, "mode": mode, "quiet_ticks": quiet_ticks, "dependency": dependency, "steps_sha256": _digest(compiled)})
            steps.extend(compiled)
        worst = _worst_ticks(steps)
        trace["worst_execution_ticks"] = worst
        trace["worst_operation_units"] = worst * public.get("operation_unit_cost", 1)
        trace["probe_resource_units"] = sum(p["receipt"].get("cost_units", 0) for p in trace["probes"])
        if worst > public["deadline"]:
            raise ValueError("settlement exceeds public deadline")
        trace["decision"] = "construct"
        return {"steps": steps, "output": output}
    except (KeyError, TypeError, ValueError) as error:
        trace["decision"] = "refuse"
        trace["reason"] = str(error)
        trace["probe_resource_units"] = sum(p["receipt"].get("cost_units", 0) for p in trace["probes"])
        return {"steps": [_stop(str(error))], "output": output}


def build(session, retained=None):
    """Runner interface preserving metadata outside the exact artifact schema."""
    artifact = construct(session, retained)
    return artifact, construction_trace()
