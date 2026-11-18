"""Reproduce all registered worklists, conventional alternatives and observed colors offline."""
import argparse
import hashlib
import json
from pathlib import Path

from geometry import admissible, digest, extrema, utc
from photometry import evaluate
from plan import build
from reference import targets_from_alerts
from verify import verify

ROOT = Path(__file__).resolve().parent
ALERTS_SHA256 = "bd0e18b40abb8d0371411481537485f065eb2b894df45ff1aa1fecf6422850ae"
HOLDOUT_SHA256 = "376d09cd44958c07be13641f0a3d6957607b54c1060eecc9ad2cda43badf0cad"
CATALOG_SHA256 = "0048b9b6c3b32e858df9dcb62df02fc77133cb0e89834a3c9d6c9676442d1e53"


def check_source(filename, expected):
    raw = (ROOT/filename).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"source identity differs: {filename}")
    return raw


def qualification():
    catalog = json.loads(check_source("catalog.json", CATALOG_SHA256))
    alerts = json.loads(check_source("sources/fink-alerts.json", ALERTS_SHA256))
    check_source("sources/fink-holdout.json", HOLDOUT_SHA256)
    if targets_from_alerts(alerts) != catalog["targets"]:
        raise ValueError("catalog projection differs from original alert response")
    mission = json.loads((ROOT/"mission.json").read_text())
    ref = catalog["reference"]
    max_error = 0
    for obj in catalog["targets"]:
        for i, stamp in enumerate(mission["slots_utc"]):
            low, high = extrema(mission, utc(stamp), obj)
            astro_low, astro_high = ref["min_alt_deg"][obj["id"]][i], ref["max_sun_alt_deg"][i]
            max_error = max(max_error, abs(low-astro_low), abs(high-astro_high))
            if admissible(mission, low, high) != admissible(mission, astro_low, astro_high):
                raise ValueError("candidate and direct calendars disagree on eligibility")
    if max_error > 0.1:
        raise ValueError("target or solar ephemerides disagree")
    cases = []
    for visits in (1, 2):
        for budget in range(len(mission["slots_utc"]) + 1):
            request = {**mission, "max_slots": budget, "visits_per_target": visits}
            worklist = build(request, catalog)
            receipt = verify(request, catalog, worklist)
            cases.append({"id": f"b{budget}-v{visits}", "budget": budget, "visits": visits,
                          "accepted": receipt["accepted"], "objective": worklist["objective"],
                          "direct_objective": receipt["direct_objective"], "slots": worklist["slots"],
                          "mission_sha256": worklist["mission_sha256"]})
    return {"schema": 1, "issuer": catalog["issuer"], "scope": mission["scope"],
            "dispatch_authorized": False, "mission": mission, "catalog_sha256": digest(catalog),
            "targets": catalog["targets"], "source_url": catalog["source_url"],
            "alerts_sha256": ALERTS_SHA256, "source_retrieved_utc": "2026-11-18T01:11:38Z",
            "classification": catalog["classification"], "geometry_comparisons": len(catalog["targets"])*len(mission["slots_utc"]),
            "max_angle_difference_deg": round(max_error, 6), "cases": cases, "photometry": evaluate(),
            "exploratory_color_counts": [{"max_gap_minutes": gap, "accepted_pairs": evaluate(gap)["direct_sql"]["accepted_pairs"]}
                                         for gap in (5, 10, 30, 60, 120)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="compare against the frozen public projection")
    group.add_argument("--out", type=Path, help="write a new public projection")
    args = parser.parse_args()
    result = qualification()
    if args.check:
        if result != json.loads((ROOT/"public.json").read_text()):
            raise SystemExit("public projection differs")
    else:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    photo = result["photometry"]
    print(f'{len(result["cases"])} accepted schedules; {photo["public_rows"]} held-out measurements; '
          f'{len(photo["pairs"])}/{photo["targets"]} two-band products')
