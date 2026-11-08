#!/usr/bin/env python3
"""Render the two protocol-first test fields from retained, verified masks.

Authoring only: this script performs no model inference, parameter search,
selection by quality, or metric calculation. Both complete reproductions must
already exist. The official first BBBC039 test field and the first registered
BBBC007 test field are fixed by order, not chosen using their scores.

Run in the registered numeric environment plus requirements-figures.txt:
    python3 -B construction/figures.py --cache /absolute/public-data \
        --classical /absolute/classical-projection \
        --incumbent /absolute/incumbent --output /absolute/new/figures

The output is a publication PNG plus a provenance receipt. Original image,
reference, prediction, and numeric result bytes are never modified. The output
directory must be new, so a replacement proof cannot silently overwrite one.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from skimage.segmentation import find_boundaries

import builder
import data


HERE = Path(__file__).resolve().parent
EXPECTED_SOURCE = "IXMtest_A09_s1_w1CE70AD49-290D-4312-82E6-CDC717F32637"
EXPECTED_SUCCESSOR = "f113/AS_09125_040701150004_A02f00"
OUTPUT_NAME = "protocol-first-fields.png"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    return data.sha256(Path(path))


def mask_record(root, relative, case):
    """Load only the fixed field's mask record; do not read field scores."""
    cohort = root / relative
    manifest_path = cohort / "MASKS.json"
    manifest = read_json(manifest_path)
    record = manifest[case.name]
    mask_path = (cohort / record["path"]).resolve()
    require(mask_path.is_relative_to(cohort.resolve()), "Mask path escapes its cohort")
    require(sha256(mask_path) == record["sha256"], "Mask file digest differs from receipt")
    with Image.open(mask_path) as image:
        labels = np.asarray(image).copy()
    require(labels.ndim == 2 and labels.shape == case.truth.shape, "Mask geometry differs")
    require(labels.dtype.kind in "ui", "Expected integer instance labels")
    require(builder.label_array_hash(labels) == record["label_array_sha256"],
            "Mask pixel digest differs from receipt")
    require(builder.label_array_hash(case.truth) == record["reference_label_array_sha256"],
            "Decoded reference differs from experiment")
    require(case.sources == record["sources"], "Observation or reference source differs")
    receipt = {
        "cohort": relative,
        "manifest_sha256": sha256(manifest_path),
        "mask_path": record["path"],
        "mask_sha256": record["sha256"],
        "label_array_sha256": record["label_array_sha256"],
    }
    return labels, receipt


def display_channel(value):
    """Fixed per-channel 1st--99th percentile display contrast, linear/clipped."""
    value = np.asarray(value)
    require(value.ndim == 2 and np.isfinite(value).all(), "Invalid scalar observation")
    low, high = np.percentile(value, [1, 99], method="linear")
    require(high > low, "Selected observation has no display range")
    shown = np.clip((value.astype(np.float64) - low) / (high - low), 0, 1)
    return shown, {"lower_percentile": 1, "upper_percentile": 99,
                   "lower_value": float(low), "upper_value": float(high),
                   "percentile_method": "linear", "gamma": 1.0,
                   "applied_to": "display only; never instrument input or scoring"}


def label_rgb(labels, namespace):
    """Categorical display colors are deliberately unrelated across panels."""
    ids = np.unique(labels)
    colors = np.zeros((int(ids.max(initial=0)) + 1, 3), dtype=np.float64)
    for object_id in ids[ids > 0]:
        digest = hashlib.sha256(f"{namespace}/{int(object_id)}".encode()).digest()
        hue = int.from_bytes(digest[:4], "big") / 2**32
        colors[int(object_id)] = colorsys.hsv_to_rgb(hue, 0.60, 0.94)
    shown = colors[labels]
    shown[find_boundaries(labels, mode="inner", background=0)] = (0.97, 0.97, 0.97)
    return shown


