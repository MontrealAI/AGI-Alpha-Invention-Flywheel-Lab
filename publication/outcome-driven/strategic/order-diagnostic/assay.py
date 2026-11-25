"""Run the fixed structured witness diagnostic and record exact agreement."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform
from time import perf_counter

from reference import reference
from witness import assess


def scenario(order="usable", visibility="explicit", revisions="closed"):
    events = {"offer": "pilot", "plan": "pilot", "state": "rival", "reading": "pilot", "binding": "pilot"}
    phases = dict(notice="offer", policy="plan", fix="state", signal="reading", row="binding")
    before = [["offer", "state"], ["plan", "state"], ["state", "reading"], ["reading", "binding"]]
    access = [["offer", "rival", "state", True], ["plan", "rival", "state", True],
              ["reading", "pilot", "reading", True]]
    if order == "transitive":
        events["calibration"] = "observer"
        before.remove(["state", "reading"])
        before.extend([["state", "calibration"], ["calibration", "reading"]])
    elif order == "incomparable":
        before.remove(["reading", "binding"])
    elif order == "late":
        before.remove(["reading", "binding"])
        before.append(["binding", "reading"])
    elif order == "policy-after-state":
        before.remove(["plan", "state"])
        before.append(["state", "plan"])
        access.remove(["plan", "rival", "state", True])
    elif order == "cyclic":
        before.append(["binding", "offer"])

    if visibility != "unknown-opponent":
        access.append(["reading", "rival", "binding", visibility == "opponent-sees"])
    access.append(["reading", "observer", "binding", visibility == "other-actor-sees"])
    if visibility == "conflict":
        access.append(["reading", "rival", "reading", True])

    revision_events = []
    if revisions in ("feedback", "provisional", "row-feedback"):
        events["change"] = "rival"
        revision_events.append("change")
        if revisions == "provisional":
            before.append(["change", "state"])
        else:
            before.append(["state", "change"])
            outcome = "reading" if revisions == "feedback" else "binding"
            access.append([outcome, "rival", "change", True])

    return {"actors": ["pilot", "rival", "observer"], "events": events, "phases": phases, "before": before,
            "access": access, "revisions": {"complete": revisions != "open", "events": revision_events}}


def relabel_witness():
    original = scenario("transitive", revisions="provisional")
    events = dict(zip(original["events"], ("ξ7", "c2", "n5", "d4", "à1", "m3", "x6"), strict=True))
    actors = {"pilot": "partie β", "rival": "partie α", "observer": "partie γ"}
    return {
        "actors": list(reversed(actors.values())),
        "events": {events[key]: actors[value] for key, value in reversed(original["events"].items())},
        "phases": {phase: events[event] for phase, event in original["phases"].items()},
        "before": [[events[first], events[second]] for first, second in reversed(original["before"])],
        "access": [[events[item], actors[actor], events[point], yes] for item, actor, point, yes in reversed(original["access"])],
        "revisions": {"complete": True, "events": [events["change"]]},
    }


def fixtures():
    inferred = scenario()
    inferred["before"] = inferred["before"][2:]
    return {
        "complete-private": (scenario(), "private"),
        "transitive-private": (scenario("transitive"), "private"),
        "relabel-reorder-private": (relabel_witness(), "private"),
        "inferred-announcement": (inferred, "private"),
        "late": (scenario("late"), "late"),
        "adaptive-signal": (scenario(revisions="feedback"), "adaptive"),
        "adaptive-row": (scenario(revisions="row-feedback"), "adaptive"),
        "open-revisions": (scenario(revisions="open"), "unknown"),
        "unproved-observer-denial": (scenario(visibility="unknown-opponent"), "unknown"),
        "leaked-signal": (scenario(visibility="opponent-sees"), "unknown"),
        "unordered-binding": (scenario("incomparable"), "unknown"),
        "incompatible-availability": (scenario(visibility="conflict"), "invalid"),
        "explicit-cycle": (scenario("cyclic"), "invalid"),
        "external-observer": (scenario(visibility="other-actor-sees"), "unknown"),
        "late-and-adaptive": (scenario("late", revisions="row-feedback"), "adaptive"),
        "early-provisional-choice": (scenario(revisions="provisional"), "private"),
    }


def fingerprint(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def assay(registration):
    named = fixtures()
    if list(named) != registration["fixtures"]:
        raise ValueError("The named test roster changed")
    factors = registration["factorial"]
    crossed = {"/".join(values): scenario(*values) for values in product(
        factors["order"], factors["visibility"], factors["revisions"])}
    if len(crossed) != factors["cases"]:
        raise ValueError("The crossed test denominator changed")
    documents = {key: input_ for key, (input_, _) in named.items()} | crossed
    if any(len(document["events"]) > factors["max_events"] for document in documents.values()):
        raise ValueError("The registered finite reference envelope changed")

    start = perf_counter()
    actual = {key: assess(witness) for key, witness in documents.items()}
    closure_seconds = perf_counter() - start
    start = perf_counter()
    expected = {key: reference(witness) for key, witness in documents.items()}
    reference_seconds = perf_counter() - start

    disagreements = [key for key in documents if actual[key] != expected[key]]
    absolute_checks = {key: actual[key]["timing"] == status for key, (_, status) in named.items()}
    counts = Counter(result["timing"] for result in expected.values())
    false_privates = [key for key in disagreements if actual[key]["timing"] == "private" and expected[key]["timing"] != "private"]
    missed_privates = [key for key in disagreements if expected[key]["timing"] == "private" and actual[key]["timing"] != "private"]
    succeeded = (not disagreements and all(absolute_checks.values())
                 and set(counts) == {"private", "late", "adaptive", "unknown", "invalid"})
    return {
        "schema": "frontier/strategic-order-assay-v1", "passed": succeeded,
        "cases": len(documents), "named_checks_passed": sum(absolute_checks.values()),
        "named_cases": {key: actual[key]["timing"] for key in named},
        "crossed_cases": len(crossed), "whole_proof_matches": len(documents) - len(disagreements),
        "disagreements": disagreements, "reference_dispositions": dict(counts),
        "false_privates": false_privates, "missed_privates": missed_privates,
        "ambiguous_binding_control": actual["unordered-binding"],
        "late_and_adaptive_control": actual["late-and-adaptive"],
        "evidence_sha256": fingerprint(actual), "reference_evidence_sha256": fingerprint(expected),
        "structured_inputs_sha256": fingerprint(documents), "python": platform.python_version(),
        "processor": platform.machine(), "wall_seconds": {"closure": closure_seconds, "enumeration": reference_seconds},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--example", choices=fixtures())
    action.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.example:
        print(json.dumps(fixtures()[args.example][0], indent=2, ensure_ascii=False))
        return
    root = Path(__file__).resolve().parent
    registration = (root / "PRE-REGISTRATION.json").read_bytes()
    report = assay(json.loads(registration))
    report["registration_sha256"] = sha256(registration).hexdigest()
    report["source_sha256"] = {name: sha256((root / name).read_bytes()).hexdigest()
                               for name in ("witness.py", "reference.py", "assay.py")}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("passed", "cases", "whole_proof_matches", "reference_dispositions")}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
