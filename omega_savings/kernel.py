"""Portable, finite constructor for accepted repeated linear-response work.

This composes established pivoted LU, reuse, and Woodbury methods. It is not
an invented numerical algorithm or an unconstrained agent. All policy inputs
are supplied matrices, right-hand sides, declared updates and buyer tolerances;
the generated request contains neither evaluator family nor random seed.

Operation counts are a declared scalar-work proxy, not measured hardware FLOPs,
cloud savings, human labor or money. Fraction-based production verification is
reported separately from floating-point production and one-time qualification.
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np

REQUEST_SCHEMA = "omega-savings/linear-request/v1"
PLAN_SCHEMA = "omega-savings/linear-plan/v1"
RESULT_SCHEMA = "omega-savings/linear-result/v1"
METHODS = ("direct", "reuse", "woodbury")
POLICIES = ("adaptive", "conventional", "ordinary_reuse", "no_learning",
            "weak_analogy", "random_analogy", *METHODS)
FAMILIES = ("rhs", "low_rank", "dense_change", "noisy_update",
            "ill_conditioned", "singular", "successor_rhs", "successor_low_rank")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _matrix(value, name):
    if not isinstance(value, list) or not value or any(not isinstance(row, list) for row in value):
        raise ValueError(name + "_MATRIX_REQUIRED")
    if any(type(v) not in (int, float) for row in value for v in row):
        raise ValueError(name + "_REAL_NUMBERS_REQUIRED")
    a = np.asarray(value, dtype=float)
    if a.ndim != 2 or not all(a.shape) or not np.isfinite(a).all():
        raise ValueError(name + "_FINITE_MATRIX_REQUIRED")
    return a


def validate_request(request):
    """Validate an exact, finite local-work schema, without evaluator metadata."""
    required = {"schema", "id", "base_matrix", "cases", "goal"}
    if not isinstance(request, dict) or set(request) != required or request["schema"] != REQUEST_SCHEMA:
        raise ValueError("EXACT_LINEAR_REQUEST_REQUIRED")
    if not isinstance(request["id"], str) or not request["id"]:
        raise ValueError("REQUEST_ID_REQUIRED")
    goal = request["goal"]
    if not isinstance(goal, dict) or set(goal) != {"outcome", "absolute_tolerance", "relative_tolerance",
                                                   "max_condition_bound", "allow_network", "allow_external_actions"}:
        raise ValueError("EXACT_GOAL_REQUIRED")
    if goal["outcome"] != "solve_linear_responses" or goal["allow_network"] is not False or goal["allow_external_actions"] is not False:
        raise ValueError("LOCAL_LINEAR_OUTCOME_REQUIRED")
    for key in ("absolute_tolerance", "relative_tolerance", "max_condition_bound"):
        value = goal[key]
        if type(value) not in (int, float) or not np.isfinite(value) or value <= 0:
            raise ValueError("POSITIVE_FINITE_TOLERANCE_REQUIRED")
    base = _matrix(request["base_matrix"], "BASE")
    n = len(base)
    if base.shape != (n, n):
        raise ValueError("SQUARE_BASE_REQUIRED")
    if not isinstance(request["cases"], list) or not request["cases"]:
        raise ValueError("NONEMPTY_CASES_REQUIRED")
    for case in request["cases"]:
        if not isinstance(case, dict) or set(case) != {"matrix", "rhs", "update"}:
            raise ValueError("EXACT_CASE_REQUIRED")
        if _matrix(case["matrix"], "CASE").shape != (n, n):
            raise ValueError("MATCHED_MATRIX_REQUIRED")
        if not isinstance(case["rhs"], list) or len(case["rhs"]) != n or any(type(v) not in (int, float) for v in case["rhs"]):
            raise ValueError("MATCHED_REAL_RHS_REQUIRED")
        if not np.isfinite(np.asarray(case["rhs"], dtype=float)).all():
            raise ValueError("FINITE_RHS_REQUIRED")
        update = case["update"]
        if update is not None:
            if not isinstance(update, dict) or set(update) != {"u", "v"}:
                raise ValueError("EXACT_UPDATE_REQUIRED")
            u = _matrix(update["u"], "U")
            v = _matrix(update["v"], "V")
            if u.shape != v.shape or u.shape[0] != n or not 1 <= u.shape[1] <= n:
                raise ValueError("MATCHED_UPDATE_REQUIRED")
    return request


def _factor_ops(n):
    # Scalar elimination divisions + multiply/add updates; excludes pivot search.
    return n * (n - 1) * (4 * n + 1) // 6


def _solve_ops(n):
    return 2 * n * n - n


def operation_counts(request, method, *, inspection_extra=0):
    """Exact integer counts in the declared dense scalar arithmetic proxy."""
    n = len(request["base_matrix"])
    q = len(request["cases"])
    direct = q * (_factor_ops(n) + _solve_ops(n))
    if method == "direct":
        production = direct
    elif method == "reuse":
        production = _factor_ops(n) + q * _solve_ops(n)
    elif method == "woodbury":
        production = _factor_ops(n)
        seen = set()
        for case in request["cases"]:
            update = case["update"]
            r = len(update["u"][0])
            key = digest(update)
            if key not in seen:
                seen.add(key)
                production += r * _solve_ops(n) + r * r * (2 * n - 1) + r + _factor_ops(r)
            production += _solve_ops(n) + r * (2 * n - 1) + _solve_ops(r) + n * (2 * r - 1) + n
    else:
        production = 0
    # Both alternatives validate and inspect matrix entries. Constructor-specific
    # update checking is additional, and is charged even when it finds no reuse.
    common = q * (3 * n * n + n)
    rational_verify = q * (3 * n * n + 6 * n + 10) if method else 0
    guard = q * n * n if method == "reuse" else 0
    if method == "woodbury":
        guard = sum(n * n * (2 * len(c["update"]["u"][0]) + 1) for c in request["cases"])
    candidate = production + common + inspection_extra + guard + rational_verify
    baseline = direct + common + q * (3 * n * n + 6 * n + 10)
    return {
        "definition": "integer scalar-work proxy; rational and float operations are not equivalent hardware costs",
        "production_float_ops": int(production), "direct_float_ops": int(direct),
        "common_inspection_scalar_ops": common, "selection_extra_scalar_ops": int(inspection_extra),
        "execution_guard_scalar_ops": int(guard),
        "production_verify_rational_ops": rational_verify,
        "candidate_complete_proxy_units": int(candidate), "direct_complete_proxy_units": int(baseline),
        "saved_proxy_units": int(baseline - candidate) if method else 0,
        "qualification_float_ops": int(direct + q * 4 * n ** 3),
        "qualification_note": "separate direct reference solves and SVD condition diagnostics; SVD is a leading-order proxy",
        "serialization_bytes": len(json.dumps(request, sort_keys=True, allow_nan=False).encode()),
        "dimensions": n, "cases": q,
    }


def _program(method, request_sha):
    """Generate a complete local program from a finite reviewed method template."""
    return f'''# Generated known-method linear-response plan. No network or external actions.
import hashlib
import json
import sys
import warnings
import numpy as np
from scipy.linalg import lu_factor, lu_solve, LinAlgWarning

METHOD = {method!r}
REQUEST_SHA256 = {request_sha!r}

def solve_payload(request):
    observed = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if observed != REQUEST_SHA256:
        raise ValueError("REQUEST_CHANGED")
    base = np.asarray(request["base_matrix"], dtype=float)
    cases = request["cases"]
    output = []
    if METHOD == "reuse":
        reference = np.asarray(cases[0]["matrix"], dtype=float)
        if any(not np.array_equal(np.asarray(c["matrix"], dtype=float), reference) for c in cases):
            raise ValueError("REUSE_INAPPLICABLE")
    elif METHOD == "woodbury":
        for case in cases:
            update = case["update"]
            if update is None:
                raise ValueError("WOODBURY_INAPPLICABLE")
            u, v = np.asarray(update["u"], dtype=float), np.asarray(update["v"], dtype=float)
            a = np.asarray(case["matrix"], dtype=float)
            bound = 8 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(a))))
            if not np.allclose(a, base + u @ v.T, rtol=0, atol=bound):
                raise ValueError("WOODBURY_INAPPLICABLE")
    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        shared = lu_factor(base if METHOD == "woodbury" else np.asarray(cases[0]["matrix"], dtype=float)) if METHOD != "direct" else None
        updates = {{}}
        for case in cases:
            b = np.asarray(case["rhs"], dtype=float)
            if METHOD == "direct":
                x = lu_solve(lu_factor(np.asarray(case["matrix"], dtype=float)), b)
            elif METHOD == "reuse":
                x = lu_solve(shared, b)
            else:
                update = case["update"]
                key = json.dumps(update, sort_keys=True, separators=(",", ":"))
                if key not in updates:
                    u = np.asarray(update["u"], dtype=float)
                    v = np.asarray(update["v"], dtype=float)
                    z = lu_solve(shared, u)
                    small = np.eye(u.shape[1]) + v.T @ z
                    updates[key] = (z, v, lu_factor(small))
                z, v, small_factor = updates[key]
                y = lu_solve(shared, b)
                x = y - z @ lu_solve(small_factor, v.T @ y)
            if not np.isfinite(x).all():
                raise ValueError("NONFINITE_SOLUTION")
            output.append(x.tolist())
    return output

if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as source:
        request = json.load(source)
    print(json.dumps({{"solutions": solve_payload(request), "request_sha256": REQUEST_SHA256}}, allow_nan=False))
'''


def construct(request, policy="adaptive", assets=None):
    """Inspect observable structure and choose among feasible established methods.

    A retained asset is inert method content, never a numerical factorization or
    inherited authority. Equal-content ordinary reuse gets the identical menu.
    """
    started = time.perf_counter()
    validate_request(request)
    if policy not in POLICIES:
        raise ValueError("UNKNOWN_POLICY")
    methods = list(METHODS)
    if assets is not None:
        if not isinstance(assets, dict) or set(assets) != {"schema", "available_methods"} or assets["schema"] != "omega-savings/method-assets/v1":
            raise ValueError("EXACT_INERT_METHOD_ASSET_REQUIRED")
        methods = assets["available_methods"]
        if not isinstance(methods, list) or not methods or len(set(methods)) != len(methods) or any(m not in METHODS for m in methods):
            raise ValueError("INVALID_METHOD_ASSETS")
    base = np.asarray(request["base_matrix"], dtype=float)
    n = len(base)
    matrices = [np.asarray(c["matrix"], dtype=float) for c in request["cases"]]
    equal = all(np.array_equal(a, matrices[0]) for a in matrices)
    update_valid = True
    extra = len(matrices) * n * n
    observed_ranks = []
    for case, a in zip(request["cases"], matrices):
        update = case["update"]
        if update is None:
            update_valid = False
            continue
        u = np.asarray(update["u"], dtype=float)
        v = np.asarray(update["v"], dtype=float)
        r = u.shape[1]
        observed_ranks.append(r)
        extra += n * n * (2 * r - 1)
        reconstructed = base + u @ v.T
        bound = 8 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(a))))
        if not np.allclose(a, reconstructed, rtol=0, atol=bound):
            update_valid = False
    feasible = [m for m in methods if m == "direct" or m == "reuse" and equal or m == "woodbury" and update_valid]
    hypotheses = {"same_matrix": equal, "declared_low_rank_updates": update_valid,
                  "neither_reuse_hypothesis": not equal and not update_valid,
                  "observed_update_ranks": observed_ranks}
    # Cheap planning bound is rederived exactly by the independent verifier.
    bounds = []
    for a in matrices:
        margin = np.min(np.abs(np.diag(a)) - (np.sum(np.abs(a), axis=1) - np.abs(np.diag(a))))
        bounds.append(float(np.linalg.norm(a, ord=np.inf) / margin) if margin > 0 else None)
    reasons = []
    if any(b is None for b in bounds):
        reasons.append("NO_DECLARED_CHEAP_FORWARD_BOUND")
    elif max(bounds) > request["goal"]["max_condition_bound"]:
        reasons.append("CONDITION_BOUND_EXCEEDS_CONTRACT")
    if not feasible:
        reasons.append("NO_APPLICABLE_AVAILABLE_METHOD")
    chosen = None
    if not reasons:
        if policy in METHODS:
            chosen = policy
        elif policy == "no_learning":
            chosen = "direct"
        elif policy == "weak_analogy":
            chosen = "reuse"  # Same dimensions alone are a deliberately weak analogy.
        elif policy == "random_analogy":
            chosen = feasible[int(digest(request)[:16], 16) % len(feasible)]
        else:
            chosen = min(feasible, key=lambda m: (operation_counts(request, m)["candidate_complete_proxy_units"], METHODS.index(m)))
        if chosen not in feasible:
            reasons.append("SELECTED_METHOD_INAPPLICABLE")
            chosen = None
    sha = digest(request)
    program = _program(chosen, sha) if chosen else ""
    plan = {"schema": PLAN_SCHEMA, "status": "ready" if chosen else "declined", "policy": policy,
            "method": chosen, "request_sha256": sha, "hypotheses": hypotheses,
            "feasible_methods": feasible, "reasons": reasons,
            "condition_bounds_planning_only": bounds,
            "program": program, "program_sha256": hashlib.sha256(program.encode()).hexdigest(),
            "count_model": operation_counts(request, chosen, inspection_extra=extra),
            "constructor_wall_seconds": time.perf_counter() - started,
            "construction_scope": "finite developer-authored established-method compiler; no autonomous algorithm-invention claim"}
    return plan


def execute(request, plan):
    """Execute the generated program, bound to the exact validated request."""
    started = time.perf_counter()
    validate_request(request)
    if plan.get("schema") != PLAN_SCHEMA or plan.get("request_sha256") != digest(request):
        raise ValueError("PLAN_REQUEST_BINDING")
    method = plan.get("method")
    if plan.get("status") == "declined":
        return {"schema": RESULT_SCHEMA, "status": "declined", "solutions": [],
                "request_sha256": digest(request), "program_sha256": plan["program_sha256"],
                "plan": plan, "count_model": plan["count_model"], "wall_seconds": 0.0,
                "reasons": plan["reasons"]}
    expected = _program(method, digest(request)) if method in METHODS else None
    if expected is None or plan.get("program") != expected or plan.get("program_sha256") != hashlib.sha256(expected.encode()).hexdigest():
        raise ValueError("UNREVIEWED_PROGRAM")
    # The generated program independently guards only its selected method.
    # Its work is explicitly counted; it does not repeat all construction.
    namespace = {"__name__": "omega_generated_plan"}
    try:
        exec(compile(expected, "<omega-linear-plan>", "exec"), namespace)
        solutions = namespace["solve_payload"](request)
        status, reasons = "executed", []
    except (ValueError, np.linalg.LinAlgError, Warning) as exc:
        solutions, status, reasons = [], "failed", [type(exc).__name__ + ":" + str(exc)]
    return {"schema": RESULT_SCHEMA, "status": status, "solutions": solutions,
            "request_sha256": digest(request), "program_sha256": plan["program_sha256"],
            "plan": plan, "count_model": plan["count_model"],
            "wall_seconds": time.perf_counter() - started, "reasons": reasons}


def solve(request, method="adaptive", assets=None):
    return execute(request, construct(request, method, assets))


def retained_assets(methods=METHODS):
    return {"schema": "omega-savings/method-assets/v1", "available_methods": list(methods)}


def build_request(seed, family, n=24, cases=8, rank=2):
    """Deterministic synthetic corpus generator; does not run any policy.

    Successors use different base construction and RHS distributions, not stored
    numeric factors. They are fresh mathematical workloads, not physical claims.
    """
    if type(seed) is not int or family not in FAMILIES:
        raise ValueError("KNOWN_CORPUS_FAMILY_AND_INTEGER_SEED_REQUIRED")
    if any(type(v) is not int or v <= 0 for v in (n, cases, rank)) or rank > n:
        raise ValueError("POSITIVE_DIMENSIONS_REQUIRED")
    rng = np.random.default_rng(seed)
    raw = rng.normal(0, 0.1, (n, n))
    np.fill_diagonal(raw, 0.0)
    base = raw + np.diag(np.sum(np.abs(raw), axis=1) + 2.0)
    if family.startswith("successor"):
        # Dense directed transport-response equations: I - 0.6 P.
        p = rng.uniform(0, 1, (n, n))
        p /= p.sum(axis=1, keepdims=True)
        base = np.eye(n) - 0.6 * p
    if family == "ill_conditioned":
        base = np.diag(np.geomspace(1.0, 1e-14, n))
    if family == "singular":
        base = np.eye(n)
        base[-1, -1] = 0
    rows = []
    for i in range(cases):
        b = rng.normal(0, 1, n)
        if family.startswith("successor"):
            b = rng.uniform(0, 1, n) ** 2 + (i + 1) / cases
        a = base.copy()
        update = None
        if family in ("low_rank", "noisy_update", "successor_low_rank"):
            scale = 0.04 if family != "successor_low_rank" else 0.004
            u = rng.normal(0, scale, (n, rank))
            v = rng.normal(0, scale, (n, rank))
            a = base + u @ v.T
            update = {"u": u.tolist(), "v": v.tolist()}
            if family == "noisy_update":
                a += rng.normal(0, 1e-3, (n, n))
        elif family == "dense_change":
            delta = rng.normal(0, 0.02, (n, n))
            a = base + delta
        rows.append({"matrix": a.tolist(), "rhs": b.tolist(), "update": update})
    request = {"schema": REQUEST_SCHEMA, "id": "pending", "base_matrix": base.tolist(), "cases": rows,
               "goal": {"outcome": "solve_linear_responses", "absolute_tolerance": 1e-10,
                        "relative_tolerance": 1e-8, "max_condition_bound": 1e10,
                        "allow_network": False, "allow_external_actions": False}}
    request["id"] = "linear-" + digest(request)[:16]
    validate_request(request)
    return request
