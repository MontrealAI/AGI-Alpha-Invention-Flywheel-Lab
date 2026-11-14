"""Source-bound two-family geometry-independent *conditional* no-go.

No physical validation, buyer observation, finance transaction or optimization.
The ordinary closed-form algebra is the strongest mathematical baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "research/blue_sky064/public_calibration.json"
REGISTRATION = ROOT / "campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json"
FIXTURE_HASH = "7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced"
REGISTRATION_HASH = "6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa"
T_95_DF2 = 4.302652729911275  # two-sided Student t, df=2
QS = (0.0, 0.25, 0.50, 1.0)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_SOURCE_JSON_KEY")
        result[key] = value
    return result


def _finite_positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def load_verified(path: Path, expected: str):
    """Bind source bytes; no claim of race-proof path custody."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError("FROZEN_SOURCE_FILE_INVALID")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("FROZEN_SOURCE_BYTES_CHANGED")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)


def ols_interval(rows):
    """Same first-three-row origin fit as original probe; no fitted data changes."""
    if type(rows) is not list or len(rows) < 3:
        raise ValueError("MISSING_CALIBRATION_ROWS")
    train = rows[:3]
    if any(
        type(r) is not list or len(r) != 4
        or any(type(v) not in (float, int) or not math.isfinite(v) for v in r)
        or r[0] <= 0
        for r in train
    ):
        raise ValueError("INVALID_CALIBRATION_ROWS")
    denom = sum(row[0] ** 2 for row in train)
    slope = sum(row[0] * row[2] for row in train) / denom
    residual_sum = sum((row[2] - slope * row[0]) ** 2 for row in train)
    margin = T_95_DF2 * math.sqrt(residual_sum / 2 / denom)
    low, high = max(0.0, slope - margin), slope + margin
    if not all(_finite_positive(x) for x in (low, slope, high)):
        raise ValueError("NONPOSITIVE_COEFFICIENT_INTERVAL")
    return {"low": low, "estimate": slope, "high": high}


def source_families(fixture, registration):
    if fixture.get("schema") != "blue-sky064/public-calibration-fixture/v1" or fixture.get("license") != "CC-BY-4.0":
        raise ValueError("WRONG_FROZEN_SOURCE_SCHEMA_OR_LICENSE")
    names = registration.get("families")
    if registration.get("schema") != "friction064/mixed-hold-slide-probe/v1" or names != ["Batch1_R496", "Batch2_R1543"]:
        raise ValueError("WRONG_FROZEN_TWO_FAMILY_REGISTRATION")
    if registration.get("necessary_construction_target", {}).get("increase_in_static_dynamic_ratio_at_least") != 0.05:
        raise ValueError("REGISTERED_TARGET_CHANGED")
    original = fixture.get("calibration")
    if type(original) is not list:
        raise ValueError("MISSING_SOURCE_CALIBRATION")
    rows = {}
    for family in original:
        if family.get("id") in rows:
            raise ValueError("DUPLICATE_SOURCE_FAMILY")
        rows[family.get("id")] = family
    result = {}
    for name in names:
        family = rows.get(name)
        if family is None:
            raise ValueError("MISSING_REGISTERED_FAMILY")
        params = {}
        for phase in ("s", "d"):
            for kind, source_key in (("sigma", "force_rows"), ("B", "area_rows")):
                params[kind + "_" + phase] = ols_interval(
                    family["phases"][phase][source_key]
                )
        result[name] = params
    return result


def _coefficients(family, choice):
    """Return source-law S,D; choices must bind coefficients in one world."""
    def get(key):
        return family[key][choice[key]]
    return get("sigma_s") * get("B_s"), get("sigma_d") * get("B_d")


def ratio(s, d):
    if not all(_finite_positive(v) for v in (s, d)):
        raise ValueError("POSITIVE_FRICTION_COEFFICIENTS_REQUIRED")
    return s / d


