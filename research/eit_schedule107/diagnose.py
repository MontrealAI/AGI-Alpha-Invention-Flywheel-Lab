"""EIT107 — source-bound ternary electrode schedule, NOT a validated sensor.

Immutable H1 protocol is in PROTOCOL.md at freeze commit
929f0b0fb1fb70a9298d520bfa668536b4133b27.
"""
from collections import Counter, defaultdict
import csv
from hashlib import md5, sha256
import io
import json
import math
import time
from urllib.request import Request, urlopen

SOURCE_URL = "https://zenodo.org/records/7192883/files/circle_petg.csv?download=1"
SOURCE_MD5 = "262a968766cd034914155ac2bfcd121e"
SOURCE_SHA256 = "2e6b357e41b8b69bca8e23ce7a8b924677bae80ecab34da8830a4edada4ab62f"
SOURCE_BYTES = 9232257
MAX_BYTES = 15000000
MAX_ROWS = 250000
CHANNELS = tuple(f"E_{i:02d}" for i in range(1, 17))
FIELDS = ("value_desc", "object", "material", "r", "phi", "meas_num", "ex_mat_0", "ex_mat_1") + CHANNELS


def verify_source(blob):
    if not blob or len(blob) > MAX_BYTES or len(blob) != SOURCE_BYTES:
        raise ValueError("SOURCE_SIZE_CHANGED")
    if md5(blob).hexdigest() != SOURCE_MD5:
        raise ValueError("SOURCE_MD5_CHANGED")
    if sha256(blob).hexdigest() != SOURCE_SHA256:
        raise ValueError("SOURCE_SHA256_CHANGED")
    return {"url": SOURCE_URL, "md5": SOURCE_MD5, "sha256": SOURCE_SHA256, "bytes": len(blob)}


def classify_token(token):
    """Distinct finite F, explicit NA N, blank E; no coercion/imputation."""
    if not isinstance(token, str):
        raise ValueError("RAGGED_MEASUREMENT_ROW")
    if token == "NA":
        return "N"
    if token == "":
        return "E"
    if token != token.strip():
        raise ValueError("PADDED_OR_WHITESPACE_TOKEN")
    try:
        number = float(token)
    except ValueError as exc:
        raise ValueError("UNKNOWN_MEASUREMENT_TOKEN") from exc
    if not math.isfinite(number):
        raise ValueError("NONFINITE_MEASUREMENT")
    return "F"


def parse_pair(row):
    try:
        a, b = int(row["ex_mat_0"]), int(row["ex_mat_1"])
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_INJECTION_INDEX") from exc
    if a == b or not (0 <= a < 16 and 0 <= b < 16):
        raise ValueError("INVALID_INJECTION_PAIR")
    return a, b


