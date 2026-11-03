from __future__ import annotations

try:
    from .kernel import Certificate, validate_game
except ImportError:
    from kernel import Certificate, validate_game


def full_tree_layers(transitions, safe, targets, horizon, invariant=None, memoize=False):
    validate_game(transitions, safe, targets, horizon, invariant)
    allowed = set(safe) & (set(transitions) if invariant is None else set(invariant))
    goal, cache, policy = set(targets), {}, {}
    checks = 0

    def win(state, remaining):
        nonlocal checks
        if state not in allowed:
            return False
        if state in goal:
            return True
        if remaining == 0:
            return False
        if memoize and (state, remaining) in cache:
            return cache[state, remaining]
        for action, outcomes in sorted(transitions[state].items()):
            okay = True
            for next_state in outcomes:
                checks += 1
                if not win(next_state, remaining - 1):
                    okay = False
                    break
            if okay:
                policy[remaining, state] = action
                cache[state, remaining] = True
                return True
        cache[state, remaining] = False
        return False

    layers = [{state for state in transitions if win(state, remaining)} for remaining in range(horizon + 1)]
    return Certificate(layers, policy, checks)
