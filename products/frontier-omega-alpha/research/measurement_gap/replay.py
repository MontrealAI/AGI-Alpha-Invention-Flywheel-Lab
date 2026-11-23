#!/usr/bin/env python3
"""Reconstruct public ZTF measurements hidden from all matched prediction arms."""
from argparse import ArgumentParser
from collections import defaultdict
from decimal import Decimal
from itertools import product
import math
from pathlib import Path
import random
import secrets
from statistics import mean, pstdev
import sys
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "autonomous_endpoint"))
from common import SANDBOX, atomic, clock, encode, load_module, measure, read, require, sha
from cycle import exclusive_state, signature, verify

wire = load_module("frozen_broker_acquisition", HERE.parent / "photometry_resilience" / "replay.py")
REGISTRATION = HERE / "registration.json"
PRIOR = HERE.parent / "photometry_resilience" / "evidence" / "confirmation.json"
CLI = ("nearest", "linear", "local-cubic", "multiband-gp", "cross-band-correction")
WEIGHTS = (0.0, 0.25, 0.5, 1.0)
GP_GRID = tuple(product((1.5, 4.0, 8.0), (0.0, 0.6, 0.9)))


def get(url, registration):
    return wire.public_query(url, {"request_timeout_seconds": registration["source_timeout_seconds"],
                                  "max_reply_bytes": registration["maximum_request_bytes"]})


def exposures(ids, registration):
    if not ids:
        return [], {"state": "EMPTY_TARGET_ROSTER"}
    uri = registration["reference"]["objects"] + "?" + urlencode({"objectId": ",".join(ids),
                              "columns": wire.COLUMNS, "output-format": "json"})
    rows, source = get(uri, registration)
    points, invalid, conflicts = wire.project(rows, "fink", ids, Decimal(0), wire.jd(registration["cutoff_utc_day"]))
    return points, source | {"in_scope_exposures": len(points), "malformed_rows": invalid, "conflicts_withheld": conflicts}


def prior_targets(registration):
    require(sha(PRIOR.read_bytes()) == registration["reference"]["receipt_sha256"], "PRIOR_RECEIPT_CHANGED")
    receipt = verify(PRIOR)["receipt"]
    development = receipt["freeze"]["development_targets"]
    later = receipt["campaigns"][0]["observations"]["targets"]
    earlier = receipt["campaigns"][1]["observations"]["targets"]
    require(len(set(development + later + earlier)) == len(development + later + earlier), "TARGET_LEAKAGE")
    return development, later, earlier


def line(left, right, instant):
    delta = right[0] - left[0]
    proportion = (instant - left[0]) / delta
    return left[1] + proportion * (right[1] - left[1])


def bracket(points, instant, max_days):
    left = [p for p in points if instant - max_days <= p[0] < instant]
    right = [p for p in points if instant < p[0] <= instant + max_days]
    return (left[-1], right[0]) if left and right else None


def source_value(records, time, max_days):
    for point in records:
        if point[0] == time:
            return point[1]
    anchors = bracket(records, time, max_days)
    return line(*anchors, time) if anchors else None


def cubic(records, left, right):
    before = [p for p in records if p[0] < left[0]]
    after = [p for p in records if p[0] > right[0]]
    average = line(left, right, 0.0)
    if not before or not after:
        return average
    p, q = before[-1], after[0]
    y0, y1 = left[1], right[1]
    widths = [left[0] - p[0], right[0] - left[0], q[0] - right[0]]
    slopes = [(y0-p[1])/widths[0], (y1-y0)/widths[1], (q[1]-y1)/widths[2]]

    def derivative(a, b, h0, h1):
        if a*b <= 0:
            return 0.0
        w0, w1 = 2*h1+h0, h1+2*h0
        return (w0+w1) / (w0/a+w1/b)

    h = widths[1]
    m0 = derivative(slopes[0], slopes[1], widths[0], h)
    m1 = derivative(slopes[1], slopes[2], h, widths[2])
    x = -left[0]/h
    return ((2*x**3-3*x**2+1)*y0 + (x**3-2*x**2+x)*h*m0 + (-2*x**3+3*x**2)*y1 + (x**3-x**2)*h*m1)


