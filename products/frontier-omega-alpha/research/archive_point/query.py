#!/usr/bin/env python3
"""Read a historical NOAA grid point within the registered payload budget."""
from argparse import ArgumentParser
from datetime import date

from point import forecast_at
from replay import REGISTRATION, direct_decode, encode, fetch_index, read, require


def query(spec):
    configuration = read(REGISTRATION)
    contract = configuration["test_contract"]
    budget = contract["decoded_case_payload_budget_bytes"]
    base, offset, total, index = fetch_index(configuration["origin"], spec)
    if offset is None:
        return {"state": "ABSTAIN", "reason": "FIELD_INDEX_UNAVAILABLE", "index_source": index}
    limit = min(contract["candidate_max_prefix_bytes"], budget - index["body_bytes"])
    require(limit >= 1024, "INDEX_EXHAUSTED_QUERY_BUDGET")
    result = direct_decode(base, offset, total, limit, spec, lambda payload, case: forecast_at(payload, total, case))
    consumed = index["body_bytes"] + result["source"]["body_bytes"]
    require(consumed <= budget, "DIRECT_QUERY_BUDGET_EXCEEDED")
    return {"state": result["disposition"] if result["disposition"] == "AVAILABLE" else "ABSTAIN",
            "case": spec, "body_bytes": consumed, "budget_bytes": budget, "index_source": index, "field": result}


def main():
    args = ArgumentParser(description=__doc__)
    args.add_argument("--day", type=date.fromisoformat, required=True)
    args.add_argument("--cycle", choices=("00", "06", "12", "18"), required=True)
    args.add_argument("--latitude", type=float, required=True)
    args.add_argument("--longitude", type=float, required=True)
    parsed = args.parse_args()
    spec = {"day": parsed.day.strftime("%Y%m%d"), "cycle": parsed.cycle, "latitude": parsed.latitude,
            "longitude": parsed.longitude}
    try:
        status = query(spec)
    except (OSError, TypeError, ValueError) as error:
        status = {"state": "ABSTAIN", "reason": str(error) if str(error).isupper() else type(error).__name__}
    print(encode(status).decode(), end="")
    return 0 if status["state"] == "AVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
