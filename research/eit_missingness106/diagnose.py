"""EIT106: independent *diagnostic*, never a masked-voltage acceptance validator.

Public physical source: Zenodo 7192883 v1.  The exact rejected source identity
is pinned; all measurements remain third-party, with no imputation.
"""
import csv
from collections import Counter
from hashlib import md5, sha256
import io
import json
import math
import time
from urllib.request import Request, urlopen

SOURCE_URL = "https://zenodo.org/records/7192883/files/circle_petg.csv?download=1"
SOURCE_MD5 = "262a968766cd034914155ac2bfcd121e"
MAX_BYTES = 15_000_000
MAX_ROWS = 250_000
ELECTRODES = tuple(f"E_{i:02d}" for i in range(1, 17))
REQUIRED = ("value_desc", "ex_mat_0", "ex_mat_1") + ELECTRODES
CATEGORIES = ("finite", "literal_na", "empty", "whitespace_only", "padded_na",
              "padded_finite", "nonfinite", "other_text")
STRICTLY_UNEXPECTED = set(CATEGORIES) - {"finite", "literal_na"}


def verify_source(data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("SOURCE_SIZE_OUTSIDE_REGISTERED_LIMIT")
    if md5(data).hexdigest() != SOURCE_MD5:
        raise ValueError("SOURCE_BYTES_CHANGED")
    return {"official_md5": SOURCE_MD5, "sha256": sha256(data).hexdigest(),
            "bytes": len(data), "url": SOURCE_URL}


def classify(value):
    if not isinstance(value, str):
        raise ValueError("RAGGED_SOURCE_ROW")
    if value == "NA":
        return "literal_na"
    if value == "":
        return "empty"
    trimmed = value.strip()
    if not trimmed:
        return "whitespace_only"
    if trimmed == "NA":
        return "padded_na"
    try:
        parsed = float(value)
    except ValueError:
        return "other_text"
    if not math.isfinite(parsed):
        return "nonfinite"
    return "finite" if value == trimmed else "padded_finite"


def diagnostic(data):
    """Count source representations, never fill or reclassify missing data."""
    body = data.decode("utf-8-sig")
    first = body.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    cols = tuple(reader.fieldnames or ())
    if not cols or len(cols) != len(set(cols)):
        raise ValueError("DUPLICATE_OR_MISSING_CSV_HEADER")
    if set(REQUIRED) - set(cols):
        raise ValueError("SOURCE_REQUIRED_COLUMNS_ABSENT")
    total, measurements, affected, any_na, min_finite, max_finite = 0, 0, 0, 0, 16, 0
    by_category, on_injection, off_injection = Counter(), Counter(), Counter()
    by_channel = {k: Counter() for k in ELECTRODES}
    distinct_pairs = set()
    for row in reader:
        total += 1
        if total > MAX_ROWS:
            raise ValueError("SOURCE_ROW_LIMIT")
        if None in row or any(v is None for v in row.values()):
            raise ValueError("RAGGED_SOURCE_ROW")
        if row["value_desc"] != "measurement":
            continue
        measurements += 1
        try:
            a, b = int(row["ex_mat_0"]), int(row["ex_mat_1"])
        except (ValueError, TypeError) as e:
            raise ValueError("INVALID_EXCITATION_INDEX") from e
        if a == b or not (0 <= a < 16 and 0 <= b < 16):
            raise ValueError("INVALID_EXCITATION_PAIR")
        distinct_pairs.add((a, b))
        n_finite, n_unexpected, n_na = 0, 0, 0
        for i, column in enumerate(ELECTRODES):
            category = classify(row[column])
            by_category[category] += 1
            by_channel[column][category] += 1
            (on_injection if i in (a, b) else off_injection)[category] += 1
            n_finite += category == "finite"
            n_unexpected += category in STRICTLY_UNEXPECTED
            n_na += category == "literal_na"
        affected += n_unexpected > 0
        any_na += n_na > 0
        min_finite = min(min_finite, n_finite)
        max_finite = max(max_finite, n_finite)
    if measurements == 0:
        raise ValueError("NO_MEASURED_ROWS")
    if sum(by_category.values()) != 16 * measurements:
        raise AssertionError("INTERNAL_COUNT_MISMATCH")
    return {
        "csv_rows": total, "measurement_rows": measurements,
        "injection_pair_count": len(distinct_pairs),
        "voltage_cells_observed": 16 * measurements,
        "original_EIT105_strict_contract": "FAILED_HISTORICAL",
        "original_EIT105_masked_contract": "FAILED_HISTORICAL",
        "invalid_or_unrepresented_rows": affected, "rows_with_literal_NA": any_na,
        "finite_per_row_min": min_finite, "finite_per_row_max": max_finite,
        "category_counts": {k: by_category[k] for k in CATEGORIES},
        "on_injection_category_counts": {k: on_injection[k] for k in CATEGORIES},
        "off_injection_category_counts": {k: off_injection[k] for k in CATEGORIES},
        "channel_category_counts": {
            k: {cat: by_channel[k][cat] for cat in CATEGORIES} for k in ELECTRODES
        },
        "unknown_tokens_accepted_as_voltage": False,
        "all_missing_values_left_unimputed": True,
        "new_accepted_physical_outcomes": 0,
    }


def run():
    start_cpu, start = time.process_time(), time.monotonic()
    request = Request(SOURCE_URL, headers={"User-Agent": "AGI-ALPHA-EIT106-research-diagnostic/1"})
    with urlopen(request, timeout=90) as response:
        data = response.read(MAX_BYTES + 1)
    verified = verify_source(data)
    counts = diagnostic(data)
    return {
        "schema": "eit106/source-token-inventory/v1",
        "source": verified,
        "inventory": counts,
        "historical_failures_retained": [42551099436, 42551635036],
        "research_verdict": "DIAGNOSTIC_ONLY_NO_BID_NO_DEPLOY",
        "new_physical_acquisitions": 0,
        "actual_collections_usd": 0,
        "native_accounts_operated": 0,
        "complete_cost_profit_usd": None,
        "actual_platform_billing_usd": None,
        "cpu_seconds_process": round(time.process_time() - start_cpu, 6),
        "wall_seconds": round(time.monotonic() - start, 6),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
