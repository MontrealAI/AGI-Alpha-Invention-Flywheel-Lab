from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, recall_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from portfolio071 import sensor_interface as producer
from portfolio071.sensor_interface import SensorModel


EXPECTED_ARCHIVE = "98fe3a30981a222dd4518fbcc3dddd45d5c0ce9b03ef6dc6fe5cf7a04cfbff5e"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_batches(base, numbers):
    rows, gas, concentration, batch = [], [], [], []
    for number in numbers:
        for line in (Path(base) / f"batch{number}.dat").read_text().splitlines():
            parts = line.split()
            label, ppm = parts[0].split(";")
            indexed = [part.split(":") for part in parts[1:]]
            if [int(x[0]) for x in indexed] != list(range(1, 129)):
                raise ValueError("Source feature indexes changed")
            rows.append([float(x[1]) for x in indexed])
            gas.append(int(label)); concentration.append(float(ppm)); batch.append(number)
    result = {"X": np.asarray(rows), "gas": np.asarray(gas), "ppm": np.asarray(concentration), "batch": np.asarray(batch)}
    if not np.isfinite(result["X"]).all() or not np.isfinite(result["ppm"]).all():
        raise ValueError("Nonfinite measured source")
    return result


def row_hashes(X):
    return [hashlib.sha256(np.asarray(row, dtype="<f8").tobytes()).hexdigest() for row in X]


def identity_metrics(model, data):
    output = model.predict(data["X"])
    y, accepted = data["gas"], output["accepted"]
    decision = np.where(accepted, output["values"], 0)
    recalls = recall_score(y, decision, labels=range(1, 7), average=None, zero_division=0)
    macro = float(f1_score(y, decision, labels=range(1, 7), average="macro", zero_division=0))
    coverage = float(np.mean(accepted))
    unconditional = float(f1_score(y, output["values"], labels=range(1, 7), average="macro", zero_division=0))
    risk_curve = []
    for quantile in (0.25, 0.5, 0.75, 0.9, 1.0):
        count = max(1, int(len(y) * quantile))
        selected = np.argsort(output["ood_score"], kind="stable")[:count]
        risk_curve.append({"coverage": count / len(y), "classification_error": float(np.mean(output["values"][selected] != y[selected]))})
    return {"n": len(y), "coverage": coverage, "macro_f1_with_abstention_as_error": macro,
            "macro_f1_without_abstention": unconditional,
            "recall_by_gas": {str(i + 1): float(r) for i, r in enumerate(recalls)},
            "accepted": bool(coverage >= 0.90 and macro >= 0.80 and np.min(recalls) >= 0.60),
            "coverage_risk_curve_diagnostic_not_retuned": risk_curve}


def concentration_metrics(model, data, ranges):
    output = model.predict(data["X"])
    ppm, gas, accepted = data["ppm"], data["gas"], output["accepted"]
    norm = np.asarray([ranges[int(label)] for label in gas])
    errors = np.abs(output["values"] - ppm) / norm
    groups = {}
    for label in np.unique(gas):
        mask = gas == label
        selected = mask & accepted
        groups[str(label)] = {"n": int(np.sum(mask)), "coverage": float(np.mean(accepted[mask])),
                             "normalized_mae_all": float(np.mean(errors[mask])),
                             "normalized_mae_accepted": float(np.mean(errors[selected])) if np.any(selected) else None}
    pooled_all = float(np.mean(errors))
    pooled_accepted = float(np.mean(errors[accepted])) if np.any(accepted) else None
    coverage = float(np.mean(accepted))
    interval_covered = (ppm >= output["lower"]) & (ppm <= output["upper"])
    risk_curve = []
    for quantile in (0.25, 0.5, 0.75, 0.9, 1.0):
        count = max(1, int(len(ppm) * quantile))
        selected = np.argsort(output["ood_score"], kind="stable")[:count]
        risk_curve.append({"coverage": count / len(ppm), "normalized_mae": float(np.mean(errors[selected]))})
    return {"n": len(ppm), "coverage": coverage, "normalized_mae_all": pooled_all,
            "normalized_mae_accepted": pooled_accepted, "by_gas": groups,
            "empirical_interval_coverage_all": float(np.mean(interval_covered)),
            "interval_guarantee": "None: tuning residual intervals are evaluated under temporal distribution shift.",
            "accepted": bool(coverage >= 0.80 and pooled_all <= 0.10 and all(g["normalized_mae_all"] <= 0.20 for g in groups.values())),
            "coverage_risk_curve_diagnostic_not_retuned": risk_curve}


def subset(data, mask):
    return {key: value[mask] for key, value in data.items()}


def independently_reconstruct_frame(X):
    a = np.asarray(X).reshape(-1, 16, 8)
    scale = np.sqrt(np.sum(a * a, axis=1))
    scale = np.where(scale == 0, 1.0, scale)
    return np.concatenate([(a / scale[:, None, :]).reshape(-1, 128), np.log(scale)], axis=1)


