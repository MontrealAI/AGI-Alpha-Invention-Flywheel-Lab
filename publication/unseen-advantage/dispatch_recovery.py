"""Check whether the two published MATLAB matrix representations identify a full input."""

from argparse import ArgumentParser
import json
import math
from pathlib import Path
import struct
import zlib

from dispatch_inputs import KM_PER_CAR_MINUTE, PLANTS, PINS, TRUCK_MULTIPLIER
from dispatch_inputs import check_bytes, normalized

MATRIX_NAMES = (b"prod2constr_matrix", b"DistanceMatrix")
MAX_INFLATED_BYTES = 1_048_576
NUMERIC_STORAGE = {1: "b", 2: "B", 3: "h", 4: "H", 5: "i", 6: "I", 7: "f", 9: "d"}


def element(data, offset):
    """Read the small or regular little-endian MAT v5 data element."""
    if offset + 8 > len(data):
        raise ValueError("truncated MAT tag")
    tag, size = struct.unpack_from("<II", data, offset)
    if tag >> 16:
        size = tag >> 16
        if size > 4:
            raise ValueError("invalid MAT small element")
        return tag & 65535, data[offset + 4:offset + 4 + size], offset + 8
    start = offset + 8
    end = start + size
    next_offset = end if tag == 15 else (end + 7) & ~7
    if next_offset > len(data):
        raise ValueError("truncated MAT payload")
    return tag, data[start:end], next_offset


def source_matrices(raw):
    """Read just the two real double arrays, without loading MATLAB objects."""
    if raw[126:128] != b"IM":
        raise ValueError("expected a little-endian MAT v5 source")
    arrays = {}
    cursor = 128
    while cursor < len(raw):
        tag, payload, cursor = element(raw, cursor)
        if tag == 15:
            inflater = zlib.decompressobj()
            expanded = inflater.decompress(payload, MAX_INFLATED_BYTES)
            if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError("oversized or invalid MAT compression")
            tag, payload, _ = element(expanded, 0)
        if tag != 14:
            continue
        _, flags, offset = element(payload, 0)
        if len(flags) != 8 or flags[0] != 6:
            continue
        _, dimensions, offset = element(payload, offset)
        _, name, offset = element(payload, offset)
        if name not in MATRIX_NAMES:
            continue
        kind, values, offset = element(payload, offset)
        if name in arrays or len(dimensions) != 8 or kind not in NUMERIC_STORAGE or offset != len(payload):
            raise ValueError("ambiguous or unsupported numeric array")
        rows, cols = struct.unpack("<ii", dimensions)
        value_format = NUMERIC_STORAGE[kind]
        if min(rows, cols) < 1 or len(values) != struct.calcsize(value_format) * rows * cols:
            raise ValueError("invalid MAT matrix dimensions")
        flat = struct.unpack(f"<{rows * cols}{value_format}", values)
        arrays[name] = [list(flat[i::rows]) for i in range(rows)]
    if set(arrays) != set(MATRIX_NAMES):
        raise ValueError("registered source matrices are absent")
    return tuple(arrays[name] for name in MATRIX_NAMES)


def finite_time(distance):
    """Return a unique nonnegative float preimage of the published conversion."""
    estimate = distance / KM_PER_CAR_MINUTE
    if not math.isfinite(estimate) or estimate < 0:
        return None
    neighbors = (math.nextafter(estimate, -math.inf), estimate,
                 math.nextafter(estimate, math.inf))
    matches = [value for value in neighbors
               if value >= 0 and value * KM_PER_CAR_MINUTE == distance]
    if len(matches) != 1:
        return None
    (value,) = matches
    if any(neighbor >= 0 and neighbor * KM_PER_CAR_MINUTE == distance
           for neighbor in (math.nextafter(value, -math.inf), math.nextafter(value, math.inf))):
        return None
    return value


def analyze(case, raw, inventory):
    check_bytes(case, raw)
    return reconcile(case, source_matrices(raw), inventory)


def reconcile(case, matrices, inventory):
    travel, distance = matrices
    order_ids = [row["id"] for row in inventory["orders"]]
    rows = len(travel)
    result = {"case": case, "source_sha256": PINS[case][2],
              "orders": len(order_ids), "travel_rows": rows,
              "travel_columns": len(travel[0]), "distance_shape": [len(distance), len(distance[0])],
              "recovered_cells": 0, "verdict": "ABSTAIN"}
    if len(set(order_ids)) != len(order_ids) or len(travel[0]) != PLANTS or (
            len(distance) != rows + PLANTS or len(distance[0]) != rows + PLANTS):
        return dict(result, reason="unsupported_structure")

    overlap = []
    gaps = []
    recovered = {}
    for i, row in enumerate(travel):
        for j, value in enumerate(row):
            forward = distance[j][PLANTS + i]
            reverse = distance[PLANTS + i][j]
            if math.isnan(value) and math.isnan(forward) and math.isnan(reverse):
                gaps.append([i, j])
            elif math.isfinite(value) and value >= 0 and (
                    forward == reverse == value * KM_PER_CAR_MINUTE):
                overlap.append([i, j])
            elif math.isnan(value) and forward == reverse and math.isfinite(forward):
                unique = finite_time(forward)
                if unique is None:
                    gaps.append([i, j])
                else:
                    recovered[i, j] = unique
            else:
                return dict(result, reason="contradictory_representation", cell=[i, j])

    result.update(overlap_cells=len(overlap), unidentifiable_cells=gaps)
    if rows != len(order_ids) or not inventory["travel_row_mapping_verified"]:
        if rows == len(order_ids) - 1 and not gaps and not recovered:
            return dict(result, reason="row_identity_not_established", counterexamples=[
                {"omitted_order": order_ids[0], "order_for_first_observed_row": order_ids[1]},
                {"omitted_order": order_ids[-1], "order_for_first_observed_row": order_ids[0]},
            ])
        return dict(result, reason="row_identity_not_established")

    if gaps:
        i, j = gaps[0]
        witnessed_nan = all(math.isnan(value) for value in (travel[i][j],
                             distance[j][PLANTS + i], distance[PLANTS + i][j]))
        result["reason"] = "source_value_not_identified"
        if witnessed_nan:
            result["counterexamples"] = [{"cell": [i, j], "hypothetical_car_minutes": minutes}
                                         for minutes in (12.0, 24.0)]
        return result

    car = [[recovered.get((i, j), value) for j, value in enumerate(row)]
           for i, row in enumerate(travel)]
    return dict(result, verdict="RECOVERED_INPUT" if recovered else "SOURCE_READY",
                recovered_cells=len(recovered), order_ids=order_ids,
                truck_travel_minutes=[[value * TRUCK_MULTIPLIER for value in row] for row in car])


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=PINS)
    parser.add_argument("raw", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = analyze(args.case, args.raw.read_bytes(), normalized(args.case, args.repo))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
