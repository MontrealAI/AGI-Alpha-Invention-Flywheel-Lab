"""Preregistered KIT4 real-tank sparse-observation dependency test; no financial authority."""
import argparse
import hashlib
import io
import json
import math
import os
import re
import time
import urllib.request
import zipfile
from pathlib import Path
import numpy as np
from scipy.io import loadmat

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "PROTOCOL.json").read_text())
MD5 = PROTOCOL["source"]["expected_md5"]
URL = PROTOCOL["source"]["archive_url"]
LABELS = {name: kind for role, kind in (("development_plastic", "PLASTIC"), ("development_metal", "METAL"), ("heldout_plastic", "PLASTIC"), ("heldout_metal", "METAL")) for name in PROTOCOL["cases"][role]}
DEV = PROTOCOL["cases"]["development_plastic"] + PROTOCOL["cases"]["development_metal"]
TEST = PROTOCOL["cases"]["heldout_plastic"] + PROTOCOL["cases"]["heldout_metal"]
PATTERNS = PROTOCOL["physical_operation"]["all_patterns"]
BUDGET = PROTOCOL["physical_operation"]["retained_patterns"]

def raw_archive(path=None):
    if path is not None:
        data = Path(path).read_bytes()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "AGI-ALPHA-physical-EIT-research/1.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read(5_000_000)
    if len(data) > 5_000_000 or hashlib.md5(data).hexdigest() != MD5:
        raise ValueError("FROZEN_PHYSICAL_SOURCE_CHECKSUM_MISMATCH")
    return data

def load_physical(data):
    required = set(LABELS) | {PROTOCOL["cases"]["background"]}
    rows, hashes = {}, {}
    with zipfile.ZipFile(io.BytesIO(data), "r") as z:
        members = [x for x in z.infolist() if not x.is_dir() and x.filename.endswith(".mat")]
        if len(members) < len(required):
            raise ValueError("FROZEN_SOURCE_MEMBER_COUNT_CHANGED")
        selected = {}
        for m in members:
            if m.file_size > 1_000_000 or m.filename.startswith("/") or ".." in Path(m.filename).parts or "\\" in m.filename:
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            base = Path(m.filename).name
            if not re.fullmatch(r"datamat_[0-9]+_[0-9]+\.mat", base):
                continue
            if base in selected:
                raise ValueError("AMBIGUOUS_SOURCE_CASE")
            selected[base] = m
        if not required.issubset(selected):
            raise ValueError("REGISTERED_CASE_MISSING")
        fixed_patterns = None
        for name in sorted(required):
            sample = z.read(selected[name])
            hashes[name] = hashlib.sha256(sample).hexdigest()
            mat = loadmat(io.BytesIO(sample), verify_compressed_data_integrity=True)
            for field, expected in (("Uel", (16, 79)), ("CurrentPattern", (16, 79)), ("MeasPattern", (16, 16))):
                if field not in mat or mat[field].shape != expected or not np.issubdtype(mat[field].dtype, np.number) or not np.all(np.isfinite(mat[field])):
                    raise ValueError("SOURCE_MATRIX_INVALID_" + field + "_" + name)
            patterns = (np.asarray(mat["CurrentPattern"], dtype=float), np.asarray(mat["MeasPattern"], dtype=float))
            if fixed_patterns is not None and not all(np.allclose(a, b, rtol=0, atol=1e-12) for a, b in zip(fixed_patterns, patterns)):
                raise ValueError("EXCITATION_OR_MEASUREMENT_CHANGED")
            fixed_patterns = patterns
            rows[name] = np.asarray(mat["Uel"], dtype=float).T.copy()
    return rows, hashes, len(members)