def fresh_successor(train, tune, inherited, X):
    begin, cpu = time.perf_counter(), time.process_time()
    scale = StandardScaler().fit(independently_reconstruct_frame(train["X"]))
    a = scale.transform(independently_reconstruct_frame(train["X"]))
    b = scale.transform(independently_reconstruct_frame(tune["X"]))
    y, yt = np.log1p(train["ppm"]), np.log1p(tune["ppm"])
    best, best_key = None, None
    for C, gamma in producer.GRID:
        model = SVR(C=C, gamma=gamma, epsilon=0.05, kernel="rbf", cache_size=128).fit(a, y)
        key = (float(np.mean(np.abs(yt - model.predict(b)))), C, str(gamma))
        if best_key is None or key < best_key:
            best, best_key = model, key
    pred = np.maximum(0, np.expm1(np.clip(best.predict(scale.transform(independently_reconstruct_frame(X))), -30, 30)))
    reference = inherited.predict(X)["values"]
    return {"max_prediction_difference_ppm": float(np.max(np.abs(pred - reference))),
            "allclose_at_1e_minus_9": bool(np.allclose(pred, reference, atol=1e-9, rtol=1e-9)),
            "selected": {"C": best_key[1], "gamma": best_key[2]},
            "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - begin,
            "meaning": "Independent reconstruction plus equal search; a tie refutes a special retained-discovery-procedure advantage."}


