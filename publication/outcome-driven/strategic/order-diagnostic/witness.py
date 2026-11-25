"""Check event order and checkpoint availability under a declared two-player game."""

import argparse
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
import json
from pathlib import Path


PHASES = {"notice", "policy", "fix", "signal", "row"}


def distinct_strings(items):
    return (isinstance(items, list) and all(isinstance(item, str) and item for item in items)
            and len(set(items)) == len(items))


def read_witness(document):
    if not isinstance(document, dict) or set(document) != {"actors", "events", "phases", "before", "access", "revisions"}:
        raise ValueError("Expected actors, events, phases, before, access and revisions")
    actors, events, phases = (document[key] for key in ("actors", "events", "phases"))
    if not distinct_strings(actors) or not isinstance(events, dict) or not all(
            isinstance(event, str) and event and actor in actors for event, actor in events.items()):
        raise ValueError("Each named event needs a declared actor")
    if (not isinstance(phases, dict) or set(phases) != PHASES or not distinct_strings(list(phases.values()))
            or not set(phases.values()).issubset(events)):
        raise ValueError("The five phases need distinct declared events")
    payer, opponent = events[phases["row"]], events[phases["fix"]]
    if payer == opponent or any(events[phases[key]] != payer for key in ("notice", "policy")):
        raise ValueError("The payer announces and sets policy, and a different actor fixes the state")
    revisions = document["revisions"]
    if (not isinstance(revisions, dict) or set(revisions) != {"complete", "events"}
            or type(revisions["complete"]) is not bool or not distinct_strings(revisions["events"])
            or any(event in phases.values() or events.get(event) != opponent for event in revisions["events"])):
        raise ValueError("Revision opportunities need distinct additional opponent events and explicit coverage")

    parents = {event: set() for event in events}
    if not isinstance(document["before"], list):
        raise ValueError("Order constraints must be a list of event pairs")
    for pair in document["before"]:
        if not isinstance(pair, list) or len(pair) != 2 or not all(
                isinstance(event, str) and event in events for event in pair):
            raise ValueError("Order constraints need two declared events")
        earlier, later = pair
        parents[later].add(earlier)

    claims = defaultdict(lambda: {True: set(), False: set()})
    if not isinstance(document["access"], list):
        raise ValueError("Access claims must be a list")
    for claim in document["access"]:
        if not isinstance(claim, list) or len(claim) != 4:
            raise ValueError("Access requires an event outcome, actor, checkpoint and boolean")
        outcome, actor, checkpoint, seen = claim
        if (not isinstance(outcome, str) or outcome not in events or actor not in actors
                or not isinstance(checkpoint, str) or checkpoint not in events or type(seen) is not bool):
            raise ValueError("Access claims must refer to declared actors and events")
        claims[outcome, actor][seen].add(checkpoint)
        if seen and outcome != checkpoint:
            parents[checkpoint].add(outcome)

    # Denial after the same actor already had access would contradict retention.
    for by_access in claims.values():
        for seen_at in by_access[True]:
            parents[seen_at].update(by_access[False])
    return parents, claims, payer, opponent


def assess(document):
    parents, claims, payer, opponent = read_witness(document)
    predecessors = {}
    try:
        for event in TopologicalSorter(parents).static_order():
            predecessors[event] = parents[event].union(*(predecessors[parent] for parent in parents[event]))
    except CycleError:
        return {"timing": "invalid", "proof": None}

    def before(earlier, later):
        return earlier in predecessors[later]

    def available(outcome, actor, checkpoint):
        checkpoints = claims[outcome, actor]
        if any(prior == checkpoint or before(prior, checkpoint) for prior in checkpoints[True]):
            return True
        if before(checkpoint, outcome) or any(
                later == checkpoint or before(checkpoint, later) for later in checkpoints[False]):
            return False
        return None

    notice, policy, fix, signal, row = (document["phases"][key]
                                        for key in ("notice", "policy", "fix", "signal", "row"))
    revisions = document["revisions"]
    early_revisions = sorted(event for event in revisions["events"] if before(event, fix))
    feedback = sorted([event, outcome] for event in revisions["events"] for outcome in (signal, row)
                      if before(outcome, event) and available(outcome, opponent, event) is True)
    proof = {
        "notice_before_fix": before(notice, fix),
        "policy_before_fix": before(policy, fix),
        "opponent_has_notice": available(notice, opponent, fix),
        "opponent_has_policy": available(policy, opponent, fix),
        "fix_before_signal": before(fix, signal),
        "signal_before_row": before(signal, row),
        "row_before_signal": before(row, signal),
        "signal_access_by_row": {actor: available(signal, actor, row) for actor in document["actors"]},
        "complete_revision_coverage": revisions["complete"],
        "revisions_before_fix": early_revisions,
        "feedback_revisions": feedback,
    }
    if feedback:
        timing = "adaptive"
    elif proof["row_before_signal"]:
        timing = "late"
    elif (all(proof[fact] is True for fact in ("notice_before_fix", "policy_before_fix", "opponent_has_notice",
                                             "opponent_has_policy", "fix_before_signal", "signal_before_row",
                                             "complete_revision_coverage"))
          and len(early_revisions) == len(revisions["events"])
          and all(access is (actor == payer) for actor, access in proof["signal_access_by_row"].items())):
        timing = "private"
    else:
        timing = "unknown"
    return {"timing": timing, "proof": proof}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("witness", type=Path)
    args = parser.parse_args()
    print(json.dumps(assess(json.loads(args.witness.read_bytes())), indent=2, sort_keys=True))