def solve_positive_definite(values, response):
    """Cholesky solve for the small local regression; all diagonals have known noise."""
    size = len(response)
    triangle = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i+1):
            n = values[i][j] - sum(triangle[i][k]*triangle[j][k] for k in range(j))
            triangle[i][j] = math.sqrt(n) if i == j else n / triangle[j][j]
    lower = []
    for i, target in enumerate(response):
        lower.append((target - sum(triangle[i][j]*lower[j] for j in range(i))) / triangle[i][i])
    weights = [0.0] * size
    for i in reversed(range(size)):
        weights[i] = (lower[i] - sum(triangle[j][i]*weights[j] for j in range(i+1, size))) / triangle[i][i]
    return weights


def gp(same, auxiliary, anchors, max_days, length, cross):
    pack = []
    for band, rows in enumerate((same, auxiliary)):
        closest = sorted((p for p in rows if abs(p[0]) <= max_days), key=lambda p: abs(p[0]))[:6]
        if band == 0:
            closest = list(dict.fromkeys(closest + list(anchors)))
        pack.extend((*p, band) for p in closest)
    offsets = {band: mean([p[1] for p in pack if p[3] == band]) for band in {p[3] for p in pack}}
    response = [y-offsets[band] for _, y, _, band in pack]
    variance = max(0.05, pstdev(response))**2

    def kernel(t, u, b1, b2):
        r = math.sqrt(3.0) * abs(t-u) / length
        return variance * (1+r) * math.exp(-r) * (1 if b1 == b2 else cross)

    matrix = [[kernel(t, u, b, other) + (sigma**2 + 0.03**2 if i == j else 0.0)
               for j, (u, _, _, other) in enumerate(pack)] for i, (t, _, sigma, b) in enumerate(pack)]
    weights = solve_positive_definite(matrix, response)
    return offsets[0] + sum(w * kernel(t, 0.0, b, 0) for w, (t, _, _, b) in zip(weights, pack, strict=True))


def support(rows, held, span):
    moment = Decimal(held["jd"])
    band = held["band"]
    filters = defaultdict(dict)
    for item in rows:
        if item["target"] != held["target"] or item["id"] == held["id"]:
            continue
        offset = float(Decimal(item["jd"]) - moment)
        if item["band"] == band and offset == 0:
            continue
        seen = filters[item["band"]]
        value = (offset, float(item["mag"]), float(item["sigma"]))
        if abs(offset) <= 2 * span and (offset not in seen or value[2] < seen[offset][2]):
            seen[offset] = value
    primary = sorted(filters[band].values())
    secondary = sorted(filters[3-band].values())
    anchors = bracket(primary, 0.0, span)
    return primary, secondary, anchors


def draw(rows, ids, span, maximum, generator):
    admitted, coverage = [], {}
    for object_id in ids:
        candidates = sorted((r for r in rows if r["target"] == object_id), key=lambda r: r["id"])
        viable = [item for item in candidates if support(rows, item, span)[2]]
        chosen = generator.sample(viable, min(maximum, len(viable))) if len(viable) > maximum else viable
        admitted.extend(chosen)
        coverage[object_id] = {"exposures": len(candidates), "eligible_bracketed": len(viable), "held": len(chosen)}
    return admitted, coverage


def prediction_inputs(rows, held, span):
    same, aux, anchors = support(rows, held, span)
    require(anchors is not None, "NO_LEGAL_MEASUREMENT_BRACKET")
    left, right = anchors
    a, b, center = [source_value(aux, instant, span) for instant in (left[0], right[0], 0.0)]
    correction = None if any(x is None for x in (a, b, center)) else center-line((left[0], a), (right[0], b), 0.0)
    return same, aux, anchors, correction


def summarize(records, arm, tolerance):
    per_object = defaultdict(list)
    for row in records:
        guess = row["predicted"][arm]
        if guess is not None:
            per_object[row["target"]].append(abs(Decimal(str(guess))-Decimal(row["measured_mag"])))
    errors = [error for seq in per_object.values() for error in seq]
    return {"objects": len(per_object), "held": len(records), "answered": len(errors),
            "within_tolerance": sum(e <= tolerance for e in errors),
            "object_mae": float(mean([mean(seq) for seq in per_object.values()])) if errors else None}


