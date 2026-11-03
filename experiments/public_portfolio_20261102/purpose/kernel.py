from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Certificate:
    layers: list[set[str]]
    policy: dict[tuple[int, str], str]
    transition_checks: int

    @property
    def winning(self):
        return self.layers[-1]

    def as_json(self):
        return {"layers": [sorted(x) for x in self.layers], "policy": [[t, s, a] for (t, s), a in sorted(self.policy.items())], "transition_checks": self.transition_checks}


def validate_game(transitions, safe, targets, horizon, invariant=None):
    if type(horizon) is not int or horizon < 0:
        raise ValueError("horizon must be a nonnegative integer")
    if not isinstance(transitions, dict) or not transitions or any(not isinstance(s, str) for s in transitions):
        raise ValueError("nonempty finite string-state game required")
    domain = set(transitions)
    for collection in (safe, targets, domain if invariant is None else invariant):
        if not set(collection) <= domain:
            raise ValueError("set contains an undeclared state")
    for actions in transitions.values():
        if not isinstance(actions, dict):
            raise ValueError("state actions must be a dictionary")
        for action, outcomes in actions.items():
            if not isinstance(action, str) or not isinstance(outcomes, (tuple, list)) or not outcomes:
                raise ValueError("nonempty adversarial outcome list required")
            if any(next_state not in domain for next_state in outcomes):
                raise ValueError("transition leaves declared domain")


def reach_avoid(transitions, safe, targets, horizon, invariant=None):
    validate_game(transitions, safe, targets, horizon, invariant)
    allowed = set(safe) & (set(transitions) if invariant is None else set(invariant))
    terminal = set(targets) & allowed
    layers, policy, checks = [terminal], {}, 0
    for remaining in range(1, horizon + 1):
        prior = layers[-1]
        current = set(prior)
        for state in sorted(allowed - terminal):
            for action, outcomes in sorted(transitions[state].items()):
                checks += len(outcomes)
                if all(next_state in prior for next_state in outcomes):
                    current.add(state)
                    policy[remaining, state] = action
                    break
        layers.append(current)
    return Certificate(layers, policy, checks)


def recovery_set(transitions, safe, emergency, horizon):
    return reach_avoid(transitions, safe, emergency, horizon)


def verify_certificate(transitions, safe, targets, certificate, invariant=None):
    allowed = set(safe) & (set(transitions) if invariant is None else set(invariant))
    if not certificate.layers or certificate.layers[0] != (set(targets) & allowed):
        return False
    for remaining in range(1, len(certificate.layers)):
        previous, current = certificate.layers[remaining - 1:remaining + 1]
        expected = set(targets) & allowed
        for state in allowed - set(targets):
            if any(outcomes and all(next_state in previous for next_state in outcomes) for outcomes in transitions[state].values()):
                expected.add(state)
        if expected != current:
            return False
        for state in current - set(targets):
            action = certificate.policy.get((remaining, state))
            if action not in transitions[state] or not all(next_state in previous for next_state in transitions[state][action]):
                return False
    return True
