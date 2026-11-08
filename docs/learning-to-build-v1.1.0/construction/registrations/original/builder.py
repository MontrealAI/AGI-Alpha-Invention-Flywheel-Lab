#!/usr/bin/env python3
"""Finite recipe construction and explicitly bounded experience update.

No operator is discovered here.  Greedy coverage learns one ordering of a
supplied recipe bank from actual donor evaluations.  The ordinary comparator
gets the entire same table and ranks by mean donor quality.  Every ranked
constructor can evaluate all candidates; exhaustive search is a separate
strong conventional route.
"""
from __future__ import annotations

import csv
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import linear_sum_assignment
from skimage.segmentation import find_boundaries

import instrument


MEAN_METRICS = ("instance_f1", "relative_count_error", "foreground_dice",
                "internal_boundary_f1", "boundary_precision", "boundary_recall")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing an empty comparison table: {path}")
    keys = list(rows[0])
    if any(set(row) != set(keys) for row in rows):
        raise ValueError("Inconsistent comparison-table columns")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def label_array_hash(labels: np.ndarray) -> str:
    # Shape is part of the digest; labels use a canonical unsigned 32-bit
    # little-endian representation independent of machine-native byte order.
    h = hashlib.sha256(json.dumps(list(labels.shape), separators=(",", ":")).encode() + b"\n")
    h.update(labels.astype("<u4").tobytes(order="C"))
    return h.hexdigest()


def internal_boundary(labels: np.ndarray) -> np.ndarray:
    boundary = find_boundaries(labels, connectivity=1, mode="inner", background=0)
    interior = ndi.binary_erosion(labels > 0, structure=np.ones((3, 3), dtype=bool), border_value=0)
    return boundary & interior


def score_masks(predicted: np.ndarray, reference: np.ndarray) -> dict:
    predicted, reference = np.asarray(predicted), np.asarray(reference)
    if (predicted.shape != reference.shape or predicted.ndim != 2
            or predicted.dtype.kind not in "ui" or reference.dtype.kind not in "ui"
            or np.any(predicted < 0) or np.any(reference < 0)):
        raise ValueError("Scoring requires matching nonnegative integer instance-label images")
    pred_ids, pred_index = np.unique(predicted, return_inverse=True)
    true_ids, true_index = np.unique(reference, return_inverse=True)
    pred_n, true_n = int(np.count_nonzero(pred_ids)), int(np.count_nonzero(true_ids))
    table = np.bincount((pred_index * len(true_ids) + true_index).ravel(),
                        minlength=len(pred_ids) * len(true_ids)).reshape(len(pred_ids), len(true_ids))
    intersection = table[np.ix_(pred_ids != 0, true_ids != 0)]
    pred_area = table.sum(axis=1)[pred_ids != 0]
    true_area = table.sum(axis=0)[true_ids != 0]
    union = pred_area[:, None] + true_area[None, :] - intersection
    iou = np.divide(intersection, union, out=np.zeros(intersection.shape, dtype=float), where=union > 0)
    if pred_n and true_n:
        eligible = iou > 0.5
        first, second = linear_sum_assignment(-eligible.astype(np.int8))
        matched = eligible[first, second]
        tp = int(matched.sum())
        area_errors = np.abs(pred_area[first[matched]] - true_area[second[matched]]) / true_area[second[matched]]
        matched_area_error_sum = float(area_errors.sum())
    else:
        tp = 0
        matched_area_error_sum = 0.0
    fp, fn = pred_n - tp, true_n - tp
    denom = 2 * tp + fp + fn
    f1 = float(2 * tp / denom) if denom else 1.0
    pred_fg, true_fg = predicted > 0, reference > 0
    area_sum = int(pred_fg.sum() + true_fg.sum())
    dice = float(2 * np.count_nonzero(pred_fg & true_fg) / area_sum) if area_sum else 1.0
    pred_boundary, true_boundary = internal_boundary(predicted), internal_boundary(reference)
    npred, ntrue = int(pred_boundary.sum()), int(true_boundary.sum())
    if not npred and not ntrue:
        precision = recall = boundary_f1 = 1.0
    elif not npred or not ntrue:
        precision = recall = boundary_f1 = 0.0
    else:
        to_true = ndi.distance_transform_edt(~true_boundary)
        to_pred = ndi.distance_transform_edt(~pred_boundary)
        precision = float(np.mean(to_true[pred_boundary] <= 2.0))
        recall = float(np.mean(to_pred[true_boundary] <= 2.0))
        boundary_f1 = float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"predicted_count": pred_n, "reference_count": true_n,
            "tp": tp, "fp": fp, "fn": fn, "instance_f1": f1,
            "relative_count_error": float(abs(pred_n - true_n) / max(1, true_n)),
            "foreground_dice": dice, "boundary_precision": precision,
            "boundary_recall": recall, "internal_boundary_f1": boundary_f1,
            "reference_internal_boundary_pixels": ntrue,
            "predicted_internal_boundary_pixels": npred,
            "reference_foreground_pixels": int(true_fg.sum()),
            "predicted_foreground_pixels": int(pred_fg.sum()),
            "matched_area_error_sum": matched_area_error_sum,
            "matched_area_relative_error": matched_area_error_sum / tp if tp else None,
            "matched_pair_count": tp,
            "matched_reference_fraction": float(tp / true_n) if true_n else None,
            "matched_predicted_fraction": float(tp / pred_n) if pred_n else None}