def verify(batches, data, models, output, archive=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.perf_counter(), time.process_time()
    if archive is not None and sha(archive) != EXPECTED_ARCHIVE:
        raise ValueError("Registered source archive mismatch")
    tr, tu = dict(np.load(Path(data) / "train.npz")), dict(np.load(Path(data) / "tune.npz"))
    training = json.loads((Path(models) / "TRAINING.json").read_text())
    if training["constructor_sha256"] != sha(producer.__file__):
        raise ValueError("Constructor changed since training freeze")
    for label in ("k1", "k2"):
        if training[label + "_sha256"] != sha(Path(models) / (label + ".pkl")):
            raise ValueError("Frozen trained artifact changed")
    k1 = pickle.loads((Path(models) / "k1.pkl").read_bytes())
    k2 = pickle.loads((Path(models) / "k2.pkl").read_bytes())
    test1, test2 = read_batches(batches, [6]), read_batches(batches, [7, 8, 9, 10])
    fit_hashes = set(row_hashes(tr["X"]) + row_hashes(tu["X"]))
    collisions1 = np.asarray([h in fit_hashes for h in row_hashes(test1["X"])])
    collisions2 = np.asarray([h in fit_hashes for h in row_hashes(test2["X"])])
    no_collisions = not np.any(collisions1) and not np.any(collisions2)
    ranges = {int(g): float(np.ptp(tr["ppm"][tr["gas"] == g])) for g in np.unique(tr["gas"])}
    if min(ranges.values()) <= 0:
        raise ValueError("Nonpositive fit concentration range")
    result = {"schema": "portfolio071.sensor-interface.independent.v1",
              "constructor_sha256": sha(producer.__file__), "verifier_sha256": sha(__file__),
              "preregistration_sha256": sha(Path(producer.__file__).resolve().parents[1] / "experiments/portfolio_20261102/R2_PREREGISTRATION.json"),
              "source_archive_sha256": EXPECTED_ARCHIVE, "trained_artifacts": {key: training[key] for key in ("k1_sha256", "k2_sha256")},
              "source_files": {p.name: sha(p) for p in sorted(Path(batches).glob("batch*.dat"))},
              "split_counts": {"fit": len(tr["X"]), "tune": len(tu["X"]), "k1": len(test1["X"]), "k2": len(test2["X"])},
              "leakage": {"exact_fit_tune_to_k1_feature_collisions": int(np.sum(collisions1)),
                          "exact_fit_tune_to_k2_feature_collisions": int(np.sum(collisions2)),
                          "confirmation_claim_valid": bool(no_collisions),
                          "input_labels": "Only X reaches prediction. Gas/ppm/batch stay evaluator-side.",
                          "isolation": "Procedural separate-agent and data-path separation; no OS-enforced adversarial isolation."},
              "fit_gas_concentration_ranges_ppm": ranges, "k1": {}, "k2": {}, "adaptation": {}, "challenges": {}}
    for name in producer.REPRESENTATIONS:
        result["k1"][name] = identity_metrics(k1[name], test1)
        result["k2"][name] = concentration_metrics(k2[name], test2, ranges)
        result["k2"][name]["by_batch"] = {str(b): concentration_metrics(k2[name], subset(test2, test2["batch"] == b), ranges) for b in (7, 8, 9, 10)}
    example = tr["X"][:16]
    roundtrip = producer.reconstruct(producer.decompose(example))
    independent = independently_reconstruct_frame(example)
    result["challenges"]["roundtrip_max_relative_error"] = float(np.max(np.abs(roundtrip - example) / np.maximum(1, np.abs(example))))
    result["challenges"]["independent_frame_max_abs_error"] = float(np.max(np.abs(independent - producer.decompose(example))))
    result["challenges"]["zero_roundtrip"] = bool(np.array_equal(producer.reconstruct(producer.decompose(np.zeros((3, 128)))), np.zeros((3, 128))))
    result["challenges"]["ratio_gain_alias_max_error"] = float(np.max(np.abs(producer.representation(example, "ratio_only") - producer.representation(example * 10, "ratio_only"))))
    result["challenges"]["ratio_alias_scope"] = "Algebraic loss of amplitude; no gas concentration truth fabricated for gain-perturbed rows."
    for name, bad in {"nan": np.full((1, 128), np.nan), "infinity": np.full((1, 128), np.inf), "wrong_shape": np.zeros((1, 127))}.items():
        try:
            k1["frame"].predict(bad)
            refused = False
        except ValueError:
            refused = True
        result["challenges"][name + "_refused"] = refused
    for name, changed in {"gain_1000": example * 1000, "one_missing_sensor": np.column_stack((np.zeros((len(example), 8)), example[:, 8:]))}.items():
        pred = k1["frame"].predict(changed)
        result["challenges"][name] = {"accepted_fraction": float(np.mean(pred["accepted"])),
                                     "scope": "Numerical challenge only; accepted does not establish physical validity."}
    original = k2["frame"].predict(test2["X"])
    again = k2["frame"].predict(test2["X"])
    ordinary = pickle.loads(pickle.dumps(k2["frame"], protocol=5)).predict(test2["X"])
    result["challenges"]["repeat_exact"] = bool(np.array_equal(original["values"], again["values"]))
    result["ordinary_reuse"] = {"predictions_equal": bool(np.array_equal(original["values"], ordinary["values"])),
                                "acceptance_equal": bool(np.array_equal(original["accepted"], ordinary["accepted"])),
                                "meaning": "Equal retained content works without a claimed discovery procedure."}
    result["fresh_successor"] = fresh_successor(tr, tu, k2["frame"], test2["X"])
    for b in (6, 7, 8, 9, 10):
        full = test1 if b == 6 else subset(test2, test2["batch"] == b)
        cal, remaining = subset(full, np.arange(len(full["X"])) < 20), subset(full, np.arange(len(full["X"])) >= 20)
        task, baseline = ("gas", k1) if b == 6 else ("ppm", k2)
        adapted = producer.recalibrate(baseline, tr["X"], tr[task], cal["X"], cal[task])
        result["adaptation"][str(b)] = {"labeled_calibration_rows": 20, "scored_rows": len(remaining["X"]),
            "no_cross_batch_state": True, "models": {}}
        for name, model in adapted.items():
            metrics = identity_metrics(model, remaining) if b == 6 else concentration_metrics(model, remaining, ranges)
            result["adaptation"][str(b)]["models"][name] = {**metrics, "refit_cpu_seconds": model.fit_cpu_seconds, "refit_wall_seconds": model.fit_wall_seconds}
    frame1, frame2 = result["k1"]["frame"], result["k2"]["frame"]
    best1 = max(result["k1"][name]["macro_f1_with_abstention_as_error"] for name in ("raw", "signed_log"))
    best2 = min(result["k2"][name]["normalized_mae_all"] for name in ("raw", "signed_log"))
    result["verdict"] = {"artifact_constructed": True, "purpose_bridge_accepted": result["challenges"]["roundtrip_max_relative_error"] <= 1e-10,
        "k1_contract_accepted": bool(no_collisions and frame1["accepted"]),
        "k2_diagnostic_contract_accepted": bool(no_collisions and frame2["accepted"]),
        "qualified_k1_to_k2_sequence": bool(no_collisions and frame1["accepted"] and frame2["accepted"]),
        "k1_error_reduction_vs_strongest_conventional": (frame1["macro_f1_with_abstention_as_error"] - best1) / (1 - best1) if best1 < 1 else 0.0,
        "k2_error_reduction_vs_strongest_conventional": (best2 - frame2["normalized_mae_all"]) / best2 if best2 > 0 else 0.0,
        "special_retained_discovery_advantage": False,
        "physical_instrument_qualified": False, "commercial_data_rights_resolved": False,
        "stop": "No retuning on confirmation; failed K1 makes successor a diagnostic, not inheritance of a qualified capability."}
    result["resource_use"] = {"verification_cpu_seconds": time.process_time() - cpu,
        "verification_wall_seconds": time.perf_counter() - started,
        "constructor_fit_cpu_seconds": sum(v["fit_cpu_seconds"] for task in ("k1", "k2") for v in training[task].values()),
        "fitted_tuning_candidates": len(training["tuning"]), "adaptation_fits": 20, "independent_fresh_search_fits": len(producer.GRID),
        "actual_incremental_purchase_usd": 0, "agent_token_count": None, "host_or_model_account_bill": None,
        "human_minutes_measured": None, "human_intervention_requested_for_fit": 0}
    (output / "RESULTS.json").write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"verdict": result["verdict"], "split_counts": result["split_counts"], "leakage": result["leakage"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for arg in ("batches", "data", "models", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    verify(args.batches, args.data, args.models, args.output, args.archive)
