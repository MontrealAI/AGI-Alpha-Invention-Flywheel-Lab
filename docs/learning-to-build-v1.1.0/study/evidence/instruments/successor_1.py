#!/usr/bin/env python3
# Generated from an authored finite measurement specification.
import json
import sys
SPEC_HASH = '505f0c24781e510faa087e47c21e7d3f7552e7ee33de060cdda5d0d8b40fd8e3'
FIELDS = ['q', 'p', 'r']

def measure(row):
    if set(row) != set(FIELDS) or any(type(row[k]) is not int for k in FIELDS):
        raise ValueError("exact integer schema required")
    value = (2 * row['q']) + (-1 * row['p']) + (6 * row['r']) + 1
    return {"weighted_measurement": value, "accepted": value >= 7, "spec_sha256": SPEC_HASH}

if __name__ == "__main__":
    for line in sys.stdin:
        print(json.dumps(measure(json.loads(line)), sort_keys=True))
