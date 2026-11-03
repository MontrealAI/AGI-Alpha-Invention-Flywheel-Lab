from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import json

try:
    from .kernel import reach_avoid, recovery_set
except ImportError:
    from kernel import reach_avoid, recovery_set


def belief_id(state, worlds):
    return json.dumps([state, sorted(worlds)], separators=(",", ":"))


def compile_belief_game(world_models):
    if not isinstance(world_models, dict) or not world_models or any(not isinstance(w, str) for w in world_models):
        raise ValueError("named finite world models required")
    names = sorted(world_models)
    states = set(world_models[names[0]])
    if not states or any(set(model) != states for model in world_models.values()):
        raise ValueError("all worlds must declare the same observed physical states")
    for model in world_models.values():
        for actions in model.values():
            if not isinstance(actions, dict):
                raise ValueError("actions dictionary required")
            for action, outcomes in actions.items():
                if not isinstance(action, str) or not outcomes or not isinstance(outcomes, (tuple, list)):
                    raise ValueError("nonempty modeled outcomes required")
                for outcome in outcomes:
                    if len(outcome) != 2 or outcome[0] not in states or not isinstance(outcome[1], str):
                        raise ValueError("outcome must be (declared next state, observation label)")
    game, metadata = {}, {}
    for count in range(1, len(names) + 1):
        for possible in combinations(names, count):
            for state in sorted(states):
                identifier = belief_id(state, possible)
                metadata[identifier] = {"physical_state": state, "possible_worlds": list(possible)}
                common = set.intersection(*(set(world_models[w][state]) for w in possible))
                actions = {}
                for action in sorted(common):
                    groups = defaultdict(set)
                    for world in possible:
                        for next_state, observation in world_models[world][state][action]:
                            groups[next_state, observation].add(world)
                    actions[action] = sorted({belief_id(next_state, worlds) for (next_state, _), worlds in groups.items()})
                game[identifier] = actions
    return game, metadata


def construct_diagnosis(world_models, safe_states, emergency_states, diagnosis_horizon, recovery_horizon, inherited_kernel=True):
    game, metadata = compile_belief_game(world_models)
    safe = {s for s, m in metadata.items() if m["physical_state"] in safe_states}
    emergency = {s for s, m in metadata.items() if m["physical_state"] in emergency_states}
    diagnosed = {s for s, m in metadata.items() if len(m["possible_worlds"]) == 1}
    if inherited_kernel:
        recovery = recovery_set(game, safe, emergency, recovery_horizon)
        certificate = reach_avoid(game, safe, diagnosed, diagnosis_horizon, recovery.winning)
    else:
        try:
            from .specialist import full_tree_layers
        except ImportError:
            from specialist import full_tree_layers
        recovery = full_tree_layers(game, safe, emergency, recovery_horizon, memoize=True)
        certificate = full_tree_layers(game, safe, diagnosed, diagnosis_horizon, invariant=recovery.winning, memoize=True)
    return {"game": game, "metadata": metadata, "safe": safe, "emergency": emergency, "diagnosed": diagnosed, "recovery": recovery, "certificate": certificate}