def fit(rows, ids, registration, state):
    span = registration["within_side_days"]
    tolerance = Decimal(str(registration["tolerance_mag"]))
    examples, _ = draw(rows, ids, span, registration["per_confirmation_object_max"], random.Random(565))
    corrections, comparators = [], []
    for item in examples:
        same, aux, pair, correction = prediction_inputs(rows, item, span)
        base = line(*pair, 0.0)
        row = {"target": item["target"], "measured_mag": item["mag"]}
        corrections.append(row | {"predicted": {str(w): base + w*(correction or 0.0) for w in WEIGHTS}})
        comparators.append(row | {"predicted": {f"{d},{c}": gp(same, aux, pair, span, d, c) for d, c in GP_GRID}})
    scores = {"correction": {str(w): summarize(corrections, str(w), tolerance) for w in WEIGHTS},
              "gp": {f"{d},{c}": summarize(comparators, f"{d},{c}", tolerance) for d, c in GP_GRID}}
    if not examples:
        return {"cross_band_weight": "0.0", "gp_setting": "4.0,0.6", "fit_status": "NO_DEVELOPMENT_CASES"}, scores
    require(SANDBOX.is_file() and sha(SANDBOX.read_bytes()) == wire.SANDBOX_HASH, "SANDBOX_IDENTITY_CHANGED")
    sandbox = load_module("measurement_fit_sandbox", SANDBOX)
    chooser = HERE / "choose.py"
    receipt = sandbox.run(chooser, "choose", scores, sha(chooser.read_bytes()))
    require(receipt["state"] == "COMPLETE", "DEVELOPMENT_FIT_FAILED")
    return receipt["worker"]["result"] | {"fit_status": "FROZEN", "constructor": receipt["worker"]["confinement"]}, scores


def score(rows, ids, plan, registration, seed):
    span = registration["within_side_days"]
    length, cross = (float(x) for x in plan["gp_setting"].split(","))
    strength = float(plan["cross_band_weight"])
    chosen, coverage = draw(rows, ids, span, registration["per_confirmation_object_max"], random.Random(seed))
    observed = []
    adjusted = 0
    for item in chosen:
        same, aux, pair, correction = prediction_inputs(rows, item, span)
        left, right = pair
        base = line(left, right, 0.0)
        outputs = {"nearest": min(pair, key=lambda p: abs(p[0]))[1], "linear": base,
                   "local-cubic": cubic(same, left, right), "multiband-gp": gp(same, aux, pair, span, length, cross),
                   "cross-band-correction": base + strength*(correction or 0.0)}
        require(all(math.isfinite(x) for x in outputs.values()), "NONFINITE_PREDICTION")
        adjusted += int(strength != 0 and correction is not None)
        observed.append({"target": item["target"], "held_id": item["id"], "band": item["band"], "jd": item["jd"],
                         "measured_mag": item["mag"], "formal_sigma": item["sigma"], "predicted": outputs})
    tolerance = Decimal(str(registration["tolerance_mag"]))
    metrics = {arm: summarize(observed, arm, tolerance) for arm in CLI}
    advantage = observed and all(metrics[CLI[-1]]["object_mae"] < metrics[name]["object_mae"] and
                                metrics[CLI[-1]]["within_tolerance"] > metrics[name]["within_tolerance"] for name in CLI[:-1])
    return {"coverage": coverage, "cases": observed, "metrics": metrics, "applied_corrections": adjusted,
            "passes_complete_technical_comparison": bool(advantage)}


def identity():
    paths = [REGISTRATION, HERE / "choose.py", Path(__file__).resolve(), Path(wire.__file__)]
    return {str(p.relative_to(HERE.parent)): sha(p.read_bytes()) for p in paths}