def render(panel_rows, output):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
                         "savefig.facecolor": "white"})
    fig = plt.figure(figsize=(7.0, 4.65), dpi=300, facecolor="white")
    lefts = [0.035, 0.278, 0.521, 0.764]
    width = 0.218
    for x, heading in zip(lefts, ("Observation", "Reference", "Classical", "Pretrained")):
        fig.text(x + width / 2, 0.965, heading, ha="center", va="top",
                 fontsize=9, weight="bold", color="#201529")
    for index, panels in enumerate(panel_rows):
        title = ("A   Nuclei · first official BBBC039 test field" if index == 0
                 else "B   Cell bodies · first registered BBBC007 test field")
        fig.text(0.035, 0.897 if index == 0 else 0.493, title,
                 va="top", fontsize=8.5, weight="bold", color="#482A50")
        bottom, height = ((0.574, 0.284) if index == 0 else (0.097, 0.355))
        for x, panel in zip(lefts, panels):
            ax = fig.add_axes([x, bottom, width, height])
            ax.imshow(panel, cmap="gray" if panel.ndim == 2 else None,
                      vmin=0, vmax=1, interpolation="nearest", aspect="equal")
            ax.set_axis_off()
    fig.text(0.035, 0.030, "Observation: A, DNA in gray; B, DNA in cyan and actin in magenta.",
             fontsize=7, color="#655F6A")
    fig.savefig(output / OUTPUT_NAME, dpi=300,
                metadata={"Title": "Learning to Build: protocol-first test fields",
                          "Description": "Display-only comparison; see protocol-first-fields.json."})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--classical", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new figure output directory")
    protocol_path = HERE / "PROTOCOL-amendment-2.json"
    protocol = read_json(protocol_path)
    archives = data.verify_archives(args.cache, protocol["data"]["archives"])
    first_source = data.metadata039(args.cache)["test"][0]
    first_successor = protocol["data"]["bbbc007"]["test_ids"][0]
    require(Path(first_source).stem == EXPECTED_SOURCE, "Official source test order changed")
    require(first_successor == EXPECTED_SUCCESSOR, "Registered successor test order changed")
    results = {}
    for name, root in (("classical", args.classical), ("pretrained", args.incumbent)):
        result_path = root / "RESULTS.json"
        require(read_json(result_path)["status"] == "COMPLETE", f"{name} run is incomplete")
        results[name] = {"results_sha256": sha256(result_path)}
    cases = [data.load039(args.cache, "test", [first_source])[0],
             data.load007(args.cache, [first_successor])[0]]
    panel_rows, field_receipts = [], []
    for index, case in enumerate(cases):
        classical_cohort = ("source/test" if index == 0
                            else "successor/updated_no_artifact/holdout")
        pretrained_cohort = "source/test" if index == 0 else "successor/test"
        classical, classical_receipt = mask_record(args.classical, classical_cohort, case)
        pretrained, pretrained_receipt = mask_record(args.incumbent, pretrained_cohort, case)
        dna, dna_display = display_channel(case.dna)
        displays = {"dna": dna_display}
        if case.actin is None:
            observation = dna
        else:
            actin, actin_display = display_channel(case.actin)
            displays["actin"] = actin_display
            observation = np.stack([actin, dna, np.maximum(dna, actin)], axis=-1)
        panel_rows.append([observation, label_rgb(case.truth, case.name + "/reference"),
                           label_rgb(classical, case.name + "/classical"),
                           label_rgb(pretrained, case.name + "/pretrained")])
        field_receipts.append({"field": case.name, "shape": list(case.truth.shape),
                               "selection": "first in declared test order, without using scores",
                               "sources": case.sources, "display": displays,
                               "reference_label_array_sha256": builder.label_array_hash(case.truth),
                               "classical": classical_receipt, "pretrained": pretrained_receipt})
    args.output.mkdir(parents=True)
    render(panel_rows, args.output)
    receipt = {
        "schema": "learning-to-build/scientific-figure/v1",
        "status": "RENDERED_FROM_RETAINED_MASKS",
        "figure": {"path": OUTPUT_NAME, "sha256": sha256(args.output / OUTPUT_NAME)},
        "authoring_source_sha256": sha256(Path(__file__)),
        "registered_protocol_sha256": sha256(protocol_path),
        "archives": archives, "results": results, "fields": field_receipts,
        "runtime": {"python": platform.python_version(),
                    **{name: importlib.metadata.version(name) for name in
                       ("numpy", "Pillow", "scipy", "scikit-image", "matplotlib")}},
        "display_scope": {
            "geometry": "full field, no crop; equal aspect; nearest display sampling",
            "raw_observations": "frozen data.load039/load007 and registered scalar adapter",
            "contrast": "1st to 99th percentile independently per channel; linear, clipped; display only",
            "instance_colors": "SHA-256-derived categorical colors per panel; no label correspondence implied",
            "borders": "white inner instance boundaries for visibility; recorded masks remain unchanged",
            "reference": "registered decoded masks, including the BBBC007 complete-in-frame convention",
            "interpretation": "two ordered examples, not cohort evidence or a qualification decision",
        },
    }
    (args.output / "protocol-first-fields.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "output": str(args.output),
                      "fields": [row["field"] for row in field_receipts]}, sort_keys=True))


if __name__ == "__main__":
    main()
