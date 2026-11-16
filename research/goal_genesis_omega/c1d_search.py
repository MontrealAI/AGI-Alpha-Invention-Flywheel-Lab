"""Goal Genesis Ω — an actual attempt on open optimization constant C_1d.

Read one public, pinned preexisting certificate, discover an improved signed
autoconvolution step function if possible, and publish a checkable witness.
This is optimization, NOT autonomous goal generation or mathematical novelty
unless a new exact value beats all registered incumbent bounds.

The source certificate is fetched read-only from its author's own repository:
  steps-re/c1d-certificate @ 9a091494facc801eaf6b92b175b63c58b7c3b30b
It is NOT redistributed in this repository. Model access, credentials and
external payments are not required.

The source has no explicit licence. A derived construction must preserve
the attribution and rights caveat; publishing it requires rights assessment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve, correlate
from scipy.special import logsumexp

UPSTREAM = (
    "https://raw.githubusercontent.com/steps-re/c1d-certificate/"
    "9a091494facc801eaf6b92b175b63c58b7c3b30b/construction.json"
)
SOURCE_SHA256 = "3dd39fae744555179b0356b84e752db724e892bd23dda51403976edfb5b3a28c"
REPORTED_BEST_NUM = 9900630255081376929482866688
REPORTED_BEST_DEN = 6805830738283663732311831361


def read_upstream(source=None):
    if source is None:
        with urlopen(UPSTREAM, timeout=25) as stream:
            blob = stream.read(100_000)
    else:
        blob = Path(source).read_bytes()
    if hashlib.sha256(blob).hexdigest() != SOURCE_SHA256:
        raise ValueError("PINNED_SOURCE_HASH_MISMATCH")
    raw = json.loads(blob)
    if type(raw) is not dict or type(raw.get("values")) is not list or len(raw["values"]) != 600:
        raise ValueError("UPSTREAM_CERTIFICATE_MALFORMED")
    v = np.array(raw["values"], dtype=np.float64)
    if not np.all(np.isfinite(v)) or abs(v.sum()) < 1e-6:
        raise ValueError("BAD_SEED_VALUES")
    return v


def score(v):
    if abs(v.sum()) < 1e-10:
        return float("inf")
    return float((2 * len(v)) * np.max(np.abs(fftconvolve(v, v, mode="full"))) / v.sum() ** 2)


def smooth(z, beta):
    """Smooth max of |v*v|, with analytic projected gradient.

    v has *exact mean 1* at every step, so normalization cannot be gamed.
    The benchmark objective is evaluated separately with exact arithmetic.
    """
    n = len(z)
    v = 1.0 + z - z.mean()
    c = fftconvolve(v, v, mode="full")
    logits = np.concatenate((beta * c, -beta * c))
    total = logsumexp(logits)
    weights = np.exp(logits - total)
    w = weights[:len(c)] - weights[len(c):]
    grad_v = 2.0 * correlate(w, v, mode="valid", method="fft")
    grad = (2.0 / n) * (grad_v - grad_v.mean())
    value = (2.0 / n) * (total / beta)
    return float(value), grad.astype(np.float64)


def descend(v, *, iters, schedule):
    """Two controls: original construction and unconstrained smooth minimax.

    It is *not* an exhaustive search of all mathematical methods.
    """
    n = len(v)
    v = v * (n / v.sum())
    z = v - 1.0
    best = v.copy()
    best_score = score(best)
    trace = []
    for beta in schedule:
        def target(x):
            return smooth(x, beta)
        opt = minimize(target, z, method="L-BFGS-B", jac=True,
                       options={"maxiter": iters, "ftol": 1e-13, "gtol": 1e-9,
                                "maxls": 50, "maxcor": 25})
        z = opt.x
        v = 1 + z - z.mean()
        got = score(v)
        if got < best_score:
            best = v.copy()
            best_score = got
        trace.append({"beta": beta, "iterations": int(opt.nit),
                      "actual_ratio": got, "best_actual_ratio": best_score,
                      "solver_success": bool(opt.success)})
    return best, trace


def run(source=None, max_n=2400, iters=750, seed=711021):
    initial = read_upstream(source)
    baseline = score(initial)
    rng = np.random.default_rng(seed)
    if not 1.4600 < baseline < 1.4605:
        raise ValueError("KNOWN_600_CELL_ORACLE_DID_NOT_REPLAY")
    stages = []
    carry = initial.copy()
    champion = (score(carry), carry.copy())
    for n in (600, 1200, 2400):
        if n > max_n:
            break
        if n != len(carry):
            if n % len(carry) != 0:
                raise ValueError("INVALID_UPSAMPLE")
            carry = np.repeat(carry, n // len(carry))
        # Three materially different continuations: conservative, wider
        # softmax basin search, and an independently perturbed restart.
        attempts = [("sharp", carry.copy(), (10, 30, 100, 300, 1000)),
                    ("broad", carry.copy(), (2, 8, 30, 150, 600))]
        if n >= 1200:
            jitter = rng.normal(size=n) * max(0.01, 0.015 * float(np.std(carry)))
            attempts.append(("perturbed", carry + jitter, (3, 12, 50, 200, 900)))
        winner = (score(carry), carry.copy(), "unaltered_inherited_baseline")
        details = []
        for name, proposed, schedule in attempts:
            candidate, history = descend(proposed, iters=iters, schedule=schedule)
            s = score(candidate)
            details.append({"strategy": name, "ratio": s, "trace": history})
            if s < winner[0]:
                winner = (s, candidate.copy(), name)
        carry = winner[1].copy()
        if winner[0] < champion[0]:
            champion = (winner[0], winner[1].copy())
        stages.append({"cells": n, "inherited_ratio": score(np.repeat(initial, n // 600)),
                       "winner": winner[2], "best_ratio": winner[0], "attempts": details})
        print("STAGE", n, "NUMERICAL", f"{winner[0]:.14f}",
              "BENCHMARK", f"{REPORTED_BEST_NUM/REPORTED_BEST_DEN:.14f}",
              "WINNER", winner[2], flush=True)
    value, candidate = champion
    # Use printed round-trip doubles; independent exact verifier is the judge.
    arr = [float(x) for x in candidate]
    result = {
        "schema": "montreal-ai/goal-genesis/c1d-candidate/v1",
        "title": "Open-problem attack: signed autoconvolution constant C_1d",
        "hypothesis": "A multi-resolution search might find a witness below the strongest publicly reported upper bound.",
        "external_problem": "https://teorth.github.io/optimizationproblems/constants/1d.html",
        "initial_certificate": {
            "url": UPSTREAM,
            "sha256": SOURCE_SHA256,
            "original_author_attribution": "steps-re/c1d-certificate (STEPS2026; original numerical values)",
            "upstream_rights": "No explicit license detected; data fetched for read-only research; derivative rights review remains necessary."
        },
        "incumbent": {"exact_num": str(REPORTED_BEST_NUM), "exact_den": str(REPORTED_BEST_DEN),
                      "attribution": "J2026, stronger 81,920-cell bound claimed in open teorth/optimizationproblems PR #312, Nov 3 2026; not a merged, peer-certified theorem"},
        "algorithm": {"seed":seed,"max_n":max_n,"iterations_per_stage_and_temperature":iters,
                      "objective":"2*n*max(|convolve(values,values)|)/(sum(values)^2)",
                      "method":"projected smooth-minimax L-BFGS-B with independent controls; not a claim of global optimality"},
        "source_baseline_numerical": baseline,
        "stages": stages,
        "numerical_final_ratio": value,
        "values": arr,
        "claim_boundary": "Not certified until separate exact-rational checker; not an autonomous goal-formulation experiment."
    }
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=None)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--max-cells", type=int, choices=(600, 1200, 2400), default=2400)
    p.add_argument("--iterations", type=int, default=750)
    args = p.parse_args(argv)
    if args.output.exists():
        raise ValueError("DO_NOT_OVERWRITE_EXISTING_OUTPUT")
    result = run(args.source, args.max_cells, args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print("CANDIDATE_FILE", args.output, flush=True)


if __name__ == "__main__":
    main()
