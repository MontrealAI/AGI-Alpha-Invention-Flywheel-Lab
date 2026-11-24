"""Conventional SciPy source reconciliation and an independent witness verifier."""

from io import BytesIO
import numpy as np
from scipy.io import loadmat

from dispatch_inputs import KM_PER_CAR_MINUTE, PLANTS, PINS, TRUCK_MULTIPLIER, check_bytes


def read_arrays(case, raw):
    check_bytes(case, raw)
    values = loadmat(BytesIO(raw), variable_names=["instance_specs", "prod2constr_matrix",
                                                   "DistanceMatrix"], simplify_cells=True)
    return (values["instance_specs"], np.asarray(values["prod2constr_matrix"], dtype=float),
            np.asarray(values["DistanceMatrix"], dtype=float))


def unique_inverse(km):
    x = km / KM_PER_CAR_MINUTE
    if not np.isfinite(x) or x < 0:
        return None
    candidates = np.r_[x, np.nextafter(float(x), [-np.inf, np.inf])]
    for value in candidates[(candidates >= 0) & (candidates * KM_PER_CAR_MINUTE == km)]:
        adjacent = np.nextafter(value, [-np.inf, np.inf])
        if not np.any((adjacent >= 0) & (adjacent * KM_PER_CAR_MINUTE == km)):
            return float(value)
    return None


def conventional(case, raw, inventory):
    specs, car, distance = read_arrays(case, raw)
    rows, columns = car.shape
    count = len(inventory["orders"])
    diagnosis = {"case": case, "orders": count, "source_spec_orders": int(specs["number_of_Orders"]),
                 "travel_shape": list(car.shape), "distance_shape": list(distance.shape),
                 "row_mapping_verified": inventory["travel_row_mapping_verified"],
                 "verdict": "ABSTAIN"}
    if columns != PLANTS or distance.shape != (rows + PLANTS, rows + PLANTS):
        return dict(diagnosis, reason="unsupported_structure"), None
    published = np.asarray(inventory["source_car_travel_minutes"], dtype=float)
    if not np.array_equal(car, published, equal_nan=True):
        return dict(diagnosis, reason="normalized_raw_disagreement"), None

    outbound = distance[:PLANTS, PLANTS:].T
    inbound = distance[PLANTS:, :PLANTS]
    missing = np.isnan(car)
    diagnostic = dict(diagnosis, missing_travel=int(missing.sum()),
                      missing_distance_forward=int(np.isnan(outbound).sum()),
                      missing_distance_reverse=int(np.isnan(inbound).sum()))
    if not np.array_equal(outbound, inbound, equal_nan=True) or not np.array_equal(
            outbound[~missing], (car * KM_PER_CAR_MINUTE)[~missing]) or not (
            np.all(np.isfinite(car[~missing])) and np.all(car[~missing] >= 0)):
        return dict(diagnostic, reason="contradictory_representation"), None
    if rows != count or not inventory["travel_row_mapping_verified"]:
        return dict(diagnostic, reason="row_identity_not_established"), None
    completed = car.copy()
    for i, j in zip(*np.where(missing)):
        estimate = unique_inverse(outbound[i, j])
        if estimate is None:
            return dict(diagnostic, reason="source_value_not_identified"), None
        completed[i, j] = estimate
    truck = (completed * TRUCK_MULTIPLIER).tolist()
    return dict(diagnostic, verdict="RECOVERED_INPUT" if missing.any() else "SOURCE_READY",
                recovered_cells=int(missing.sum())), truck


def check_result(case, raw, inventory, result, baseline, truck_minutes):
    """Check identities, numeric outputs, and two explicit admissible alternatives."""
    if result.get("case") != case or result.get("source_sha256") != PINS[case][2]:
        return False
    if result["verdict"] != baseline["verdict"]:
        return False
    _, records, distance = read_arrays(case, raw)
    ids = [order["id"] for order in inventory["orders"]]
    if (result["orders"] != len(ids)
            or [result["travel_rows"], result["travel_columns"]] != list(records.shape)
            or result["distance_shape"] != list(distance.shape)):
        return False
    if result["overlap_cells"] != np.isfinite(records).sum():
        return False
    if truck_minutes is not None:
        return (result["order_ids"] == ids and result["truck_travel_minutes"] == truck_minutes
                and result["recovered_cells"] == baseline["recovered_cells"])
    if result["reason"] != baseline["reason"] or result["recovered_cells"] != 0:
        return False
    witnesses = result.get("counterexamples", [])
    if result["reason"] == "row_identity_not_established":
        if len(records) != len(ids) - 1 or len(witnesses) != 2 or np.isnan(records).any():
            return False
        suggested = {item["omitted_order"] for item in witnesses}
        if len(suggested) != 2 or not suggested.issubset(ids):
            return False
        first_rows = set()
        for item in witnesses:
            order = [oid for oid in ids if oid != item["omitted_order"]]
            if order[0] != item["order_for_first_observed_row"]:
                return False
            completion = dict(zip(order, records, strict=True))
            completion[item["omitted_order"]] = np.full(PLANTS, 12.0)
            projection = [completion[oid] for oid in ids if oid != item["omitted_order"]]
            if not np.array_equal(records, projection):
                return False
            first_rows.add(order[0])
        return len(first_rows) == 2
    if result["reason"] == "source_value_not_identified":
        outbound = distance[:PLANTS, PLANTS:].T
        inbound = distance[PLANTS:, :PLANTS]
        unknown = np.isnan(records)
        if (result["unidentifiable_cells"] != np.argwhere(unknown).tolist()
                or not np.array_equal(unknown, np.isnan(outbound))
                or not np.array_equal(unknown, np.isnan(inbound)) or len(witnesses) != 2):
            return False
        if witnesses[0]["cell"] != witnesses[1]["cell"]:
            return False
        i, j = witnesses[0]["cell"]
        if not (0 <= i < len(records) and 0 <= j < PLANTS and unknown[i, j]):
            return False
        alternatives = {item["hypothetical_car_minutes"] for item in witnesses}
        if len(alternatives) != 2:
            return False
        for value in alternatives:
            if not np.isfinite(value) or value < 0:
                return False
            completion = np.where(unknown, 12.0, records)
            completion[i, j] = value
            converted = completion * KM_PER_CAR_MINUTE
            if not (np.array_equal(records[~unknown], completion[~unknown])
                    and np.array_equal(outbound[~unknown], converted[~unknown])
                    and np.array_equal(inbound[~unknown], converted[~unknown])):
                return False
        return True
    return not witnesses
