#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Author replayable hidden geospatial cases before receiving the candidate."""

import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from reference import calculate


def record(id_, lon, lat=0, mag=5, when=10, updated=99):
    return dict(id=id_, lon=lon, lat=lat, mag=mag, time_ms=when, updated_ms=updated)


def bounds(west, east, south=-10, north=10, minimum=4, start=0, end=20):
    return dict(west=west, east=east, south=south, north=north, min_magnitude=minimum, start_ms=start, end_ms=end)


def make(id_, family, limit, records):
    return dict(id=id_, family=family, input=dict(bounds=limit, records=records))


def authored():
    neighbors = [record("far-west", "-179.8"), record("far-east", "179.8"), record("zero-meridian", 0),
                 record("edge-positive", 180), record("edge-negative", -180), record("edge-west", 170),
                 record("edge-east", -170), record("too-late", 179, when=20), record("at-start", 179, when=0),
                 record("threshold", -179, mag=4), record("north-limit", 180, lat=10), record("south-limit", -180, lat=-10)]
    revision = [record("withdrawn-mag", 178, updated=12), record("withdrawn-mag", 178, mag=None, updated=13),
                record("withdrawn-lon", 179, updated=12), record("withdrawn-lon", 169, updated=13),
                record("withdrawn-time", 178, when=19, updated=12), record("withdrawn-time", 178, when=20, updated=13),
                record("latest-enters", 0, updated=12), record("latest-enters", -179, updated=13),
                record("outside-conflict", 25, mag=0), record("outside-conflict", 24, mag=0),
                record("conflict-time", 180, when=9), record("conflict-time", -180, when=10),
                record("conflict-lat", 180, lat="0.1"), record("conflict-lat", -180, lat="0.10000000000000001"),
                record("same-physical-id", 180), record("same-physical-id", "-1.80e2", lat="-0.00", mag="5.00"),
                record("old-conflict-resolved", -180, mag=6, updated=15), record("old-conflict-resolved", -180, mag=7, updated=15),
                record("old-conflict-resolved", -180, mag=8, updated=16)]
    precision = [record("left-just-inside", "179.950000000000000000001"), record("left-just-outside", "179.949999999999999999999"),
                 record("right-just-inside", "-179.950000000000000000001"), record("right-just-outside", "-179.949999999999999999999"),
                 record("smallest-magnitude-in", 180, mag="4.000000000000000000001"),
                 record("near-magnitude-out", 180, mag="3.999999999999999999999"),
                 record("exact-magnitude", 180, mag="4.000000000000000000000"),
                 record("latitude-near-out", 180, lat="10.000000000000000000001"),
                 record("latitude-near-in", 180, lat="9.999999999999999999999")]
    return [make("seam-box", "boundary", bounds(170, -170), neighbors),
            make("right-connected", "boundary", bounds(170, 180), neighbors),
            make("left-connected", "boundary", bounds(-180, -170), neighbors),
            make("degenerate-positive", "boundary", bounds(180, 180), neighbors),
            make("degenerate-wrap", "boundary", bounds(180, -180), neighbors),
            make("full-circumference", "boundary", bounds(-180, 180), neighbors),
            make("revision-quarantine", "revision", bounds(170, -170), revision),
            make("exact-decimal", "precision", bounds("179.95", "-179.95"), precision)]


def random_cases(seed):
    random = Random(seed)
    cases = []
    for index in range(24):
        # Every fourth case is a paired updatable observation panel.
        left, right = ((150 + random.randrange(29), -150 - random.randrange(29)) if index % 4 < 3
                       else sorted(random.sample(range(-130, 131), 2)))
        start = random.randrange(-10, 0)
        end = start + random.randrange(3, 25)
        limit = bounds(left, right, -8, 23, random.randrange(-2, 6), start, end)
        observations = []
        size = 0 if index in (8, 19) else random.randrange(5, 13)
        for j in range(size):
            name = f"hold-{index:02}-{random.getrandbits(24):06x}"
            revision = random.getrandbits(40)
            point = random.choice((left, right, 180, -180, 0, random.randrange(-180, 181), left - 1, right + 1))
            mag = random.choice((None, limit["min_magnitude"], random.randrange(-3, 8)))
            row = record(name, point, random.choice((-8, 23, random.randrange(-28, 31))), mag,
                         random.choice((start, end, random.randrange(start - 4, end + 5))), revision)
            observations.append(row)
            if j % 3 == 0:
                observations.append({**row, "updated_ms": revision - 1, "mag": 9})
            if j % 4 == 1:
                observations.append({**row, "mag": 8 if mag != 8 else 7})
            if j % 5 == 2:
                observations.append({**row, "updated_ms": revision + 1, "time_ms": start})
        random.shuffle(observations)
        cases.append(make(f"seeded-{index:02}", "seeded", limit, observations))
    return cases


def invariants(seam, right, left):
    original = seam["input"]
    rows, limit = original["records"], original["bounds"]
    reverse = make("permuted-seam", "invariance", limit, rows[::-1])
    flipped = make("equivalent-representation", "invariance", limit, [
        {**row, "lon": -row["lon"]} if row["lon"] in (-180, 180) else row for row in rows])
    dominated = make("dominated-old-data", "invariance", limit, rows + [
        {**row, "updated_ms": row["updated_ms"] - 1, "mag": None} for row in rows])
    renamed = make("shifted-latitude", "invariance", {**limit, "south": limit["south"] + 3, "north": limit["north"] + 3},
                   [{**row, "lat": row["lat"] + 3} for row in rows])
    expected = calculate(original)
    assert all(calculate(twin["input"]) == expected for twin in (reverse, flipped, dominated, renamed))
    split = [calculate(case["input"]) for case in (right, left)]
    assert sorted(set(split[0]["included"]) | set(split[1]["included"])) == expected["included"]
    return [reverse, flipped, dominated, renamed]


def observations(source):
    collection = json.loads(source, parse_float=str)
    rows = [record(feature["id"], *feature["geometry"]["coordinates"][:2],
                   feature["properties"]["mag"], feature["properties"]["time"], feature["properties"]["updated"])
            for feature in collection["features"]]
    start = int(datetime(2014, 6, 20, tzinfo=UTC).timestamp() * 1000)
    end = int(datetime(2014, 6, 26, tzinfo=UTC).timestamp() * 1000)
    return [make("aleutians-complete", "USGS", bounds(165, -165, 48, 57, "5.5", start, end), rows),
            make("aleutians-western-lobe", "USGS", bounds(-180, -165, 48, 57, "5.5", start, end), rows),
            make("aleutians-higher-threshold", "USGS", bounds(165, -165, 48, 57, "6.0", start, end), rows),
            make("aleutians-exact-cutoff", "USGS", bounds(165, -165, 48, 57, "5.5", start, rows[0]["time_ms"]), rows)]


def write(root, seed, source_file):
    source = source_file.read_bytes()
    anchors = authored()
    panels = anchors + random_cases(seed) + invariants(*anchors[:3]) + observations(source)
    assert len({panel["id"] for panel in panels}) == len(panels) == 40
    oracle = {panel["id"]: calculate(panel["input"]) for panel in panels}
    assert len(oracle["aleutians-complete"]["included"]) == 8 and "usc000rki5" in oracle["aleutians-higher-threshold"]["included"]
    (root / "CASES.jsonl").write_text("".join(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n" for case in panels))
    (root / "ORACLE.json").write_text(json.dumps(oracle, sort_keys=True, indent=2) + "\n")
    (root / "SEED.json").write_text(json.dumps({"seed": seed, "source_sha256": sha256(source).hexdigest()}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write(args.output, args.seed, args.source)
