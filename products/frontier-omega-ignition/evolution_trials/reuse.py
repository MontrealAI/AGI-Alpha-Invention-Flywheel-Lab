"""What can the earlier delivered colour products alone establish for same-band alerting?"""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INVENTION = HERE.parent / "invention"


def read_original(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Changed earlier colour product: {path.name}")
    return json.loads(data)


def inventory():
    first = read_original(INVENTION / "public.json", "deb34ab3df7ba3cf301f475e1e501fbb45f55280ef8574408e91d9193b017d90")
    second = read_original(INVENTION / "next_week/RESULT.json",
                           "42e078dccc860af4c77cc1a03c9d11900c75417cb0ec53b69cd50c4762dbcfa2")
    cohorts = []
    for cohort, targets, pairs, earliest, total, end in (
        ("nov01", sorted(t["id"] for t in first["targets"]), first["photometry"]["pairs"],
         first["photometry"]["first_detections"], {}, "2026-11-08T00:00:00Z"),
        ("nov10", sorted(second["selected_target_ids"]), second["pairs_120"] + second["pairs_10"],
         [], second["positive_detections_by_target"], "2026-11-17T00:00:00Z"),
    ):
        disclosed = defaultdict(set)
        for pair in pairs:
            for band in ("g", "r"):
                disclosed[pair["target_id"], band].add(pair[f"{band}_candid"])
        first_visit = {}
        for visit in earliest:
            first_visit[visit["target_id"]] = datetime.fromisoformat(visit["utc"])
            disclosed[visit["target_id"], visit["band"]].add(visit["candid"])
        decisions = []
        for target in targets:
            for band, other in (("g", "r"), ("r", "g")):
                known = len(disclosed[target, band])
                max_visits = total[target] - len(disclosed[target, other]) if target in total else None
                # The old first-visit string has millisecond display precision; require a strict margin.
                too_late = (target in first_visit and first_visit[target] >
                            datetime.fromisoformat(end) - timedelta(days=0.5))
                enough_to_rule_out = (max_visits is not None and max_visits < 2) or too_late
                decisions.append(dict(target_id=target, band=band, retained_measurements=known,
                                      max_possible_in_band=max_visits,
                                      disposition="no_trigger_proven" if enough_to_rule_out else "insufficient_information"))
        cohorts.append(dict(id=cohort, decisions=decisions, retained_distinct_detections=sum(map(len, disclosed.values()))))
    return dict(available_at="after both colour products were issued", cohorts=cohorts,
                verified_issuance_dispositions=sum(d["disposition"] == "no_trigger_proven" for c in cohorts for d in c["decisions"]),
                total_target_band_decisions=sum(len(c["decisions"]) for c in cohorts),
                scope="Only a complete same-band history can normally select the correct comparison and held-back witness.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, help="write a fresh receipt")
    path = p.parse_args().out
    data = json.dumps(inventory(), indent=2) + "\n"
    if path:
        with path.open("x", encoding="utf-8") as f:
            f.write(data)
    else:
        print(data, end="")
