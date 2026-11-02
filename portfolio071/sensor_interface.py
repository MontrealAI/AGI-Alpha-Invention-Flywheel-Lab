from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR


GRID = ((1.0, "scale"), (10.0, "scale"), (100.0, "scale"), (10.0, 0.01), (10.0, 0.1))
REPRESENTATIONS = ("raw", "signed_log", "frame", "ratio_only")


def checked_features(X):
    a = np.asarray(X, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] != 128 or not np.isfinite(a).all():
        raise ValueError("Expected finite n by 128 sensor features")
    return a


def decompose(X):
    a = checked_features(X).reshape(-1, 16, 8)
    amplitude = np.linalg.norm(a, axis=1)
    denominator = np.where(amplitude > 0, amplitude, 1.0)
    return np.column_stack(((a / denominator[:, None, :]).reshape(-1, 128), np.log(denominator)))


def reconstruct(Z):
    z = np.asarray(Z, dtype=np.float64)
    if z.ndim != 2 or z.shape[1] != 136 or not np.isfinite(z).all():
        raise ValueError("Expected finite n by 136 interface features")
    reconstructed = z[:, :128].reshape(-1, 16, 8) * np.exp(z[:, 128:])[:, None, :]
    if not np.isfinite(reconstructed).all():
        raise ValueError("Amplitude overflow")
    return reconstructed.reshape(-1, 128)


def representation(X, mode, log_scale=None):
    a = checked_features(X)
    if mode == "raw":
        return a
    if mode == "signed_log":
        if log_scale is None:
            raise ValueError("Signed-log baseline requires fit-only scale")
        return np.arcsinh(a / np.asarray(log_scale))
    if mode == "frame":
        return decompose(a)
    if mode == "ratio_only":
        return decompose(a)[:, :128]
    raise ValueError("Unknown representation")


@dataclass
class SensorModel:
    mode: str
    task: str
    estimator: object
    scaler: object
    log_scale: object
    ood_limit: float
    params: dict
    calibration_error: float
    fit_cpu_seconds: float
    fit_wall_seconds: float

    def predict(self, X):
        z = self.scaler.transform(representation(X, self.mode, self.log_scale))
        score = np.sqrt(np.mean(np.square(z), axis=1))
        supported = score <= self.ood_limit
        raw = self.estimator.predict(z)
        if self.task == "concentration":
            values = np.maximum(0, np.expm1(np.clip(raw, -30, 30)))
            lower = np.maximum(0, np.expm1(np.clip(raw - self.calibration_error, -30, 30)))
            upper = np.maximum(0, np.expm1(np.clip(raw + self.calibration_error, -30, 30)))
        else:
            values = raw.astype(int)
            lower = upper = None
        return {"values": values, "supported": supported, "accepted": supported, "ood_score": score,
                "lower": lower, "upper": upper}


def _fit(trainX, target, tuneX, tune_target, task, inherited=None):
    trainX, tuneX = checked_features(trainX), checked_features(tuneX)
    target, tune_target = np.asarray(target), np.asarray(tune_target)
    if len(trainX) != len(target) or len(tuneX) != len(tune_target):
        raise ValueError("Length mismatch")
    if task == "concentration" and ((target < 0).any() or (tune_target < 0).any()):
        raise ValueError("Negative concentration")
    result, search = {}, []
    scale = np.maximum(np.median(np.abs(trainX), axis=0), 1e-12)
    y = np.log1p(target) if task == "concentration" else target
    yt = np.log1p(tune_target) if task == "concentration" else tune_target
    for mode in REPRESENTATIONS:
        start, cpu = time.perf_counter(), time.process_time()
        if inherited is not None and mode == "frame":
            scaler = inherited["frame"].scaler
        else:
            scaler = StandardScaler().fit(representation(trainX, mode, scale))
        a = scaler.transform(representation(trainX, mode, scale))
        b = scaler.transform(representation(tuneX, mode, scale))
        best, best_key = None, None
        for C, gamma in GRID:
            model = (SVC(C=C, gamma=gamma, kernel="rbf", cache_size=128, decision_function_shape="ovr")
                     if task == "identity" else SVR(C=C, gamma=gamma, epsilon=0.05, kernel="rbf", cache_size=128))
            model.fit(a, y)
            pred = model.predict(b)
            loss = (1 - f1_score(yt, pred, labels=range(1, 7), average="macro", zero_division=0)
                    if task == "identity" else mean_absolute_error(yt, pred))
            key = (float(loss), C, str(gamma))
            search.append({"task": task, "mode": mode, "C": C, "gamma": gamma, "tune_loss": float(loss)})
            if best_key is None or key < best_key:
                best, best_key = model, key
        threshold = float(np.quantile(np.sqrt(np.mean(np.square(b), axis=1)), 0.95, method="higher"))
        err = float(np.quantile(np.abs(yt - best.predict(b)), 0.95, method="higher")) if task == "concentration" else 0.0
        result[mode] = SensorModel(mode, task, best, scaler, scale, threshold,
                                   {"C": best_key[1], "gamma": best_key[2]}, err,
                                   time.process_time() - cpu, time.perf_counter() - start)
    return result, search


