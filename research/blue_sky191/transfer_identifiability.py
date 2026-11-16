"""Source-pinned structural transfer-identifiability witness. Research only."""
from __future__ import annotations

import argparse
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "research/blue_sky064/public_calibration.json"
REG = "campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json"
SOURCE_SHA = "7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced"
REG_SHA = "6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa"
PROTOCOL_COMMIT = "783a14d5f966a193973d6be741cfa2e2999c6a18"
SCHEMA = "agi-alpha/blue-sky191-mixed-transfer-identifiability/v1"
FAMILIES = ("Batch1_R496", "Batch2_R1543")


class Refused(ValueError):
    """Invalid or changed evidence, or inadmissible research operation."""


def unique_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Refused("DUPLICATE_JSON_KEY:" + key)
        out[key] = value
    return out


def read_pinned(path: Path, sha256: str):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise Refused("SMALL_REGULAR_SOURCE_REQUIRED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise Refused("PINNED_SOURCE_CHANGED")
    try:
        return json.loads(raw, parse_float=Decimal, object_pairs_hook=unique_keys)
    except (ValueError, UnicodeError, TypeError) as err:
        raise Refused("INVALID_SOURCE_JSON") from err


def rational(number):
    if isinstance(number, bool) or not isinstance(number, (Decimal, int, Fraction)):
        raise Refused("FINITE_RATIONAL_REQUIRED")
    number = Decimal(number) if not isinstance(number, Fraction) else number
    if isinstance(number, Decimal) and not number.is_finite():
        raise Refused("FINITE_RATIONAL_REQUIRED")
    return Fraction(number)


def source_rows(fixture, registration):
    if fixture.get("schema") != "blue-sky064/public-calibration-fixture/v1":
        raise Refused("UNRECOGNIZED_FIXTURE")
    if fixture.get("license") != "CC-BY-4.0":
        raise Refused("UNATTRIBUTED_FIXTURE")
    if registration.get("schema") != "friction064/mixed-hold-slide-probe/v1":
        raise Refused("UNRECOGNIZED_REGISTRATION")
    if tuple(registration.get("families", ())) != FAMILIES:
        raise Refused("SELECTED_FAMILIES_CHANGED")
    if rational(registration["necessary_construction_target"]["increase_in_static_dynamic_ratio_at_least"]) != Fraction(1, 20):
        raise Refused("TARGET_CHANGED")
    groups = fixture.get("calibration")
    if not isinstance(groups, list) or len(groups) != 3:
        raise Refused("ALL_PUBLISHED_SOURCE_BLOCKS_REQUIRED")
    by_id = {g.get("id"): g for g in groups if isinstance(g, dict)}
    if set(by_id) != {"Batch1_R496", "Batch2_R507", "Batch2_R1543"}:
        raise Refused("PUBLISHED_FAMILIES_CHANGED")
    if len(by_id) != len(groups):
        raise Refused("DUPLICATE_SOURCE_FAMILY")
    matrix = []
    row_counts = {}
    for family in FAMILIES:
        block = by_id[family]
        if set(block.get("phases", {})) != {"s", "d"}:
            raise Refused("PUBLISHED_PHASES_CHANGED")
        for phase in ("s", "d"):
            data = block["phases"][phase]
            areas = data["area_rows"]
            forces = data["force_rows"]
            if not isinstance(areas, list) or not isinstance(forces, list) or not 2 <= len(forces) <= 1000 or len(forces) != len(areas):
                raise Refused("SOURCE_ROW_COUNTS_INVALID")
            for area_row, force_row in zip(areas, forces):
                if not isinstance(area_row, list) or not isinstance(force_row, list) or len(area_row) != 4 or len(force_row) != 4:
                    raise Refused("FOUR_COLUMN_SOURCE_REQUIRED")
                a0, ea0, a, ea = map(rational, area_row)
                af, ef_a, f, ef = map(rational, force_row)
                if (af, ef_a) != (a, ea):
                    raise Refused("PAIRED_AREA_FORCE_ROWS_CHANGED")
                if min(a0, a, f) <= 0 or not (0 <= ea0 < a0 and 0 <= ea < a and ef >= 0):
                    raise Refused("INVALID_EXPOSED_MEASUREMENT")
                a_area = a if family == FAMILIES[0] else Fraction(0)
                b_area = a if family == FAMILIES[1] else Fraction(0)
                matrix.append(design_row(a_area, b_area, phase))
            row_counts[family + "/" + phase] = len(forces)
    return matrix, row_counts


def design_row(a, b, phase):
    a, b = rational(a), rational(b)
    if min(a, b) < 0 or a + b <= 0 or phase not in ("s", "d"):
        raise Refused("POSITIVE_GEOMETRY_AND_PHASE_REQUIRED")
    h = a * b / (a + b)
    return [a, b, h, 0, 0, 0] if phase == "s" else [0, 0, 0, a, b, h]


def rank(rows, ncols=6):
    if not rows or not isinstance(ncols, int) or not 1 <= ncols <= 20:
        raise Refused("NONEMPTY_BOUNDED_MATRIX_REQUIRED")
    mat = []
    for row in rows:
        if len(row) != ncols:
            raise Refused("MATRIX_WIDTH_CHANGED")
        mat.append([rational(v) for v in row])
    pivot_count = 0
    for col in range(ncols):
        pivot = next((i for i in range(pivot_count, len(mat)) if mat[i][col]), None)
        if pivot is None:
            continue
        mat[pivot_count], mat[pivot] = mat[pivot], mat[pivot_count]
        divisor = mat[pivot_count][col]
        mat[pivot_count] = [v / divisor for v in mat[pivot_count]]
        for i in range(len(mat)):
            if i != pivot_count and mat[i][col]:
                multiple = mat[i][col]
                mat[i] = [x - multiple * y for x, y in zip(mat[i], mat[pivot_count])]
        pivot_count += 1
        if pivot_count == ncols:
            break
    return pivot_count


def predicted_force(coefficients, a, b, phase):
    if len(coefficients) != 6:
        raise Refused("SIX_COEFFICIENTS_REQUIRED")
    vals = [rational(x) for x in coefficients]
    if any(x < 0 for x in vals):
        raise Refused("NONNEGATIVE_COEFFICIENTS_REQUIRED")
    return sum(x * y for x, y in zip(vals, design_row(a, b, phase)))


def toy_contrast():
    world0 = [2, 4, 0, 1, 2, 0]
    world1 = [2, 4, 1, 1, 2, 0]
    for phase in ("s", "d"):
        for area in (Fraction(1, 4), Fraction(1), Fraction(7, 3)):
            for a, b in ((area, 0), (0, area)):
                if predicted_force(world0, a, b, phase) != predicted_force(world1, a, b, phase):
                    raise Refused("PURE_OBSERVATION_NONIDENTITY")
    ratio0 = predicted_force(world0, 1, 1, "s") / predicted_force(world0, 1, 1, "d")
    ratio1 = predicted_force(world1, 1, 1, "s") / predicted_force(world1, 1, 1, "d")
    improvement = ratio1 / ratio0 - 1
    if (ratio0, ratio1, improvement) != (Fraction(2), Fraction(13, 6), Fraction(1, 12)):
        raise Refused("CONTRAST_ARITHMETIC_CHANGED")
    return {"pure_observations_indistinguishable": True,
            "baseline_mixed_ratio": str(ratio0),
            "alternative_mixed_ratio": str(ratio1),
            "relative_improvement": str(improvement),
            "source_target": str(Fraction(1, 20)),
            "world0_passes_target": False, "world1_passes_target": True,
            "world_coefficients_are_synthetic_not_source_estimates": True}


def analyze(fixture, registration):
    matrix, counts = source_rows(fixture, registration)
    mixed_s = design_row(1, 1, "s")
    mixed_d = design_row(1, 1, "d")
    ranks = {
        "published_pure_only": rank(matrix),
        "pure_plus_one_mixed_static": rank(matrix + [mixed_s]),
        "pure_plus_one_mixed_dynamic": rank(matrix + [mixed_d]),
        "pure_plus_both_mixed_phases": rank(matrix + [mixed_s, mixed_d]),
        "pure_plus_static_without_cross_contact": rank(matrix + [design_row(1, 0, "s")]),
    }
    if ranks != {"published_pure_only": 4, "pure_plus_one_mixed_static": 5,
                 "pure_plus_one_mixed_dynamic": 5, "pure_plus_both_mixed_phases": 6,
                 "pure_plus_static_without_cross_contact": 4}:
        raise Refused("EXPECTED_IDENTIFIABILITY_RANKS_NOT_VERIFIED")
    return {"schema": SCHEMA, "preregistration_commit": PROTOCOL_COMMIT,
            "source_fixture_sha256": SOURCE_SHA, "source_registration_sha256": REG_SHA,
            "selected_published_row_counts": counts, "selected_total_pure_rows": len(matrix),
            "parameter_dimension": 6, "exact_rational_design_ranks": ranks,
            "nullity_of_pure_only_design": 6 - ranks["published_pure_only"],
            "synthetic_indistinguishable_worlds": toy_contrast(),
            "decision": "HOLD_MIXED_TRANSFER_REQUIRES_MIXED_OBSERVATION",
            "comparison": ["A_pure_only_repeats", "B_mixed_static_and_dynamic_plus_pure_controls",
                           "C_ordinary_passive_or_active_complete_alternative", "D_no_deploy"],
            "scientific_scope": "Structural nullspace of an assumed interaction grammar; published source error-box inconsistency remains, not a fitted transfer law or empirical experiment.",
            "independent_mixed_measurement_required": True,
            "physical_instrument_qualified": False, "real_buyers_or_revenue": False,
            "trailing_365_complete_cost_profit_usd": None, "total_host_model_billing_usd": None}


def run(output: Path, root: Path = ROOT):
    output = Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise Refused("ABSOLUTE_CREATE_ONLY_OUTPUT_REQUIRED")
    wall, cpu = time.perf_counter(), time.process_time()
    result = analyze(read_pinned(root / SOURCE, SOURCE_SHA), read_pinned(root / REG, REG_SHA))
    result["wall_seconds"] = round(time.perf_counter() - wall, 6)
    result["self_cpu_seconds"] = round(time.process_time() - cpu, 6)
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644), "w") as fp:
        json.dump(result, fp, indent=2, sort_keys=True, allow_nan=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    result = run(parser.parse_args().output)
    print(json.dumps({"decision": result["decision"],
                      "ranks": result["exact_rational_design_ranks"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
