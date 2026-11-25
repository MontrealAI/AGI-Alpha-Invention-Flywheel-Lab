#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent exact rational oracle for a bounded catalog decision."""

import argparse
from fractions import Fraction
from itertools import groupby
import json
from pathlib import Path


def calculate(case):
    bounds = case["bounds"]
    west, east, south, north, minimum = (Fraction(str(bounds[key])) for key in (
        "west", "east", "south", "north", "min_magnitude"))
    # Lift the requested arc onto a line, then test a point's equivalent lifts.
    top = east if east >= west else east + 360
    grouped = groupby(sorted(case["records"], key=lambda row: row["id"]), key=lambda row: row["id"])
    result = {"included": [], "conflicting": []}
    for name, group in grouped:
        versions = sorted(group, key=lambda row: row["updated_ms"], reverse=True)
        latest = versions[0]["updated_ms"]
        variants = set()
        for record in versions:
            if record["updated_ms"] != latest:
                break
            point = Fraction(str(record["lon"]))
            if point == 180:
                point = Fraction(-180)
            magnitude = None if record["mag"] is None else Fraction(str(record["mag"]))
            variants.add((point, Fraction(str(record["lat"])), magnitude, record["time_ms"]))
        if len(variants) > 1:
            result["conflicting"].append(name)
            continue
        (point, latitude, magnitude, when), = variants
        if (magnitude is not None and magnitude >= minimum
                and south <= latitude <= north and bounds["start_ms"] <= when < bounds["end_ms"]
                and any(west <= point + shift <= top for shift in (0, 360))):
            result["included"].append(name)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    print(json.dumps(calculate(json.loads(args.case.read_text(), parse_float=str)), sort_keys=True))
