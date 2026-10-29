"""Construct a conditional DC transaction envelope from a retained screening instrument."""
import copy
import time


def construct(model, screening, maximum_mw=1000.0):
    start = time.perf_counter()
    base = screening(copy.deepcopy(model))
    changed = copy.deepcopy(model)
    changed["p_mw"][0] += 1.0
    changed["p_mw"][-1] -= 1.0
    perturbed = screening(changed)
    low, high, limiting, unknown = 0.0, maximum_mw, [], []
    for before, after in zip(base["contingencies"], perturbed["contingencies"]):
        if before["status"] != "CONNECTED" or after["status"] != "CONNECTED":
            unknown.append(before["outage"])
            continue
        for i, branch in enumerate(model["branches"]):
            if not branch["status"] or branch["id"] == before["outage"] or branch["rate_mw"] <= 0:
                continue
            flow = before["flows_mw"][i]
            gain = after["flows_mw"][i] - flow
            rate = branch["rate_mw"]
            if abs(gain) < 1e-10:
                if abs(flow) > rate + 1e-6:
                    high = -1.0
                continue
            ends = sorted([(-rate - flow) / gain, (rate - flow) / gain])
            low = max(low, ends[0])
            if ends[1] < high:
                high = ends[1]
                limiting = [{"outage": before["outage"], "branch": branch["id"]}]
    interval = [max(0.0, low), min(maximum_mw, high)] if low <= high and high >= 0 else None
    return {"artifact": "conditional-connected-contingency-transfer-envelope/v1",
            "transfer_from": model["buses"][0], "transfer_to": model["buses"][-1],
            "interval_mw": interval, "limiting_pairs": limiting, "unknown_outages": unknown,
            "operationally_admissible": False,
            "reason": "DC only; islanding unknowns, feasible generator dispatch, voltage and dynamic limits unresolved",
            "construction_wall_seconds": time.perf_counter() - start}
