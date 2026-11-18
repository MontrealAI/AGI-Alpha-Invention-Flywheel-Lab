"""Construct a portable follow-up worklist for a frozen observer and public alert catalog."""
import argparse
import csv
import itertools
import json
from functools import lru_cache
from pathlib import Path

from geometry import admissible, digest, extrema, validate


def build(mission, catalog):
    starts = validate(mission, catalog)
    targets = sorted(catalog["targets"], key=lambda t: t["id"])
    angles = {}
    choices = []
    for obj in targets:
        visible = []
        for index, start in enumerate(starts):
            low, high = extrema(mission, start, obj)
            if admissible(mission, low, high):
                visible.append(index)
                angles[(obj["id"], index)] = (round(low, 5), round(high, 5))
        bundles = []
        for group in itertools.combinations(visible, mission["visits_per_target"]):
            if len(group) == 2:
                first, last = (starts[i] for i in group)
                if first.date() == last.date() or (last - first).total_seconds() < mission["min_revisit_hours"] * 3600:
                    continue
            bundles.append((sum(1 << i for i in group), group))
        choices.append(bundles)

    @lru_cache(None)
    def allocate(obj_index, used):
        if obj_index == len(targets):
            return ()
        best = allocate(obj_index + 1, used)
        for mask, group in choices[obj_index]:
            if mask & used or (mask | used).bit_count() > mission["max_slots"]:
                continue
            with_target = ((obj_index, group),) + allocate(obj_index + 1, used | mask)
            if len(with_target) > len(best) or (len(with_target) == len(best) and with_target < best):
                best = with_target
        return best

    complete = allocate(0, 0)
    rows = []
    for obj_index, group in complete:
        obj = targets[obj_index]
        for i in group:
            low, high = angles[(obj["id"], i)]
            rows.append({"target_id": obj["id"], "utc": mission["slots_utc"][i],
                         "ra_deg": obj["ra_deg"], "dec_deg": obj["dec_deg"],
                         "min_alt_deg": low, "max_sun_alt_deg": high})
    return {"scope": mission["scope"], "dispatch_authorized": False,
            "mission_sha256": digest(mission), "catalog_sha256": digest(catalog),
            "objective": len(complete), "slots": sorted(rows, key=lambda r: r["utc"])}


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission", type=Path, default=here / "mission.json")
    parser.add_argument("--catalog", type=Path, default=here / "catalog.json")
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    args = parser.parse_args()
    mission = json.loads(args.mission.read_text())
    catalog = json.loads(args.catalog.read_text())
    result = build(mission, catalog)
    from verify import verify
    evidence = verify(mission, catalog, result)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "worklist.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.out / "acceptance.json").write_text(json.dumps(evidence, indent=2) + "\n")
    with (args.out / "worklist.csv").open("w", newline="") as stream:
        fields = ["target_id", "utc", "ra_deg", "dec_deg", "min_alt_deg", "max_sun_alt_deg"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["slots"])
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