def run(state, output):
    require(not output.resolve().is_relative_to(state.resolve()), "EXPORT_REQUIRES_DISTINCT_DIRECTORY")
    with exclusive_state(state):
        registration = read(REGISTRATION)
        development, later, earlier = prior_targets(registration)
        freeze_file = state / "frozen.json"
        if not freeze_file.exists():
            costs = {}
            with measure(costs, "development_acquisition"):
                rows, source = exposures(development, registration)
            with measure(costs, "development_comparison_and_frozen_construction"):
                plan, scores = fit(rows, development, registration, state)
            atomic(freeze_file, {"identity": identity(), "source": source, "plan": plan, "comparison": scores,
                                 "costs": costs, "frozen_utc": clock()})
        frozen = read(freeze_file)
        require(frozen["identity"] == identity(), "FROZEN_EXPERIMENT_CHANGED")
        target_file = state / "selected.json"
        if not target_file.exists():
            query = registration["reference"]["roster"] + "?" + urlencode({"class": "SLSN candidate", "n": 100,
                          "startdate": "2026-11-17", "stopdate": registration["cutoff_utc_day"],
                          "columns": "i:objectId,i:jd", "output-format": "json"})
            roster, trace = get(query, registration)
            fresh = wire.select(roster, wire.jd("2026-11-17"), wire.jd(registration["cutoff_utc_day"]),
                                set(development + later + earlier), 6)
            atomic(target_file, {"cohorts": {"later-targets": later, "earlier-targets": earlier, "fresh-targets": fresh},
                                  "fresh_roster_source": trace, "planned_after_freeze": clock()})
        selected = read(target_file)
        campaigns = {}
        for name, ids in selected["cohorts"].items():
            checkpoint = state / f"{name}.json"
            if not checkpoint.exists():
                rows, source = exposures(ids, registration)
                atomic(checkpoint, {"targets": ids, "source": source, "rows": rows, "seed": secrets.token_hex(16)})
            observed = read(checkpoint)
            require(observed["targets"] == ids, "TARGET_CHECKPOINT_CHANGED")
            costs = {}
            with measure(costs, "held_measurement_comparison"):
                evaluation = score(observed["rows"], ids, frozen["plan"], registration, observed["seed"])
            campaigns[name] = observed | {"evaluation": evaluation, "costs": costs}
        require(frozen["identity"] == identity(), "FROZEN_EXPERIMENT_CHANGED_DURING_REPLAY")
        receipt = {"schema": "frontier-omega-alpha/missing-measurement-receipt-v1", "finished_utc": clock(),
                   "frozen": frozen, "selection": selected, "campaigns": campaigns,
                   "registration_sha256": sha(REGISTRATION.read_bytes()), "routine_operator_steps": 0,
                   "all_technical_comparisons_pass": all(row["evaluation"]["passes_complete_technical_comparison"]
                                                        for row in campaigns.values()),
                   "productive_s1": "UNQUALIFIED", "s2_and_learning": "UNPROVEN",
                   "complete_operating_cost": None, "endpoint": "ABSTAIN", "endpoint_incumbent": "indexed-sqlite"}
        output.parent.mkdir(parents=True, exist_ok=True)
        atomic(output, signature(state, receipt))


def audit(path, key):
    receipt = verify(path, key)["receipt"]
    registration = read(REGISTRATION)
    require(receipt["frozen"]["identity"] == identity(), "SIGNED_EXPERIMENT_SOURCE_CHANGED")
    cases = 0
    for cohort in receipt["campaigns"].values():
        recomputed = score(cohort["rows"], cohort["targets"], receipt["frozen"]["plan"], registration, cohort["seed"])
        require(recomputed == cohort["evaluation"], "HELD_MEASUREMENT_EVALUATION_MISMATCH")
        cases += len(recomputed["cases"])
    return {"signature_verified": True, "cohorts": len(receipt["campaigns"]), "held_measurements": cases}


def main():
    parser = ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    live = actions.add_parser("run")
    live.add_argument("--state", type=Path, required=True)
    live.add_argument("--output", type=Path, required=True)
    check = actions.add_parser("audit")
    check.add_argument("receipt", type=Path)
    check.add_argument("--key-sha256", required=True)
    args = parser.parse_args()
    if args.action == "run":
        run(args.state, args.output)
    else:
        print(encode(audit(args.receipt, args.key_sha256)).decode(), end="")


if __name__ == "__main__":
    main()
