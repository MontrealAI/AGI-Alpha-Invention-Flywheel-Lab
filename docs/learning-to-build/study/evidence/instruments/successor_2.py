#!/usr/bin/env python3
# Generated from an authored finite measurement specification.
import json
import sys
SPEC_HASH = '6a5894d62352d70062b92e6b2174ebc83db317ab2fb1437fc035152a428a2396'
FIELDS = ['m0', 'm1', 'm2', 'm3']

def measure(row):
    if set(row) != set(FIELDS) or any(type(row[k]) is not int for k in FIELDS):
        raise ValueError("exact integer schema required")
    value = (3 * row['m0']) + (2 * row['m1']) + (-2 * row['m2']) + (3 * row['m3']) + 6
    return {"weighted_measurement": value, "accepted": value >= 10, "spec_sha256": SPEC_HASH}

if __name__ == "__main__":
    for line in sys.stdin:
        print(json.dumps(measure(json.loads(line)), sort_keys=True))
