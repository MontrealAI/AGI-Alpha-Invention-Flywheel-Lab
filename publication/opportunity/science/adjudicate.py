"""Score separately reduced, locked TOI-216 observations against their admission rules."""

from datetime import datetime
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


SECONDS_PER_DAY = 86400


def verified(path, digest):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"Frozen output digest mismatch for {path.name}")
    return json.loads(raw)


def qualified_ground(ground):
    if ground["verdict"] != "MEASURE" or ground["basis"] != "BJD_TDB":
        return False
    for variant in ground["variants"]:
        counts = variant["cadence_counts"]
        if (not 0.010 <= variant["fractional_depth"] <= 0.025
                or not 4.3 <= variant["duration_hours"] <= 6.8
                or counts["before"] < 5 or counts["after"] < 5
                or counts["ingress"] < 3 or counts["egress"] < 3
                or {"center", "duration", "depth"}.intersection(variant["parameter_at_bound"])):
            return False
    return True


def cross_clock_gap(event, ground):
    """Coarse separation only, with a margin far wider than barycentric corrections."""
    start = datetime.fromisoformat(ground["ground_visit_utc"][0])
    ground_start_jd = 2440587.5 + start.timestamp() / SECONDS_PER_DAY
    tdb_egress = event["mid_bjd_tdb"] + event["duration_hour"] / 48.0
    clock_allowance_s = 1000
    return {
        "tess_fourth_contact_bjd_tdb": tdb_egress,
        "independent_ground_first_exposure_jd_utc": ground_start_jd,
        "raw_cross_scale_gap_hours": (ground_start_jd - tdb_egress) * 24,
        "coarse_clock_allowance_seconds": clock_allowance_s,
        "remaining_gap_hours_under_allowance": (ground_start_jd - tdb_egress) * 24 - clock_allowance_s / 3600,
        "scope": "Post-fit chronology diagnostic. No precise UTC-to-TDB conversion or new fit was performed.",
        "timescale_reference": "https://doi.org/10.1086/655938",
    }


def main():
    base = Path(__file__).resolve().parent
    freeze = json.loads((base / "FREEZE.json").read_bytes())
    registration_digest = freeze["REGISTRATION.json"]
    registration = verified(base / "REGISTRATION.json", registration_digest)
    case = registration["held_case"]
    arms = {arm: verified(base / f"{arm.upper()}.json", freeze[f"{arm.upper()}.json"])
            for arm in ("ground", "tess")}
    if any(value["registration_sha256"] != registration_digest or value["arm"] != arm
           for arm, value in arms.items()):
        raise ValueError("Arm identity or registration mismatch")
    ground, tess = (arms[arm]["result"] for arm in ("ground", "tess"))
    group, = tess["groups"]
    lo, hi = case["wide_match_band_bjd_tdb"]
    targets = [e for e in group["events"] if e["verdict"] == "MEASURE"
               and e["planet"] == case["scheduled_ground_label"] and lo <= e["mid_bjd_tdb"] <= hi]
    comparisons = {}
    status = "ABSTAIN_GROUND_CLOCK_AND_COVERAGE" if not qualified_ground(ground) else "ABSTAIN_TESS_IDENTITY"
    keys = ("planet", "mid_bjd_tdb", "timing_error_min", "depth_ppt", "duration_hour", "sector", "fitted_components")
    if len(targets) == 1:
        if ground["verdict"] == "ABSTAIN_INVALID_BJD_TDB_AND_SHORT_VISIT":
            comparisons["coarse_chronology"] = cross_clock_gap(targets[0], ground)
        if qualified_ground(ground):
            ground_s = ground["conditional_timing_uncertainty_s"]
            tess_lower_s, tess_upper_s = (60 * value for value in targets[0]["timing_error_min"])
            status = "ABSTAIN_UNCERTAINTY"
            if all(isfinite(s) and 0 < s <= 300 for s in (ground_s, tess_lower_s, tess_upper_s)):
                ground_minus_tess_s = SECONDS_PER_DAY * (ground["primary_mid_bjd_tdb"] - targets[0]["mid_bjd_tdb"])
                limit_s = max(120, 3 * hypot(ground_s, max(tess_lower_s, tess_upper_s)))
                comparisons["conditional_centres"] = {
                    "absolute_difference_s": abs(ground_minus_tess_s),
                    "acceptance_limit_s": limit_s,
                    "intervals_overlap_at_one_sigma": -tess_lower_s - ground_s <= ground_minus_tess_s <= tess_upper_s + ground_s,
                }
                status = "CONCORDANT" if abs(ground_minus_tess_s) <= limit_s else "FAIL_MIDPOINT_AGREEMENT"
    receipt = {
        "schema": "frontier/independent-transit-confirmation-result-v1",
        "case": case,
        "baseline": registration["baseline"],
        "bindings": freeze,
        "tess": {"eligible_tess_only_measurements": [{k: e[k] for k in keys} for e in targets],
                 "source_product": tess["sources"][0], "time_system": tess["time_system"],
                 "software": tess["software"], "screened_abstentions": len(group["screened_abstentions"])},
        "ground": ground,
        "comparison": comparisons,
        "paired_attribution_verdict": status,
        "accepted_paired_events": int(status == "CONCORDANT"),
        "forecast_qualification": "ABSTAIN",
        "forecast_scope": registration["forecast_scope"],
    }
    (base / "RESULT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(status)


if __name__ == "__main__":
    main()
