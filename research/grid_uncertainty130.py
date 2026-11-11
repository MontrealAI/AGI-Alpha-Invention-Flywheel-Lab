"""Fixed-DC-model N-0/N-1 interval-flow certificate. Research only, no grid control."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


class InvalidModel(ValueError):
    pass


def _finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def validate(model):
    if not isinstance(model, dict) or set(model) != {"base_mva", "buses", "p_mw", "branches"}:
        raise InvalidModel("MODEL_SCHEMA")
    buses, branches, p = model["buses"], model["branches"], model["p_mw"]
    if (not isinstance(buses, list) or not 2 <= len(buses) <= 200 or
            any(type(b) is not int for b in buses) or len(set(buses)) != len(buses)):
        raise InvalidModel("BUSES_INVALID")
    if (not isinstance(branches, list) or not 1 <= len(branches) <= 500 or
            not isinstance(p, list) or len(p) != len(buses) or not all(_finite(x) for x in p)):
        raise InvalidModel("INJECTIONS_OR_BRANCHES_INVALID")
    if not _finite(model["base_mva"]) or model["base_mva"] <= 0:
        raise InvalidModel("BASE_MVA_INVALID")
    seen = set()
    for b in branches:
        if not isinstance(b, dict) or set(b) != {"id", "from_bus", "to_bus", "x", "tap", "shift_deg", "rate_mw", "status"}:
            raise InvalidModel("BRANCH_SCHEMA")
        if type(b["id"]) is not int or b["id"] in seen:
            raise InvalidModel("BRANCH_ID")
        seen.add(b["id"])
        if (type(b["from_bus"]) is not int or type(b["to_bus"]) is not int or
                b["from_bus"] not in buses or b["to_bus"] not in buses or b["from_bus"] == b["to_bus"]):
            raise InvalidModel("BRANCH_ENDPOINT")
        if any(not _finite(b[k]) for k in ("x", "tap", "shift_deg", "rate_mw")):
            raise InvalidModel("BRANCH_NONFINITE")
        if b["x"] <= 0 or b["tap"] <= 0 or b["rate_mw"] < 0 or type(b["status"]) is not int or b["status"] not in (0, 1):
            raise InvalidModel("BRANCH_UNSUPPORTED")


def connected(model, outage=None):
    adjacency = {i: [] for i in model["buses"]}
    for i, b in enumerate(model["branches"]):
        if b["status"] and i != outage:
            adjacency[b["from_bus"]].append(b["to_bus"])
            adjacency[b["to_bus"]].append(b["from_bus"])
    seen, stack = set(), [model["buses"][0]]
    while stack:
        v = stack.pop()
        if v not in seen:
            seen.add(v)
            stack.extend(adjacency[v])
    return len(seen) == len(adjacency)


def radii_for(model, fraction):
    if not _finite(fraction) or fraction < 0:
        raise InvalidModel("UNCERTAINTY_FRACTION_INVALID")
    return [fraction * max(abs(p), 1.0) for p in model["p_mw"][1:]]


def _matrix(model, outage=None):
    n = len(model["buses"])
    ids = {bus: k for k, bus in enumerate(model["buses"])}
    active = [(i, b) for i, b in enumerate(model["branches"])
              if b["status"] == 1 and i != outage]
    a = np.zeros((len(active), n - 1), dtype=float)
    w = np.empty(len(active), dtype=float)
    shift = np.empty(len(active), dtype=float)
    for k, (_, b) in enumerate(active):
        fr, to = ids[b["from_bus"]], ids[b["to_bus"]]
        if fr:
            a[k, fr - 1] += 1.0
        if to:
            a[k, to - 1] -= 1.0
        w[k] = 1.0 / (float(b["x"]) * float(b["tap"]))
        shift[k] = math.radians(b["shift_deg"])
    matrix = a.T @ (w[:, None] * a)
    if not np.isfinite(matrix).all() or np.linalg.cond(matrix) > 1e12:
        raise InvalidModel("ILL_CONDITIONED_DC_SYSTEM")
    return active, a, w, shift, matrix


def case(model, radii):
    """Every rated branch has a mathematical box extremizer; no AC/dispatch claim."""
    validate(model)
    if not connected(model):
        raise InvalidModel("DISCONNECTED_BASE")
    if (not isinstance(radii, (tuple, list)) or len(radii) != len(model["buses"]) - 1 or
            any(not _finite(x) or x < 0 for x in radii)):
        raise InvalidModel("UNCERTAINTY_BOX_INVALID")
    u = np.asarray(radii, dtype=float)
    base = float(model["base_mva"])
    p = np.asarray(model["p_mw"][1:], dtype=float)
    outcomes = []
    for outage in [None] + [i for i, b in enumerate(model["branches"]) if b["status"]]:
        label = None if outage is None else model["branches"][outage]["id"]
        if not connected(model, outage):
            outcomes.append({"outage_id": label, "status": "ISLANDING_UNKNOWN", "rated": [], "unrated_ids": []})
            continue
        active, a, w, shift, bmat = _matrix(model, outage)
        theta = np.linalg.solve(bmat, p / base + a.T @ (w * shift))
        flows = base * w * (a @ theta - shift)
        # MW per MW because the base cancels between theta and flow equations.
        sensitivity = w[:, None] * (a @ np.linalg.solve(bmat, np.eye(len(p))))
        rated = []
        unrated_ids = []
        overloaded = False
        for k, (_, branch) in enumerate(active):
            if branch["rate_mw"] == 0:
                unrated_ids.append(branch["id"])
                continue
            coeff = sensitivity[k]
            # Sign maximizes absolute flow. Ties choose the positive extremum.
            sign = 1 if flows[k] >= 0 else -1
            delta = sign * np.sign(coeff) * u
            witness = float(flows[k] + coeff @ delta)
            worst = float(abs(flows[k]) + np.abs(coeff) @ u)
            if not math.isfinite(worst) or abs(abs(witness) - worst) > 1e-7:
                raise InvalidModel("BOX_EXTREMIZER_INVALID")
            violation = worst > float(branch["rate_mw"]) + 1e-6
            overloaded = overloaded or violation
            rated.append({"branch_id": branch["id"], "maximum_absolute_mw": worst,
                          "line_rating_mw": float(branch["rate_mw"]),
                          "attaining_delta_non_slack_mw": delta.tolist(),
                          "violates_rating": bool(violation)})
        status = ("UNRATED_NO_COMPLETE_CERTIFICATE" if unrated_ids else
                  "MODEL_UNSAFE" if overloaded else "DC_BOX_N1_WITHIN_DECLARED_RATED_LIMITS")
        outcomes.append({"outage_id": label, "status": status,
                         "rated": rated, "unrated_ids": unrated_ids})
    return {"radii_non_slack_mw": list(map(float, u)), "outcomes": outcomes,
            "model_sha256": hashlib.sha256(json.dumps(model, sort_keys=True, allow_nan=False,
                                                       separators=(",", ":")).encode()).hexdigest(),
            "scope": "SYNTHETIC_UNCERTAINTY_FIXED_DC_MODEL_ONLY"}


def build_pinned(output):
    from grid_screen import load_case
    root = Path(__file__).resolve().parents[1]
    paths = [root / "research/pglib_opf_case14_ieee.m", root / "research/pglib_opf_case30_ieee.m"]
    result = {"schema": "grid-uncertainty130/candidate/v1", "source_note": "PGLib v23.07 source, authored MW boxes; not AC or grid certification",
              "case_records": []}
    for path in paths:
        model = load_case(path)
        for scale in (0.0, 0.02, 0.10):
            rec = case(model, radii_for(model, scale))
            rec.update(case_name=path.name, case_bytes_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       authored_fraction=scale)
            result["case_records"].append(rec)
    output = Path(output)
    if output.exists():
        raise FileExistsError("OUTPUT_MUST_BE_CREATE_ONLY")
    output.write_text(json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Offline DC box witnesses; NOT grid/AC acceptance")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_pinned(args.output)


if __name__ == "__main__":
    main()
