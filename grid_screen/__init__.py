"""Trusted fixed DC screening kernel; not generated-program execution or AC certification."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

MAX_BUSES, MAX_BRANCHES = 200, 500


def fingerprint(model):
    return hashlib.sha256(json.dumps(model, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate(model):
    if not isinstance(model, dict) or set(model) != {"base_mva", "buses", "p_mw", "branches"}:
        raise ValueError("Exact model schema required")
    buses, branches, p = model["buses"], model["branches"], model["p_mw"]
    if not isinstance(buses, list) or not 2 <= len(buses) <= MAX_BUSES or any(type(b) is not int for b in buses) or len(set(buses)) != len(buses):
        raise ValueError("Invalid or excessive bus list")
    if not isinstance(branches, list) or not 1 <= len(branches) <= MAX_BRANCHES:
        raise ValueError("Invalid or excessive branch list")
    numeric = lambda v: type(v) in (int, float) and math.isfinite(v)
    if not numeric(model["base_mva"]) or model["base_mva"] <= 0:
        raise ValueError("Invalid base MVA")
    if not isinstance(p, list) or len(p) != len(buses) or not all(numeric(v) for v in p):
        raise ValueError("Invalid injections")
    ids = set()
    for b in branches:
        if not isinstance(b, dict) or set(b) != {"id", "from_bus", "to_bus", "x", "tap", "shift_deg", "rate_mw", "status"}:
            raise ValueError("Exact branch schema required")
        if type(b["id"]) is not int or b["id"] in ids:
            raise ValueError("Duplicate or invalid branch id")
        ids.add(b["id"])
        if any(type(b[k]) is not int or b[k] not in buses for k in ("from_bus", "to_bus")) or b["from_bus"] == b["to_bus"]:
            raise ValueError("Invalid branch endpoints")
        if not all(numeric(b[k]) for k in ("x", "tap", "shift_deg", "rate_mw")) or b["x"] <= 0 or b["tap"] <= 0 or b["rate_mw"] < 0:
            raise ValueError("Unsupported electrical parameters")
        if type(b["status"]) is not int or b["status"] not in (0, 1):
            raise ValueError("Invalid status")
    fingerprint(model)


def load_case(path):
    """Parse numeric MATPOWER matrices without evaluating MATLAB or embedded code."""
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Case exceeds byte limit")
    text = re.sub(r"%[^\n]*", "", path.read_text())
    def matrix(name, width):
        match = re.search(r"mpc\." + name + r"\s*=\s*\[([^]]*)\]\s*;", text)
        if match is None:
            raise ValueError("Missing numeric matrix " + name)
        rows = []
        for row in match[1].split(";"):
            if row.strip():
                fields = row.split()
                if len(fields) < width or not all(re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", f) for f in fields):
                    raise ValueError("Non-numeric or short matrix row")
                rows.append([float(f) for f in fields])
        return rows
    bus, gen, branch = matrix("bus", 13), matrix("gen", 10), matrix("branch", 13)
    base = re.search(r"mpc\.baseMVA\s*=\s*([0-9.eE+-]+)\s*;", text)
    if base is None or not 2 <= len(bus) <= MAX_BUSES or len(branch) > MAX_BRANCHES:
        raise ValueError("Missing base or oversized network")
    def integer(v):
        if not v.is_integer():
            raise ValueError("Non-integral identifier/status")
        return int(v)
    buses = [integer(r[0]) for r in bus]
    p = [-r[2] - r[4] for r in bus]
    for g in gen:
        if integer(g[7]) == 1:
            if integer(g[0]) not in buses:
                raise ValueError("Generator references missing bus")
            p[buses.index(integer(g[0]))] += g[1]
    # Declared derived scenario: first bus supplies the mismatch. Not feasible dispatch.
    p[0] -= sum(p)
    model = {"base_mva": float(base[1]), "buses": buses, "p_mw": p,
             "branches": [{"id": i, "from_bus": integer(r[0]), "to_bus": integer(r[1]),
                           "x": r[3], "tap": r[8] if r[8] else 1.0,
                           "shift_deg": r[9], "rate_mw": r[5], "status": integer(r[10])}
                          for i, r in enumerate(branch)]}
    validate(model)
    return model


def connected(model, outage=None):
    adjacent = {b: [] for b in model["buses"]}
    for row, b in enumerate(model["branches"]):
        if b["status"] and row != outage:
            adjacent[b["from_bus"]].append(b["to_bus"])
            adjacent[b["to_bus"]].append(b["from_bus"])
    reached, todo = set(), [model["buses"][0]]
    while todo:
        b = todo.pop()
        if b not in reached:
            reached.add(b)
            todo.extend(adjacent[b])
    return len(reached) == len(adjacent)


def _compile(model, need_h=True):
    n, m = len(model["buses"]), len(model["branches"])
    a, weight, shift = np.zeros((m, n)), np.zeros(m), np.zeros(m)
    for i, b in enumerate(model["branches"]):
        a[i, model["buses"].index(b["from_bus"])] = 1
        a[i, model["buses"].index(b["to_bus"])] = -1
        weight[i] = b["status"] / (b["x"] * b["tap"])
        shift[i] = math.radians(b["shift_deg"])
    p = np.array(model["p_mw"], dtype=float) / model["base_mva"]
    p[0] -= p.sum()
    reduced = a[:, 1:]
    matrix = reduced.T @ (weight[:, None] * reduced)
    if np.linalg.cond(matrix) > 1e12:
        raise ValueError("Ill-conditioned DC system; requires alternate analysis")
    theta = np.linalg.solve(matrix, p[1:] + reduced.T @ (weight * shift))
    flows = model["base_mva"] * weight * (reduced @ theta - shift)
    h = weight[:, None] * (reduced @ np.linalg.solve(matrix, reduced.T)) if need_h else None
    return flows, h


def _row(model, i, flows):
    if flows is None:
        return {"outage": model["branches"][i]["id"], "status": "ISLANDING_UNKNOWN", "flows_mw": None, "overloads": []}
    overloads = [b["id"] for j, b in enumerate(model["branches"])
                 if b["status"] and j != i and b["rate_mw"] > 0 and abs(flows[j]) > b["rate_mw"] + 1e-6]
    return {"outage": model["branches"][i]["id"], "status": "CONNECTED", "flows_mw": flows.tolist(), "overloads": overloads}


def screen(model, cache=None):
    validate(model)
    if not connected(model):
        raise ValueError("Base model disconnected; not screened")
    key = fingerprint(model)
    # The cache stores trusted internal arrays. Hash the arrays as well as their model key.
    reused = False
    if cache is not None and cache.get("model_sha256") == key:
        try:
            f = np.asarray(cache["flows"], dtype=float)
            h = np.asarray(cache["h"], dtype=float)
            integrity = hashlib.sha256(f.tobytes() + h.tobytes()).hexdigest()
            reused = f.shape == (len(model["branches"]),) and h.shape == (len(f), len(f)) and integrity == cache["array_sha256"]
        except (KeyError, ValueError, TypeError):
            reused = False
    if not reused:
        f, h = _compile(model)
        if cache is not None:
            cache.clear()
            cache.update(model_sha256=key, flows=f.tolist(), h=h.tolist(),
                         array_sha256=hashlib.sha256(f.tobytes() + h.tobytes()).hexdigest())
    rows = []
    for i, b in enumerate(model["branches"]):
        if not b["status"]:
            continue
        if not connected(model, i):
            rows.append(_row(model, i, None))
            continue
        denominator = 1 - h[i, i]
        if abs(denominator) < 1e-10:
            raise ValueError("Near-singular connected contingency; requires alternate analysis")
        flows = f + h[:, i] * f[i] / denominator
        flows[i] = 0
        rows.append(_row(model, i, flows))
    return {"model_sha256": key, "contingencies": rows, "cache_reused": bool(reused)}


def exact_screen(model):
    """Competent ordinary alternative: full fresh solve for each connected outage."""
    validate(model)
    if not connected(model):
        raise ValueError("Base model disconnected")
    rows = []
    for i, b in enumerate(model["branches"]):
        if not b["status"]:
            continue
        if not connected(model, i):
            rows.append(_row(model, i, None))
        else:
            altered = copy.deepcopy(model)
            altered["branches"][i]["status"] = 0
            f, _ = _compile(altered, need_h=False)
            rows.append(_row(model, i, f))
    return {"model_sha256": fingerprint(model), "contingencies": rows, "cache_reused": False}


def legacy_screen(model):
    """Preserved development defect: silently suppress the singular outage division."""
    validate(model)
    f, h = _compile(model)
    rows = []
    for i, b in enumerate(model["branches"]):
        if b["status"]:
            d = 1 - h[i, i]
            flows = f.copy() if abs(d) < 1e-10 else f + h[:, i] * f[i] / d
            flows[i] = 0
            rows.append(_row(model, i, flows))
    return {"model_sha256": fingerprint(model), "contingencies": rows, "cache_reused": False}
