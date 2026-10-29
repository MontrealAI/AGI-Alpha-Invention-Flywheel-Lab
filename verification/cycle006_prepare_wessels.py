"""Protected all-cell Wessels raw-count pilot with control-only readout selection."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import h5py
import numpy as np

SOURCE_SHA = "5da0485aed81b23bda57b4a7b4510a394682d54911416db89b4846ff6dd34732"
SOURCE_MD5 = "6897bfdcda928a678208fecf4eeb282e"
SALT = "cycle006-wessels-raw-prospective-pair-v1"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write("\n")


def decode(values):
    return [value.decode() if isinstance(value, bytes) else str(value) for value in values]


def prepare(source, public, private):
    started, cpu = time.monotonic(), time.process_time()
    if sha(source) != SOURCE_SHA:
        raise ValueError("RAW_WESSELS_SOURCE_IDENTITY_MISMATCH")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    with h5py.File(source, "r") as data:
        names = decode(data["var/gene_symbol"][:])
        categories = decode(data["obs/perturbation/categories"][:])
        codes = np.asarray(data["obs/perturbation/codes"][:], dtype=np.int64)
        shape = tuple(int(value) for value in data["X"].attrs["shape"])
        if shape != (30707, 21052) or len(names) != shape[1] or len(set(names)) != len(names) or len(codes) != shape[0]:
            raise ValueError("RAW_WESSELS_AXIS_SCOPE")
        if (codes < 0).any() or (codes >= len(categories)).any() or categories.count("control") != 1:
            raise ValueError("RAW_WESSELS_CONDITION_SCOPE")
        singles = {label for label in categories if label != "control" and "_" not in label}
        pairs_by_label = {}
        canonical_categories = []
        for label in categories:
            if label == "control" or label in singles:
                canonical_categories.append(label)
            else:
                pieces = label.split("_")
                if len(pieces) != 2 or len(set(pieces)) != 2 or not set(pieces) <= singles:
                    raise ValueError("RAW_WESSELS_MISSING_SINGLE_OR_PAIR_SCOPE")
                pair = "+".join(sorted(pieces))
                pairs_by_label[label] = pair
                canonical_categories.append(pair)
        pair_ids = sorted(set(pairs_by_label.values()))
        if len(pair_ids) != 158 or len(singles) != 28:
            raise ValueError("RAW_WESSELS_EXPECTED_CONDITION_SET")
        ordering = sorted(pair_ids, key=lambda pair: hashlib.sha256((SOURCE_SHA + "|" + SALT + "|" + pair).encode()).hexdigest())
        development, heldout = ordering[:100], ordering[100:]
        partition = {"source_sha256": SOURCE_SHA, "salt": SALT, "development_pairs": development, "heldout_pairs": heldout,
            "rule": "Pair labels only; canonicalize labels and pool cells before means. First100 development, remaining58 protected. No X numerical values inspected before writing this record.",
            "status": "FROZEN_BEFORE_ANY_COUNT_READ"}
        write(public / "PARTITION_BEFORE_OUTCOMES.json", partition)
        groups = sorted(set(canonical_categories))
        group_index = {label: index for index, label in enumerate(groups)}
        row_groups = np.asarray([group_index[canonical_categories[code]] for code in codes], dtype=np.int64)
        group_counts = np.bincount(row_groups, minlength=len(groups))
        if (group_counts <= 0).any() or int(group_counts.sum()) != shape[0]:
            raise ValueError("RAW_WESSELS_EMPTY_OR_LOST_COHORT")
        pointers = np.asarray(data["X/indptr"][:], dtype=np.int64)
        if len(pointers) != shape[0] + 1 or pointers[0] != 0 or pointers[-1] != len(data["X/data"]) or (np.diff(pointers) < 0).any():
            raise ValueError("RAW_WESSELS_CSR_SCOPE")
        control_rows = np.where(row_groups == group_index["control"])[0]
        control_sum = np.zeros(shape[1], dtype=np.float64)
        zero_library_cells = 0
        for row in control_rows:
            first, last = int(pointers[row]), int(pointers[row + 1])
            values = np.asarray(data["X/data"][first:last], dtype=np.float64)
            indices = np.asarray(data["X/indices"][first:last], dtype=np.int64)
            if (values < 0).any() or not np.isfinite(values).all() or (indices < 0).any() or (indices >= shape[1]).any() or (np.diff(indices) <= 0).any():
                raise ValueError("RAW_WESSELS_NONCANONICAL_CONTROL_CSR")
            total = values.sum()
            if total:
                np.add.at(control_sum, indices, np.log1p(values * (10000.0 / total)))
        control_mean = control_sum / len(control_rows)
        top = sorted(range(shape[1]), key=lambda index: (-control_mean[index], names[index]))[:1000]
        selected = sorted(top, key=lambda index: names[index])
        panel_names = np.asarray([names[index] for index in selected])
        to_panel = np.full(shape[1], -1, dtype=np.int64)
        to_panel[selected] = np.arange(1000)
        sums = np.zeros((len(groups), 1000), dtype=np.float64)
        for start in range(0, shape[0], 512):
            stop = min(start + 512, shape[0])
            first, last = int(pointers[start]), int(pointers[stop])
            values = np.asarray(data["X/data"][first:last], dtype=np.float64)
            indices = np.asarray(data["X/indices"][first:last], dtype=np.int64)
            lengths = np.diff(pointers[start:stop + 1])
            row_ids = np.repeat(np.arange(stop - start), lengths)
            if (values < 0).any() or not np.isfinite(values).all() or (indices < 0).any() or (indices >= shape[1]).any():
                raise ValueError("RAW_WESSELS_INVALID_COUNTS_OR_INDEX")
            differences = np.diff(indices)
            boundaries = np.cumsum(lengths)[:-1] - 1
            boundaries = boundaries[(boundaries >= 0) & (boundaries < len(differences))]
            differences[boundaries] = 1
            if (differences <= 0).any():
                raise ValueError("RAW_WESSELS_NONCANONICAL_CSR")
            totals = np.bincount(row_ids, weights=values, minlength=stop - start)
            zero_library_cells += int((totals == 0).sum())
            factors = np.divide(10000.0, totals, out=np.zeros_like(totals), where=totals != 0)
            normalized = np.log1p(values * factors[row_ids])
            panel_ids = to_panel[indices]
            mask = panel_ids >= 0
            joint = row_groups[start:stop][row_ids[mask]] * 1000 + panel_ids[mask]
            sums += np.bincount(joint, weights=normalized[mask], minlength=len(groups) * 1000).reshape(len(groups), 1000)
        means = sums / group_counts[:, None]
        if not np.allclose(means[group_index["control"]], control_mean[selected], rtol=1e-10, atol=1e-12):
            raise ValueError("CONTROL_TWO_PASS_NORMALIZATION_DISAGREEMENT")
    def arrays(pairs):
        components = [pair.split("+") for pair in pairs]
        return {"pairs": np.asarray(pairs), "genes": panel_names,
            "A": np.asarray([means[group_index[pieces[0]]] for pieces in components]),
            "B": np.asarray([means[group_index[pieces[1]]] for pieces in components]),
            "ctrl": np.repeat(means[group_index["control"]][None, :], len(pairs), axis=0),
            "AB": np.asarray([means[group_index[pair]] for pair in pairs])}
    dev, protected = arrays(development), arrays(heldout)
    dev["fit_indices"], dev["calibration_indices"] = np.arange(75), np.arange(75, 100)
    np.savez_compressed(public / "development.npz", **dev)
    np.savez_compressed(public / "heldout_features.npz", **{key: value for key, value in protected.items() if key != "AB"})
    np.savez_compressed(private / "heldout_truth.npz", **protected)
    report = {"schema": "agi-alpha-cycle006-wessels-protected-raw-pilot/v1", "source_sha256": SOURCE_SHA,
        "source_md5": SOURCE_MD5, "source_bytes": source.stat().st_size, "verifier_source_sha256": sha(Path(__file__)),
        "source_url": "https://zenodo.org/records/13350497/files/WesselsSatija2023.h5ad",
        "cell_line": "THP-1", "celltype": "monocytes", "perturbation_modality": "human CRISPR-cas13",
        "all_cells": shape[0], "all_genes_used_for_library_normalization": shape[1], "selected_control_only_readouts": 1000,
        "control_cells": len(control_rows), "zero_library_cells_retained_as_zero": zero_library_cells,
        "group_cell_counts": {name: int(group_counts[group_index[name]]) for name in groups},
        "development_pairs": development, "heldout_pairs": heldout,
        "partition_before_count_read_sha256": sha(public / "PARTITION_BEFORE_OUTCOMES.json"),
        "public_files": {name: sha(public / name) for name in ("development.npz", "heldout_features.npz")},
        "protected_truth_sha256": sha(private / "heldout_truth.npz"),
        "preprocessing": "All cells, all genes contribute per-cell library normalization to10000 then log1p; mean normalized expression by canonical condition. Canonical label duplicates pool cells before means. Top1000 genes selected from CONTROLmean only, tiesalphabetic; exported geneaxis alphabetic. No AB-dependent gene selection or arbitrary cell truncation.",
        "changed_boundary": "Distinct raw THP-1 CRISPR-cas13 analysis, not NormanK562CRISPRa and not parity with the authors laterQC/downsampling/HVG/S3publishedbenchmark. Refit coordinates and outputcoefficients on this family; only qualified generative mechanisms may transfer.",
        "limits": ["Raw158pairs differs from published157processed pair count; no benchmark-equivalence claim", "No biologicalreplicate or clinical inference; cells and readoutgenes share conditions/library normalization", "Builder cannot read rawX/originalAB or verifier privateoutcomes; samehost/model procedural protection only"],
        "resources": {"wall_seconds": time.monotonic() - started, "process_cpu_seconds": time.process_time() - cpu},
        "status": "FRESH_FAMILY_SPLIT_FROZEN; heldoutpredictiveoutcomesunrun"}
    write(public / "SPLIT.json", report)
    write(private / "PRIVATE_LOCATION.json", {"truth": str(private / "heldout_truth.npz"), "source_sha256": SOURCE_SHA, "public_split_sha256": sha(public / "SPLIT.json"), "protected_truth_sha256": report["protected_truth_sha256"]})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.public, args.private)
    print(json.dumps({"public": str(args.public), "development_pairs": len(report["development_pairs"]), "heldout_pairs": len(report["heldout_pairs"]), "source_sha256": report["source_sha256"]}))
