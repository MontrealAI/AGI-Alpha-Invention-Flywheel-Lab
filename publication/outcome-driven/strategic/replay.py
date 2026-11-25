"""Apply reviewed independent strategic interpretations to authorized input records."""

import argparse
import json
from pathlib import Path

from formalize import FIELDS, compile_reviewed, read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("cases", "proposals", "approved"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    cases = read_jsonl(args.cases)
    proposals = read_jsonl(args.proposals)
    approved = read_jsonl(args.approved)
    by_id = {row["id"]: row for row in approved}
    opinions = {row["id"]: row for row in proposals}
    if not cases or len(cases) != len(proposals) or len(cases) != len(approved) or set(by_id) != set(opinions):
        raise ValueError("The same complete case roster needs both proposal and independent approval")
    if len(by_id) != len(cases) or {case["id"] for case in cases} != set(by_id):
        raise ValueError("The approved case records differ")
    for case in cases:
        identity = case["id"]
        verified = {}
        for field in FIELDS:
            if field not in opinions[identity] or field not in by_id[identity]:
                raise ValueError("Both interpretations need all semantic fields")
            verified[field] = by_id[identity][field]
        proposal = {field: opinions[identity][field] for field in FIELDS}
        result = compile_reviewed(case, proposal, verified)
        print(json.dumps({"id": identity, "outcome": result}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