def aggregate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("A cohort must contain at least one field")
    result = {"fields": len(rows)}
    for metric in MEAN_METRICS:
        result[f"mean_{metric}"] = float(np.mean([float(row[metric]) for row in rows]))
    result["boundary_bearing_fields"] = sum(int(row["reference_internal_boundary_pixels"]) > 0 for row in rows)
    bearing = [float(row["internal_boundary_f1"]) for row in rows
               if int(row["reference_internal_boundary_pixels"]) > 0]
    result["mean_boundary_f1_on_reference_boundary_bearing_fields"] = float(np.mean(bearing)) if bearing else None
    result["total_reference_instances"] = sum(int(row["reference_count"]) for row in rows)
    result["total_predicted_instances"] = sum(int(row["predicted_count"]) for row in rows)
    result["matched_pair_count"] = sum(int(row["matched_pair_count"]) for row in rows)
    result["matched_area_error_sum"] = sum(float(row["matched_area_error_sum"]) for row in rows)
    pairs = result["matched_pair_count"]
    result["pooled_matched_area_relative_error"] = result["matched_area_error_sum"] / pairs if pairs else None
    count = result["total_reference_instances"]
    result["matched_reference_fraction"] = float(pairs / count) if count else None
    return result


def qualifies(summary: dict, task: str, criteria: dict, heldout: bool = False) -> bool:
    if task == "nuclei":
        bounds = criteria["nuclei"]
        return bool(summary["mean_instance_f1"] >= bounds["mean_instance_f1_at_iou_strictly_greater_than_0_5_min"]
                    and summary["mean_relative_count_error"] <= bounds["mean_relative_count_error_max"]
                    and summary["mean_foreground_dice"] >= bounds["mean_foreground_dice_min"])
    bounds = criteria["cells"]
    bearing_score = summary["mean_boundary_f1_on_reference_boundary_bearing_fields"]
    return bool(summary["mean_internal_boundary_f1"] >= bounds["mean_internal_boundary_f1_within_2_pixels_min"]
                and bearing_score is not None
                and bearing_score >= bounds["mean_boundary_f1_on_reference_boundary_bearing_fields_min"]
                and summary["mean_relative_count_error"] <= bounds["mean_relative_count_error_max"]
                and summary["mean_foreground_dice"] >= bounds["mean_foreground_dice_min"]
                and summary["boundary_bearing_fields"] >= bounds[
                    "minimum_boundary_bearing_test_fields" if heldout else "minimum_boundary_bearing_calibration_fields"])


def fixed_order() -> list[str]:
    def key(recipe):
        return (recipe.background != "opening", recipe.threshold != "li",
                recipe.watershed_surface != "intensity", -recipe.seed_distance)
    return [r.id for r in sorted(instrument.recipes(), key=key)]


def donor_summaries(rows: list[dict]) -> dict[str, dict]:
    expected = set(instrument.RECIPE_MAP)
    if {row["recipe_id"] for row in rows} != expected:
        raise ValueError("Donor history must include every registered recipe")
    result = {}
    field_set = None
    for recipe in instrument.recipes():
        cohort = [row for row in rows if row["recipe_id"] == recipe.id]
        fields = [row["field"] for row in cohort]
        if len(fields) != len(set(fields)) or (field_set is not None and set(fields) != field_set):
            raise ValueError("Donor recipes must have exactly the same unique fields")
        field_set = set(fields)
        result[recipe.id] = aggregate(cohort)
    return result


def select_donor(rows: list[dict]) -> tuple[str, dict[str, dict]]:
    summaries = donor_summaries(rows)
    selected = min(summaries, key=lambda rid: (summaries[rid]["mean_relative_count_error"],
                                              -summaries[rid]["mean_instance_f1"],
                                              -summaries[rid]["mean_foreground_dice"], rid))
    return selected, summaries


def empirical_order(rows: list[dict]) -> list[str]:
    summaries = donor_summaries(rows)
    return sorted(summaries, key=lambda rid: (-summaries[rid]["mean_instance_f1"],
                                               -summaries[rid]["mean_foreground_dice"],
                                               summaries[rid]["mean_relative_count_error"], rid))


