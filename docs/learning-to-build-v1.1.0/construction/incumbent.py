#!/usr/bin/env python3
"""Operate a separately registered, pretrained CellposeDINO practical alternative.

This is an external stock of learned weights, not one of the six causal recipe
arms. The predictor receives only raw DNA/actin channels. Reference annotations
are used afterward for the same registered measurement and acceptance criteria.
No third-party weights or source code are redistributed by this module.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
PRIMARY_REGISTRATION = "REGISTRATION-amendment-1.json"
MODEL = {
    "name": "cpdino-vitb",
    "repository": "mouseland/cellpose-sam",
    "revision": "7c61431b5fbb078f3296754bd15d9f51b320f837",
    "bytes": 343599997,
    "sha256": "3ed4c06a3963ab13ff377d4e2957174aaaf637434eb031ae9931fcbfaf9a217f",
}
UPSTREAM = {
    "cellpose_version": "4.2.1.1",
    "cellpose_wheel_sha256": "6c5c5159fd459115bee390ffb01d94d5e1006b97c211bf3c1a7b37d5395a1a13",
    "dinov3_commit": "6876159a11b4df116f30f667f8c9888617df0751",
    "dinov3_archive_sha256": "94da41da596633a73619078bb3bbde64ff3be95c55e8658638fa57c542cc4fe7",
}
CONFIGURATION = {
    "device": "cpu", "use_bfloat16": False,
    "torch_threads": 1, "torch_interop_threads": 1, "torch_seed": 0,
    "input_channels": {"nuclei": ["DNA", "zero", "zero"],
                       "cells": ["actin", "DNA", "zero"]},
    "fine_tuning": False, "calibration_parameter_selection": False,
    "reference_inputs_to_predictor": False,
    "allowed_missing_nonlearned_state": {"diam_labels": 30.0, "diam_mean": 30.0},
    "evaluation": {
        "batch_size": 1, "resample": True, "channels": None,
        "channel_axis": -1, "z_axis": None, "normalize": True,
        "rescale": None, "diameter": None, "flow_threshold": 0.4,
        "cellprob_threshold": 0.0, "do_3D": False, "anisotropy": None,
        "flow3D_smooth": 0, "stitch_threshold": 0.0, "min_size": 15,
        "max_size_fraction": 0.4, "niter": None, "augment": False,
        "tile_overlap": 0.1, "bsize": 384, "compute_masks": True,
    },
    "border_policy": {"nuclei": "Keep border objects, as in the primary BBBC039 protocol.",
                      "cells": "Exclude complete predicted objects touching the image frame, then relabel, as in the primary BBBC007 protocol."},
}
RUNTIME_PACKAGES = (
    "cellpose", "dinov3", "torch", "torchvision", "numpy", "scipy",
    "scikit-image", "Pillow", "opencv-python-headless", "fastremap",
    "fill-voids", "imagecodecs", "tifffile", "segment-anything",
    "natsort", "tqdm", "imageio", "lazy-loader", "networkx",
)
IMPLEMENTATION_FILES = ("incumbent.py", "data.py", "builder.py", "instrument.py")
COHORTS = {
    "source_validation": {"dataset": "bbbc039", "split": "validation", "task": "nuclei", "directory": "source/validation", "heldout": False},
    "source_test": {"dataset": "bbbc039", "split": "test", "task": "nuclei", "directory": "source/test", "heldout": True},
    "successor_calibration": {"dataset": "bbbc007", "split": "calibration", "task": "cells", "directory": "successor/calibration", "heldout": False},
    "successor_test": {"dataset": "bbbc007", "split": "test", "task": "cells", "directory": "successor/test", "heldout": True},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def completed_tree(directory):
    entries = []
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "Completed evidence cannot contain symlinks")
        if path.is_file() and path != directory / "COMPLETION.json":
            entries.append({"path": path.relative_to(directory).as_posix(),
                            "bytes": path.stat().st_size, "sha256": digest(path)})
    return entries


def seal_completion(directory):
    started, cpu = time.perf_counter(), time.process_time()
    require(not (directory / "COMPLETION.json").exists(), "A completed evidence tree is immutable")
    entries = completed_tree(directory)
    seal = {"schema": "learning-to-build/incumbent-completion/v1", "files": entries,
            "tree_sha256": hashlib.sha256(canonical(entries).encode()).hexdigest(),
            "seal_cpu_seconds": time.process_time() - cpu,
            "seal_wall_seconds": time.perf_counter() - started,
            "scope": "Exact saved-file identity. Independent scientific verification uses check.py; this is not an external signature."}
    write_json(directory / "COMPLETION.json", seal)
    return seal


def verify_completion(directory, identity):
    seal = read_json(directory / "COMPLETION.json")
    require(seal["schema"] == "learning-to-build/incumbent-completion/v1", "Unknown completion seal")
    actual = completed_tree(directory)
    require(canonical(seal["files"]) == canonical(actual) and
            seal["tree_sha256"] == hashlib.sha256(canonical(actual).encode()).hexdigest(),
            "Completed evidence tree changed; preserve and independently inspect it")
    result = read_json(directory / "RESULTS.json")
    require(result["status"] == "COMPLETE" and
            canonical(result["identity"]) == canonical(identity), "Completed result identity differs")
    require(read_json(directory / "STATUS.json")["status"] == "COMPLETE" and
            canonical(result["sessions"]) == canonical(read_json(directory / "SESSIONS.json")),
            "Completed status or session record differs")
    return seal


def implementation_bindings():
    return {name: digest(ROOT / name) for name in IMPLEMENTATION_FILES}


def runtime_versions():
    return {"python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in RUNTIME_PACKAGES}}


def upstream_python_bindings():
    result = {}
    for name in ("cellpose", "dinov3"):
        module = importlib.import_module(name)
        directory = Path(module.__file__).resolve().parent
        files = {str(path.relative_to(directory)): digest(path)
                 for path in sorted(directory.rglob("*.py"))}
        result[name] = {"files": len(files),
                        "sha256": hashlib.sha256(canonical(files).encode()).hexdigest()}
    return result


def configure_process(weights):
    # These changes apply only to this explicitly launched baseline process.
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["CELLPOSE_LOCAL_MODELS_PATH"] = str(Path(weights).resolve().parent)
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)


def load_model(weights):
    import torch
    from cellpose import models
    weights = Path(weights).resolve()
    require(weights.is_file() and not weights.is_symlink(), "Missing regular model file")
    require(weights.stat().st_size == MODEL["bytes"] and digest(weights) == MODEL["sha256"],
            "Model bytes do not match the frozen public weights")
    started, cpu = time.perf_counter(), time.process_time()
    model = models.CellposeModel(pretrained_model=str(weights), gpu=False,
                                 device=torch.device("cpu"), use_bfloat16=False)
    state = torch.load(weights, map_location="cpu", weights_only=True, mmap=True)
    loaded = model.net.load_state_dict(state, strict=False)
    expected = CONFIGURATION["allowed_missing_nonlearned_state"]
    require(set(loaded.missing_keys) == set(expected) and not loaded.unexpected_keys,
            "Unexpected missing or surplus pretrained state tensors")
    parameters = dict(model.net.named_parameters())
    for name, value in expected.items():
        parameter = parameters[name]
        require(parameter.numel() == 1 and not parameter.requires_grad and parameter.item() == value,
                "Unfrozen compatibility scalar: " + name)
    model.net.eval()
    receipt = {
        "backbone": model.backbone, "device": str(model.net.device),
        "dtype": str(model.net.dtype),
        "parameters": sum(p.numel() for p in model.net.parameters()),
        "missing_nonlearned_scalars": expected, "unexpected_keys": [],
        "all_learned_tensors_loaded": True,
        "load_cpu_seconds": time.process_time() - cpu,
        "load_wall_seconds": time.perf_counter() - started,
    }
    return model, receipt


def preflight(weights):
    configure_process(weights)
    _, loading = load_model(weights)
    return {"schema": "learning-to-build/incumbent-preflight/v1",
            "mode": "model-load-only", "model": MODEL, "upstream": UPSTREAM,
            "configuration": CONFIGURATION, "cohort_specification": COHORTS,
            "runtime_versions": runtime_versions(),
            "upstream_python_sha256": upstream_python_bindings(),
            "implementation_files": implementation_bindings(),
            "primary_protocol_sha256": digest(ROOT / "PROTOCOL.json"),
            "primary_registration": {"file": PRIMARY_REGISTRATION, "sha256": digest(ROOT / PRIMARY_REGISTRATION)},
            "loading": loading, "pixels_decoded": 0, "predictions_performed": 0,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def contract(protocol_path, registration_path, cache=None):
    protocol, registration = read_json(protocol_path), read_json(registration_path)
    require(protocol["schema"] == "learning-to-build/incumbent-protocol/v1", "Unknown incumbent protocol")
    require(registration["schema"] == "learning-to-build/incumbent-registration/v1", "Unknown incumbent registration")
    require(digest(protocol_path) == registration["protocol_sha256"], "Incumbent protocol is not registered")
    for key, value in (("model", MODEL), ("upstream", UPSTREAM), ("configuration", CONFIGURATION)):
        require(canonical(protocol[key]) == canonical(value), "Changed incumbent " + key)
    primary_path = ROOT / "PROTOCOL.json"
    require(digest(primary_path) == protocol["primary_protocol_sha256"], "Primary protocol identity changed")
    primary = read_json(primary_path)
    primary_registration_path = ROOT / PRIMARY_REGISTRATION
    require(digest(primary_registration_path) == protocol["primary_registration_sha256"],
            "Primary amended registration identity changed")
    primary_registration = read_json(primary_registration_path)
    require(primary_registration["protocol_sha256"] == digest(primary_path), "Primary registration protocol differs")
    amendment = primary_registration["amendment"]
    require(amendment["path"] == "AMENDMENT-1.json" and digest(ROOT / amendment["path"]) == amendment["sha256"],
            "Primary format amendment identity changed")
    cohorts = protocol["cohorts"]
    require(set(cohorts) == set(COHORTS), "Unknown or missing incumbent cohort")
    for split, names in cohorts.items():
        require(isinstance(names, list) and names and all(isinstance(name, str) for name in names)
                and len(names) == len(set(names)), "Invalid registered field IDs: " + split)
        if split.startswith("successor_"):
            primary_ids = primary["data"]["bbbc007"][COHORTS[split]["split"] + "_ids"]
            require(canonical(names) == canonical(primary_ids), "Incumbent successor cohort differs from primary comparison")
    if cache is not None:
        import data
        metadata = data.metadata039(cache)
        for split in ("validation", "test"):
            expected = [Path(name).stem for name in metadata[split]]
            require(canonical(cohorts["source_" + split]) == canonical(expected),
                    "Incumbent source cohort differs from the official split")
    require(canonical(protocol["cohort_specification"]) == canonical(COHORTS), "Changed cohort tasks or operation order")
    bindings = implementation_bindings()
    for name, expected in primary_registration["implementation_files"].items():
        require(bindings.get(name) == expected, "Incumbent uses a different primary implementation: " + name)
    require(canonical(registration["implementation_files"]) == canonical(bindings), "Changed incumbent implementation")
    runtime = runtime_versions()
    frozen = registration["runtime_versions"]
    require(runtime["python"].split(".")[:2] == frozen["python"].split(".")[:2], "Different Python minor version")
    require(canonical(runtime["packages"]) == canonical(frozen["packages"]), "Different registered dependency versions")
    upstream = upstream_python_bindings()
    require(canonical(upstream) == canonical(registration["upstream_python_sha256"]), "Changed upstream Python source")
    identity = {"protocol_sha256": digest(protocol_path), "registration_sha256": digest(registration_path),
                "primary_protocol_sha256": digest(primary_path),
                "primary_registration_sha256": digest(primary_registration_path),
                "primary_amendment": amendment, "implementation_files": bindings,
                "model": MODEL, "configuration": CONFIGURATION, "cohorts": cohorts,
                "cohort_specification": COHORTS, "runtime_versions": runtime,
                "upstream_python_sha256": upstream}
    return primary, cohorts, identity


def predict(model, dna, actin, task):
    """No reference mask, learned ordering, calibration score or case object enters here."""
    import numpy as np
    import torch
    require(task in CONFIGURATION["input_channels"], "Unknown registered measurement task")
    require(dna.ndim == 2 and dna.dtype.kind in "uif" and
            bool(np.all(np.isfinite(dna))), "Invalid DNA input pixels")
    if task == "cells":
        require(actin is not None and actin.ndim == 2 and dna.shape == actin.shape and
                actin.dtype.kind in "uif" and bool(np.all(np.isfinite(actin))),
                "Expected paired two-dimensional actin/DNA channels")
        channels = np.stack((actin, dna, np.zeros_like(dna)), axis=-1)
    else:
        require(actin is None, "The source nuclei task accepts only a DNA channel")
        channels = np.stack((dna, np.zeros_like(dna), np.zeros_like(dna)), axis=-1)
    with torch.inference_mode():
        masks, _, _ = model.eval(channels, **CONFIGURATION["evaluation"])
    masks = np.asarray(masks)
    require(masks.ndim == 2 and masks.shape == dna.shape and masks.dtype.kind in "ui" and
            bool(np.all(masks >= 0)), "Invalid model output")
    return masks


def write_split(directory, field_receipts):
    import builder
    import instrument
    rows = [item["metrics"] for item in field_receipts]
    builder.write_csv(directory / "metrics.csv", rows)
    write_json(directory / "MASKS.json", {item["field"]: item["mask"] for item in field_receipts})
    with (directory / "measurements.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["field"] + instrument.MEASUREMENT_FIELDS)
        writer.writeheader()
        for item in field_receipts:
            writer.writerows(item["measurements"])
    return rows


def run(args):
    started, cpu = time.perf_counter(), time.process_time()
    configure_process(args.weights)
    primary, cohorts, identity = contract(args.protocol, args.registration, args.cache.resolve())
    import numpy as np
    import data
    import builder
    import instrument
    output = args.output.expanduser()
    require(output.is_absolute(), "Output must be an absolute path")
    output = output.resolve()
    require(not output.is_relative_to(ROOT.parent), "Run outside the canonical source tree")
    archives = data.archive_manifest(args.cache.resolve())
    require(canonical(archives) == canonical(primary["data"]["archives"]), "Public input archive identity differs")
    identity["archives"] = archives
    if args.resume:
        require(output.is_dir(), "Resume requires an existing run")
        require(canonical(read_json(output / "IDENTITY.json")) == canonical(identity), "Resume identity mismatch")
        if (output / "RESULTS.json").is_file():
            seal = verify_completion(output, identity)
            return {"status": "ALREADY_COMPLETE", "results_sha256": digest(output / "RESULTS.json"),
                    "completion_tree_sha256": seal["tree_sha256"],
                    "predictions_performed_this_invocation": 0}
    else:
        require(not output.exists(), "Output already exists; use a new path or explicit resume")
        output.mkdir(parents=True)
        write_json(output / "IDENTITY.json", identity)
    sessions_path = output / "SESSIONS.json"
    sessions = read_json(sessions_path) if sessions_path.is_file() else []
    new_fields = 0
    try:
        model, loading = load_model(args.weights)
        write_json(output / "STATUS.json", {"status": "RUNNING", "mode": "separate-practical-alternative"})
        split_results = {}
        for split, cohort in COHORTS.items():
            names = cohorts[split]
            directory = output / cohort["directory"]
            directory.mkdir(parents=True, exist_ok=True)
            fields = directory / "fields"
            fields.mkdir(exist_ok=True)
            lookup039 = ({Path(name).stem: name for name in data.metadata039(args.cache.resolve())[cohort["split"]]}
                         if cohort["dataset"] == "bbbc039" else None)
            receipts = []
            for name in names:
                slug = builder.field_slug(name)
                receipt_path = fields / (slug + ".json")
                if receipt_path.is_file():
                    item = read_json(receipt_path)
                    require(item["field"] == name and digest(directory / item["mask"]["path"]) == item["mask"]["sha256"],
                            "Changed completed field during resume")
                    if cohort["task"] == "cells":
                        raw_mask = item["mask"]["pre_border_exclusion"]
                        require(digest(directory / raw_mask["path"]) == raw_mask["sha256"],
                                "Changed pre-border-exclusion mask during resume")
                else:
                    wall, field_cpu = time.perf_counter(), time.process_time()
                    case = (data.load039(args.cache.resolve(), cohort["split"], [lookup039[name]])[0]
                            if lookup039 is not None else data.load007(args.cache.resolve(), [name])[0])
                    require(case.name == name, "Loaded input field differs from registered identity")
                    prediction_start = time.process_time()
                    raw = predict(model, case.dna, case.actin, cohort["task"])
                    raw_count = int(np.count_nonzero(np.unique(raw)))
                    predicted = instrument.exclude_frame_objects(raw) if cohort["task"] == "cells" else raw
                    prediction_cpu = time.process_time() - prediction_start
                    scoring_start = time.process_time()
                    scores = builder.score_masks(predicted, case.truth)
                    scoring_cpu = time.process_time() - scoring_start
                    relative = "masks/" + slug + ".png"
                    mask_sha = instrument.save_labels(directory / relative, predicted)
                    array_sha = builder.label_array_hash(predicted)
                    measurements = [{"field": name, **row} for row in instrument.measurements(predicted)]
                    row = {"field": name, "recipe_id": MODEL["name"], "task": cohort["task"],
                           "height": int(predicted.shape[0]), "width": int(predicted.shape[1]),
                           **scores, "label_array_sha256": array_sha, "mask_path": relative,
                           "mask_sha256": mask_sha, "artifact_executed": False, "reference_inputs_used": False,
                           "frame_objects_excluded": raw_count - scores["predicted_count"],
                           "segmentation_cpu_seconds": prediction_cpu, "scoring_cpu_seconds": scoring_cpu,
                           "actual_cpu_seconds": time.process_time() - field_cpu,
                           "actual_wall_seconds": time.perf_counter() - wall}
                    item = {"field": name, "metrics": row, "measurements": measurements,
                            "mask": {"path": relative, "sha256": mask_sha, "label_array_sha256": array_sha,
                                     "shape": list(predicted.shape), "sources": case.sources,
                                     "reference_label_array_sha256": builder.label_array_hash(case.truth),
                                     "decoder_diagnostics": case.decoder_diagnostics}}
                    if cohort["task"] == "cells":
                        raw_path = "pre_border_masks/" + slug + ".png"
                        item["mask"]["pre_border_exclusion"] = {
                            "path": raw_path, "sha256": instrument.save_labels(directory / raw_path, raw),
                            "label_array_sha256": builder.label_array_hash(raw),
                            "shape": list(raw.shape), "objects": raw_count}
                    write_json(receipt_path, item)
                    new_fields += 1
                    print(json.dumps({"split": split, "completed_field": name, "new_fields": new_fields}), flush=True)
                receipts.append(item)
                write_split(directory, receipts)
            rows = write_split(directory, receipts)
            summary = builder.aggregate(rows)
            accepted = builder.qualifies(summary, cohort["task"], primary["criteria"], heldout=cohort["heldout"])
            split_results[split] = {"field_ids": names, "directory": cohort["directory"],
                                    "task": cohort["task"], "summary": summary, "accepted": accepted}
        sessions.append({"status": "COMPLETE", "new_fields": new_fields,
                         "actual_cpu_seconds": time.process_time() - cpu,
                         "actual_wall_seconds": time.perf_counter() - started})
        write_json(sessions_path, sessions)
        result = {"schema": "learning-to-build/incumbent-results/v1", "status": "COMPLETE",
                  "identity": identity, "model_loading": loading, "splits": split_results,
                  "sessions": sessions, "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "comparison_role": "Pretrained practical alternative with different learned stock; outside the six equal-content causal arms.",
                  "comparison_selection_timing": "Selected after the classical source validation/test outcomes were observed, before any neural input decoding or predictions. No parameters were selected using these cohorts.",
                  "pretraining_overlap_with_evaluation_data": "Unknown; not excluded.",
                  "cost_scope": "Measured process CPU/wall and published model bytes. Upstream training, authoring, development, host/inference billing and unrecorded interruption intervals are unknown, not zero. No financial transactions.",
                  "rights_scope": "Research operation only. Cellpose code is BSD-3-Clause; model-card metadata says BSD-3-Clause, its documented training data are CC-BY-NC, and DINOv3 has separate custom terms. Commercial permissions are not established. No upstream source or weights redistributed.",
                  "new_physical_acquisitions": 0, "real_customer_acceptance": False,
                  "receipts_or_profit_established": False}
        write_json(output / "RESULTS.json", result)
        write_json(output / "STATUS.json", {"status": "COMPLETE", "fields": sum(map(len, cohorts.values()))})
        seal_completion(output)
        return result
    except BaseException as error:
        sessions.append({"status": "INTERRUPTED_OR_FAILED", "new_fields": new_fields,
                         "actual_cpu_seconds": time.process_time() - cpu,
                         "actual_wall_seconds": time.perf_counter() - started,
                         "error_type": type(error).__name__, "error": str(error)})
        write_json(sessions_path, sessions)
        write_json(output / "STATUS.json", {"status": "INTERRUPTED_OR_FAILED", "error_type": type(error).__name__,
                                           "completed_field_receipts_preserved": True})
        raise


def operate(args):
    """Apply the fixed instrument to supplied raw channels, without references."""
    started, cpu = time.perf_counter(), time.process_time()
    configure_process(args.weights)
    _, _, identity = contract(args.protocol, args.registration)
    import numpy as np
    from PIL import Image
    import builder
    import instrument
    require(args.output.is_absolute(), "Output must be an absolute path")
    output = args.output.resolve()
    require(not output.is_relative_to(ROOT.parent) and not output.exists(),
            "Choose a new output directory outside the canonical source tree")
    require((args.task == "cells") == (args.actin is not None),
            "Cells require DNA and actin; nuclei require DNA alone")
    output.mkdir(parents=True)
    inputs = {}
    try:
        channels = {}
        for name, path in (("dna", args.dna), ("actin", args.actin)):
            if path is None:
                continue
            require(path.is_file(), "Missing image file: " + str(path))
            with Image.open(path) as image:
                channels[name] = np.asarray(image).copy()
            inputs[name] = {"file": path.name, "bytes": path.stat().st_size,
                            "sha256": digest(path), "shape": list(channels[name].shape),
                            "dtype": str(channels[name].dtype)}
        model, loading = load_model(args.weights)
        raw = predict(model, channels["dna"], channels.get("actin"), args.task)
        labels = instrument.exclude_frame_objects(raw) if args.task == "cells" else raw
        mask_sha = instrument.save_labels(output / "labels.png", labels)
        rows = instrument.measurements(labels)
        instrument.write_measurements(output / "measurements.csv", rows)
        result = {"schema": "learning-to-build/incumbent-operation/v1", "status": "OPERATED",
                  "task": args.task, "identity": identity, "model_loading": loading,
                  "inputs": inputs, "objects": len(rows), "measurement_units": "pixels",
                  "outputs": {"labels.png": {"sha256": mask_sha,
                    "label_array_sha256": builder.label_array_hash(labels)},
                    "measurements.csv": {"sha256": digest(output / "measurements.csv")}},
                  "actual_cpu_seconds": time.process_time() - cpu,
                  "actual_wall_seconds": time.perf_counter() - started,
                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "reference_inputs_used": False, "accuracy_on_supplied_images_established": False,
                  "scope": "Fixed pretrained research instrument operated on supplied channels; no new training, qualification, biological conclusion or commercial permission is established."}
        if args.task == "cells":
            result["outputs"]["pre_border_labels.png"] = {
                "sha256": instrument.save_labels(output / "pre_border_labels.png", raw),
                "label_array_sha256": builder.label_array_hash(raw)}
            result["frame_objects_excluded"] = int(np.count_nonzero(np.unique(raw))) - len(rows)
        result["actual_cpu_seconds"] = time.process_time() - cpu
        result["actual_wall_seconds"] = time.perf_counter() - started
        write_json(output / "OPERATION.json", result)
        return result
    except BaseException as error:
        write_json(output / "OPERATION_FAILED.json", {
            "status": "FAILED", "identity": identity, "inputs": inputs,
            "error_type": type(error).__name__, "error": str(error),
            "actual_cpu_seconds": time.process_time() - cpu,
            "actual_wall_seconds": time.perf_counter() - started})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("preflight", help="Verify model loading and versions without pixels or inference")
    prepare.add_argument("--weights", required=True, type=Path)
    prepare.add_argument("--output", type=Path)
    execute = sub.add_parser("run", help="Execute only the separately registered real-data comparison")
    execute.add_argument("--weights", required=True, type=Path)
    execute.add_argument("--cache", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    execute.add_argument("--protocol", type=Path, default=ROOT / "INCUMBENT_PROTOCOL.json")
    execute.add_argument("--registration", type=Path, default=ROOT / "INCUMBENT_REGISTRATION.json")
    execute.add_argument("--resume", action="store_true")
    apply = sub.add_parser("operate", help="Apply the registered fixed instrument to supplied raw image channels")
    apply.add_argument("--weights", required=True, type=Path)
    apply.add_argument("--task", required=True, choices=("nuclei", "cells"))
    apply.add_argument("--dna", required=True, type=Path)
    apply.add_argument("--actin", type=Path)
    apply.add_argument("--output", required=True, type=Path)
    apply.add_argument("--protocol", type=Path, default=ROOT / "INCUMBENT_PROTOCOL.json")
    apply.add_argument("--registration", type=Path, default=ROOT / "INCUMBENT_REGISTRATION.json")
    args = parser.parse_args()
    result = preflight(args.weights) if args.command == "preflight" else operate(args) if args.command == "operate" else run(args)
    if args.command == "preflight" and args.output:
        require(not args.output.exists(), "Preflight output already exists; preserve it")
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
