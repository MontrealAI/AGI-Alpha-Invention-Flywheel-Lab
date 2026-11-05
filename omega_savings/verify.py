"""Independent acceptance of delivered linear responses.

Production verification uses exact rational arithmetic on the supplied binary64
numbers. Strict row diagonal dominance gives ||A^-1||_inf <= 1/alpha, so the
exact residual bounds forward error without refactorizing. Unknown applicability
fails closed. One-time qualification separately pays for NumPy reference solves
and SVD condition diagnostics; it does not silently weaken the buyer contract.

The verifier does not call the producer, inspect its policy, or trust its claim
of completion. It is procedural independence on the same host, not external
certification or a physical-model validation.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import time

import numpy as np


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _real(value):
    if type(value) not in (int, float) or not np.isfinite(value):
        raise ValueError("FINITE_REAL_REQUIRED")
    return Fraction(value)


def _request_shape(request):
    if not isinstance(request, dict) or set(request) != {"schema", "id", "base_matrix", "cases", "goal"} or request["schema"] != "omega-savings/linear-request/v1":
        raise ValueError("EXACT_LINEAR_REQUEST_REQUIRED")
    if not isinstance(request["id"], str) or not request["id"]:
        raise ValueError("REQUEST_ID_REQUIRED")
    base = request["base_matrix"]
    if not isinstance(base, list) or not base or any(not isinstance(row, list) or len(row) != len(base) for row in base):
        raise ValueError("SQUARE_BASE_REQUIRED")
    for row in base:
        for value in row:
            _real(value)
    if not isinstance(request["cases"], list) or not request["cases"]:
        raise ValueError("NONEMPTY_CASES_REQUIRED")
    goal = request["goal"]
    expected = {"outcome", "absolute_tolerance", "relative_tolerance", "max_condition_bound", "allow_network", "allow_external_actions"}
    if not isinstance(goal, dict) or set(goal) != expected or goal["outcome"] != "solve_linear_responses" or goal["allow_network"] is not False or goal["allow_external_actions"] is not False:
        raise ValueError("EXACT_LOCAL_GOAL_REQUIRED")
    for key in ("absolute_tolerance", "relative_tolerance", "max_condition_bound"):
        if _real(goal[key]) <= 0:
            raise ValueError("POSITIVE_TOLERANCE_REQUIRED")
    return len(base)


def verify(request, plan_or_result, result=None):
    """Verify production results; optional middle plan is ignored for acceptance."""
    artifact = plan_or_result if result is None else result
    started = time.perf_counter()
    reasons = []
    max_scaled = 0.0
    max_forward = 0.0
    max_absolute = 0.0
    max_condition = 0.0
    ops = 0
    case_bounds = []
    try:
        n = _request_shape(request)
        if not isinstance(artifact, dict) or artifact.get("schema") != "omega-savings/linear-result/v1":
            raise ValueError("RESULT_SCHEMA_REQUIRED")
        if artifact.get("status") != "executed":
            raise ValueError("EXECUTED_RESULT_REQUIRED")
        if artifact.get("request_sha256") != digest(request):
            raise ValueError("INPUT_BINDING")
        solutions = artifact.get("solutions")
        if not isinstance(solutions, list) or len(solutions) != len(request["cases"]):
            raise ValueError("COMPLETE_DELIVERY_REQUIRED")
        goal = request["goal"]
        atol, rtol = _real(goal["absolute_tolerance"]), _real(goal["relative_tolerance"])
        for index, (case, row) in enumerate(zip(request["cases"], solutions)):
            if not isinstance(case, dict) or set(case) != {"matrix", "rhs", "update"}:
                raise ValueError("EXACT_CASE_REQUIRED")
            update = case["update"]
            if update is not None:
                if not isinstance(update, dict) or set(update) != {"u", "v"}:
                    raise ValueError("EXACT_UPDATE_REQUIRED")
                u, v = update["u"], update["v"]
                if not isinstance(u, list) or not isinstance(v, list) or len(u) != n or len(v) != n or not isinstance(u[0], list) or not 1 <= len(u[0]) <= n:
                    raise ValueError("MATCHED_UPDATE_REQUIRED")
                rank = len(u[0])
                if any(not isinstance(r, list) or len(r) != rank for r in u + v):
                    raise ValueError("MATCHED_UPDATE_REQUIRED")
                for r in u + v:
                    for value in r:
                        _real(value)
            matrix = case["matrix"]
            if not isinstance(matrix, list) or len(matrix) != n or any(not isinstance(r, list) or len(r) != n for r in matrix):
                raise ValueError("MATCHED_MATRIX_REQUIRED")
            if not isinstance(case["rhs"], list) or len(case["rhs"]) != n or not isinstance(row, list) or len(row) != n:
                raise ValueError("MATCHED_RHS_AND_SOLUTION_REQUIRED")
            a = [[_real(v) for v in r] for r in matrix]
            b, x = list(map(_real, case["rhs"])), list(map(_real, row))
            norms = [sum(map(abs, r)) for r in a]
            alpha = min(2 * abs(a[i][i]) - norms[i] for i in range(n))
            if alpha <= 0:
                reasons.append("NO_FORWARD_BOUND:" + str(index))
                continue
            condition = max(norms) / alpha
            max_condition = max(max_condition, float(condition))
            if condition > _real(goal["max_condition_bound"]):
                reasons.append("CONDITION_BOUND_EXCEEDS_CONTRACT:" + str(index))
            residual = max(abs(b[i] - sum(a[i][j] * x[j] for j in range(n))) for i in range(n))
            absolute = residual / alpha
            xnorm = max(map(abs, x))
            bnorm = max(map(abs, b))
            denominator = max(norms) * xnorm + bnorm
            scaled = residual / denominator if denominator else Fraction(0)
            # ||x_exact|| >= ||x_delivered|| - absolute_error_bound.
            lower = xnorm - absolute
            relative = absolute / lower if lower > 0 else (Fraction(0) if absolute == 0 else None)
            accepted_error = absolute <= atol or relative is not None and relative <= rtol
            if not accepted_error:
                reasons.append("FORWARD_ERROR_CONTRACT:" + str(index))
            max_scaled = max(max_scaled, float(scaled))
            max_absolute = max(max_absolute, float(absolute))
            if relative is not None and max_forward is not None:
                max_forward = max(max_forward, float(relative))
            elif absolute:
                max_forward = None
            ops += 3 * n * n + 6 * n + 10
            case_bounds.append({"case": index, "absolute_error_bound": float(absolute),
                                "relative_error_bound": float(relative) if relative is not None else None,
                                "diagonal_margin": float(alpha), "condition_bound": float(condition)})
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError) as exc:
        reasons.append(str(exc))
    return {"accepted": not reasons, "reasons": sorted(set(reasons)),
            "max_scaled_residual": max_scaled, "max_absolute_error_bound": max_absolute,
            "max_relative_error_bound": max_forward, "max_condition_bound": max_condition,
            "max_oracle_relative_error": None, "verification_ops": ops,
            "operation_kind": "exact rational scalar proxy; bit complexity and hardware cost differ from float ops",
            "case_bounds": case_bounds, "wall_seconds": time.perf_counter() - started,
            "scope": "supplied finite binary64 linear systems; mathematical output only",
            "independence": "separate exact residual and inverse-norm bound, same host; no producer solve or trust in plan"}


production_verify = verify


def qualify(request, artifact):
    """One-time full independent numerical qualification, separately costed."""
    started = time.perf_counter()
    report = verify(request, artifact)
    reasons = list(report["reasons"])
    errors = []
    conditions = []
    reference_ops = 0
    try:
        n = _request_shape(request)
        if artifact.get("status") != "executed":
            raise ValueError("EXECUTED_RESULT_REQUIRED")
        for case, output in zip(request["cases"], artifact["solutions"]):
            a = np.asarray(case["matrix"], dtype=float)
            b = np.asarray(case["rhs"], dtype=float)
            x = np.asarray(output, dtype=float)
            oracle = np.linalg.solve(a, b)
            condition = float(np.linalg.cond(a))
            error = float(np.linalg.norm(x - oracle, ord=np.inf) / max(np.linalg.norm(oracle, ord=np.inf), np.finfo(float).tiny))
            conditions.append(condition)
            errors.append(error)
            if not np.isfinite(error) or error > request["goal"]["relative_tolerance"] and np.max(np.abs(x - oracle)) > request["goal"]["absolute_tolerance"]:
                reasons.append("REFERENCE_DISAGREEMENT")
            if not np.isfinite(condition) or condition > request["goal"]["max_condition_bound"]:
                reasons.append("REFERENCE_CONDITION_LIMIT")
            reference_ops += n * (n - 1) * (4 * n + 1) // 6 + 2 * n * n - n + 4 * n ** 3
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError) as exc:
        reasons.append(str(exc))
    return {**report, "accepted": not reasons, "reasons": sorted(set(reasons)),
            "max_oracle_relative_error": max(errors) if errors else None,
            "max_svd_condition_diagnostic": max(conditions) if conditions else None,
            "qualification_float_ops": reference_ops,
            "wall_seconds": time.perf_counter() - started,
            "qualification_scope": "one-time NumPy direct-solve and SVD diagnostics in addition to production acceptance"}
