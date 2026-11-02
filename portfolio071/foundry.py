from __future__ import annotations

import hashlib
import itertools
import json
import time

import numpy as np


class QualificationError(ValueError):
    pass


def _matrix(model):
    a = np.asarray(model["transition"], dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or not 2 <= len(a) <= 8:
        raise QualificationError("Finite experiment requires square dimension 2 through 8")
    if not np.isfinite(a).all() or np.min(a) < -1e-10 or np.max(a.sum(axis=0)) > 1 + 1e-10:
        raise QualificationError("Mass-transition contract violated")
    return np.maximum(0, a)


def identify(oracle, dimension, tolerance=1e-8):
    if not 2 <= dimension <= 8 or tolerance <= 0 or not np.isfinite(tolerance):
        raise QualificationError("Invalid registered instrument request")
    records = []
    start, cpu = time.perf_counter(), time.process_time()

    def query(x):
        y = np.asarray(oracle(np.asarray(x, dtype=float).copy()), dtype=float)
        if y.shape != (dimension,) or not np.isfinite(y).all():
            raise QualificationError("Malformed observation")
        records.append({"input": np.asarray(x, dtype=float).tolist(), "observed": y.tolist()})
        return y

    zero = query(np.zeros(dimension))
    if np.max(np.abs(zero)) > tolerance:
        raise QualificationError("Unmodeled injection or observation offset")
    columns = [query(np.eye(dimension)[j]) for j in range(dimension)]
    a = np.column_stack(columns)
    model = {"schema": "portfolio071.transport.instrument.v1", "dimension": dimension,
             "transition": a.tolist(), "tolerance": tolerance}
    a = _matrix(model)
    probes = (np.arange(1, dimension + 1, dtype=float), np.arange(dimension, 0, -1, dtype=float) ** 2)
    errors = []
    for weights in probes:
        x = weights / weights.sum()
        errors.append(float(np.max(np.abs(query(x) - a @ x))))
    if max(errors) > tolerance:
        raise QualificationError("Linearity confirmation failed")
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    model.update({"query_count": len(records), "query_receipt_sha256": hashlib.sha256(encoded).hexdigest(),
                  "queries": records, "probe_errors": errors,
                  "fit_cpu_seconds": time.process_time() - cpu, "fit_wall_seconds": time.perf_counter() - start,
                  "class_assumption": "Time-invariant nonnegative linear compartment map, column sums at most one, noiseless measurements within declared numerical tolerance.",
                  "qualification_limit": "Finite probes check implementation in the supplied class; they do not establish the class, physical linearity, or arbitrary future drift."})
    return model


def _nodes(nodes, dimension, name):
    values = tuple(int(x) for x in nodes)
    if len(set(values)) != len(values) or any(x < 0 or x >= dimension for x in values):
        raise QualificationError("Invalid " + name)
    return values


def choose_sensors(model, source_nodes, horizon, sensor_costs, min_separation=0.02):
    a = _matrix(model)
    n = len(a)
    sources = _nodes(source_nodes, n, "source nodes")
    costs = np.asarray(sensor_costs, dtype=float)
    if not sources or not 1 <= horizon <= 12 or costs.shape != (n,) or (costs < 0).any() or not np.isfinite(costs).all() or min_separation <= 0 or not np.isfinite(min_separation):
        raise QualificationError("Invalid sensor request")
    start, cpu = time.perf_counter(), time.process_time()
    x = np.eye(n)[:, sources]
    history = []
    for _ in range(horizon):
        x = a @ x
        history.append(x.copy())
    signatures = np.stack(history)
    best, candidates = None, 0
    for flags in itertools.product((0, 1), repeat=n):
        chosen = tuple(i for i, f in enumerate(flags) if f)
        candidates += 1
        separation = float("inf") if len(sources) == 1 else 0.0
        if chosen and len(sources) > 1:
            observed = signatures[:, chosen, :].reshape(-1, len(sources))
            separation = min(float(np.max(np.abs(observed[:, i] - observed[:, j])))
                             for i in range(len(sources)) for j in range(i + 1, len(sources)))
        if separation < min_separation:
            continue
        key = (float(costs[list(chosen)].sum()), len(chosen), chosen)
        if best is None or key < best[0]:
            best = key, separation
    return {"schema": "portfolio071.transport.sensors.v1", "accepted": best is not None,
            "source_nodes": list(sources), "horizon": horizon, "minimum_required_separation": min_separation,
            "sensor_nodes": list(best[0][2]) if best else [], "cost_units": best[0][0] if best else None,
            "achieved_separation": best[1] if best and np.isfinite(best[1]) else None,
            "candidate_count": candidates, "optimality_gap_in_finite_catalogue": 0.0 if best else None,
            "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - start,
            "cost_scope": "Supplied nonmonetary sensor-installation units; physical procurement and qualification are unmeasured."}


def evaluate_treatment(model, source_nodes, protected_nodes, horizon, fractions):
    a = _matrix(model)
    n = len(a)
    sources = _nodes(source_nodes, n, "source nodes")
    protected = _nodes(protected_nodes, n, "protected nodes")
    f = np.asarray(fractions, dtype=float)
    if not sources or not protected or not 1 <= horizon <= 12 or f.shape != (n,) or not np.isfinite(f).all() or (f < 0).any() or (f > 1).any():
        raise QualificationError("Invalid treatment request")
    x = np.eye(n)[:, sources]
    removed, decayed, exposure = np.zeros(len(sources)), np.zeros(len(sources)), np.zeros(len(sources))
    history, max_mass_error = [], 0.0
    for step in range(horizon):
        removal = f[:, None] * x
        removed += removal.sum(axis=0)
        surviving = x - removal
        nxt = a @ surviving
        loss = surviving.sum(axis=0) - nxt.sum(axis=0)
        if np.min(loss) < -1e-8:
            raise QualificationError("Unaccounted mass creation")
        decayed += loss
        x = nxt
        exposure += x[list(protected)].sum(axis=0)
        error = np.abs(x.sum(axis=0) + removed + decayed - 1)
        max_mass_error = max(max_mass_error, float(np.max(error)))
        history.append({"step": step + 1, "remaining_mass": x.sum(axis=0).tolist(), "removed_mass": removed.tolist(),
                        "decayed_mass": decayed.tolist(), "protected_cumulative_exposure": exposure.tolist()})
    return {"maximum_exposure": float(np.max(exposure)), "per_source_exposure": exposure.tolist(),
            "source_nodes": list(sources), "max_mass_balance_error": max_mass_error,
            "maximum_removed_mass": float(np.max(removed)), "trace": history}


def design_mitigation(model, source_nodes, protected_nodes, horizon, exposure_limit, installation_costs,
                      operating_costs, eligible_nodes=None, disposal_cost=0.0, removal_choices=(0.0, 0.5, 1.0)):
    a = _matrix(model)
    n = len(a)
    sources = _nodes(source_nodes, n, "source nodes")
    protected = _nodes(protected_nodes, n, "protected nodes")
    eligible = set(_nodes(range(n) if eligible_nodes is None else eligible_nodes, n, "eligible nodes"))
    install, operating = np.asarray(installation_costs, dtype=float), np.asarray(operating_costs, dtype=float)
    if (install.shape != (n,) or operating.shape != (n,) or not np.isfinite(install).all()
            or not np.isfinite(operating).all() or np.min(install) < 0 or np.min(operating) < 0
            or not np.isfinite(exposure_limit) or exposure_limit < 0 or disposal_cost < 0 or not np.isfinite(disposal_cost)):
        raise QualificationError("Invalid mitigation costs or limit")
    removal_choices = tuple(float(x) for x in removal_choices)
    if not removal_choices or len(set(removal_choices)) != len(removal_choices) or any(not np.isfinite(x) or x < 0 or x > 1 for x in removal_choices):
        raise QualificationError("Invalid removal choices")
    start, cpu = time.perf_counter(), time.process_time()
    best, candidates = None, 0
    choices = [removal_choices if i in eligible else (0.0,) for i in range(n)]
    for fractions in itertools.product(*choices):
        candidates += 1
        outcome = evaluate_treatment(model, sources, protected, horizon, fractions)
        if outcome["maximum_exposure"] > exposure_limit + 1e-9:
            continue
        f = np.asarray(fractions)
        cost = float(np.sum(install[f > 0]) + horizon * np.dot(operating, f) + disposal_cost * outcome["maximum_removed_mass"])
        key = cost, int(np.count_nonzero(f)), fractions
        if best is None or key < best[0]:
            best = key, outcome
    return {"schema": "portfolio071.transport.mitigation.v1", "accepted": best is not None,
            "fractions": list(best[0][2]) if best else None, "cost_units": best[0][0] if best else None,
            "source_nodes": list(sources), "protected_nodes": list(protected), "horizon": horizon,
            "exposure_limit": exposure_limit, "outcome": best[1] if best else None,
            "candidate_count": candidates, "optimality_gap_in_finite_catalogue": 0.0 if best else None,
            "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - start,
            "cost_scope": "Supplied engineering installation/operation/disposal units, not dollars or measured equipment performance.",
            "information": "One robust treatment plan must serve every listed possible release source; true source is never an input."}
