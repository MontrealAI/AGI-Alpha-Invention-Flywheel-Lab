#!/usr/bin/env python3
# Generated from an authored finite measurement specification.
import json
import sys
SPEC_HASH = '130687c6e35546b1f0b9da23b53c8adf8860a367b653f56a931194556a5cda80'
FIELDS = ['a', 'b', 'c']

def measure(row):
    if set(row) != set(FIELDS) or any(type(row[k]) is not int for k in FIELDS):
        raise ValueError("exact integer schema required")
    value = (2 * row['a']) + (2 * row['b']) + (1 * row['c']) + 1
    return {"weighted_measurement": value, "accepted": value >= 2, "spec_sha256": SPEC_HASH}

if __name__ == "__main__":
    for line in sys.stdin:
        print(json.dumps(measure(json.loads(line)), sort_keys=True))
