"""Physical-source-only EIT237: frozen chest-phantom sparse-pattern comparison.

No physical or medical deployment, new native account, paid model call or commerce.
Never use the second repetition to design the first repetition's acquisition rows.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import random
import re
import resource
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

import numpy as np

PARENT = "f0987aa48d5c9136b28540f54eabf5367e63bbe6"
HELPER_COMMIT = "2d39ab38e79578fe8eaabee68cc71ecd648a9165"
HELPER_BLOB = "40cc5428b33e6ad449cdf4b7687f11ea83d12bd5"
SOURCE_SHA = "ad193cd88288e3d6f8ea87f76d8ed2f06382291ab494d55efe08806c65ff994c"
PROTOCOL = "research/eit_chest_sparse237/PROTOCOL.md"
ROWS = 79
COLS = 16
SPARSE_K = 8
FIXED = (0, 10, 20, 30, 40, 50, 60, 70)
SCHEMA = "agi-alpha/eit-chest-sparse237/physical-reanalysis-v1"


class Refusal(ValueError):
    """A failed fixed-input source or scientific acceptance gate."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_helper():
    """Fetch verified, immutable EIT193 code, then import exact helper."""
    url = ("https://raw.githubusercontent.com/MontrealAI/"
           "AGI-Alpha-Invention-Flywheel-Lab/" + HELPER_COMMIT +
           "/tools/eit_inventory_bridge193.py")
    with urlopen(Request(url, headers={"User-Agent": "AGI-ALPHA-EIT237/1"}),
                 timeout=60) as response:
        location = urlsplit(response.geturl())
        if location.scheme != "https" or location.hostname != "raw.githubusercontent.com":
            raise Refusal("EIT237_HELPER_REDIRECT_REJECTED")
        raw = response.read(50_001)
    if not 0 < len(raw) <= 50_000:
        raise Refusal("EIT237_HELPER_SIZE_REJECTED")
    gitblob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if gitblob != HELPER_BLOB:
        raise Refusal("EIT237_ORIGINAL_HELPER_BLOB_CHANGED")
    return raw


