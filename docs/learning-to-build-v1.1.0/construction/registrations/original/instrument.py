#!/usr/bin/env python3
"""A bounded, inspectable classical microscopy measurement instrument.

The operators and the 24-recipe grammar are supplied by the authors.  An
emitted instrument binds one recipe, one task and these exact program bytes.
Measurements are in pixels; this program does not infer physical scale or
make biological, diagnostic, clinical or laboratory-certification claims.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import itertools
import json
from pathlib import Path
import shutil
import time

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.filters import threshold_li, threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import remove_small_objects
from skimage.segmentation import watershed


SCHEMA = "learning-to-build/microscopy-instrument/v1"
PARAMETERS = {
    "normalization_percentiles": [1.0, 99.8],
    "background_opening_square_side_pixels": 31,
    "gaussian_sigma": 1.0,
    "minimum_object_area_pixels": 20,
    "fill_holes": True,
    "foreground_connectivity": 2,
    "seed_totality_connectivity": 1,
    "peak_exclude_border": False,
    "cell_mask_closing_square_side_pixels": 3,
    "cell_border_policy": "exclude_complete_labels_touching_the_image_frame",
    "watershed_connectivity": 1,
    "watershed_compactness": 0.0,
    "measurement_units": "pixels",
}


@dataclass(frozen=True)
class Recipe:
    id: str
    background: str
    threshold: str
    seed_distance: int
    watershed_surface: str


def recipes() -> list[Recipe]:
    combinations = itertools.product(("none", "opening"), ("li", "otsu"),
                                     (4, 7, 10), ("distance", "intensity"))
    return [Recipe(f"r{index:02d}", *values) for index, values in enumerate(combinations)]


RECIPE_MAP = {recipe.id: recipe for recipe in recipes()}


def recipe_from_dict(value: dict) -> Recipe:
    if not isinstance(value, dict) or set(value) != set(Recipe.__dataclass_fields__):
        raise ValueError("Unexpected recipe fields")
    if (any(type(value[key]) is not str for key in ("id", "background", "threshold", "watershed_surface"))
            or type(value["seed_distance"]) is not int):
        raise ValueError("Recipe parameters have unsupported types")
    recipe = Recipe(**value)
    if recipe.id not in RECIPE_MAP or asdict(RECIPE_MAP[recipe.id]) != value:
        raise ValueError("Recipe is outside the frozen 24-candidate grammar")
    return recipe


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def bank_hash() -> str:
    return canonical_hash({"recipes": [asdict(r) for r in recipes()], "parameters": PARAMETERS})


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(text: str) -> object:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)


def _validated_pixels(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 2 or min(array.shape, default=0) < 3:
        raise ValueError(f"{name} must be a two-dimensional image of at least 3x3 pixels")
    if array.dtype.kind not in "uif" or not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError(f"{name} must contain finite nonnegative numeric pixels")
    return array.astype(np.float64, copy=False)


def _normalized(value: np.ndarray) -> np.ndarray:
    low, high = np.percentile(value, PARAMETERS["normalization_percentiles"])
    if high <= low:
        return np.zeros(value.shape, dtype=np.float64)
    return np.clip((value - low) / (high - low), 0.0, 1.0)


def _prepared(value: np.ndarray, recipe: Recipe) -> np.ndarray:
    work = _normalized(value)
    if recipe.background == "opening":
        size = PARAMETERS["background_opening_square_side_pixels"]
        work = np.maximum(work - ndi.grey_opening(work, size=(size, size), mode="reflect"), 0.0)
    return ndi.gaussian_filter(work, PARAMETERS["gaussian_sigma"], mode="reflect")


def _foreground(work: np.ndarray, recipe: Recipe) -> np.ndarray:
    if float(np.max(work)) <= float(np.min(work)):
        return np.zeros(work.shape, dtype=bool)
    cutoff = threshold_li(work) if recipe.threshold == "li" else threshold_otsu(work)
    if not np.isfinite(cutoff):
        raise ValueError("Threshold calculation returned a non-finite cutoff")
    foreground = remove_small_objects(work > cutoff,
                                      min_size=PARAMETERS["minimum_object_area_pixels"],
                                      connectivity=PARAMETERS["foreground_connectivity"])
    return ndi.binary_fill_holes(foreground)


def _relabel(value: np.ndarray) -> np.ndarray:
    ids = np.unique(value)
    ids = ids[ids > 0]
    if not len(ids):
        return np.zeros(value.shape, dtype=np.int32)
    result = np.zeros(value.shape, dtype=np.int32)
    foreground = value > 0
    result[foreground] = np.searchsorted(ids, value[foreground]) + 1
    return result


def segment_nuclei(dna: np.ndarray, recipe: Recipe) -> np.ndarray:
    dna = _validated_pixels(dna, "DNA")
    work = _prepared(dna, recipe)
    foreground = _foreground(work, recipe)
    if not foreground.any():
        return np.zeros(dna.shape, dtype=np.int32)
    distance = ndi.distance_transform_edt(foreground)
    locations = peak_local_max(distance, min_distance=recipe.seed_distance,
                               labels=foreground.astype(np.uint8), exclude_border=False)
    markers = np.zeros(dna.shape, dtype=np.int32)
    for index, (row, column) in enumerate(locations, start=1):
        markers[row, column] = index
    # Every disconnected foreground component needs a seed, even if a nearby
    # component suppressed its local maximum.  This is a fixed totality rule.
    components, number = ndi.label(foreground, structure=ndi.generate_binary_structure(2, 1))
    next_marker = int(markers.max()) + 1
    seeded = set(int(v) for v in np.unique(components[markers > 0]))
    for component in (i for i in range(1, number + 1) if i not in seeded):
        region = components == component
        positions = np.flatnonzero(region)
        best = positions[int(np.argmax(distance.ravel()[positions]))]
        markers.ravel()[best] = next_marker
        next_marker += 1
    surface = -distance if recipe.watershed_surface == "distance" else -work
    result = watershed(surface, markers=markers, mask=foreground, connectivity=1,
                       compactness=0.0, watershed_line=False)
    sizes = np.bincount(result.ravel())
    too_small = sizes < PARAMETERS["minimum_object_area_pixels"]
    too_small[0] = False
    result[too_small[result]] = 0
    return _relabel(result)


def exclude_frame_objects(labels: np.ndarray) -> np.ndarray:
    result = labels.copy()
    border_ids = np.unique(np.concatenate((result[0], result[-1], result[:, 0], result[:, -1])))
    result[np.isin(result, border_ids[border_ids > 0])] = 0
    return _relabel(result)


def segment_cells(dna: np.ndarray, actin: np.ndarray, recipe: Recipe,
                  nucleus_labels: np.ndarray | None = None,
                  foreground_override: np.ndarray | None = None) -> np.ndarray:
    """Raw-channel seeded watershed; overrides are for labelled diagnostics.

    Primary operation obtains all seeds from the measured DNA image and all
    foreground from the measured actin image.  No reference annotations enter
    that path.  The optional arguments allow a separate reference-input
    diagnostic without pretending it is a raw-channel instrument.
    """
    dna = _validated_pixels(dna, "DNA")
    actin = _validated_pixels(actin, "actin")
    if dna.shape != actin.shape:
        raise ValueError("DNA and actin image shapes differ")
    if nucleus_labels is None:
        nucleus_labels = segment_nuclei(dna, recipe)
    else:
        nucleus_labels = np.asarray(nucleus_labels)
        if (nucleus_labels.shape != dna.shape or nucleus_labels.dtype.kind not in "iu"
                or np.any(nucleus_labels < 0)):
            raise ValueError("Nucleus labels must be nonnegative integers matching the input shape")
        nucleus_labels = _relabel(nucleus_labels)
    if not np.any(nucleus_labels):
        return np.zeros(dna.shape, dtype=np.int32)
    work = _prepared(actin, recipe)
    if foreground_override is None:
        foreground = _foreground(work, recipe) | (nucleus_labels > 0)
        width = PARAMETERS["cell_mask_closing_square_side_pixels"]
        foreground = ndi.binary_closing(foreground, structure=np.ones((width, width)), border_value=0)
        foreground = ndi.binary_fill_holes(foreground) | (nucleus_labels > 0)
    else:
        foreground = np.asarray(foreground_override, dtype=bool)
        if foreground.shape != dna.shape:
            raise ValueError("Diagnostic foreground shape mismatch")
        nucleus_labels = nucleus_labels.copy()
        nucleus_labels[~foreground] = 0
    distance = ndi.distance_transform_edt(foreground)
    surface = -distance if recipe.watershed_surface == "distance" else -work
    result = watershed(surface, markers=nucleus_labels, mask=foreground,
                       connectivity=1, compactness=0.0, watershed_line=False)
    return exclude_frame_objects(_relabel(result))


def apply(dna: np.ndarray, recipe: Recipe, task: str,
          actin: np.ndarray | None = None) -> np.ndarray:
    if task == "nuclei":
        return segment_nuclei(dna, recipe)
    if task == "cells":
        if actin is None:
            raise ValueError("The whole-cell instrument requires an actin channel")
        return segment_cells(dna, actin, recipe)
    raise ValueError(f"Unknown measurement task: {task}")


MEASUREMENT_FIELDS = ["label", "area_pixels", "centroid_row", "centroid_column",
                      "perimeter_pixels", "equivalent_diameter_pixels", "eccentricity",
                      "major_axis_length_pixels", "minor_axis_length_pixels"]


def measurements(labels: np.ndarray) -> list[dict]:
    result = []
    for region in regionprops(labels):
        result.append({"label": int(region.label), "area_pixels": int(region.area),
                       "centroid_row": float(region.centroid[0]),
                       "centroid_column": float(region.centroid[1]),
                       "perimeter_pixels": float(region.perimeter),
                       "equivalent_diameter_pixels": float(region.equivalent_diameter_area),
                       "eccentricity": float(region.eccentricity),
                       "major_axis_length_pixels": float(region.axis_major_length),
                       "minor_axis_length_pixels": float(region.axis_minor_length)})
    return result


def save_labels(path: Path, labels: np.ndarray) -> str:
    if int(labels.max(initial=0)) >= 65536:
        raise ValueError("16-bit output format cannot represent this many instances")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(labels.astype(np.uint16)).save(path, format="PNG")
    return file_hash(path)


def write_measurements(path: Path, rows: list[dict], field: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (["field"] if field is not None else []) + MEASUREMENT_FIELDS
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(({"field": field} | row) if field is not None else row)


def emit(directory: Path, recipe: Recipe, task: str, provenance: dict) -> dict:
    recipe_from_dict(asdict(recipe))
    if task not in ("nuclei", "cells"):
        raise ValueError("Unsupported emitted measurement task")
    directory.mkdir(parents=True, exist_ok=False)
    program = directory / "instrument.py"
    shutil.copyfile(Path(__file__), program)
    result = {"schema": SCHEMA, "task": task, "recipe": asdict(recipe),
              "recipe_bank_sha256": bank_hash(), "parameters": PARAMETERS,
              "program_sha256": file_hash(program), "provenance": provenance,
              "measurement_units": "pixels", "clinical_use": False}
    (directory / "instrument.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def read_instrument(path: Path, verify_program: bool = True) -> dict:
    value = strict_json(path.read_text())
    required = {"schema", "task", "recipe", "recipe_bank_sha256", "parameters",
                "program_sha256", "provenance", "measurement_units", "clinical_use"}
    if set(value) != required or value["schema"] != SCHEMA:
        raise ValueError("Unsupported or incomplete instrument document")
    recipe_from_dict(value["recipe"])
    if value["task"] not in ("nuclei", "cells") or canonical_hash(value["parameters"]) != canonical_hash(PARAMETERS):
        raise ValueError("Instrument task or implementation parameters do not match")
    if value["recipe_bank_sha256"] != bank_hash():
        raise ValueError("Stale recipe-bank binding")
    if verify_program and file_hash(path.parent / "instrument.py") != value["program_sha256"]:
        raise ValueError("Stale or corrupted executable binding")
    if value["measurement_units"] != "pixels" or value["clinical_use"] is not False:
        raise ValueError("Unsupported instrument scope")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, required=True)
    parser.add_argument("--dna", type=Path, required=True)
    parser.add_argument("--actin", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = read_instrument(args.recipe)
    if file_hash(Path(__file__)) != document["program_sha256"]:
        raise ValueError("Run the executable supplied with this instrument document")
    if document["task"] == "cells" and args.actin is None:
        raise ValueError("Whole-cell measurement requires --actin")
    if args.output.exists():
        raise ValueError("Output directory already exists; choose a fresh destination")
    inputs = {"dna": {"path": str(args.dna), "sha256": file_hash(args.dna)}}
    with Image.open(args.dna) as image:
        dna = np.asarray(image).copy()
    actin = None
    if args.actin is not None:
        inputs["actin"] = {"path": str(args.actin), "sha256": file_hash(args.actin)}
        with Image.open(args.actin) as image:
            actin = np.asarray(image).copy()
    wall, cpu = time.perf_counter(), time.process_time()
    labels = apply(dna, recipe_from_dict(document["recipe"]), document["task"], actin)
    rows = measurements(labels)
    args.output.mkdir(parents=True)
    label_hash = save_labels(args.output / "labels.png", labels)
    write_measurements(args.output / "measurements.csv", rows)
    result = {"schema": "learning-to-build/instrument-operation/v1", "task": document["task"],
              "instrument_sha256": file_hash(args.recipe), "inputs": inputs,
              "labels_sha256": label_hash, "instances": len(rows),
              "foreground_pixels": int(np.count_nonzero(labels)),
              "actual_cpu_seconds": time.process_time() - cpu,
              "actual_wall_seconds": time.perf_counter() - wall,
              "measurement_units": "pixels", "external_qualification": False}
    (args.output / "OPERATION.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