def scan_csv(blob):
    body = blob.decode("utf-8-sig")
    first_line = body.split("\n", 1)[0]
    sep = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=sep)
    names = tuple(reader.fieldnames or ())
    if not names or len(set(names)) != len(names) or not set(FIELDS).issubset(names):
        raise ValueError("INVALID_OR_INCOMPLETE_CSV_HEADER")
    pairs = Counter()
    masks = defaultdict(Counter)
    masks_by_object = defaultdict(lambda: defaultdict(Counter))
    mask_hist = Counter()
    objects = Counter()
    groups = set()
    total = count = injection_numeric = unequal_finite = 0
    finite_hist = Counter()
    missing_on = Counter()
    missing_off = Counter()
    token_hist = Counter()
    for row in reader:
        total += 1
        if total > MAX_ROWS:
            raise ValueError("REGISTERED_ROW_LIMIT")
        if None in row or any(x is None for x in row.values()):
            raise ValueError("RAGGED_SOURCE_ROW")
        if row["value_desc"] != "measurement":
            continue
        count += 1
        a, b = parse_pair(row)
        mask = "".join(classify_token(row[k]) for k in CHANNELS)
        pair_name = f"{a:02d}-{b:02d}"
        pairs[pair_name] += 1
        masks[pair_name][mask] += 1
        obj = row["object"]
        masks_by_object[pair_name][obj][mask] += 1
        objects[obj] += 1
        groups.add((obj, row["material"], row["r"], row["phi"], row["meas_num"]))
        mask_hist[mask] += 1
        n_finite = mask.count("F")
        finite_hist[n_finite] += 1
        unequal_finite += n_finite != 12
        for i, category in enumerate(mask):
            token_hist[category] += 1
            if i in (a, b):
                missing_on[category] += 1
                injection_numeric += category == "F"
            else:
                missing_off[category] += 1
    if count < 1:
        raise ValueError("NO_MEASUREMENT_ROWS")
    pair_mask_count = {pair: len(counts) for pair, counts in sorted(masks.items())}
    deterministic = all(n == 1 for n in pair_mask_count.values())
    object_divergence = sum(
        len(set.union(*(set(ms) for ms in by_object.values()))) > 1
        for by_object in masks_by_object.values()
    )
    hypothesis = deterministic and injection_numeric == 0 and unequal_finite == 0
    if sum(token_hist.values()) != 16 * count:
        raise AssertionError("BROKEN_MEASUREMENT_RECONCILIATION")
    return {
        "csv_rows": total,
        "measurement_rows_not_independent_specimens": count,
        "distinct_specimen_group_keys_not_independence_proof": len(groups),
        "distinct_object_labels": len(objects),
        "object_row_counts": dict(sorted(objects.items())),
        "distinct_injection_pairs_not_acquisition_reduction": len(pairs),
        "per_pair_row_counts": dict(sorted(pairs.items())),
        "per_pair_ternary_mask_count": pair_mask_count,
        "per_pair_ternary_masks": {
            pair: [{"mask": m, "rows": qty} for m, qty in sorted(counter.items())]
            for pair, counter in sorted(masks.items())
        },
        "total_distinct_ternary_masks": len(mask_hist),
        "pairs_with_object_label_mask_divergence": object_divergence,
        "actual_finite_channel_histogram": dict(sorted(finite_hist.items())),
        "token_totals_F_N_E": dict(sorted(token_hist.items())),
        "on_injection_token_totals": dict(sorted(missing_on.items())),
        "off_injection_token_totals": dict(sorted(missing_off.items())),
        "rows_not_exactly_12_finite": unequal_finite,
        "numeric_on_injection_cells": injection_numeric,
        "H1_pair_only_mask_schedule": "RETAIN_DATA_REPRESENTATION_ONLY" if hypothesis else "REJECT_PAIR_ONLY_PROJECTION",
        "H1_supported_on_exact_exposed_file_only": hypothesis,
        "all_missing_left_unimputed": True,
        "blank_E_kept_distinct_from_NA": True,
        "physical_acquisition_semantics_qualified": False,
        "new_independent_physical_specimens": 0,
        "customer_acceptances": 0,
        "commercial_collections_usd": 0,
        "native_accounts_operated": 0
    }


def run():
    t0, c0 = time.perf_counter(), time.process_time()
    request = Request(SOURCE_URL, headers={"User-Agent": "AGI-ALPHA-EIT107-public-source/1"})
    with urlopen(request, timeout=90) as response:
        blob = response.read(MAX_BYTES + 1)
    identity = verify_source(blob)
    counts = scan_csv(blob)
    return {
        "schema": "eit107/frozen-source-ternary-schedule/v1",
        "protocol_freeze_commit": "929f0b0fb1fb70a9298d520bfa668536b4133b27",
        "source": identity, "diagnostic": counts,
        "historical_eit105_strict": "FAILED_RETAINED_42551099436",
        "historical_eit105_masked": "FAILED_RETAINED_42551635036",
        "physical_end_use": "UNQUALIFIED", "commercial_profit": None,
        "actual_platform_billing_usd": None,
        "decision": "HOLD_NO_BID_NO_DEPLOY",
        "process_cpu_seconds": round(time.process_time() - c0, 6),
        "wall_seconds": round(time.perf_counter() - t0, 6)
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