def load_helper(raw: bytes, root: Path):
    file = root / "eit_inventory_bridge193.py"
    file.write_bytes(raw)
    spec = importlib.util.spec_from_file_location("eit_inventory_bridge193_pinned", file)
    if spec is None or spec.loader is None:
        raise Refusal("EIT237_HELPER_IMPORT_REFUSED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def read_original_matrices() -> tuple[dict[tuple[str, int], np.ndarray], list[dict]]:
    """Exact original public ZIP and all previous strict original-source gates."""
    with tempfile.TemporaryDirectory(prefix="eit237-chest-original-") as tmp:
        root = Path(tmp)
        helper = load_helper(source_helper(), root)
        pinned = helper.load_exact_modules(root)
        live = pinned["tools.eit_live_source192"]
        inspector = pinned["research.eit_independent190.inspect"]
        manifest = live.read_manifest()
        size, md5 = live.choose_target(manifest)
        if size != 24539080 or md5 != "8514af69c0277f339d5576dd4eb9a598":
            raise Refusal("EIT237_ORIGINAL_MANIFEST_CHANGED")
        archive = root / "official.zip"
        actual_sha = live.get_exact_archive(archive, size, md5)
        if actual_sha != SOURCE_SHA:
            raise Refusal("EIT237_ORIGINAL_ARCHIVE_SHA_CHANGED")
        typed = live.qualify_archive(archive)
        parsed = helper.analyze_genuine_members(archive, typed, inspector.mat_variables)
        if parsed["data_matrices"] != 8 or len(typed["sidecars"]) != 19:
            raise Refusal("EIT237_ORIGINAL_SOURCE_COVERAGE_CHANGED")
        members = parsed["matlab_members"]
        chosen = []
        for entry in members:
            names = {v["name"]: v["shape"] for v in entry.get("variables", [])}
            if "voltages_matrix" in names:
                if (names["voltages_matrix"] != [ROWS, COLS] or
                        names.get("currents_matrix") != [ROWS, COLS]):
                    raise Refusal("EIT237_ORIGINAL_MEASUREMENT_SHAPES_CHANGED")
                chosen.append(entry)
        if len(chosen) != 8:
            raise Refusal("EIT237_ALL_EIGHT_MEASUREMENTS_REQUIRED")
        records = []
        matrices = {}
        with ZipFile(archive) as z:
            for entry in sorted(chosen, key=lambda x: x["member"]):
                name = entry["member"]
                basename = name.rsplit("/", 1)[-1]
                match = re.fullmatch(r"(.+)_([12])\.mat", basename, flags=re.IGNORECASE)
                if not match:
                    raise Refusal("EIT237_EXACT_REPETITION_FILENAME_REQUIRED")
                cls, rep = match.group(1), int(match.group(2))
                if (cls, rep) in matrices:
                    raise Refusal("EIT237_DUPLICATE_PHYSICAL_REPETITION")
                original = z.read(name)
                if sha256(original) != entry["sha256"]:
                    raise Refusal("EIT237_MEMBER_SHA_CHANGED")
                if entry["format"] in ("MATLAB5", "MATLAB4-scipy-validated"):
                    from scipy.io import loadmat
                    value = loadmat(io.BytesIO(original),
                                    variable_names=["voltages_matrix"])["voltages_matrix"]
                elif entry["format"] == "HDF5-v7.3":
                    import h5py
                    with h5py.File(io.BytesIO(original), "r") as h:
                        value = h["voltages_matrix"][:]
                else:
                    raise Refusal("EIT237_UNSUPPORTED_GENUINE_MATRIX_FORMAT")
                matrix = np.asarray(value)
                if (matrix.shape != (ROWS, COLS) or
                        np.iscomplexobj(matrix) or not np.issubdtype(matrix.dtype, np.number)):
                    raise Refusal("EIT237_REAL_ORIENTATION_SHAPE_REQUIRED")
                matrix = np.asarray(matrix, dtype=np.float64)
                if not np.isfinite(matrix).all():
                    raise Refusal("EIT237_NONFINITE_PHYSICAL_VOLTAGE")
                matrices[(cls, rep)] = matrix
                records.append({"member": name, "original_sha256": entry["sha256"],
                                "numeric_sha256": sha256(matrix.astype("<f8").tobytes()),
                                "shape": [ROWS, COLS], "repetition": rep})
        validate_matrices(matrices)
        return matrices, records


def validate_matrices(data: dict) -> tuple[str, ...]:
    if not isinstance(data, dict) or len(data) != 8:
        raise Refusal("EIT237_EIGHT_FIXED_RECORDS_REQUIRED")
    labels = tuple(sorted({k[0] for k in data
                           if isinstance(k, tuple) and len(k) == 2
                           and isinstance(k[0], str) and k[0]}))
    if len(labels) != 4 or set(data) != {(c, r) for c in labels for r in (1, 2)}:
        raise Refusal("EIT237_FOUR_EXACT_REPETITION_PAIRS_REQUIRED")
    for m in data.values():
        if (not isinstance(m, np.ndarray) or m.shape != (ROWS, COLS)
                or np.iscomplexobj(m) or not np.issubdtype(m.dtype, np.number)
                or not np.isfinite(m).all()):
            raise Refusal("EIT237_SOURCE_ARRAY_INVALID")
    return labels


def choose_greedy_rows(train: dict[str, np.ndarray]) -> tuple[int, ...]:
    """Max-min separation over SIX pairs, using training only, k=8."""
    labels = sorted(train)
    if len(labels) != 4:
        raise Refusal("EIT237_FOUR_TRAINING_CLASSES_REQUIRED")
    pairwise = []
    for i in range(4):
        for j in range(i+1, 4):
            pairwise.append(np.sum(
                (train[labels[i]] - train[labels[j]]) ** 2, axis=1))
    pairwise = np.array(pairwise)
    if pairwise.shape != (6, ROWS) or not np.isfinite(pairwise).all():
        raise Refusal("EIT237_TRAINING_DISTANCES_INVALID")
    used, cumulative = [], np.zeros(6, dtype=np.float64)
    for _ in range(SPARSE_K):
        best, best_value = None, -math.inf
        for row in range(ROWS):
            if row in used:
                continue
            value = float(np.min(cumulative + pairwise[:, row]))
            if value > best_value:
                best, best_value = row, value
        if best is None or not math.isfinite(best_value):
            raise Refusal("EIT237_GREEDY_SELECTION_INVALID")
        used.append(best)
        cumulative += pairwise[:, best]
    return tuple(sorted(used))


def classify(templates: dict[str, np.ndarray], observation: np.ndarray,
             selected: tuple[int, ...]) -> tuple[str, float]:
    ds = []
    for label in sorted(templates):
        diff = observation[list(selected)] - templates[label][list(selected)]
        distance = float(np.sum(diff * diff))
        if not math.isfinite(distance):
            raise Refusal("EIT237_NONFINITE_CLASSIFICATION_DISTANCE")
        ds.append((distance, label))
    ds.sort(key=lambda x: (x[0], x[1]))
    return ds[0][1], ds[1][0] - ds[0][0]


def evaluate(data: dict) -> dict:
    labels = validate_matrices(data)
    all_results = {p: [] for p in ("greedy8", "full79", "fixed8", "random8")}
    selected_by_fold = {}
    for trainrep, testrep in ((1, 2), (2, 1)):
        train = {name: data[(name, trainrep)] for name in labels}
        selected = {
            "greedy8": choose_greedy_rows(train),
            "full79": tuple(range(ROWS)),
            "fixed8": FIXED,
            "random8": tuple(sorted(random.Random(237).sample(range(ROWS), 8))),
        }
        selected_by_fold[f"{trainrep}_to_{testrep}"] = {
            k: list(v) for k, v in selected.items() if k != "full79"}
        for arm, rows in selected.items():
            for name in labels:
                predicted, margin = classify(train, data[(name, testrep)], rows)
                all_results[arm].append({
                    "train_repetition": trainrep, "test_repetition": testrep,
                    "true_label": name, "predicted_label": predicted,
                    "correct": predicted == name,
                    "nearest_margin_squared": margin,
                })
    for arm in all_results:
        if len(all_results[arm]) != 8:
            raise Refusal("EIT237_FROZEN_EIGHT_CASE_DENOMINATOR_CHANGED")
    complete = all(a["correct"] and a["nearest_margin_squared"] > 0 and
                   a["predicted_label"] == b["predicted_label"]
                   for a, b in zip(all_results["greedy8"], all_results["full79"]))
    return {
        "class_labels_from_original_public_filenames": list(labels),
        "selected_patterns_by_fold": selected_by_fold,
        "arms": {name: {
            "correct": sum(x["correct"] for x in records),
            "denominator": 8,
            "minimum_squared_distance_margin": min(
                x["nearest_margin_squared"] for x in records),
            "all_predictions": records,
        } for name, records in all_results.items()},
        "registered_sparse_criterion_met": bool(complete),
    }


def run(public_out: Path, failure_out: Path) -> dict:
    if public_out.exists() or public_out.is_symlink() or failure_out.exists() or failure_out.is_symlink():
        raise FileExistsError("EIT237_CREATE_ONLY_PUBLIC_RECEIPTS")
    start = time.perf_counter()
    begin = resource.getrusage(resource.RUSAGE_SELF)
    try:
        protocol = Path(PROTOCOL).read_bytes()
        matrices, member_receipts = read_original_matrices()
        result = evaluate(matrices)
        end = resource.getrusage(resource.RUSAGE_SELF)
        result.update({
            "schema": SCHEMA,
            "precode_freeze": "30cb329be1530478ec3142cde39399a9c3ff3361",
            "protocol_sha256": sha256(protocol),
            "parent_main": PARENT,
            "original_archive_sha256": SOURCE_SHA,
            "original_EIT193_helper_commit": HELPER_COMMIT,
            "original_EIT193_helper_blob": HELPER_BLOB,
            "source_member_receipts": member_receipts,
            "measured_wall_seconds": round(time.perf_counter() - start, 6),
            "measured_process_cpu_seconds": round(
                end.ru_utime + end.ru_stime - begin.ru_utime - begin.ru_stime, 6),
            "measured_max_rss_kib": end.ru_maxrss,
            "complete_host_and_model_bill_usd": None,
            "external_paid_collections_usd": 0,
            "physical_eight_pattern_measurement_performed": False,
            "independent_property_truth_validated": False,
            "actual_economic_advantage_proven": False,
            "decision": "HOLD_NO_BID_NO_DEPLOY",
        })
        with public_out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        return result
    except Exception as exc:
        failure = {
            "schema": SCHEMA, "status": "FAILED",
            "exception_type": type(exc).__name__,
            "reason_code": str(exc) if isinstance(exc, Refusal) else "UNCLASSIFIED_FAILURE",
            "source_archive_sha256": SOURCE_SHA, "decision": "HOLD_NO_BID_NO_DEPLOY",
        }
        with failure_out.open("x", encoding="utf-8") as f:
            json.dump(failure, f, indent=2, sort_keys=True)
            f.write("\n")
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--public", required=True, type=Path)
    p.add_argument("--failure", required=True, type=Path)
    a = p.parse_args(argv)
    outcome = run(a.public, a.failure)
    print(json.dumps({
        "criterion": outcome["registered_sparse_criterion_met"],
        "greedy8_correct": outcome["arms"]["greedy8"]["correct"],
        "full79_correct": outcome["arms"]["full79"]["correct"],
        "fixed8_correct": outcome["arms"]["fixed8"]["correct"],
        "random8_correct": outcome["arms"]["random8"]["correct"],
        "source_sha256": SOURCE_SHA, "physical_construction": False,
        "commercial_collections_usd": 0, "decision": outcome["decision"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