def physical_features(rows):
    bg = rows[PROTOCOL["cases"]["background"]]
    all_names = DEV + TEST
    train_raw = np.stack([(rows[k] - bg).reshape(-1) for k in DEV])
    trial_raw = np.stack([(rows[k] - bg).reshape(-1) for k in TEST])
    means = train_raw.mean(axis=0)
    spread = train_raw.std(axis=0)
    floor = max(float(np.median(spread)) * 0.01, 1e-9)
    scale = np.maximum(spread, floor)
    return ((train_raw - means) / scale).reshape(len(DEV), 79, 16), ((trial_raw - means) / scale).reshape(len(TEST), 79, 16), floor

def centroid_predict(X, y, item, selected, leave_out=None):
    keep = [i for i in range(len(y)) if i != leave_out]
    means = {kind: X[[i for i in keep if y[i] == kind]][:, selected].mean(axis=0) for kind in ("PLASTIC", "METAL")}
    if any(not np.all(np.isfinite(v)) for v in means.values()):
        raise ValueError("NONFINITE_CLASS_MEAN")
    d = {kind: float(np.sum((item[selected] - means[kind]) ** 2)) for kind in means}
    if math.isclose(d["PLASTIC"], d["METAL"], abs_tol=1e-10, rel_tol=1e-12):
        return "ABSTAIN", 0.0
    best = min(d, key=d.get)
    return best, abs(d["PLASTIC"] - d["METAL"])

def class_labels(names):
    return [LABELS[k] for k in names]

def score_prediction(preds, truth):
    stats = {kind: {"correct": 0, "total": 0} for kind in ("PLASTIC", "METAL")}
    for predicted, target in zip(preds, truth):
        stats[target]["total"] += 1
        stats[target]["correct"] += int(predicted == target)
    balanced = sum(stats[k]["correct"] / stats[k]["total"] for k in stats) / 2
    return sum(predicted == target for predicted, target in zip(preds, truth)), balanced

def loo_score(X, y, selected):
    preds, margins = [], []
    for i in range(len(y)):
        pred, margin = centroid_predict(X, y, X[i], selected, i)
        preds.append(pred)
        margins.append(margin)
    return score_prediction(preds, y)[1], float(sum(margins))

def fisher_scores(X, y):
    p = X[np.array(y) == "PLASTIC"]
    m = X[np.array(y) == "METAL"]
    contrast = ((p.mean(axis=0) - m.mean(axis=0)) ** 2).sum(axis=1)
    within = ((p - p.mean(axis=0)) ** 2).sum(axis=(0,2)) / len(p) + ((m - m.mean(axis=0)) ** 2).sum(axis=(0,2)) / len(m)
    return contrast / (0.05 + within)

def robust_scores(X, y, names):
    by_count = {}
    for count in ("1", "2"):
        ids_p = [i for i,k in enumerate(names) if k.split("_")[1] == count and y[i] == "PLASTIC"]
        ids_m = [i for i,k in enumerate(names) if k.split("_")[1] == count and y[i] == "METAL"]
        if not ids_p or not ids_m:
            raise ValueError("REGISTERED_COUNT_CLASS_MISSING")
        diff = X[ids_p].mean(axis=0) - X[ids_m].mean(axis=0)
        by_count[count] = (diff ** 2).sum(axis=1)
    plastic = X[np.array(y) == "PLASTIC"]
    metal = X[np.array(y) == "METAL"]
    within = ((plastic - plastic.mean(axis=0)) ** 2).sum(axis=(0,2)) / len(plastic) + ((metal - metal.mean(axis=0)) ** 2).sum(axis=(0,2)) / len(metal)
    return np.minimum(by_count["1"], by_count["2"]) / (0.05 + within)

def rank_top(scores):
    return sorted(range(PATTERNS), key=lambda i: (-float(scores[i]), i))[:BUDGET]

def greedy_loo(X, y, fisher):
    selected = []
    for _ in range(BUDGET):
        options = []
        for i in range(PATTERNS):
            if i in selected:
                continue
            accuracy, margin = loo_score(X, y, selected + [i])
            options.append((accuracy, float(fisher[i]), margin, -i, i))
        selected.append(max(options)[-1])
    return selected