def weight_response(weights, a, b):
    """Return R and normalized family-B share for one physical indentation."""
    if type(weights) not in (tuple, list) or len(weights) != 2:
        raise ValueError("TWO_NONNEGATIVE_WEIGHTS_REQUIRED")
    if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in weights):
        raise ValueError("FINITE_NONNEGATIVE_WEIGHTS_REQUIRED")
    wa, wb = weights
    if wa == wb == 0:
        raise ValueError("POSITIVE_DYNAMIC_RESPONSE_REQUIRED")
    sa, da = a
    sb, db = b
    if not all(_finite_positive(x) for x in (sa, da, sb, db)):
        raise ValueError("POSITIVE_SOURCE_COEFFICIENTS_REQUIRED")
    den = wa * da + wb * db
    if not _finite_positive(den):
        raise ValueError("POSITIVE_DYNAMIC_RESPONSE_REQUIRED")
    frac_b = wb * db / den
    response = (wa * sa + wb * sb) / den
    if not all(math.isfinite(v) for v in (frac_b, response)):
        raise ValueError("NONFINITE_RESPONSE")
    return response, frac_b


def delta_and_identity(first, second, a, b):
    """Exact mixture identity for arbitrary nonnegative geometry weights."""
    r0, f0 = weight_response(first, a, b)
    r1, f1 = weight_response(second, a, b)
    direct = r1 - r0
    identity = (f1 - f0) * (ratio(*b) - ratio(*a))
    return direct, identity, f1 - f0


def interval_coefficient(entry, side, q):
    if type(q) not in (float, int) or not math.isfinite(q) or not 0 <= q <= 1:
        raise ValueError("INVALID_DECLARED_INTERVAL_CONTRACTION")
    center = entry["estimate"]
    endpoint = entry[side]
    answer = center + q * (endpoint - center)
    if not _finite_positive(answer):
        raise ValueError("NONPOSITIVE_CONTRACTED_INTERVAL")
    return answer


def endpoint_world(families, q):
    a, b = [families[k] for k in ("Batch1_R496", "Batch2_R1543")]
    # Adverse shared world maximizes A's static/dynamic ratio while
    # minimizing B's. All eight choices are from the same source box.
    ac = {k: interval_coefficient(e, "high" if k.endswith("_s") else "low", q)
          for k, e in a.items()}
    bc = {k: interval_coefficient(e, "low" if k.endswith("_s") else "high", q)
          for k, e in b.items()}
    sa, da = ac["sigma_s"] * ac["B_s"], ac["sigma_d"] * ac["B_d"]
    sb, db = bc["sigma_s"] * bc["B_s"], bc["sigma_d"] * bc["B_d"]
    return {
        "family_A_ratio_max": ratio(sa, da),
        "family_B_ratio_min": ratio(sb, db),
        "B_minus_A_min_gap": ratio(sb, db) - ratio(sa, da),
        "shared_world_coefficients": {"A": ac, "B": bc},
        "source_model_sign_robust": ratio(sb, db) > ratio(sa, da),
    }


def nominal_world(families):
    data = {}
    for label, name in (("A", "Batch1_R496"), ("B", "Batch2_R1543")):
        c = {k: v["estimate"] for k, v in families[name].items()}
        data[label] = c
    ra = (data["A"]["sigma_s"] * data["A"]["B_s"]
          / (data["A"]["sigma_d"] * data["A"]["B_d"]))
    rb = (data["B"]["sigma_s"] * data["B"]["B_s"]
          / (data["B"]["sigma_d"] * data["B"]["B_d"]))
    return {"family_A_ratio": ra, "family_B_ratio": rb,
            "B_minus_A_gap": rb - ra, "shared_world_coefficients": data}


