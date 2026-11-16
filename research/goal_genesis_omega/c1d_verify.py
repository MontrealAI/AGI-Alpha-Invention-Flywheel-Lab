"""Independent exact-rational certificate checker for C_1d (stdlib only).

Reads every step value as an *exact binary64 rational*, using one common
power-of-two denominator; independently checks EVERY autoconvolution knot
with Python integers. It does not import the numerical optimizer or SciPy.

A passing certificate below the published SCiEL bound is a mathematically
valid tighter *upper bound*, conditional on source attribution and literature
currency. It is NOT a proof that the value of the constant is exact.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path

BEST = Fraction(38534420343892614563110610373646557184000,
                26432274393314964174848236787785831382961)
EXPECTED_SCHEMA = "montreal-ai/goal-genesis/c1d-candidate/v1"


def evaluate_exact(values):
    if type(values) is not list or not 2 <= len(values) <= 10000:
        raise ValueError("INVALID_STEP_COUNT")
    if any(type(v) is not float or not math.isfinite(v) for v in values):
        raise ValueError("INVALID_BINARY64_WEIGHT")
    ratios = [v.as_integer_ratio() for v in values]
    den = max(b for _,b in ratios)
    if not (den > 0 and den & (den - 1) == 0):
        raise ValueError("NON_BINARY_POWER_DENOMINATOR")
    integers = [a * (den // b) for a,b in ratios]
    total = sum(integers)
    if total == 0:
        raise ValueError("ZERO_SIGNED_INTEGRAL")
    n = len(integers)
    # This is intentionally structurally unlike the FFT-based search.
    # The proof's entire strength is a finite exact integer identity.
    max_abs = 0
    argmax = None
    for k in range(2*n-1):
        a = max(0,k-n+1);b = min(k,n-1)+1
        s = sum(integers[i] * integers[k-i] for i in range(a,b))
        if abs(s) > max_abs:
            max_abs=abs(s);argmax=k
    if max_abs == 0:
        raise ValueError("DEGENERATE_CONVOLUTION")
    value = Fraction(2*n*max_abs,total*total)
    return value, {"cells":n,"critical_knot":argmax,"max_integer_convolution":str(max_abs),
                   "weight_sum_integer":str(total),"common_denominator":str(den),
                   "witness_type":"uniform binary64-valued signed step function on [-1/4,1/4]"}


def verify_file(path):
    raw = Path(path).read_bytes()
    candidate = json.loads(raw)
    if type(candidate) is not dict or candidate.get("schema") != EXPECTED_SCHEMA:
        raise ValueError("WRONG_CERTIFICATE_SCHEMA")
    incumbent=candidate.get("incumbent")
    if type(incumbent) is not dict or incumbent.get("exact_num") != str(BEST.numerator) or incumbent.get("exact_den") != str(BEST.denominator):
        raise ValueError("INCUMBENT_TAMPERING")
    exact, details = evaluate_exact(candidate.get("values"))
    stated = candidate.get("numerical_final_ratio")
    if type(stated) is not float or not math.isfinite(stated) or abs(float(exact)-stated)>3e-8:
        raise ValueError("FALSE_NUMERICAL_SCORE")
    status="BEATS_REPORTED_FRONTIER" if exact < BEST else "DOES_NOT_BEAT_REPORTED_FRONTIER"
    # Deliberate independent no-promotion gate: no equality or rounding win.
    return {
        "schema":"montreal-ai/goal-genesis/c1d-independent-exact-verdict/v1",
        "status": status,
        "candidate_sha256":sha256(raw).hexdigest(),
        "exact_numerator":str(exact.numerator),
        "exact_denominator":str(exact.denominator),
        "candidate_decimal_16":format(float(exact),".16f"),
        "incumbent_decimal_16":format(float(BEST),".16f"),
        "improvement":float(BEST-exact),
        "reconstruction":details,
        "scope":"Exact upper bound for the specified C_1d signed autoconvolution constant; search novelty, rights and peer review remain separate.",
        "excluded_claims":["autonomous scientific goal discovery","optimal global constant","certified improvement if status does not say BEATS_REPORTED_FRONTIER","physical deployment","economic benefit","independent external peer review"]
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    if args.output.exists():
        raise ValueError("OUTPUT_ALREADY_EXISTS")
    verdict=verify_file(args.candidate)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(verdict,sort_keys=True,indent=2)+"\n")
    print("EXACT_VERDICT",verdict["status"],"ratio",verdict["candidate_decimal_16"],flush=True)
    print("EVIDENCE_SCOPE",verdict["scope"],flush=True)
    print("CERTIFICATE_OUTPUT_PATH",args.output,flush=True)


if __name__=="__main__":
    main()
