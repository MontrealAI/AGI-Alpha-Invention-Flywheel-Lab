"""Optional fast acceptance instrument with an exact Fraction fallback.

Each arithmetic bound is computed using IEEE directed rounding by reviewed C
source. Runtime self-tests and pinned conservative compiler flags are mandatory.
No compiled binary is checked into Git. Default verify.verify remains the exact
Fraction implementation until separate qualification justifies promotion.

Immutable prepared input contains its own exact request bytes and read-only
numeric buffers. It may be reused for that request only; a new request must be
validated and hashed anew. No financial or execution authority is inherited.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import numpy as np

from .verify import verify as _fraction_verify

FLAGS = ("-std=c11", "-O2", "-fPIC", "-shared", "-frounding-math",
         "-ffp-contract=off", "-fno-fast-math", "-fexcess-precision=standard")


class InstrumentUnavailable(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _array(value, shape):
    if not isinstance(value, list):
        raise ValueError("LIST_NUMERIC_INPUT_REQUIRED")
    rows = value if len(shape) == 2 else [value]
    if any(not isinstance(row, list) for row in rows):
        raise ValueError("LIST_NUMERIC_ROWS_REQUIRED")
    for row in rows:
        for v in row:
            if type(v) not in (int, float) or not math.isfinite(v):
                raise ValueError("FINITE_REAL_REQUIRED")
            if type(v) is int and int(float(v)) != v:
                raise InstrumentUnavailable("INTEGER_NOT_EXACTLY_BINARY64")
    a = np.asarray(value, dtype=np.float64)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError("MATCHED_FINITE_NUMERIC_SHAPE_REQUIRED")
    # Immutable bytes own the buffer: callers cannot re-enable NumPy writes.
    return np.frombuffer(a.tobytes(order="C"), dtype=np.float64).reshape(shape)


@dataclass(frozen=True)
class PreparedRequest:
    canonical_json: bytes
    request_sha256: str
    n: int
    matrices: tuple
    rhs: tuple
    absolute_tolerance: float
    relative_tolerance: float
    max_condition_bound: float
    preparation_wall_seconds: float


def prepare_request(request):
    """Qualify a new input boundary once; retain immutable data, not authority."""
    start = time.perf_counter()
    if not isinstance(request, dict) or set(request) != {"schema", "id", "base_matrix", "cases", "goal"} or request["schema"] != "omega-savings/linear-request/v1":
        raise ValueError("EXACT_LINEAR_REQUEST_REQUIRED")
    if not isinstance(request["id"], str) or not request["id"]:
        raise ValueError("REQUEST_ID_REQUIRED")
    base = request["base_matrix"]
    if not isinstance(base, list) or not base:
        raise ValueError("SQUARE_BASE_REQUIRED")
    n = len(base)
    _array(base, (n, n))
    goal = request["goal"]
    keys = {"outcome", "absolute_tolerance", "relative_tolerance", "max_condition_bound", "allow_network", "allow_external_actions"}
    if not isinstance(goal, dict) or set(goal) != keys or goal["outcome"] != "solve_linear_responses" or goal["allow_network"] is not False or goal["allow_external_actions"] is not False:
        raise ValueError("EXACT_LOCAL_GOAL_REQUIRED")
    for k in ("absolute_tolerance", "relative_tolerance", "max_condition_bound"):
        if type(goal[k]) not in (int, float) or not math.isfinite(goal[k]) or goal[k] <= 0:
            raise ValueError("POSITIVE_FINITE_TOLERANCE_REQUIRED")
    cases = request["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("NONEMPTY_CASES_REQUIRED")
    matrices, rhs = [], []
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"matrix", "rhs", "update"}:
            raise ValueError("EXACT_CASE_REQUIRED")
        matrices.append(_array(case["matrix"], (n, n)))
        rhs.append(_array(case["rhs"], (n,)))
        update = case["update"]
        if update is not None:
            if not isinstance(update, dict) or set(update) != {"u", "v"} or not isinstance(update["u"], list) or len(update["u"]) != n or not isinstance(update["u"][0], list):
                raise ValueError("EXACT_UPDATE_REQUIRED")
            rank = len(update["u"][0])
            if not 1 <= rank <= n:
                raise ValueError("MATCHED_UPDATE_REQUIRED")
            _array(update["u"], (n, rank)); _array(update["v"], (n, rank))
    content = _canonical(request)
    return PreparedRequest(content, hashlib.sha256(content).hexdigest(), n,
                           tuple(matrices), tuple(rhs), goal["absolute_tolerance"],
                           goal["relative_tolerance"], goal["max_condition_bound"],
                           time.perf_counter() - start)


@lru_cache(maxsize=4)
def _compile(source_sha256, compiler, source_bytes, flags):
    started = time.perf_counter()
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        raise InstrumentUnavailable("C_SOURCE_IDENTITY_CHANGED")
    # A private fresh directory prevents loading an arbitrary preexisting cache
    # binary. This in-process cache is keyed by exact source and compiler path.
    directory = tempfile.TemporaryDirectory(prefix="omega-interval-")
    source, binary = Path(directory.name) / "interval.c", Path(directory.name) / "interval.so"
    source.write_bytes(source_bytes)
    command = [compiler, *flags, str(source), "-o", str(binary), "-lm"]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            raise InstrumentUnavailable("STRICT_C_COMPILATION_FAILED:" + completed.stderr[-1000:])
        library = ctypes.CDLL(str(binary))
        library.omega_interval_self_test.restype = ctypes.c_int
        library.omega_interval_self_test.argtypes = []
        if library.omega_interval_self_test() != 0:
            raise InstrumentUnavailable("DIRECTED_ROUNDING_OR_SUBNORMAL_SELF_TEST_FAILED")
        pointer = ctypes.POINTER(ctypes.c_double)
        library.omega_interval_bound.argtypes = [ctypes.c_size_t, pointer, pointer, pointer, pointer]
        library.omega_interval_bound.restype = ctypes.c_int
        version = subprocess.run([compiler, "--version"], check=False, capture_output=True, text=True).stdout.splitlines()
        metadata = {"source_sha256": source_sha256, "flags": list(flags),
                    "compiler": version[0] if version else compiler,
                    "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "self_test_passed": True, "compile_wall_seconds": time.perf_counter() - started,
                    "cache_scope": "this process, exact C source and compiler; fresh private binary outside Git"}
        return library, metadata, directory
    except Exception:
        directory.cleanup()
        raise


def instrument():
    source = Path(__file__).with_name("interval.c").read_bytes()
    compiler = shutil.which("cc") or shutil.which("gcc")
    if not compiler:
        raise InstrumentUnavailable("NO_STANDARD_C_COMPILER")
    library, metadata, _ = _compile(hashlib.sha256(source).hexdigest(), compiler, source, tuple(FLAGS))
    return library, metadata


def _fallback(request, artifact, reason, started):
    attempted = time.perf_counter() - started
    if isinstance(request, PreparedRequest):
        request = json.loads(request.canonical_json)
    checked = _fraction_verify(request, artifact)
    return {**checked, "instrument": "exact_fraction_fallback", "fallback_reason": reason,
            "fraction_fallback_wall_seconds": checked["wall_seconds"],
            "interval_attempt_wall_seconds": attempted,
            "wall_seconds": time.perf_counter() - started,
            "total_wall_seconds": time.perf_counter() - started,
            "fast_path": False}


def verify_interval(request, artifact, *, fallback=True):
    """Accept only conservative interval evidence, otherwise Fraction or refusal."""
    started = time.perf_counter()
    original = request
    try:
        prepared = request if isinstance(request, PreparedRequest) else prepare_request(request)
        if not isinstance(artifact, dict) or artifact.get("schema") != "omega-savings/linear-result/v1" or artifact.get("status") != "executed":
            raise ValueError("EXECUTED_RESULT_REQUIRED")
        if artifact.get("request_sha256") != prepared.request_sha256:
            raise ValueError("INPUT_BINDING")
        rows = artifact.get("solutions")
        if not isinstance(rows, list) or len(rows) != len(prepared.matrices):
            raise ValueError("COMPLETE_DELIVERY_REQUIRED")
        library, metadata = instrument()
        bounds, reasons = [], []
        for i, (matrix, rhs, row) in enumerate(zip(prepared.matrices, prepared.rhs, rows)):
            x = _array(row, (prepared.n,))
            out = np.empty(5, dtype=np.float64)
            pointer = ctypes.POINTER(ctypes.c_double)
            code = library.omega_interval_bound(prepared.n, matrix.ctypes.data_as(pointer),
                      rhs.ctypes.data_as(pointer), x.ctypes.data_as(pointer), out.ctypes.data_as(pointer))
            if code:
                raise InstrumentUnavailable("INTERVAL_BOUND_UNAVAILABLE:" + str(code))
            alpha, condition, absolute, relative, scaled = map(float, out)
            if condition > prepared.max_condition_bound:
                reasons.append("CONDITION_BOUND_EXCEEDS_CONTRACT:" + str(i))
            if absolute > prepared.absolute_tolerance and relative > prepared.relative_tolerance:
                reasons.append("FORWARD_ERROR_CONTRACT:" + str(i))
            bounds.append({"case": i, "diagonal_margin_lower_bound": alpha,
                           "condition_bound": condition, "absolute_error_bound": absolute,
                           "relative_error_bound": relative if math.isfinite(relative) else None,
                           "scaled_residual_upper_bound": scaled})
        if reasons and fallback:
            return _fallback(original, artifact, "INTERVAL_REQUIRES_EXACT_ADJUDICATION:" + "|".join(reasons), started)
        relative_bounds = [r["relative_error_bound"] for r in bounds]
        return {"accepted": not reasons, "reasons": reasons, "fast_path": True,
                "instrument": "c_directed_rounding", "instrument_metadata": metadata,
                "max_absolute_error_bound": max(r["absolute_error_bound"] for r in bounds),
                "max_relative_error_bound": max(relative_bounds) if all(r is not None for r in relative_bounds) else None,
                "max_scaled_residual": max(r["scaled_residual_upper_bound"] for r in bounds),
                "max_condition_bound": max(r["condition_bound"] for r in bounds),
                "max_oracle_relative_error": None,
                "verification_ops": len(bounds) * (8 * prepared.n ** 2 + 16 * prepared.n),
                "operation_kind": "directed binary64 arithmetic proxy; separate from rational verification count",
                "case_bounds": bounds, "wall_seconds": time.perf_counter() - started,
                "total_wall_seconds": time.perf_counter() - started,
                "prepared_boundary_reused": isinstance(original, PreparedRequest),
                "boundary_preparation_wall_seconds": prepared.preparation_wall_seconds,
                "scope": "conservative bounds for immutable supplied binary64 systems on runtime-qualified host",
                "independence": "separate directed interval residual and inverse bound; no producer solve"}
    except (ValueError, TypeError, IndexError, KeyError, OverflowError, InstrumentUnavailable, OSError) as exc:
        if fallback:
            return _fallback(original, artifact, type(exc).__name__ + ":" + str(exc), started)
        return {"accepted": False, "reasons": [type(exc).__name__ + ":" + str(exc)],
                "fast_path": False, "instrument": "unavailable_or_rejected",
                "wall_seconds": time.perf_counter() - started, "total_wall_seconds": time.perf_counter() - started}


def benchmark_iteration(directory):
    """One finite development iteration, with full workflow costs and controls.

    Exactly seeds11/12, n32/64/128, rhs/low_rank, three alternating repetitions.
    Confirmation inputs are never generated. Exact Fraction qualification may
    be reused only for identical request and delivered-solution bytes.
    """
    import statistics
    from .kernel import build_request, construct, execute, digest
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise ValueError("FRESH_INTERVAL_DEVELOPMENT_OUTPUT_REQUIRED")
    directory.mkdir(parents=True, exist_ok=True)
    _, metadata = instrument()
    registration = {"role": "development", "seeds": [11, 12], "dimensions": [32, 64, 128],
                    "families": ["rhs", "low_rank"], "policies": ["adaptive", "conventional", "numpy_direct"],
                    "repetitions": 3, "instrument": metadata,
                    "stopping_rule": "one complete fixed development grid; no confirmation tuning or indefinite search",
                    "sources": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (Path(__file__), Path(__file__).with_suffix('.c'), Path(__file__).with_name('kernel.py'), Path(__file__).with_name('verify.py'))},
                    "cost_note": "Each full workflow includes fresh input-boundary preparation, constructor if used, execution and the same fast independent checker. Cold compiler build and Fraction qualification are separate one-time costs. No time-to-money conversion."}
    (directory / "registration.json").write_bytes(_canonical(registration))
    rows, qualifications = [], {}
    for seed in registration["seeds"]:
        for n in registration["dimensions"]:
            for family in registration["families"]:
                request = build_request(seed, family, n=n, cases=8, rank=2)
                for repetition in range(3):
                    order = registration["policies"][repetition:] + registration["policies"][:repetition]
                    for policy in order:
                        started = time.perf_counter()
                        boundary = prepare_request(request)
                        if policy == "numpy_direct":
                            solutions = [np.linalg.solve(a, b).tolist() for a, b in zip(boundary.matrices, boundary.rhs)]
                            artifact = {"schema": "omega-savings/linear-result/v1", "status": "executed",
                                        "request_sha256": boundary.request_sha256, "solutions": solutions}
                            method = "numpy_direct"
                        else:
                            plan = construct(request, policy)
                            artifact = execute(request, plan)
                            method = plan["method"]
                        before_check = time.perf_counter()
                        checked = verify_interval(boundary, artifact)
                        wall = time.perf_counter() - started
                        key = boundary.request_sha256 + ":" + digest(artifact.get("solutions"))
                        reused = key in qualifications
                        if not reused:
                            qualifications[key] = _fraction_verify(request, artifact)
                        exact = qualifications[key]
                        row = {"seed": seed, "n": n, "family": family, "policy": policy,
                               "repetition": repetition, "method": method, "request_sha256": boundary.request_sha256,
                               "solution_sha256": digest(artifact.get("solutions")),
                               "fast_accepted": checked["accepted"], "exact_accepted": exact["accepted"],
                               "fast_path": checked["fast_path"], "false_positive": checked["accepted"] and not exact["accepted"],
                               "boundary_preparation_seconds": boundary.preparation_wall_seconds,
                               "precheck_workflow_seconds": before_check - started,
                               "fast_check_seconds": checked["wall_seconds"], "whole_workflow_seconds": wall,
                               "exact_fraction_qualification_seconds": exact["wall_seconds"],
                               "identical_output_qualification_reused": reused,
                               "reasons": checked["reasons"]}
                        rows.append(row)
                        (directory / "results.json").write_bytes(_canonical({"rows": rows}))
    groups = []
    for n in registration["dimensions"]:
        for family in registration["families"]:
            medians = {p: statistics.median(r["whole_workflow_seconds"] for r in rows
                        if r["n"] == n and r["family"] == family and r["policy"] == p)
                       for p in registration["policies"]}
            groups.append({"n": n, "family": family, "median_whole_workflow_seconds": medians,
                           "adaptive_beats_numpy_direct_on_this_host": medians["adaptive"] < medians["numpy_direct"]})
    totals = {p: sum(r["whole_workflow_seconds"] for r in rows if r["policy"] == p)
              for p in registration["policies"]}
    qualification_seconds = sum(q["wall_seconds"] for q in qualifications.values())
    summary = {"registered_rows": 108, "completed_rows": len(rows),
               "fast_accepted": sum(r["fast_accepted"] for r in rows),
               "exact_accepted": sum(r["exact_accepted"] for r in rows),
               "false_positives": sum(r["false_positive"] for r in rows), "groups": groups,
               "whole_workflow_total_seconds_by_arm": totals,
               "cold_compile_seconds": metadata["compile_wall_seconds"],
               "whole_workflow_plus_one_compile_by_arm": {p: t + metadata["compile_wall_seconds"] for p, t in totals.items()},
               "actual_unique_fraction_qualification_count": len(qualifications),
               "actual_fraction_qualification_seconds": qualification_seconds,
               "default_fraction_verifier_changed": False,
               "scope": "Measured one-host development comparison, not a general speed theorem, real buyer demand or avoided cash.",
               "next_rule": "Keep valid instrument if useful; preserve full-workflow losses. No further tuning on confirmation."}
    (directory / "summary.json").write_bytes(_canonical(summary))
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True)
    args = parser.parse_args()
    print(json.dumps(benchmark_iteration(args.benchmark), sort_keys=True, indent=2))
