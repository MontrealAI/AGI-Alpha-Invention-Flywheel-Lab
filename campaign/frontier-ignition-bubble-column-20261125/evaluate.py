#!/usr/bin/env python3
"""Prospectively frozen reduced-input bubble-column decision experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

PARTITIONS = ("full_train", "val", "test")
HOLDOUT_SPARGERS = {"S_3", "S_2_6", "S_2_3_5"}
HOLDOUT_FLOWS = {1.5, 3.5, 5.5}
RIDGE_ALPHA = 1.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def port_bits(label: str) -> np.ndarray:
    if label == "S_all":
        return np.ones(6, dtype=np.float64)
    active = {int(token) for token in label.split("_")[1:]}
    return np.array([float(i in active) for i in range(1, 7)], dtype=np.float64)


def bits_label(bits: np.ndarray) -> str:
    active = [str(i + 1) for i, value in enumerate(bits) if value]
    return "S_all" if len(active) == 6 else "S_" + "_".join(active)


def reduced_indices() -> np.ndarray:
    # f0 real ring 1, followed by f0 imaginary ring 1.
    return np.r_[np.arange(0, 1024), np.arange(8192, 9216)]


def contiguous_segments(labels: np.ndarray, flows: np.ndarray):
    start = 0
    for i in range(1, len(labels) + 1):
        changed = i == len(labels) or labels[i] != labels[start] or float(flows[i]) != float(flows[start])
        if changed:
            yield start, i, str(labels[start]), float(flows[start])
            start = i


def load_groups(root: Path):
    groups = []
    ridx = reduced_indices()
    for partition in PARTITIONS:
        x_path = root / f"{partition}_Xraw.npy"
        labels = np.load(root / f"{partition}_Y_S.npy", allow_pickle=True).astype(str)
        flows = np.load(root / f"{partition}_Y_F.npy").astype(np.float64)
        x = np.load(x_path, mmap_mode="r")
        if x.shape[1] != 65536:
            raise ValueError(f"unexpected feature width in {x_path}: {x.shape}")
        for ordinal, (start, end, label, flow) in enumerate(contiguous_segments(labels, flows)):
            block = np.asarray(x[start:end], dtype=np.float64)
            full_mean = block.mean(axis=0)
            groups.append({
                "id": f"{partition}:{ordinal}:{start}-{end}",
                "partition": partition,
                "start": start,
                "end": end,
                "label": label,
                "flow": flow,
                "ports": port_bits(label),
                "reduced": full_mean[ridx],
                "full": full_mean,
            })
    return groups


class StandardizedDualRidge:
    def __init__(self, alpha: float = RIDGE_ALPHA):
        self.alpha = alpha

    def fit(self, x: np.ndarray, y: np.ndarray):
        self.x_mean = x.mean(axis=0)
        self.x_scale = x.std(axis=0)
        self.x_scale[self.x_scale < 1e-12] = 1.0
        z = (x - self.x_mean) / self.x_scale
        self.y_mean = y.mean(axis=0)
        yc = y - self.y_mean
        gram = z @ z.T
        self.dual = np.linalg.solve(gram + self.alpha * np.eye(len(z)), yc)
        self.z_train = z
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        z = (x - self.x_mean) / self.x_scale
        return (z @ self.z_train.T) @ self.dual + self.y_mean


class StandardizedNearestNeighbour:
    def fit(self, x: np.ndarray, y: np.ndarray):
        self.mean = x.mean(axis=0)
        self.scale = x.std(axis=0)
        self.scale[self.scale < 1e-12] = 1.0
        self.x = (x - self.mean) / self.scale
        self.y = y
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        z = (x - self.mean) / self.scale
        out = []
        for row in z:
            distances = np.mean((self.x - row) ** 2, axis=1)
            out.append(self.y[int(np.argmin(distances))])
        return np.asarray(out)


def evaluate(name: str, model, x_train, y_train, x_test, test_groups):
    raw = model.fit(x_train, y_train).predict(x_test)
    rows = []
    for group, prediction in zip(test_groups, raw):
        pred_bits = prediction[:6] >= 0.5
        pred_flow = float(np.clip(prediction[6], 1.0, 6.5))
        exact_ports = bool(np.array_equal(pred_bits, group["ports"].astype(bool)))
        abs_error = abs(pred_flow - group["flow"])
        rows.append({
            "group_id": group["id"],
            "actual_ports": group["label"],
            "predicted_ports": bits_label(pred_bits),
            "actual_flow_l_min": group["flow"],
            "predicted_flow_l_min": round(pred_flow, 6),
            "absolute_flow_error_l_min": round(abs_error, 6),
            "exact_ports": exact_ports,
            "within_0_25_l_min": bool(abs_error < 0.25),
            "decision_pass": bool(exact_ports and abs_error < 0.25),
        })
    return {
        "name": name,
        "groups": len(rows),
        "exact_port_groups": sum(r["exact_ports"] for r in rows),
        "flow_groups_within_0_25_l_min": sum(r["within_0_25_l_min"] for r in rows),
        "joint_decision_groups": sum(r["decision_pass"] for r in rows),
        "max_absolute_flow_error_l_min": max(r["absolute_flow_error_l_min"] for r in rows),
        "all_groups_pass": all(r["decision_pass"] for r in rows),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    groups = load_groups(args.data_root)
    train = [g for g in groups if g["label"] not in HOLDOUT_SPARGERS and g["flow"] not in HOLDOUT_FLOWS]
    test = [g for g in groups if g["label"] in HOLDOUT_SPARGERS and g["flow"] in HOLDOUT_FLOWS]
    if not train or not test:
        raise RuntimeError(f"registered split empty: train={len(train)} test={len(test)}")

    y_train = np.stack([np.r_[g["ports"], g["flow"]] for g in train])
    results = []
    for feature, label in (("reduced", "one_ring_1khz"), ("full", "all_rings_all_frequencies")):
        x_train = np.stack([g[feature] for g in train])
        x_test = np.stack([g[feature] for g in test])
        results.append(evaluate(f"ridge_{label}", StandardizedDualRidge(), x_train, y_train, x_test, test))
        results.append(evaluate(f"nearest_neighbour_{label}", StandardizedNearestNeighbour(), x_train, y_train, x_test, test))

    primary = next(r for r in results if r["name"] == "ridge_one_ring_1khz")
    full_ridge = next(r for r in results if r["name"] == "ridge_all_rings_all_frequencies")
    registered_pass = bool(primary["all_groups_pass"] and primary["joint_decision_groups"] >= full_ridge["joint_decision_groups"])
    verdict = (
        "PASS — retrospective reduced-input sufficiency established; no operational or economic consequence established"
        if registered_pass else
        "FAIL — the reduced-input construction did not preserve every registered operating-point decision"
    )
    payload = {
        "schema": "frontier-ignition-bubble-column-v1",
        "source": {
            "doi": "10.5281/zenodo.21773393",
            "data_root": str(args.data_root),
            "array_sha256": {p.name: sha256(p) for p in sorted(args.data_root.glob("*.npy"))},
        },
        "registration": {
            "holdout_spargers": sorted(HOLDOUT_SPARGERS),
            "holdout_flows_l_min": sorted(HOLDOUT_FLOWS),
            "success": "every held-out group has exact port set and absolute flow error <0.25 L/min; no fewer joint passes than full-input ridge",
            "train_groups": len(train),
            "test_groups": len(test),
            "input_coordinates_reduced": 2048,
            "input_coordinates_full": 65536,
            "coordinate_reduction_factor": 32,
        },
        "results": results,
        "registered_pass": registered_pass,
        "verdict": verdict,
        "direct_alternative": {
            "name": "commanded valve state plus Bronkhorst controller reference",
            "archive_role": "defines labels",
            "expected_on_archived_command_and_total_flow_outcome": "exact by construction",
            "unmeasured": "actual per-port delivered flow during obstruction, leak, or valve fault",
        },
        "not_established": [
            "new physical experiment", "fault detection", "operator action", "installed cost reduction",
            "avoided production loss", "buyer acceptance", "adoption", "payment", "complete lifecycle cost",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = [
        "# Registered outcome", "", f"**{verdict}**", "",
        f"Training groups: {len(train)}; registered held-out groups: {len(test)}.", "",
        "| Comparator | Exact ports | Flow < 0.25 L/min | Joint decisions | All groups |",
        "|---|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(f"| {r['name']} | {r['exact_port_groups']}/{r['groups']} | {r['flow_groups_within_0_25_l_min']}/{r['groups']} | {r['joint_decision_groups']}/{r['groups']} | {'yes' if r['all_groups_pass'] else 'no'} |")
    lines += [
        "", "The direct valve/controller alternative defines the archived command-state and total-flow labels and remains stronger for that accepted outcome.",
        "The archive cannot test actual per-port delivery faults, operational action, installed savings, adoption or payment. No flagship or breakthrough claim is admitted from this result alone.",
    ]
    (args.output / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"registered_pass": registered_pass, "verdict": verdict, "test_groups": len(test)}))


if __name__ == "__main__":
    main()
