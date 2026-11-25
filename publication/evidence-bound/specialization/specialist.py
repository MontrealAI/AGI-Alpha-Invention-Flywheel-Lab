# SPDX-License-Identifier: Apache-2.0
"""Select historical geospatial records by exact revision and closed point bounds."""

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


def decimal(value):
    if type(value) not in (int, str, Decimal):
        raise ValueError("Coordinates and magnitude must be decimal numbers")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal number") from error
    if not result.is_finite():
        raise ValueError("Nonfinite decimal value")
    return result


def coordinate(value, bound):
    value = decimal(value)
    if not -bound <= value <= bound:
        raise ValueError("Coordinate lies outside its geographic range")
    return value


def timestamp(value):
    if type(value) is not int:
        raise ValueError("Timestamps must be integer milliseconds")
    return value


def in_longitude(longitude, west, east):
    def segment(value):
        if west <= east:
            return west <= value <= east
        return value >= west or value <= east
    return segment(longitude) or (longitude == -180 and segment(180))


def audit(case):
    bounds = case["bounds"]
    west, east = (coordinate(bounds[name], 180) for name in ("west", "east"))
    south, north = (coordinate(bounds[name], 90) for name in ("south", "north"))
    start, end = (timestamp(bounds[name]) for name in ("start_ms", "end_ms"))
    minimum = decimal(bounds["min_magnitude"])
    if south > north or start >= end:
        raise ValueError("Latitude and time bounds are reversed or empty")

    latest = {}
    for raw in case["records"]:
        key = raw["id"]
        if not isinstance(key, str) or not key.strip() or not key.isprintable():
            raise ValueError("Event ID must be nonblank printable text")
        update = timestamp(raw["updated_ms"])
        longitude = coordinate(raw["lon"], 180)
        latitude = coordinate(raw["lat"], 90)
        magnitude = None if raw["mag"] is None else decimal(raw["mag"])
        event_time = timestamp(raw["time_ms"])
        fields = (-180 if longitude == 180 else longitude, latitude, magnitude, event_time)
        version = latest.get(key)
        if version is None or version[0] < update:
            latest[key] = (update, fields, False)
        elif update == version[0] and version[1] != fields:
            latest[key] = (update, version[1], True)

    included = []
    conflicting = []
    for key in sorted(latest):
        _, (longitude, latitude, magnitude, event_time), conflict = latest[key]
        if conflict:
            conflicting.append(key)
        elif (start <= event_time < end and south <= latitude <= north and
              magnitude is not None and magnitude >= minimum and in_longitude(longitude, west, east)):
            included.append(key)
    return {"included": included, "conflicting": conflicting}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    try:
        result = audit(json.loads(args.case.read_bytes(), parse_float=Decimal))
    except (OSError, TypeError, KeyError, ValueError) as error:
        parser.exit(2, f"Invalid case ({type(error).__name__}): {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
