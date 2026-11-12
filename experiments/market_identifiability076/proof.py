"""A source-model impossibility witness, NOT a real billing or clinical audit."""
import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

AMOUNT_FIELDS = ("submitted", "allowed", "medicare_paid", "standardized")
OUTPUT_FIELDS = ("Avg_Sbmtd_Chrg", "Avg_Mdcr_Alowd_Amt", "Avg_Mdcr_Pymt_Amt", "Avg_Mdcr_Stdzd_Amt")
MICRO_FIELDS = ("claim_id", "beneficiary_id", "service_date", "rendering_npi", "hcpcs", "place", "services") + AMOUNT_FIELDS


def frozen_worlds():
    common = {"beneficiary_id": "SYNTHETIC_B1", "rendering_npi": "SYNTHETIC_NPI",
              "hcpcs": "SYNTHETIC_CODE", "place": "O", "services": 1,
              "submitted": "100.00", "allowed": "80.00",
              "medicare_paid": "64.00", "standardized": "64.00"}
    first = dict(common, claim_id="SYNTHETIC_C1", service_date="2024-02-03")
    second = dict(common, claim_id="SYNTHETIC_C2", service_date="2024-05-09")
    duplicated = dict(second, claim_id="SYNTHETIC_C1")
    return [first, second], [first, duplicated]


def validate(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("NONEMPTY_MICRO_WORLD_REQUIRED")
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(MICRO_FIELDS):
            raise ValueError("COMPLETE_TYPED_SOURCE_FIELDS_REQUIRED")
        for key in ("claim_id", "beneficiary_id", "service_date", "rendering_npi", "hcpcs", "place"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError("INVALID_IDENTIFIER_OR_DATE")
        if type(row["services"]) is not int or row["services"] <= 0:
            raise ValueError("INVALID_SERVICE_COUNT")
        for key in AMOUNT_FIELDS:
            try:
                amount = Decimal(row[key])
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("INVALID_MONETARY_CELL") from None
            if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
                raise ValueError("INVALID_MONETARY_CELL")


def aggregate(rows):
    """A projection onto specifically named CMS aggregate-field semantics."""
    validate(rows)
    groups = {}
    for row in rows:
        key = (row["rendering_npi"], row["hcpcs"], row["place"])
        groups.setdefault(key, []).append(row)
    output = []
    for (npi, code, place), group in sorted(groups.items()):
        services = sum(r["services"] for r in group)
        if services <= 0:
            raise ValueError("ZERO_SERVICES")
        record = {
            "Rndrng_NPI": npi, "HCPCS_Cd": code, "Place_Of_Srvc": place,
            "Tot_Benes": len({r["beneficiary_id"] for r in group}),
            "Tot_Srvcs": services,
            "Tot_Bene_Day_Srvcs": len({(r["beneficiary_id"], r["service_date"]) for r in group})
        }
        for field, output_field in zip(AMOUNT_FIELDS, OUTPUT_FIELDS):
            total = sum((Decimal(r[field]) * r["services"] for r in group), Decimal("0"))
            record[output_field] = str((total / services).quantize(Decimal("0.01")))
        output.append(record)
    return output


def private_duplicate_claim_ids(rows):
    validate(rows)
    counts = Counter(r["claim_id"] for r in rows)
    return any(n > 1 for n in counts.values())


def witness():
    clean, duplicate = frozen_worlds()
    p0, p1 = aggregate(clean), aggregate(duplicate)
    t0, t1 = private_duplicate_claim_ids(clean), private_duplicate_claim_ids(duplicate)
    if p0 != p1 or t0 == t1 or t0 or not t1:
        raise AssertionError("FROZEN_IDENTIFIABILITY_WITNESS_FAILED")
    published_projection = json.dumps(p0, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": "agi-alpha/market-identifiability076/result-v1",
        "world_count": 2, "synthetic_only": True,
        "public_projection_sha256": hashlib.sha256(published_projection).hexdigest(),
        "public_projection": p0,
        "both_worlds_same_public_input": p0 == p1,
        "private_correctness_labels": {"distinct_claim_ids": not t0, "repeated_claim_id": t1},
        "public_only_identifiability": False,
        "proof": "Any deterministic public-only decision receives the same projection in both worlds yet the correct private duplicate-ID labels differ.",
        "strong_ordinary_private_data_comparator": "EXACT_IDENTIFIER_GROUP_BY_DETECTS_DIFFERENCE_IF_AUTHORIZED_DATA_EXIST",
        "decision": "NO_DEPLOY",
        "reason": "Public aggregates lack claim identifiers; live VA RFI is nonbinding and confers neither claim-data rights nor commercial acceptance.",
        "native_account_run": False, "collected_revenue_usd": 0,
        "native_trailing_365_profit_usd": None, "target_3000000000_achieved": False
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise SystemExit("NEW_OUTPUT_PATH_REQUIRED")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = witness()
    result["preregistration_sha256"] = hashlib.sha256(
        (Path(__file__).parent / "PREREGISTRATION.json").read_bytes()).hexdigest()
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "public_only_identifiability": False,
                      "result": str(out), "source": result["preregistration_sha256"]}))


if __name__ == "__main__":
    main()
