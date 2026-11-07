"""Finite, source-bound calibration dependency experiment; no physical measurements."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

from research.blue_sky064 import probe

QS = (0.0, 0.25, 0.50)
PARAMETER_COUNT = 8
EPS = 1e-12
REGISTRATION = Path(__file__).with_name("PREREGISTRATION.md")


def source_parameters(fixture, registration):
    """Original first-three-row OLS slopes; never tune against test outputs."""
    family_by_id = {row["id"]: row for row in fixture["calibration"]}
    result = []
    for name in registration["families"]:
        family = family_by_id[name]
        for phase in ("s", "d"):
            for kind, rows in (
                ("sigma", family["phases"][phase]["force_rows"]),
                ("B", family["phases"][phase]["area_rows"]),
            ):
                fit = probe.first_three_fit(rows)
                low, high = map(float, fit["CI95_OLS"])
                estimate = float(fit["slope"])
                if not (0 < low <= estimate <= high and
                        all(math.isfinite(v) for v in (low, estimate, high))):
                    raise ValueError("NONPOSITIVE_OR_INVALID_SOURCE_INTERVAL:" + name)
                result.append({
                    "name": name + "." + kind + "_" + phase,
                    "estimate": estimate,
                    "low": low,
                    "high": high,
                })
    if len(result) != PARAMETER_COUNT:
        raise ValueError("EXACT_EIGHT_SOURCE_COEFFICIENTS_REQUIRED")
    return result


def intervals_for_mask(parameters, mask, q):
    if type(mask) is not int or mask < 0 or mask >= (1 << PARAMETER_COUNT):
        raise ValueError("INVALID_MEASUREMENT_SUBSET")
    if type(q) is not float or not math.isfinite(q) or not 0 <= q <= 1:
        raise ValueError("INVALID_REMAINING_INTERVAL_FRACTION")
    if len(parameters) != PARAMETER_COUNT:
        raise ValueError("EXACT_EIGHT_SOURCE_COEFFICIENTS_REQUIRED")
    intervals = []
    for i, param in enumerate(parameters):
        lo, est, hi = param["low"], param["estimate"], param["high"]
        if mask & (1 << i):
            lo = est - q * (est - lo)
            hi = est + q * (hi - est)
        if not (0 < lo <= est <= hi and math.isfinite(lo) and math.isfinite(hi)):
            raise ValueError("INVALID_SOURCE_INTERVAL")
        intervals.append((lo, hi))
    return intervals


def ratio_delta(values, families, registration):
    """Same eight coefficients across two indentations; no hidden-state selection."""
    if len(values) != PARAMETER_COUNT:
        raise ValueError("EXACT_EIGHT_COEFFICIENT_VALUES_REQUIRED")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in values):
        raise ValueError("POSITIVE_FINITE_VALUES_REQUIRED")
    geometry = registration["geometry"]
    indentation = registration["test_indentation_mm"]
    if len(indentation) != 2 or indentation[0] >= indentation[1]:
        raise ValueError("ORDERED_TWO_INDENTATIONS_REQUIRED")
    ratios = []
    for depth_setting in indentation:
        fs = 0.0
        fd = 0.0
        for i, family in enumerate(families):
            prefix = "family_A_" if i == 0 else "family_B_"
            local_depth = max(
                0.0,
                depth_setting - (
                    geometry["family_A_height_mm"] - geometry[prefix + "height_mm"]
                ),
            )
            area = (
                geometry[prefix + "count"] * math.pi *
                family["radius_mm"] * local_depth
            )
            fs += values[4*i] * values[4*i+1] * area
            fd += values[4*i+2] * values[4*i+3] * area
        if fd <= 0:
            raise ValueError("ZERO_DYNAMIC_CONTACT_FORCE")
        ratios.append(fs / fd)
    return ratios[1] - ratios[0]


def enumerate_worst(intervals, families, registration):
    """All 2^8 *shared* corner assignments; never optimize states separately."""
    worst = math.inf
    best = -math.inf
    worst_corner = None
    checked = 0
    for corner in itertools.product((0, 1), repeat=PARAMETER_COUNT):
        values = [intervals[i][corner[i]] for i in range(PARAMETER_COUNT)]
        delta = ratio_delta(values, families, registration)
        if delta < worst:
            worst = delta
            worst_corner = "".join(str(c) for c in corner)
        best = max(best, delta)
        checked += 1
    if checked != 256 or worst_corner is None:
        raise AssertionError("MISSING_REGISTERED_CORNERS")
    return worst, best, worst_corner


def experiment():
    fixture, regs = probe.load_inputs()
    reg = regs["MIXED_REGISTRATION.json"]
    families_by_id = {row["id"]: row for row in fixture["calibration"]}
    families = [families_by_id[name] for name in reg["families"]]
    params = source_parameters(fixture, reg)
    target = float(reg["necessary_construction_target"]
                   ["increase_in_static_dynamic_ratio_at_least"])
    nominal = ratio_delta([p["estimate"] for p in params], families, reg)
    registered_control = probe.mixed_composition(fixture, reg)
    if not (
        abs(nominal - registered_control["nominal_ratio_increase"]) <= EPS and
        target == 0.05
    ):
        raise AssertionError("FROZEN_SOURCE_MODEL_DISAGREES")
    cases = {}
    for q in QS:
        rows = []
        by_cardinality = {str(k): {"tested": 0, "certified": 0,
                                  "max_worst": -math.inf}
                          for k in range(PARAMETER_COUNT + 1)}
        for mask in range(1 << PARAMETER_COUNT):
            lo, hi, corner = enumerate_worst(
                intervals_for_mask(params, mask, q), families, reg
            )
            size = mask.bit_count()
            accepted = lo >= target
            row = {"mask": mask, "count": size,
                   "measured_coefficients": [
                       params[i]["name"] for i in range(PARAMETER_COUNT)
                       if mask & (1 << i)
                   ],
                   "worst_delta": lo, "best_delta": hi,
                   "worst_shared_corner": corner,
                   "conditional_certificate": accepted}
            rows.append(row)
            band = by_cardinality[str(size)]
            band["tested"] += 1
            band["certified"] += int(accepted)
            band["max_worst"] = max(band["max_worst"], lo)
        qualifying = [row for row in rows if row["conditional_certificate"]]
        minimal = min((row["count"] for row in qualifying), default=None)
        winners = [row["measured_coefficients"] for row in qualifying
                   if row["count"] == minimal] if minimal is not None else []
        cases[str(q)] = {
            "assumed_remaining_halfwidth_fraction": q,
            "subset_count": len(rows),
            "corner_evaluations": sum(256 for _ in rows),
            "minimal_number_of_measurements": minimal,
            "all_minimal_subsets": winners,
            "no_measure_worst": rows[0]["worst_delta"],
            "all_eight_worst": rows[-1]["worst_delta"],
            "strong_ordinary_baseline": "EXHAUSTIVE_ALL_SUBSETS_IDENTICAL",
            "by_cardinality": by_cardinality,
            "all_registered_subset_outcomes": rows,
        }
        if len(rows) != 256:
            raise AssertionError("INCOMPLETE_SUBSET_ENUMERATION")
        if not math.isclose(
            rows[0]["worst_delta"],
            registered_control["independent_interval_worst_ratio_increase"],
            rel_tol=0.0, abs_tol=EPS
        ):
            raise AssertionError("FROZEN_NO_MEASUREMENT_CONTROL_DISAGREES")
    return {
        "schema": "agi-alpha/blue-sky064-calibration-dependency/v1",
        "scope": "CONDITIONAL_COMPUTATIONAL_DIAGNOSTIC_NOT_MEASURED_TRANSFER",
        "main_source": "22678d629d986572c50891b60455911978789da5",
        "selected_candidate": "mixed_passive_static_dynamic_hold_slide",
        "source_hashes": {
            "fixture_sha256": probe.FIXTURE_SHA256,
            "registrations_sha256": probe.REGISTRATION_HASHES,
            "probe_file_sha256": probe.checksum(Path(probe.__file__)),
            "planner_sha256": probe.checksum(Path(__file__)),
            "preregistration_sha256": probe.checksum(REGISTRATION),
        },
        "target_ratio_increase": target,
        "nominal_fitted_delta": nominal,
        "no_measure_registered_worst": registered_control[
            "independent_interval_worst_ratio_increase"
        ],
        "source_coefficients": params,
        "worlds": cases,
        "physical_observations_added": 0,
        "real_buyers": 0,
        "real_collections_usd": 0,
        "modeled_financial_account": None,
        "complete_calibration_and_commercial_cost_usd": "UNKNOWN",
        "host_and_model_billing_usd": "UNKNOWN",
        "decision": "NO_DEPLOY_HOLD_PENDING_PHYSICAL_TRANSFER_AND_BUYER_EVIDENCE",
        "limitations": [
            "A chosen coefficient contraction is assumed, not an achieved acquisition.",
            "Approximate independent OLS intervals are not joint physical coverage.",
            "Contact-family mixing and physical compliance are unqualified.",
            "Strong conventional construction and active alternatives remain allowed.",
            "No price, demand, contract, earned cash, physical prototype, or successor gain."
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    directory = args.output
    if not directory.is_absolute() or directory.exists() or any(
        item.is_symlink() for item in (directory, *directory.parents)
    ):
        raise SystemExit("ABSOLUTE_NEW_NON_SYMLINK_OUTPUT_REQUIRED")
    report = experiment()
    directory.mkdir(parents=True)
    (directory / "RESULT.json").write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({
        "decision": report["decision"],
        "nominal_fitted_delta": report["nominal_fitted_delta"],
        "no_measure_registered_worst": report["no_measure_registered_worst"],
        "minimum_counts": {q: v["minimal_number_of_measurements"]
                           for q, v in report["worlds"].items()},
        "registered_subset_denominator": 256*len(QS),
        "registered_corner_denominator": 256*256*len(QS),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