def prove_all_geometry(nominal_gap, adversarial_gap):
    """Sign reversal is a complete impossibility witness for two families.

    R_i = R_A + lambda_i * (R_B-R_A).
    Sign(lambda_1-lambda_0) equals sign(a_0*b_1-a_1*b_0),
    independent of positive D_A,D_B. Thus any fixed geometry has
    delta<=0 in at least one of two worlds with opposite ratio gaps.
    """
    if not all(type(x) in (float, int) and math.isfinite(x)
               for x in (nominal_gap, adversarial_gap)):
        raise ValueError("FINITE_WORLD_GAPS_REQUIRED")
    if nominal_gap > 0 and adversarial_gap < 0:
        return "CONDITIONAL_NO_GO_ALL_FIXED_TWO_FAMILY_GEOMETRIES"
    if nominal_gap < 0 and adversarial_gap > 0:
        return "CONDITIONAL_NO_GO_ALL_FIXED_TWO_FAMILY_GEOMETRIES"
    return "NO_OPPOSITE_SIGN_WITNESS_ESTABLISHED"


def experiment(fixture_path=FIXTURE, registration_path=REGISTRATION):
    fixture = load_verified(fixture_path, FIXTURE_HASH)
    registration = load_verified(registration_path, REGISTRATION_HASH)
    families = source_families(fixture, registration)
    nominal = nominal_world(families)
    contracted = {str(q): endpoint_world(families, q) for q in QS}
    worst = contracted[str(1.0)]
    verdict = prove_all_geometry(nominal["B_minus_A_gap"], worst["B_minus_A_min_gap"])
    if verdict != "CONDITIONAL_NO_GO_ALL_FIXED_TWO_FAMILY_GEOMETRIES":
        raise ValueError("ORIGINAL_TWO_WORLD_SIGN_CERTIFICATE_ABSENT")
    return {
        "schema": "agi-alpha/two-family-geometry-no-go101/v1",
        "source_sha256": {
            "fixture": FIXTURE_HASH, "mixed_registration": REGISTRATION_HASH,
            "implementation": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "preregistration": hashlib.sha256(Path(__file__).with_name("PROTOCOL.md").read_bytes()).hexdigest(),
        },
        "prior_exposure": "EXPOSED_SOURCE_DETERMINISTIC_REPRODUCTION_NOT_BLIND",
        "registered_target_delta": 0.05,
        "model": "positive load-independent two-family weighted linear static/dynamic forces",
        "original_source_uncertainty": "independent three-row OLS intervals; not simultaneous physical coverage",
        "nominal": nominal,
        "q_contractions": contracted,
        "all_geometry_verdict": verdict,
        "analytic_identity": "Delta=(lambda1-lambda0)*(RB-RA); sign(lambda1-lambda0)=sign(a0*b1-a1*b0) for positive dynamic coefficients",
        "strong_ordinary_control": "SAME_CLOSED_FORM_SIGN_CERTIFICATE",
        "fixed_geometry_reference": "PR291 negative q=0.25 and 0.50 source-model robust target results left unchanged",
        "failure_regions": [
            "Any source world where family ratio ordering reverses defeats any fixed geometry for a positive target",
            "Nonpositive or load-varying coefficients, mixed-contact interactions, other families, and contact dynamics are outside this theorem",
        ],
        "experimental_physical_transfer": "NOT_ESTABLISHED",
        "actual_buyer_acceptance": "NOT_ESTABLISHED",
        "complete_lifecycle_cost": "UNKNOWN",
        "native_account_actions": 0,
        "actual_paid_revenue_usd": "NOT_ESTABLISHED",
        "trailing365_complete_cost_profit_usd": None,
        "target_3b_qualified": False,
        "decision": "STOP_EXACT_TWO_FAMILY_GEOMETRY_ONLY_GRAMMAR_NO_BID_NO_DEPLOY",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output
    if output.exists() or output.is_symlink() or not output.is_absolute():
        raise ValueError("FRESH_ABSOLUTE_OUTPUT_PATH_REQUIRED")
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    receipt = experiment()
    receipt["process_cpu_seconds"] = time.process_time() - start_cpu
    receipt["wall_seconds"] = time.perf_counter() - start_wall
    receipt["host_and_model_billing_usd"] = "UNKNOWN"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    (output / "RESULT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verdict": receipt["all_geometry_verdict"],
                      "decision": receipt["decision"], "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