def evaluate(archive):
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    data = raw_archive(archive)
    rows, hashes, member_count = load_physical(data)
    X, T, scale_floor = physical_features(rows)
    y, z = class_labels(DEV), class_labels(TEST)
    fisher = fisher_scores(X, y)
    designs = {
        "ordinary_fisher": rank_top(fisher),
        "ordinary_greedy_loo": greedy_loo(X, y, fisher),
        "joint_count_robust": rank_top(robust_scores(X, y, DEV)),
        "ordinary_all_patterns": list(range(PATTERNS)),
    }
    arms = {}
    for name, selected in designs.items():
        predicted = [centroid_predict(X, y, item, selected)[0] for item in T]
        correct, balanced = score_prediction(predicted, z)
        training_balanced, _ = loo_score(X, y, selected)
        arms[name] = {
            "selected_pattern_indices_zero_based": selected,
            "voltage_readings_per_case": len(selected) * 16,
            "heldout_case_predictions": [{"case": case, "truth": target, "prediction": pred} for case, target, pred in zip(TEST, z, predicted)],
            "heldout_correct": correct,
            "heldout_balanced_accuracy": round(balanced, 12),
            "development_loo_balanced_accuracy": round(training_balanced, 12),
        }
    best_control = max(arms[n]["heldout_correct"] for n in ("ordinary_fisher", "ordinary_greedy_loo"))
    proposed = arms["joint_count_robust"]["heldout_correct"]
    admitted = proposed >= 5 and proposed > best_control
    return {
        "schema": "agi-alpha/interior-eit-physical082/result/v1",
        "preregistration_commit": "035c2fc0ba2e2189e93eb4a4f57bb0b6a8664316",
        "base_commit": PROTOCOL["base_commit"],
        "source": {"doi": PROTOCOL["source"]["doi"], "archive_md5": MD5, "archive_sha256": hashlib.sha256(data).hexdigest(), "registered_case_sha256": hashes, "mat_members": member_count},
        "target": "metal-only versus plastic-only tank inclusions in physical KIT4 cases, counts 3 held out",
        "development_cases": DEV,
        "heldout_cases": TEST,
        "training_coordinate_scale_floor": scale_floor,
        "arms": arms,
        "best_equal_budget_ordinary_correct": best_control,
        "verdict": "PROVISIONAL_SPARSE_DEPENDENCY_ONLY" if admitted else "NO_ENABLING_ADVANTAGE",
        "economic_claim": "NO_CUSTOMERS_NO_NATIVE_PROFIT_NO_PHYSICAL_DEPLOYMENT",
        "resource": {"cpu_seconds_this_process": round(time.process_time() - started_cpu, 6), "wall_seconds_this_process": round(time.perf_counter() - started_wall, 6), "host_and_model_billing": None},
    }

def audit(receipt, archive):
    expected = evaluate(archive)
    observed = json.loads(Path(receipt).read_text())
    for obj in (expected, observed):
        obj.pop("resource", None)
    if observed != expected:
        raise ValueError("SOURCE_OR_DECISION_AUDIT_MISMATCH")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("run", "audit"))
    ap.add_argument("--archive")
    ap.add_argument("--output")
    ap.add_argument("--receipt")
    args = ap.parse_args()
    if args.action == "run":
        if not args.output or Path(args.output).exists():
            raise ValueError("OUTPUT_MUST_BE_NEW")
        result = evaluate(args.archive)
        Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"verdict": result["verdict"], "heldout_correct": {k: v["heldout_correct"] for k,v in result["arms"].items()}, "source_sha256": result["source"]["archive_sha256"]}, sort_keys=True))
    else:
        if not args.receipt:
            raise ValueError("AUDIT_RECEIPT_REQUIRED")
        audit(args.receipt, args.archive)
        print("INDEPENDENT_REEXECUTION_AUDIT_OK")

if __name__ == "__main__":
    main()
