#!/usr/bin/env python3
# Generated from an authored finite measurement specification.
import json
import sys
SPEC_HASH = 'dc9266889697342409a6ef878b757c15fad6cbbb2bdce793c878f876248fa4af'
FIELDS = ['z4', 'z0', 'z2', 'z1', 'z3']

def measure(row):
    if set(row) != set(FIELDS) or any(type(row[k]) is not int for k in FIELDS):
        raise ValueError("exact integer schema required")
    value = (2 * row['z4']) + (2 * row['z0']) + (-2 * row['z2']) + (3 * row['z1']) + (2 * row['z3']) + 7
    return {"weighted_measurement": value, "accepted": value >= 6, "spec_sha256": SPEC_HASH}

if __name__ == "__main__":
    for line in sys.stdin:
        print(json.dumps(measure(json.loads(line)), sort_keys=True))