def learn_coverage_order(rows: list[dict], criteria: dict) -> dict:
    summaries = donor_summaries(rows)
    covered_by = {rid: set() for rid in summaries}
    for row in rows:
        one = {f"mean_{key}": float(row[key]) for key in MEAN_METRICS}
        if qualifies(one, "nuclei", criteria):
            covered_by[row["recipe_id"]].add(row["field"])
    uncovered = {row["field"] for row in rows}
    remaining = set(summaries)
    order, steps = [], []
    while remaining:
        selected = min(remaining, key=lambda rid: (-len(covered_by[rid] & uncovered),
                                                   -summaries[rid]["mean_instance_f1"],
                                                   -summaries[rid]["mean_foreground_dice"],
                                                   summaries[rid]["mean_relative_count_error"], rid))
        newly = sorted(covered_by[selected] & uncovered)
        steps.append({"recipe_id": selected, "newly_covered_fields": newly,
                      "newly_covered_count": len(newly), "remaining_before": len(uncovered)})
        order.append(selected)
        uncovered -= covered_by[selected]
        remaining.remove(selected)
    return {"schema": "learning-to-build/finite-coverage-order/v1", "order": order,
            "steps": steps, "uncovered_fields": sorted(uncovered),
            "source_rows": len(rows), "source_fields": len({row["field"] for row in rows}),
            "operator_grammar_supplied": True, "learned_object": "ordering_parameter",
            "new_algorithm_discovery": False}


def arm_orders(donor_rows: list[dict], donor_recipe: str, criteria: dict) -> tuple[dict, dict]:
    fixed = fixed_order()
    learned = learn_coverage_order(donor_rows, criteria)
    def first(order):
        return [donor_recipe] + [rid for rid in order if rid != donor_recipe]
    return {"fixed_no_history": fixed, "ordinary_reuse": first(fixed),
            "updated_no_artifact": learned["order"],
            "updated_with_artifact": first(learned["order"]),
            "same_content_empirical": empirical_order(donor_rows),
            "full_enumeration": fixed}, learned


class RetainedNucleusArtifact:
    """Actually execute the emitted donor program for its matching recipe."""
    def __init__(self, document_path: Path):
        self.document = instrument.read_instrument(document_path)
        if self.document["task"] != "nuclei":
            raise ValueError("Expected the retained donor nucleus instrument")
        self.recipe_id = self.document["recipe"]["id"]
        self.document_sha256 = instrument.file_hash(document_path)
        self.invocations = 0
        module_name = f"_ltb_retained_{self.document_sha256[:12]}_{id(self)}"
        spec = importlib.util.spec_from_file_location(module_name, document_path.parent / "instrument.py")
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load retained executable")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = self.module
        try:
            spec.loader.exec_module(self.module)
        finally:
            sys.modules.pop(module_name, None)
        self.recipe = self.module.recipe_from_dict(self.document["recipe"])

    def predict(self, dna: np.ndarray) -> np.ndarray:
        self.invocations += 1
        return self.module.segment_nuclei(dna, self.recipe)