def fit_k1(trainX, gas, tuneX, tunegas):
    return _fit(trainX, gas, tuneX, tunegas, "identity")


def fit_k2(trainX, ppm, tuneX, tuneppm, inherited=None):
    return _fit(trainX, ppm, tuneX, tuneppm, "concentration", inherited)


def recalibrate(models, trainX, target, calibrationX, calibration_target):
    import copy
    if len(calibrationX) != 20 or len(calibration_target) != 20:
        raise ValueError("Registered adaptation consumes exactly twenty labeled rows")
    combined = np.vstack((checked_features(trainX), checked_features(calibrationX)))
    y = np.concatenate((np.asarray(target), np.asarray(calibration_target)))
    output = {}
    for name, original in models.items():
        model = copy.deepcopy(original)
        z = model.scaler.transform(representation(combined, model.mode, model.log_scale))
        start, cpu = time.perf_counter(), time.process_time()
        model.estimator.fit(z, np.log1p(y) if model.task == "concentration" else y)
        model.fit_cpu_seconds = time.process_time() - cpu
        model.fit_wall_seconds = time.perf_counter() - start
        output[name] = model
    return output


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def training_manifest(models):
    return {name: {"representation": m.mode, "task": m.task, "parameters": m.params,
                   "ood_limit": m.ood_limit, "fit_cpu_seconds": m.fit_cpu_seconds,
                   "fit_wall_seconds": m.fit_wall_seconds, "calibration_error": m.calibration_error,
                   "support_vectors": len(m.estimator.support_), "input_dimensions": m.scaler.n_features_in_}
            for name, m in models.items()}


def train(data, output):
    data, output = Path(data), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tr, tu = np.load(data / "train.npz"), np.load(data / "tune.npz")
    if set(tr["batch"]) != {1, 2, 3, 4} or set(tu["batch"]) != {5}:
        raise ValueError("Training requires registered chronological split")
    k1, search1 = fit_k1(tr["X"], tr["gas"], tu["X"], tu["gas"])
    k1_bytes = pickle.dumps(k1, protocol=5)
    (output / "k1.pkl").write_bytes(k1_bytes)
    k1_sha = hashlib.sha256(k1_bytes).hexdigest()
    k2, search2 = fit_k2(tr["X"], tr["ppm"], tu["X"], tu["ppm"], k1)
    k2_bytes = pickle.dumps(k2, protocol=5)
    (output / "k2.pkl").write_bytes(k2_bytes)
    bridge = reconstruct(decompose(tr["X"]))
    bridge_error = float(np.max(np.abs(bridge - tr["X"]) / np.maximum(1, np.abs(tr["X"]))))
    manifest = {"schema": "portfolio071.sensor-interface.training.v1", "constructor_sha256": file_hash(__file__),
                "train_sha256": file_hash(data / "train.npz"), "tune_sha256": file_hash(data / "tune.npz"),
                "k1_sha256": k1_sha, "k2_sha256": hashlib.sha256(k2_bytes).hexdigest(),
                "k1_frozen_before_k2_fit": True, "train_rows": len(tr["X"]), "tune_rows": len(tu["X"]),
                "roundtrip_max_relative_error": bridge_error, "k1": training_manifest(k1), "k2": training_manifest(k2),
                "tuning": search1 + search2, "heldout_access": "none in constructor",
                "ordinary_reuse": "The same frozen frame and model are available without a claimed discovery procedure; identical predictions are required.",
                "fresh_successor": "The parameter-free frame can be reconstructed exactly; a fresh fit on the same fit-set must tie.",
                "physical_instrument": False, "commercial_data_rights": "unresolved; research-only use"}
    (output / "TRAINING.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    m = train(args.data, args.output)
    print(json.dumps({k: m[k] for k in ("constructor_sha256", "k1_sha256", "k2_sha256", "train_rows", "tune_rows", "roundtrip_max_relative_error")}, sort_keys=True))
