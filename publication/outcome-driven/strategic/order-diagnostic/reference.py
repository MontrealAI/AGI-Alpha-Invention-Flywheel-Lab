"""Independent finite reference using complete event orders and access intervals."""

from collections import defaultdict
from itertools import permutations


def reference(document):
    events = tuple(document["events"])
    phases = document["phases"]
    notice, policy, fix, signal, row = (phases[name] for name in ("notice", "policy", "fix", "signal", "row"))
    payer, opponent = document["events"][row], document["events"][fix]
    change_options = document["revisions"]["events"]
    queries = [(notice, opponent, fix), (policy, opponent, fix)]
    queries.extend((signal, actor, row) for actor in document["actors"])
    queries.extend((outcome, opponent, change) for change in change_options for outcome in (signal, row))
    observations = defaultdict(list)
    for outcome, actor, checkpoint, available in document["access"]:
        observations[outcome, actor].append((checkpoint, available))
    for outcome, actor, _ in queries:
        observations[outcome, actor]

    possible_access = {query: set() for query in queries}
    certain_order = None
    for sequence in permutations(events):
        index = {event: position for position, event in enumerate(sequence)}
        if any(index[first] >= index[second] for first, second in document["before"]):
            continue

        access_interval = {}
        for key, mentions in observations.items():
            # Position len(events) means access is still unavailable at the last checkpoint.
            earliest, latest = index[key[0]], len(events)
            for checkpoint, available in mentions:
                if available:
                    latest = min(latest, index[checkpoint])
                else:
                    earliest = max(earliest, index[checkpoint] + 1)
            if earliest > latest:
                break
            access_interval[key] = (earliest, latest)
        if len(access_interval) != len(observations):
            continue

        order_pairs = {(first, second) for position, first in enumerate(sequence) for second in sequence[position + 1:]}
        certain_order = order_pairs if certain_order is None else certain_order.intersection(order_pairs)
        for query, answers in possible_access.items():
            outcome, actor, checkpoint = query
            earliest, latest = access_interval[outcome, actor]
            if earliest <= index[checkpoint]:
                answers.add(True)
            if latest > index[checkpoint]:
                answers.add(False)

    if certain_order is None:
        return {"timing": "invalid", "proof": None}

    def checked(outcome, actor, checkpoint):
        answers = possible_access[outcome, actor, checkpoint]
        return next(iter(answers)) if len(answers) == 1 else None

    early = sorted(change for change in change_options if (change, fix) in certain_order)
    feedback = sorted([change, outcome] for change in change_options for outcome in (signal, row)
                      if (outcome, change) in certain_order and checked(outcome, opponent, change) is True)
    observed_at_binding = {actor: checked(signal, actor, row) for actor in document["actors"]}
    notice_known = checked(notice, opponent, fix)
    policy_known = checked(policy, opponent, fix)
    required_order = ((notice, fix), (policy, fix), (fix, signal), (signal, row))
    expected_visibility = {actor: actor == payer for actor in document["actors"]}
    all_changes_early = document["revisions"]["complete"] and set(early) == set(change_options)
    private = (certain_order.issuperset(required_order) and notice_known and policy_known
               and observed_at_binding == expected_visibility and all_changes_early)
    if feedback:
        verdict = "adaptive"
    elif (row, signal) in certain_order:
        verdict = "late"
    elif private:
        verdict = "private"
    else:
        verdict = "unknown"
    return {"timing": verdict, "proof": {
        "notice_before_fix": (notice, fix) in certain_order,
        "policy_before_fix": (policy, fix) in certain_order,
        "opponent_has_notice": notice_known,
        "opponent_has_policy": policy_known,
        "fix_before_signal": (fix, signal) in certain_order,
        "signal_before_row": (signal, row) in certain_order,
        "row_before_signal": (row, signal) in certain_order,
        "signal_access_by_row": observed_at_binding,
        "complete_revision_coverage": document["revisions"]["complete"],
        "revisions_before_fix": early,
        "feedback_revisions": feedback,
    }}