def field_slug(field_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", field_id).strip("_")[:96]
    return stem + "_" + hashlib.sha256(field_id.encode()).hexdigest()[:8]


def evaluate(recipe: instrument.Recipe, task: str, cases: list,
             retain: Path | None = None, artifact: RetainedNucleusArtifact | None = None,
             direct_artifact: bool = False, oracle: bool = False) -> tuple[list[dict], dict]:
    rows, mask_manifest, measurement_rows = [], {}, []
    for case in cases:
        started_wall, started_cpu = time.perf_counter(), time.process_time()
        artifact_used = False
        if direct_artifact:
            if artifact is None:
                raise ValueError("Direct reuse requires the retained nucleus artifact")
            predicted = artifact.predict(case.dna)
            predicted = instrument.exclude_frame_objects(predicted)
            artifact_used = True
        elif oracle:
            if task != "cells" or case.nucleus_truth is None:
                raise ValueError("Reference-input diagnostic requires manual target nuclei")
            predicted = instrument.segment_cells(case.dna, case.actin, recipe,
                                                  nucleus_labels=case.nucleus_truth,
                                                  foreground_override=case.truth > 0)
        elif task == "cells" and artifact is not None and recipe.id == artifact.recipe_id:
            seeds = artifact.predict(case.dna)
            predicted = instrument.segment_cells(case.dna, case.actin, recipe, nucleus_labels=seeds)
            artifact_used = True
        else:
            predicted = instrument.apply(case.dna, recipe, task, case.actin)
        segmentation_cpu = time.process_time() - started_cpu
        scoring_cpu_start = time.process_time()
        scores = score_masks(predicted, case.truth)
        scoring_cpu = time.process_time() - scoring_cpu_start
        raw_hash = label_array_hash(predicted)
        mask_path = ""
        mask_sha256 = ""
        if retain is not None:
            name = field_slug(case.name) + ".png"
            destination = retain / "masks" / name
            mask_sha256 = instrument.save_labels(destination, predicted)
            mask_path = "masks/" + name
            mask_manifest[case.name] = {"path": mask_path, "sha256": mask_sha256,
                                        "label_array_sha256": raw_hash,
                                        "shape": list(predicted.shape), "sources": case.sources,
                                        "reference_label_array_sha256": label_array_hash(case.truth),
                                        "decoder_diagnostics": case.decoder_diagnostics}
            measurement_rows.extend({"field": case.name, **row} for row in instrument.measurements(predicted))
        rows.append({"field": case.name, "recipe_id": recipe.id, "task": task,
                     "height": int(predicted.shape[0]), "width": int(predicted.shape[1]),
                     **scores, "label_array_sha256": raw_hash,
                     "mask_path": mask_path, "mask_sha256": mask_sha256,
                     "artifact_executed": artifact_used, "reference_inputs_used": oracle,
                     "segmentation_cpu_seconds": segmentation_cpu, "scoring_cpu_seconds": scoring_cpu,
                     "actual_cpu_seconds": time.process_time() - started_cpu,
                     "actual_wall_seconds": time.perf_counter() - started_wall})
    if retain is not None:
        write_json(retain / "MASKS.json", mask_manifest)
        # An empty output must still have a useful, explicit table schema.
        path = retain / "measurements.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["field"] + instrument.MEASUREMENT_FIELDS)
            writer.writeheader()
            writer.writerows(measurement_rows)
    return rows, aggregate(rows)


def target_quality(summary: dict, recipe_id: str) -> tuple:
    bearing = summary["mean_boundary_f1_on_reference_boundary_bearing_fields"]
    return (-bearing if bearing is not None else float("inf"),
            -summary["mean_internal_boundary_f1"], -summary["mean_foreground_dice"],
            summary["mean_relative_count_error"], recipe_id)


def construct(order: list[str], cases: list, criteria: dict, output: Path,
              exhaustive: bool = False, artifact_path: Path | None = None) -> dict:
    if len(order) != len(instrument.RECIPE_MAP) or set(order) != set(instrument.RECIPE_MAP):
        raise ValueError("Every constructor must retain the complete candidate bank exactly once")
    output.mkdir(parents=True, exist_ok=False)
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    artifact = RetainedNucleusArtifact(artifact_path) if artifact_path is not None else None
    trace, all_rows, candidate_summaries = [], [], {}
    first_qualified = None
    for index, recipe_id in enumerate(order, start=1):
        candidate_wall, candidate_cpu = time.perf_counter(), time.process_time()
        rows, summary = evaluate(instrument.RECIPE_MAP[recipe_id], "cells", cases, artifact=artifact)
        accepted = qualifies(summary, "cells", criteria)
        all_rows.extend(rows)
        candidate_summaries[recipe_id] = summary
        trace.append({"evaluation_index": index, "recipe_id": recipe_id,
                      **summary, "calibration_qualified": accepted,
                      "actual_cpu_seconds": time.process_time() - candidate_cpu,
                      "actual_wall_seconds": time.perf_counter() - candidate_wall})
        # Retain completed candidates if a later candidate or external run fails.
        write_csv(output / "trace.csv", trace)
        write_csv(output / "calibration.csv", all_rows)
        if accepted and first_qualified is None:
            first_qualified = recipe_id
        if accepted and not exhaustive:
            break
    qualified_ids = [rid for rid, summary in candidate_summaries.items() if qualifies(summary, "cells", criteria)]
    selected = min(qualified_ids or list(candidate_summaries),
                   key=lambda rid: target_quality(candidate_summaries[rid], rid))
    if not exhaustive and first_qualified is not None:
        selected = first_qualified
    result = {"proposed_order": order, "executed_order": [row["recipe_id"] for row in trace],
              "calibration_candidates_executed": len(trace), "calibration_fields": len(cases),
              "calibration_field_evaluations": len(all_rows), "exhaustive": exhaustive,
              "selected_recipe_id": selected, "selected_recipe": asdict(instrument.RECIPE_MAP[selected]),
              "calibration": candidate_summaries[selected],
              "calibration_qualified": qualifies(candidate_summaries[selected], "cells", criteria),
              "artifact_access": artifact is not None,
              "artifact_invocations": artifact.invocations if artifact is not None else 0,
              "artifact_sha256": artifact.document_sha256 if artifact is not None else None,
              "actual_construction_cpu_seconds": time.process_time() - started_cpu,
              "actual_construction_wall_seconds": time.perf_counter() - started_wall}
    write_json(output / "construction.json", result)
    return result
