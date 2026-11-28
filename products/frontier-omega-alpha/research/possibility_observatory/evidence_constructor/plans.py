"""Construct a check order while preserving a fixed three-valued evidence contract."""

from functools import cache
from fractions import Fraction
from itertools import permutations

CHECKS = ("scope", "chronology", "role", "qualification")
FIXED = tuple(range(len(CHECKS)))
ALL = (1 << len(CHECKS)) - 1


def condition(actual, required, *, chronology=False):
    if actual is None:
        return None
    return actual <= required if chronology else actual == required


def check(case, index):
    details = case["observed"]
    requirements = case["required"]
    name = CHECKS[index]
    return condition(details[name], requirements[name], chronology=name == "chronology")


def evaluate(case, order):
    missing = []
    for count, index in enumerate(order, 1):
        result = check(case, index)
        if result is False:
            return "inapplicable", count, [CHECKS[index]]
        if result is None:
            missing.append(CHECKS[index])
    return ("insufficient", count, sorted(missing)) if missing else ("supported", count, [])


def masks(cases):
    """Each bit identifies a case in which the predicate definitely fails."""
    return tuple(sum(1 << i for i, case in enumerate(cases) if check(case, field) is False)
                 for field in FIXED)


def work(order, failures, size):
    survivors = (1 << size) - 1
    steps = 0
    for index in order:
        steps += survivors.bit_count()
        survivors &= ~failures[index]
    return steps


def greedy(failures, size):
    survivors = (1 << size) - 1
    remaining = list(FIXED)
    order = []
    while remaining:
        first = min(remaining, key=lambda index: (-(survivors & failures[index]).bit_count(), index))
        order.append(first)
        remaining.remove(first)
        survivors &= ~failures[first]
    return tuple(order)


def optimal(failures, size):
    survivors = (1 << size) - 1

    @cache
    def tail(checked):
        if checked == ALL:
            return 0, ()
        remaining_cases = work_survivors(checked, survivors, failures)
        choices = []
        for index in FIXED:
            if not checked & (1 << index):
                remaining_work, remaining_order = tail(checked | (1 << index))
                choices.append((remaining_work + remaining_cases.bit_count(), (index, *remaining_order)))
        return min(choices)

    return tail(0)[1]


def work_survivors(checked, all_cases, failures):
    for index in FIXED:
        if checked & (1 << index):
            all_cases &= ~failures[index]
    return all_cases


def exhaustive(failures, size):
    return min(permutations(FIXED), key=lambda order: (work(order, failures, size), order))


def worst_group(groups):
    def score(order):
        costs = [Fraction(work(order, failures, size), size) for failures, size in groups]
        return max(costs), sum(costs), order

    return min(permutations(FIXED), key=score)


def group_masks(groups):
    return [(masks(group), len(group)) for group in groups]


def pooled_masks(groups):
    combined = [case for group in groups for case in group]
    return masks(combined), len(combined)


def choose_update(groups):
    """Select a supplied update rule using only development-group omissions."""
    if len(groups) < 2 or any(not group for group in groups):
        raise ValueError("Need at least two nonempty development groups")
    scores = {"pooled": Fraction(0), "group-worst-case": Fraction(0)}
    for index, held in enumerate(groups):
        train = groups[:index] + groups[index + 1:]
        held_mask = masks(held)
        scores["pooled"] += Fraction(work(optimal(*pooled_masks(train)), held_mask, len(held)), len(held))
        scores["group-worst-case"] += Fraction(
            work(worst_group(group_masks(train)), held_mask, len(held)), len(held)
        )
    mode = min(scores, key=lambda name: (scores[name], name != "pooled"))
    chosen = optimal(*pooled_masks(groups)) if mode == "pooled" else worst_group(group_masks(groups))
    return chosen, mode, {key: str(score) for key, score in scores.items()}
