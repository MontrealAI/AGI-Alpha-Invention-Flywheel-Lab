#!/usr/bin/env python3
"""Independently check the registered microscopy evidence against public bytes.

Reference decoding, scoring, aggregation, coverage and acceptance below do not
import the producer's data, builder, run or incumbent modules.  Classical
prediction replay uses only the exact registered instrument program; it never
uses reported scores or annotations as inputs except in the labelled oracle.
The default also regenerates donor and calibration predictions, because those
tables did not retain masks.  --saved-masks-only explicitly yields LIMITED
coverage for those tables, rather than presenting consistency as reproduction.

A neural mask audit establishes what the saved predictions score, not that a
particular model produced them. Model operation/replay is a separate receipt.
Neither this checker nor a file hash proves historical execution, elapsed time,
external acceptance, commercial rights, novel confirmation, or customer value.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import importlib.util
import io
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import time
import zipfile

sys.dont_write_bytecode = True

import numpy as np
import PIL
from PIL import Image
from scipy import ndimage as ndi
import scipy
from skimage.measure import regionprops
import skimage

BASE = Path(__file__).resolve().parent
VERIFIER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PINNED = {
    "PROTOCOL-amendment-2.json": "20d28a2fffbb3189ef14492a46853e5711e03d5f94c64b9f0aeb0e934a3367ae",
    "REGISTRATION-amendment-2.json": "aae0fdb9c485c6abba2139c15ca08db7d8ce0962af1336fa20dd5be0edfe5b05",
    "AMENDMENT-2.json": "a42c99ed6057e10aa61dc87dd50d950a789de105c89b6ddfb282175deaac822a",
    "INCUMBENT_PROTOCOL-amendment-2.json": "957931af9c647d23f3bb2b20940bc121894c10e0dbc8cce6ddd0575cf780d8be",
    "INCUMBENT_REGISTRATION-amendment-2.json": "a0ff81e25aa9782921a04f58b6062ec7be86a4538156ad6f3dee77945a17764f",
    "instrument.py": "36248b79130e5b1835da55302efe63432c013b8aaac5ce5b8253a6b243f7c265",
    "builder.py": "9665f8f9e3013e54b9d065765c0fd5478940bd8d8bfcfa5eb8a7b0135b309dee",
    "data.py": "e2ba268405723a1ba997af11b25fbb67b610b04394ee7910d4ebb1e812d1bea3",
    "run.py": "137d6ac9e4ecb9ea902f27d92c71b7d2e104fbbe87405f1aa4d2fbc04926f543",
    "incumbent.py": "58dd9055aa89aa91df41336f07c639ab9ec5019c48f2d42dea4ed08ee35cce6d",
    "requirements.txt": "513e6f534053e4aa9c46e5e5de6fe3b02dd2842d7c866dbdd9199bca78ef01f0",
}
BANK_SHA = "8844f614d9840ac6385ab31b9ee543f2f4c859f755f65c1d9a7680c4ecf91297"
ARMS = ("fixed_no_history", "ordinary_reuse", "updated_no_artifact",
        "updated_with_artifact", "same_content_empirical", "full_enumeration")
MEANS = ("instance_f1", "relative_count_error", "foreground_dice",
         "internal_boundary_f1", "boundary_precision", "boundary_recall")
TIME_FIELDS = ("segmentation_cpu_seconds", "scoring_cpu_seconds",
               "actual_cpu_seconds", "actual_wall_seconds")
MEASUREMENTS = ("label", "area_pixels", "centroid_row", "centroid_column",
                "perimeter_pixels", "equivalent_diameter_pixels", "eccentricity",
                "major_axis_length_pixels", "minor_axis_length_pixels")
RECIPE_DICTS = {
    f"r{i:02d}": dict(id=f"r{i:02d}", background=b, threshold=t,
                     seed_distance=s, watershed_surface=w)
    for i, (b, t, s, w) in enumerate(itertools.product(
        ("none", "opening"), ("li", "otsu"), (4, 7, 10), ("distance", "intensity")))
}


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def finite_tree(value, path="value"):
    if isinstance(value, float):
        require(math.isfinite(value), f"Nonfinite number at {path}")
    elif isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            finite_tree(item, f"{path}[{index}]")


def json_text(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise VerificationError("Nonfinite JSON token: " + value)
    value = json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
    finite_tree(value)
    return value


def load_json(path):
    return json_text(Path(path).read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def same(actual, expected, label="value"):
    """Strict keys/types/denominators, small rounding tolerance only for floats."""
    finite_tree(actual, label)
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected),
                f"Object keys differ at {label}")
        for key in expected:
            same(actual[key], expected[key], label + "." + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected),
                f"Array cardinality differs at {label}")
        for index, value in enumerate(expected):
            same(actual[index], value, f"{label}[{index}]")
    elif expected is None or isinstance(expected, (str, bool)):
        require(type(actual) is type(expected) and actual == expected,
                f"Value/type differs at {label}: {actual!r} != {expected!r}")
    elif isinstance(expected, int):
        require(type(actual) is int and actual == expected,
                f"Integer/type differs at {label}: {actual!r} != {expected!r}")
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12),
                f"Recomputed number differs at {label}: {actual!r} != {expected!r}")
    else:
        raise VerificationError("Unsupported comparison type at " + label)


def csv_rows(path, fields=None):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames
        require(header is not None and len(header) == len(set(header)),
                "Missing or duplicated CSV column names: " + str(path))
        if fields is not None:
            require(header == list(fields), "Unexpected CSV schema: " + str(path))
        rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values())
                for row in rows), "Malformed CSV row: " + str(path))
    return rows


def typed_csv(row, template, label):
    require(set(row) == set(template), "CSV columns differ: " + label)
    result = {}
    for key, expected in template.items():
        text = row[key]
        try:
            if expected is None:
                require(text == "", "Expected empty nullable CSV cell")
                result[key] = None
            elif isinstance(expected, bool):
                require(text in ("True", "False"), "Invalid Boolean CSV cell")
                result[key] = text == "True"
            elif isinstance(expected, int):
                require(re.fullmatch(r"-?[0-9]+", text) is not None, "Invalid integer CSV cell")
                result[key] = int(text)
            elif isinstance(expected, float):
                result[key] = float(text)
                require(math.isfinite(result[key]), "Nonfinite CSV cell")
            else:
                result[key] = text
        except (ValueError, TypeError) as exc:
            raise VerificationError(f"{label}.{key}: {exc}") from exc
    return result


def unique_keys(rows, keys, expected, label):
    values = [tuple(row[key] for key in keys) for row in rows]
    require(len(values) == len(set(values)), "Duplicate " + label)
    same([list(v) for v in values], [list(v) for v in expected], label + " coverage/order")


def nonnegative_times(record, keys, label):
    for key in keys:
        value = record[key]
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                "Invalid measured time: " + label + "." + key)


def slug(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:96] + "_" + hashlib.sha256(name.encode()).hexdigest()[:8]


def label_hash(labels):
    labels = valid_labels(labels)
    header = json.dumps(list(labels.shape), separators=(",", ":")).encode()
    return hashlib.sha256(header + b"\n" + labels.astype("<u4").tobytes(order="C")).hexdigest()


def pixel_hash(pixels):
    header = canonical({"shape": list(pixels.shape), "dtype": str(pixels.dtype)}).encode()
    return hashlib.sha256(header + b"\n" + pixels.tobytes(order="C")).hexdigest()


def valid_labels(value):
    value = np.asarray(value)
    require(value.ndim == 2 and value.size > 0 and value.dtype.kind in "iu",
            "Labels must be a nonempty integer image")
    require(np.all(value >= 0) and int(value.max(initial=0)) <= 0xffffffff,
            "Labels outside the canonical nonnegative uint32 range")
    return value


def compact_labels(labels):
    labels = valid_labels(labels)
    ids = np.unique(labels)
    ids = ids[ids > 0]
    result = np.zeros(labels.shape, dtype=np.int32)
    if len(ids):
        positive = labels > 0
        result[positive] = np.searchsorted(ids, labels[positive]) + 1
    return result


def remove_frame(labels):
    labels = valid_labels(labels).copy()
    ids = np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    labels[np.isin(labels, ids[ids > 0])] = 0
    return compact_labels(labels)


def component_reference(channel):
    """Equal-colour 8-connected components, numbered by first raster pixel."""
    require(channel.ndim == 2 and channel.dtype.kind in "iu", "Invalid RGB reference channel")
    labels = np.zeros(channel.shape, dtype=np.int32)
    offset = 0
    for value in np.unique(channel):
        if value == 0:
            continue
        regions, count = ndi.label(channel == value, structure=np.ones((3, 3), dtype=bool))
        positive = regions > 0
        labels[positive] = regions[positive] + offset
        offset += count
    if not offset:
        return labels
    ids, first = np.unique(labels, return_index=True)
    foreground = ids > 0
    ordered = ids[foreground][np.argsort(first[foreground])]
    mapping = np.zeros(offset + 1, dtype=np.int32)
    mapping[ordered] = np.arange(1, len(ordered) + 1)
    return mapping[labels]


def outline_reference(raw):
    """Independent implementation of the frozen outline interpretation."""
    a = np.asarray(raw)
    if a.dtype.kind == "b":
        a = a.astype(np.uint8)
    require(a.ndim == 2 and min(a.shape) >= 3 and a.dtype.kind in "iu",
            "Reference outlines must be 2D binary integer/bool rasters")
    values = np.unique(a)
    require(len(values) <= 2, "Reference outline has more than two intensities")
    edge = np.r_[a[0], a[-1], a[:, 0], a[:, -1]]
    levels, counts = np.unique(edge, return_counts=True)
    background = levels[int(np.argmax(counts))]
    line = a != background
    regions, _ = ndi.label(~line, structure=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]))
    outside = np.unique(np.r_[regions[0], regions[-1], regions[:, 0], regions[:, -1]])
    regions[np.isin(regions, outside)] = 0
    regions = compact_labels(regions)
    attached = np.zeros(a.shape, dtype=bool)
    if np.any(regions):
        distance, nearest = ndi.distance_transform_edt(regions == 0, return_indices=True)
        attached = line & (distance <= math.sqrt(2))
        regions[attached] = regions[nearest[0][attached], nearest[1][attached]]
    frame = np.unique(np.r_[regions[0], regions[-1], regions[:, 0], regions[:, -1]])
    frame = frame[frame > 0]
    regions[np.isin(regions, frame)] = 0
    regions = compact_labels(regions)
    assigned = line & (regions > 0)
    diagnostics = {
        "shape": list(a.shape), "outline_values": [int(x) for x in values],
        "frame_background_value": int(background), "outline_pixels": int(line.sum()),
        "assigned_outline_pixels_before_frame_exclusion": int(attached.sum()),
        "frame_touching_decoded_regions_excluded": int(len(frame)),
        "assigned_outline_pixels": int(assigned.sum()),
        "assigned_outline_fraction": float(assigned.sum() / max(1, line.sum())),
        "decoded_instances": int(regions.max(initial=0)),
        "decoded_foreground_pixels": int(np.count_nonzero(regions)),
        "interpretation": "closed_4_connected_interiors_frame_excluded_nearest_line_pixels_within_sqrt2",
    }
    return regions, diagnostics


def raw_adapter(a, mode):
    require(a.dtype.kind in "uif" and np.isfinite(a).all() and np.all(a >= 0),
            "Invalid raw observation values")
    if mode == "RGB":
        require(a.ndim == 3 and a.shape[2] == 3 and a.dtype == np.uint8,
                "Unsupported RGB representation")
        rgb = a.astype(np.uint32)
        result = ((19595 * rgb[..., 0] + 38470 * rgb[..., 1] + 7471 * rgb[..., 2] + 32768) >> 16).astype(np.uint8)
        conversion, lossy = "Pillow.Image.convert(L)", True
    else:
        require(a.ndim == 2, "Unsupported scalar observation representation")
        result = a.copy()
        conversion, lossy = "none_scalar", False
    receipt = {
        "schema": "learning-to-build/raw-observation-adapter/v1",
        "input_mode": mode, "input_shape": list(a.shape), "input_dtype": str(a.dtype),
        "output_shape": list(result.shape), "output_dtype": str(result.dtype),
        "conversion": conversion, "lossy_color_projection": lossy, "spatial_transform": "none",
        "library_version": "13.0.0", "original_pixel_sha256": pixel_hash(a),
        "canonical_pixel_sha256": pixel_hash(result),
    }
    return result, receipt


@dataclass
class ReferenceCase:
    name: str
    dna: np.ndarray
    truth: np.ndarray
    sources: dict
    diagnostics: dict
    actin: np.ndarray | None = None
    nucleus_truth: np.ndarray | None = None


class PublicData:
    """No producer decoder import; every reference starts at pinned ZIP bytes."""
    def __init__(self, cache, protocol):
        self.cache = Path(cache)
        self.protocol = protocol
        self.archives = {}
        self.zips = {}
        self.members = {}
        for key, expected in protocol["data"]["archives"].items():
            path = self.cache / (key + ".zip")
            require(path.is_file() and not path.is_symlink(), "Missing regular archive: " + str(path))
            actual = dict(url=expected["url"], bytes=path.stat().st_size, sha256=file_hash(path))
            same(actual, expected, "public archive " + key)
            self.archives[key] = actual
            archive = zipfile.ZipFile(path)
            names = [item.filename for item in archive.infolist() if not item.is_dir()
                     and not item.filename.startswith("__MACOSX/")
                     and not PurePosixPath(item.filename).name.startswith(".")]
            require(len(names) == len(set(names)), "Duplicate ZIP member: " + key)
            self.zips[key], self.members[key] = archive, sorted(names)
        metadata = self.zips["bbbc039_metadata"]
        self.split039 = {s: metadata.read("metadata/" + s + ".txt").decode().splitlines()
                         for s in ("training", "validation", "test")}
        self.plates = dict(row.split(",") for row in metadata.read("metadata/filenames_and_plates.csv").decode().splitlines())
        all_names = sum(self.split039.values(), [])
        require(len(all_names) == len(set(all_names)) == 200 and set(all_names) == set(self.plates),
                "Invalid official source partition")
        require([len(self.split039[x]) for x in ("training", "validation", "test")] == [100, 50, 50],
                "Invalid official source cohort sizes")
        self.map039 = {}
        for kind, archive_key, suffixes in (
            ("dna", "bbbc039_images", (".tif", ".tiff", ".png")),
            ("truth", "bbbc039_masks", (".png",))):
            mapping = {}
            for name in self.members[archive_key]:
                path = PurePosixPath(name)
                if path.suffix.lower() in suffixes:
                    require(path.stem not in mapping, "Ambiguous source field stem")
                    mapping[path.stem] = name
            self.map039[kind] = mapping
        self.map007 = {}
        for member in self.members["bbbc007_images"]:
            path = PurePosixPath(member)
            require(path.suffix.lower() == ".tif" and len(path.parts) >= 3,
                    "Unexpected successor raw member")
            relative = PurePosixPath(*path.parts[1:])
            stem, folder = relative.stem, relative.parent.as_posix()
            if folder == "A9":
                require(stem[-1] in "df", "Unknown A9 channel")
                channel, base = ("dna" if stem[-1] == "d" else "actin"), stem[:-1]
            elif folder == "f113":
                require(stem.endswith(("d0", "d1")), "Unknown f113 channel")
                channel, base = ("dna" if stem.endswith("d0") else "actin"), stem[:-2]
            else:
                match = re.fullmatch(r"(.+)_([DF])_[12]UL", stem)
                require(match is not None, "Unknown successor channel")
                base, letter = match.groups()
                channel = "dna" if letter == "D" else "actin"
            name = (relative.parent / base).as_posix()
            mapping = self.map007.setdefault(name, {})
            require(channel not in mapping, "Duplicate successor raw channel")
            outline = "BBBC007_v1_outlines/" + relative.as_posix()
            require(outline in self.members["bbbc007_outlines"], "Missing successor reference")
            mapping[channel] = member
            mapping["nucleus_outline" if channel == "dna" else "cell_outline"] = outline
        require(len(self.map007) == 16 and all(set(v) == {"dna", "actin", "nucleus_outline", "cell_outline"}
                                              for v in self.map007.values()), "Incomplete successor pairing")
        names = sorted(self.map007)
        same(protocol["data"]["bbbc007"]["calibration_ids"], names[:4], "calibration IDs")
        same(protocol["data"]["bbbc007"]["test_ids"], names[4:], "test IDs")

    def names039(self, split):
        return [PurePosixPath(x).stem for x in self.split039[split]]

    def pixels(self, archive_key, member, include_mode=False):
        raw = self.zips[archive_key].read(member)
        with Image.open(io.BytesIO(raw)) as image:
            array, mode = np.asarray(image).copy(), image.mode
        source = dict(member=member, sha256=hashlib.sha256(raw).hexdigest(),
                      shape=list(array.shape), dtype=str(array.dtype))
        if include_mode:
            source["mode"] = mode
        return array, source, mode

    @lru_cache(maxsize=4)
    def case039(self, split, name):
        require(name in self.names039(split), "Field outside official source split")
        dna, dna_source, _ = self.pixels("bbbc039_images", self.map039["dna"][name])
        rgb, ref_source, _ = self.pixels("bbbc039_masks", self.map039["truth"][name])
        require(dna.ndim == 2 and rgb.ndim == 3 and rgb.shape[:2] == dna.shape,
                "Invalid source image/reference shapes")
        truth = component_reference(rgb[..., 0])
        original = next(x for x in self.split039[split] if PurePosixPath(x).stem == name)
        return ReferenceCase(name, dna, truth, dict(dna=dna_source, truth=ref_source,
                             plate=self.plates[original], official_split=split), {})

    @lru_cache(maxsize=4)
    def case007(self, name):
        require(name in self.map007, "Unregistered successor field")
        mapping = self.map007[name]
        raw, sources = {}, {}
        for key, member in mapping.items():
            archive = "bbbc007_images" if key in ("dna", "actin") else "bbbc007_outlines"
            a, source, mode = self.pixels(archive, member, include_mode=key in ("dna", "actin"))
            if key in ("dna", "actin"):
                a, source["observation_adapter"] = raw_adapter(a, mode)
            raw[key], sources[key] = a, source
        require(all(a.shape == raw["dna"].shape for a in raw.values()) and raw["dna"].ndim == 2,
                "Successor channel/reference shape mismatch")
        cells, cell_info = outline_reference(raw["cell_outline"])
        nuclei, nuc_info = outline_reference(raw["nucleus_outline"])
        diagnostics = dict(cell=cell_info, nucleus=nuc_info,
                           counts_agree=cell_info["decoded_instances"] == nuc_info["decoded_instances"])
        return ReferenceCase(name, raw["dna"], cells, sources, diagnostics,
                             raw["actin"], nuclei)


def inner_boundary(labels):
    """Four-neighbour label transitions inside a full 3x3 foreground square."""
    labels = valid_labels(labels)
    padded = np.pad(labels, 1, mode="edge")
    changes = ((padded[:-2, 1:-1] != labels) | (padded[2:, 1:-1] != labels)
               | (padded[1:-1, :-2] != labels) | (padded[1:-1, 2:] != labels))
    interior = ndi.minimum_filter((labels > 0).astype(np.uint8), size=3, mode="constant", cval=0) > 0
    return changes & interior


def score(prediction, reference):
    """Recompute every reported metric without the producer's score function."""
    p, t = valid_labels(prediction), valid_labels(reference)
    require(p.shape == t.shape, "Prediction/reference shape mismatch")
    pids, pindex = np.unique(p, return_inverse=True)
    tids, tindex = np.unique(t, return_inverse=True)
    pn, tn = int(np.count_nonzero(pids)), int(np.count_nonzero(tids))
    table = np.zeros((len(pids), len(tids)), dtype=np.int64)
    np.add.at(table, (pindex.ravel(), tindex.ravel()), 1)
    pa = table.sum(axis=1)[pids > 0]
    ta = table.sum(axis=0)[tids > 0]
    overlap = table[np.ix_(pids > 0, tids > 0)]
    union = pa[:, None] + ta[None, :] - overlap
    eligible = overlap * 2 > union
    # With non-overlapping label images and strict IoU > .5, a label cannot
    # have two eligible partners. This independently avoids assignment ties.
    require(np.all(eligible.sum(axis=0) <= 1) and np.all(eligible.sum(axis=1) <= 1),
            "Invalid strict-IoU matching geometry")
    pi, ti = np.nonzero(eligible)
    tp = int(len(pi))
    area_error = float(np.sum(np.abs(pa[pi] - ta[ti]) / ta[ti])) if tp else 0.0
    fp, fn = pn - tp, tn - tp
    denom = pn + tn
    f1 = 2.0 * tp / denom if denom else 1.0
    pf, tf = p > 0, t > 0
    area = int(pf.sum() + tf.sum())
    dice = 2.0 * np.count_nonzero(pf & tf) / area if area else 1.0
    pb, tb = inner_boundary(p), inner_boundary(t)
    npb, ntb = int(pb.sum()), int(tb.sum())
    if npb == ntb == 0:
        precision = recall = bf1 = 1.0
    elif npb == 0 or ntb == 0:
        precision = recall = bf1 = 0.0
    else:
        precision = float(np.count_nonzero(ndi.distance_transform_edt(~tb)[pb] <= 2) / npb)
        recall = float(np.count_nonzero(ndi.distance_transform_edt(~pb)[tb] <= 2) / ntb)
        bf1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return dict(
        predicted_count=pn, reference_count=tn, tp=tp, fp=fp, fn=fn, instance_f1=float(f1),
        relative_count_error=float(abs(pn - tn) / max(1, tn)),
        foreground_dice=float(dice), boundary_precision=precision, boundary_recall=recall,
        internal_boundary_f1=bf1, reference_internal_boundary_pixels=ntb,
        predicted_internal_boundary_pixels=npb, reference_foreground_pixels=int(tf.sum()),
        predicted_foreground_pixels=int(pf.sum()), matched_area_error_sum=area_error,
        matched_area_relative_error=area_error / tp if tp else None,
        matched_pair_count=tp, matched_reference_fraction=tp / tn if tn else None,
        matched_predicted_fraction=tp / pn if pn else None)


def aggregate(rows):
    require(len(rows) > 0, "Empty cohort cannot qualify")
    out = {"fields": len(rows)}
    for metric in MEANS:
        out["mean_" + metric] = math.fsum(row[metric] for row in rows) / len(rows)
    bearing = [row["internal_boundary_f1"] for row in rows if row["reference_internal_boundary_pixels"] > 0]
    out["boundary_bearing_fields"] = len(bearing)
    out["mean_boundary_f1_on_reference_boundary_bearing_fields"] = math.fsum(bearing) / len(bearing) if bearing else None
    out["total_reference_instances"] = sum(row["reference_count"] for row in rows)
    out["total_predicted_instances"] = sum(row["predicted_count"] for row in rows)
    out["matched_pair_count"] = sum(row["matched_pair_count"] for row in rows)
    out["matched_area_error_sum"] = math.fsum(row["matched_area_error_sum"] for row in rows)
    count, pairs = out["total_reference_instances"], out["matched_pair_count"]
    out["pooled_matched_area_relative_error"] = out["matched_area_error_sum"] / pairs if pairs else None
    out["matched_reference_fraction"] = pairs / count if count else None
    return out


def qualified(summary, task, criteria, heldout=False):
    if task == "nuclei":
        b = criteria["nuclei"]
        return bool(summary["mean_instance_f1"] >= b["mean_instance_f1_at_iou_strictly_greater_than_0_5_min"]
                    and summary["mean_relative_count_error"] <= b["mean_relative_count_error_max"]
                    and summary["mean_foreground_dice"] >= b["mean_foreground_dice_min"])
    b = criteria["cells"]
    bearing = summary["mean_boundary_f1_on_reference_boundary_bearing_fields"]
    return bool(
        summary["mean_internal_boundary_f1"] >= b["mean_internal_boundary_f1_within_2_pixels_min"]
        and bearing is not None and bearing >= b["mean_boundary_f1_on_reference_boundary_bearing_fields_min"]
        and summary["mean_relative_count_error"] <= b["mean_relative_count_error_max"]
        and summary["mean_foreground_dice"] >= b["mean_foreground_dice_min"]
        and summary["boundary_bearing_fields"] >= b["minimum_boundary_bearing_test_fields" if heldout
                                                   else "minimum_boundary_bearing_calibration_fields"])


def measure(labels, field):
    result = []
    for r in regionprops(valid_labels(labels)):
        coords = r.coords
        result.append(dict(field=field, label=int(r.label), area_pixels=int(len(coords)),
                           centroid_row=float(coords[:, 0].mean()), centroid_column=float(coords[:, 1].mean()),
                           perimeter_pixels=float(r.perimeter),
                           equivalent_diameter_pixels=float(2 * math.sqrt(len(coords) / math.pi)),
                           eccentricity=float(r.eccentricity),
                           major_axis_length_pixels=float(r.axis_major_length),
                           minor_axis_length_pixels=float(r.axis_minor_length)))
    return result


def field_record(case, recipe, task, metrics, array_sha, mask_path="", mask_sha="",
                 artifact=False, oracle=False):
    return dict(field=case.name, recipe_id=recipe, task=task,
                height=int(case.truth.shape[0]), width=int(case.truth.shape[1]), **metrics,
                label_array_sha256=array_sha, mask_path=mask_path, mask_sha256=mask_sha,
                artifact_executed=artifact, reference_inputs_used=oracle,
                **{key: 0.0 for key in TIME_FIELDS})


class Evidence:
    """Track every consumed file and reject path escapes, symlinks and omissions."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        require(self.root.is_dir(), "Missing evidence directory: " + str(self.root))
        self.used = set()
        self.actual = self.scan()
        self.initial_hashes = {name: file_hash(path) for name, path in self.actual.items()}

    def scan(self):
        actual = {}
        for path in sorted(self.root.rglob("*")):
            require(not path.is_symlink(), "Evidence contains symlink: " + str(path))
            if path.is_file():
                actual[path.relative_to(self.root).as_posix()] = path
        return actual

    def path(self, relative):
        require(isinstance(relative, str) and relative and "\\" not in relative,
                "Invalid evidence path")
        parts = PurePosixPath(relative)
        require(not parts.is_absolute() and ".." not in parts.parts
                and parts.as_posix() == relative, "Noncanonical evidence path: " + relative)
        require(relative in self.actual, "Missing evidence file: " + relative)
        path = self.actual[relative]
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(self.root),
                "Evidence path changed: " + relative)
        self.used.add(relative)
        return path

    def json(self, relative):
        return load_json(self.path(relative))

    def csv(self, relative, fields=None):
        return csv_rows(self.path(relative), fields)

    def hash(self, relative):
        return file_hash(self.path(relative))

    def tree(self, relative=""):
        prefix = relative + "/" if relative else ""
        return {name[len(prefix):]: file_hash(path) for name, path in self.actual.items()
                if name.startswith(prefix)}

    def inventory(self):
        fresh = self.scan()
        require(set(fresh) == set(self.actual), "Evidence inventory changed during verification")
        final_hashes = {name: file_hash(path) for name, path in fresh.items()}
        require(final_hashes == self.initial_hashes, "Evidence bytes changed during verification")
        require(set(self.actual) == self.used,
                "Unaccounted evidence files: " + ", ".join(sorted(set(self.actual) - self.used)[:8]))
        return {"files": len(self.actual),
                "tree_sha256": hashlib.sha256(canonical(final_hashes).encode()).hexdigest(),
                "entry_and_exit_inventory_identical": True}


def source_contract():
    for name, digest in PINNED.items():
        require((BASE / name).is_file() and file_hash(BASE / name) == digest,
                "Registered source changed: " + name)
    protocol = load_json(BASE / "PROTOCOL-amendment-2.json")
    registration = load_json(BASE / "REGISTRATION-amendment-2.json")
    require([arm["id"] for arm in protocol["arms"]] == list(ARMS), "Registered arm order changed")
    runtime = dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                   **{"scikit-image": skimage.__version__, "Pillow": PIL.__version__})
    for name, expected in registration["runtime_versions"].items():
        require(runtime[name].split(".")[:2] == expected.split(".")[:2] if name == "python"
                else runtime[name] == expected, "Checker runtime differs: " + name)
    return protocol, registration, runtime


def registered_predictor():
    """Prediction reproduction only. Acceptance functions never come from it."""
    name = "_registered_ltb_prediction_only"
    spec = importlib.util.spec_from_file_location(name, BASE / "instrument.py")
    require(spec is not None and spec.loader is not None, "Cannot load registered predictor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


class Verifier:
    def __init__(self, public, protocol, registration, replay_search=True):
        self.public, self.protocol, self.registration = public, protocol, registration
        self.replay_search = replay_search
        self.predictor = registered_predictor()
        self.replayed = {}
        self.saved_fields = 0

    def generated(self, case, recipe, task, mode="primary"):
        key = (case.name, recipe, task, mode)
        if key not in self.replayed:
            r = self.predictor.recipe_from_dict(RECIPE_DICTS[recipe])
            if mode == "oracle":
                labels = self.predictor.segment_cells(case.dna, case.actin, r,
                            nucleus_labels=case.nucleus_truth, foreground_override=case.truth > 0)
            elif mode == "old_artifact":
                labels = remove_frame(self.predictor.segment_nuclei(case.dna, r))
            else:
                labels = self.predictor.apply(case.dna, r, task, case.actin)
            self.replayed[key] = (score(labels, case.truth), label_hash(labels))
        return self.replayed[key]

    def saved_cohort(self, evidence, directory, names, case_for, recipe, task,
                     artifact=False, oracle=False, mode="primary", replay=True, incumbent=False):
        rows = evidence.csv(directory + "/metrics.csv")
        unique_keys(rows, ("field",), [(name,) for name in names], directory)
        manifest = evidence.json(directory + "/MASKS.json")
        same(sorted(manifest), sorted(names), directory + " mask coverage")
        checked, measurements, per_field = [], [], {}
        for row, name in zip(rows, names):
            case = case_for(name)
            relative = "masks/" + slug(name) + ".png"
            path = evidence.path(directory + "/" + relative)
            with Image.open(path) as image:
                require(image.format == "PNG", "Mask is not PNG")
                labels = valid_labels(np.asarray(image).copy())
            require(labels.shape == case.truth.shape, "Saved-mask shape differs from raw field")
            current_sha, array_sha = file_hash(path), label_hash(labels)
            metrics = score(labels, case.truth)
            if replay:
                regenerated, expected_sha = self.generated(case, recipe, task, mode)
                same(array_sha, expected_sha, directory + "/" + name + " regenerated prediction")
                same(metrics, regenerated, directory + "/" + name + " regenerated scores")
            expected_mask = dict(path=relative, sha256=current_sha, label_array_sha256=array_sha,
                                 shape=list(labels.shape), sources=case.sources,
                                 reference_label_array_sha256=label_hash(case.truth),
                                 decoder_diagnostics=case.diagnostics)
            extra = {}
            if incumbent and task == "cells":
                raw_path = "pre_border_masks/" + slug(name) + ".png"
                raw_file = evidence.path(directory + "/" + raw_path)
                with Image.open(raw_file) as image:
                    require(image.format == "PNG", "Pre-border mask is not PNG")
                    raw = valid_labels(np.asarray(image).copy())
                require(raw.shape == labels.shape, "Pre-border geometry differs")
                same(label_hash(remove_frame(raw)), array_sha, directory + "/" + name + " border policy")
                raw_count = int(np.count_nonzero(np.unique(raw)))
                expected_mask["pre_border_exclusion"] = dict(path=raw_path, sha256=file_hash(raw_file),
                    label_array_sha256=label_hash(raw), shape=list(raw.shape), objects=raw_count)
                extra["frame_objects_excluded"] = raw_count - metrics["predicted_count"]
            elif incumbent:
                extra["frame_objects_excluded"] = 0
            same(manifest[name], expected_mask, directory + "/" + name + " source/mask provenance")
            expected = field_record(case, recipe, task, metrics, array_sha, relative, current_sha, artifact, oracle)
            expected.update(extra)
            actual = typed_csv(row, expected, directory + "/" + name)
            nonnegative_times(actual, TIME_FIELDS, directory + "/" + name)
            for key in TIME_FIELDS:
                expected[key] = actual[key]
            same(actual, expected, directory + "/" + name + " metrics")
            field_measurements = measure(labels, name)
            if incumbent:
                receipt = evidence.json(directory + "/fields/" + slug(name) + ".json")
                same(receipt, dict(field=name, metrics=actual, measurements=field_measurements,
                                   mask=expected_mask), directory + "/" + name + " field receipt")
            checked.append(actual)
            measurements.extend(field_measurements)
            per_field[name] = {"metrics": actual, "mask": expected_mask, "measurements": field_measurements}
            self.saved_fields += 1
        reported = evidence.csv(directory + "/measurements.csv", ("field",) + MEASUREMENTS)
        require(len(reported) == len(measurements), "Missing/extra per-instance measurements: " + directory)
        for row, expected in zip(reported, measurements):
            same(typed_csv(row, expected, directory + " measurement"), expected, directory + " measurement")
        return checked, aggregate(checked), per_field

    def search_rows(self, evidence, relative, names, recipes, case_for, task, donor_recipe=None,
                    artifact_access=False):
        rows = evidence.csv(relative)
        expected_keys = [(rid, name) for rid in recipes for name in names]
        unique_keys(rows, ("recipe_id", "field"), expected_keys, relative)
        by_key = {(row["recipe_id"], row["field"]): row for row in rows}
        parsed = {}
        # Field-major replay avoids decoding each training field 24 times.
        for index, name in enumerate(names):
            case = case_for(name)
            for rid in recipes:
                row = by_key[(rid, name)]
                used = bool(artifact_access and rid == donor_recipe)
                if self.replay_search:
                    metrics, array_sha = self.generated(case, rid, task)
                    expected = field_record(case, rid, task, metrics, array_sha, artifact=used)
                    actual = typed_csv(row, expected, relative + "/" + rid + "/" + name)
                    nonnegative_times(actual, TIME_FIELDS, relative)
                    for key in TIME_FIELDS:
                        expected[key] = actual[key]
                    same(actual, expected, relative + "/" + rid + "/" + name)
                else:
                    actual = parse_unretained_row(row, case, rid, task, used, relative)
                parsed[(rid, name)] = actual
            if self.replay_search and len(names) >= 25 and (index + 1) % 25 == 0:
                print(f"Verified {relative}: {index + 1}/{len(names)} fields across {len(recipes)} recipes", file=sys.stderr, flush=True)
        return [parsed[key] for key in expected_keys]

    def check_instrument(self, evidence, directory, recipe, task, provenance):
        program_hash = evidence.hash(directory + "/instrument.py")
        same(program_hash, PINNED["instrument.py"], directory + " executable")
        expected = dict(schema="learning-to-build/microscopy-instrument/v1", task=task,
                        recipe=RECIPE_DICTS[recipe], recipe_bank_sha256=BANK_SHA,
                        parameters=self.predictor.PARAMETERS, program_sha256=program_hash,
                        provenance=provenance, measurement_units="pixels", clinical_use=False)
        same(evidence.json(directory + "/instrument.json"), expected, directory + " instrument")
        return evidence.hash(directory + "/instrument.json")

    def classical(self, root):
        e = Evidence(root)
        protocol_copy, registration_copy = e.hash("PROTOCOL.json"), e.hash("REGISTRATION.json")
        same(protocol_copy, PINNED["PROTOCOL-amendment-2.json"], "retained primary protocol")
        same(registration_copy, PINNED["REGISTRATION-amendment-2.json"], "retained primary registration")
        state = e.json("RUN_STATE.json")
        result = e.json("RESULTS.json")
        status = e.json("STATUS.json")
        require(state["schema"] == "learning-to-build/microscopy-run-state/v1"
                and state["status"] == "COMPLETE" and set(state["stages"]) == {"donor", "source", "successor"},
                "Incomplete classical run/checkpoint coverage")
        same(e.hash("RESULTS.json"), state["results_sha256"], "classical final result seal")
        binding = dict(protocol_sha256=protocol_copy, registration_sha256=registration_copy,
                       implementation_files={name: PINNED[name] for name in
                                             ("instrument.py", "builder.py", "data.py", "run.py", "requirements.txt")},
                       archives=self.public.archives, recipe_bank_sha256=BANK_SHA,
                       runtime_versions=state["bindings"]["runtime_versions"])
        validate_runtime(binding["runtime_versions"], self.registration["runtime_versions"], "classical")
        same(state["bindings"], binding, "classical source/data/runtime bindings")
        same(result["bindings"], binding, "classical result bindings")
        for stage, receipt in state["stages"].items():
            same(receipt["files"], e.tree(stage), stage + " complete checkpoint tree")
            nonnegative_times(receipt, ("actual_cpu_seconds", "actual_wall_seconds"), stage)

        training = self.public.names039("training")
        history = self.search_rows(e, "donor/history.csv", training, list(RECIPE_DICTS),
                                  lambda name: self.public.case039("training", name), "nuclei")
        donor_summaries = {rid: aggregate([row for row in history if row["recipe_id"] == rid])
                           for rid in RECIPE_DICTS}
        selected = min(donor_summaries, key=lambda rid:
            (donor_summaries[rid]["mean_relative_count_error"], -donor_summaries[rid]["mean_instance_f1"],
             -donor_summaries[rid]["mean_foreground_dice"], rid))
        orders, learned = rebuild_orders(history, donor_summaries, selected, self.protocol["criteria"])
        same(e.json("donor/learned_order.json"), learned, "learned ordering/coverage")
        same(e.json("donor/orders.json"), orders, "all six construction orders")
        donor = dict(task="nuclei", training_fields=100, recipes_evaluated=24,
                     field_evaluations=2400, selected_recipe_id=selected,
                     selected_training=donor_summaries[selected],
                     all_recipe_training_summaries=donor_summaries,
                     selected_training_qualified=qualified(donor_summaries[selected], "nuclei", self.protocol["criteria"]),
                     history_sha256=e.hash("donor/history.csv"),
                     learning_scope="Greedy coverage updates an ordering parameter of a supplied finite policy.",
                     program_or_operator_discovery=False)
        same(e.json("donor/summary.json"), donor, "donor summary")

        provenance = dict(protocol_sha256=protocol_copy, registration_sha256=registration_copy,
                          construction_history_sha256=donor["history_sha256"],
                          selection_cohort="BBBC039 official training only")
        source_sha = self.check_instrument(e, "source/instrument", selected, "nuclei", provenance)
        source = dict(selected_recipe_id=selected, cohorts={})
        for split in ("validation", "test"):
            _, summary, _ = self.saved_cohort(e, "source/" + split, self.public.names039(split),
                lambda name, split=split: self.public.case039(split, name), selected, "nuclei")
            source["cohorts"][split] = summary
            source[split + "_qualified"] = qualified(summary, "nuclei", self.protocol["criteria"])
        source["complete_qualification"] = source["validation_qualified"] and source["test_qualified"]
        source["independent_laboratory_acceptance"] = False
        source["instrument_sha256"] = source_sha
        same(e.json("source/summary.json"), source, "source qualification")

        target = self.protocol["data"]["bbbc007"]
        calibration_names, test_names = target["calibration_ids"], target["test_ids"]
        selections, arms = {}, {}
        for arm in ARMS:
            directory = "successor/" + arm
            construction = e.json(directory + "/construction.json")
            executed = construction["executed_order"]
            require(isinstance(executed, list) and 1 <= len(executed) <= 24
                    and executed == orders[arm][:len(executed)], "Invalid executed order/prefix: " + arm)
            has_artifact = arm in ("ordinary_reuse", "updated_with_artifact")
            calibration = self.search_rows(e, directory + "/calibration.csv", calibration_names, executed,
                                          self.public.case007, "cells", selected, has_artifact)
            summaries = {rid: aggregate([row for row in calibration if row["recipe_id"] == rid])
                         for rid in executed}
            is_qualified = {rid: qualified(summary, "cells", self.protocol["criteria"])
                            for rid, summary in summaries.items()}
            if arm == "full_enumeration":
                require(executed == orders[arm], "Exhaustive control omitted candidates")
            elif any(is_qualified.values()):
                require(is_qualified[executed[-1]] and not any(is_qualified[rid] for rid in executed[:-1]),
                        "Ranked construction did not stop at the first accepted candidate")
            else:
                require(len(executed) == 24, "Unqualified search stopped before exhausting the bank")
            eligible = [rid for rid in executed if is_qualified[rid]]
            chosen = min(eligible or executed, key=lambda rid: target_rank(summaries[rid], rid))
            if arm != "full_enumeration" and eligible:
                chosen = eligible[0]
            trace = e.csv(directory + "/trace.csv")
            require(len(trace) == len(executed), "Missing/surplus construction trace")
            for index, (rid, row) in enumerate(zip(executed, trace), 1):
                expected = dict(evaluation_index=index, recipe_id=rid, **summaries[rid],
                                calibration_qualified=is_qualified[rid],
                                actual_cpu_seconds=0.0, actual_wall_seconds=0.0)
                actual = typed_csv(row, expected, directory + " trace")
                nonnegative_times(actual, ("actual_cpu_seconds", "actual_wall_seconds"), directory)
                for key in ("actual_cpu_seconds", "actual_wall_seconds"):
                    expected[key] = actual[key]
                same(actual, expected, directory + " trace")
            expected_construction = dict(
                proposed_order=orders[arm], executed_order=executed,
                calibration_candidates_executed=len(executed), calibration_fields=4,
                calibration_field_evaluations=4 * len(executed), exhaustive=arm == "full_enumeration",
                selected_recipe_id=chosen, selected_recipe=RECIPE_DICTS[chosen],
                calibration=summaries[chosen], calibration_qualified=is_qualified[chosen],
                artifact_access=has_artifact,
                artifact_invocations=4 if has_artifact and selected in executed else 0,
                artifact_sha256=source_sha if has_artifact else None,
                actual_construction_cpu_seconds=construction["actual_construction_cpu_seconds"],
                actual_construction_wall_seconds=construction["actual_construction_wall_seconds"])
            nonnegative_times(construction, ("actual_construction_cpu_seconds", "actual_construction_wall_seconds"), directory)
            same(construction, expected_construction, directory + " construction decision")
            provenance = dict(protocol_sha256=protocol_copy, construction_arm=arm,
                              source_history_sha256=donor["history_sha256"], calibration_fields=calibration_names,
                              calibration_qualified=is_qualified[chosen],
                              source_artifact_sha256=source_sha if has_artifact else None)
            generated_sha = self.check_instrument(e, directory + "/instrument", chosen, "cells", provenance)
            selections[arm] = dict(recipe_id=chosen, instrument_sha256=generated_sha,
                                   calibration_candidates_executed=len(executed))
            _, holdout, _ = self.saved_cohort(e, directory + "/holdout", test_names,
                                            self.public.case007, chosen, "cells",
                                            artifact=has_artifact and chosen == selected)
            heldout_ok = qualified(holdout, "cells", self.protocol["criteria"], heldout=True)
            reported = e.json(directory + "/summary.json")
            expected_arm = dict(**expected_construction, holdout=holdout, heldout_qualified=heldout_ok,
                                complete_qualification=bool(is_qualified[chosen] and heldout_ok),
                                actual_holdout_cpu_seconds=reported["actual_holdout_cpu_seconds"],
                                actual_holdout_wall_seconds=reported["actual_holdout_wall_seconds"],
                                heldout_artifact_invocations=12 if has_artifact and chosen == selected else 0,
                                instrument_sha256=generated_sha, reference_inputs_in_primary_prediction=False)
            nonnegative_times(reported, ("actual_holdout_cpu_seconds", "actual_holdout_wall_seconds"), directory)
            same(reported, expected_arm, directory + " final summary")
            arms[arm] = expected_arm
        same(e.json("successor/SELECTIONS_BEFORE_TEST.json"), selections,
             "all-six retained pre-test selections")
        diagnostics = {}
        for name in ("old_artifact", "oracle_input"):
            directory = "successor/diagnostics/" + name
            recipe = selected if name == "old_artifact" else arms["full_enumeration"]["selected_recipe_id"]
            _, summary, _ = self.saved_cohort(e, directory, test_names, self.public.case007, recipe, "cells",
                artifact=name == "old_artifact", oracle=name == "oracle_input",
                mode="old_artifact" if name == "old_artifact" else "oracle")
            reported = e.json(directory + "/summary.json")
            expected = dict(recipe_id=recipe, holdout=summary,
                            heldout_criteria_met=qualified(summary, "cells", self.protocol["criteria"], heldout=True),
                            primary_arm=False, complete_raw_channel_qualification=False,
                            manual_reference_inputs_used=name == "oracle_input",
                            actual_cpu_seconds=reported["actual_cpu_seconds"],
                            actual_wall_seconds=reported["actual_wall_seconds"])
            nonnegative_times(reported, ("actual_cpu_seconds", "actual_wall_seconds"), directory)
            same(reported, expected, directory + " diagnostic")
            diagnostics[name] = expected
        updated, ordinary = arms["updated_no_artifact"], arms["same_content_empirical"]
        saved = ordinary["calibration_candidates_executed"] - updated["calibration_candidates_executed"]
        successor = dict(
            task="whole-cell instances from measured DNA plus actin", calibration_fields=4, heldout_fields=12,
            arms=arms, diagnostics=diagnostics,
            primary_comparison=dict(updated_arm="updated_no_artifact", conventional_arm="same_content_empirical",
                candidate_evaluations_saved=saved, updated_qualified=updated["complete_qualification"],
                conventional_qualified=ordinary["complete_qualification"],
                local_accepted_prefix_advantage=bool(updated["complete_qualification"] and saved > 0),
                general_constructor_improvement_established=False, total_lifecycle_advantage_established=False),
            any_primary_arm_qualified=any(a["complete_qualification"] for a in arms.values()),
            direct_full_enumeration_qualified=arms["full_enumeration"]["complete_qualification"],
            exclusive_artifact_enabling_established=False,
            cohort_scope="One source-ordered calibration/test split of a publicly known assay.")
        same(e.json("successor/summary.json"), successor, "complete successor result")
        validate_attempts(e, state)
        expected_result = dict(
            schema="learning-to-build/microscopy-results/v1", status="COMPLETE", bindings=binding,
            source=source, successor=successor, donor=donor, source_qualified=source["complete_qualification"],
            successor_any_primary_qualified=successor["any_primary_arm_qualified"],
            continuation_after_unqualified_donor=not source["complete_qualification"],
            completed_stage_cpu_seconds=sum(row["actual_cpu_seconds"] for row in state["stages"].values()),
            completed_stage_wall_seconds=sum(row["actual_wall_seconds"] for row in state["stages"].values()),
            all_measured_attempt_cpu_seconds=sum(row.get("actual_cpu_seconds", 0.0) for row in state["attempts"]),
            all_measured_attempt_wall_seconds=sum(row.get("actual_wall_seconds", 0.0) for row in state["attempts"]),
            has_unmeasured_interrupted_work=bool(state.get("uncommitted_stage_directories")) or any(
                row["status"] == "INTERRUPTED_WITH_UNMEASURED_REMAINDER" for row in state["attempts"]),
            cost_scope="Measured local run work; authoring, included-model billing, external acceptance and economic costs remain unmeasured.",
            economics=self.protocol["economics"], claims_not_tested=self.protocol["claims_not_tested"])
        same(result, expected_result, "complete classical result")
        same(status, dict(status="COMPLETE", scientific_run_completed=True,
             source_qualified=source["complete_qualification"],
             successor_any_primary_qualified=successor["any_primary_arm_qualified"]), "classical completion status")
        inventory = e.inventory()
        return dict(
            status="VERIFIED" if self.replay_search else "LIMITED_SAVED_MASK_AUDIT",
            inventory=inventory, registered_cohorts={"donor_training": 100, "source_validation": 50,
                "source_test": 50, "successor_calibration_per_arm": 4, "successor_test_per_arm": 12,
                "primary_arms": 6, "diagnostics": 2},
            donor_calibration_predictions_regenerated=self.replay_search,
            source_and_successor_saved_predictions_regenerated=True,
            source_qualified=source["complete_qualification"],
            successor_any_primary_qualified=successor["any_primary_arm_qualified"],
            primary_comparison=successor["primary_comparison"],
            results_sha256=e.hash("RESULTS.json"),
            scope="Reproduction and independent rescoring of exposed registered data; not fresh scientific confirmation or independent historical timing evidence.")


def parse_unretained_row(row, case, recipe, task, artifact, label):
    """Limited mode: validate semantics/coverage without certifying its pixels."""
    template = score(np.zeros_like(case.truth), case.truth)
    for key in ("matched_area_relative_error", "matched_reference_fraction", "matched_predicted_fraction"):
        template[key] = None if row.get(key) == "" else 0.0
    expected = field_record(case, recipe, task, template, row.get("label_array_sha256", ""), artifact=artifact)
    actual = typed_csv(row, expected, label)
    nonnegative_times(actual, TIME_FIELDS, label)
    for key in ("field", "recipe_id", "task", "height", "width", "mask_path",
                "mask_sha256", "artifact_executed", "reference_inputs_used"):
        same(actual[key], expected[key], label + "." + key)
    require(re.fullmatch(r"[0-9a-f]{64}", actual["label_array_sha256"]) is not None, "Invalid prediction hash")
    truth_score = score(np.zeros_like(case.truth), case.truth)
    for key in ("reference_count", "reference_internal_boundary_pixels", "reference_foreground_pixels"):
        same(actual[key], truth_score[key], label + "." + key)
    require(0 <= actual["tp"] <= min(actual["predicted_count"], actual["reference_count"])
            and actual["fp"] == actual["predicted_count"] - actual["tp"]
            and actual["fn"] == actual["reference_count"] - actual["tp"]
            and actual["matched_pair_count"] == actual["tp"], "Invalid match/count arithmetic")
    require(0 <= actual["predicted_count"] <= case.truth.size
            and 0 <= actual["predicted_foreground_pixels"] <= case.truth.size
            and 0 <= actual["predicted_internal_boundary_pixels"] <= case.truth.size, "Invalid predicted counts")
    for key in ("instance_f1", "foreground_dice", "boundary_precision", "boundary_recall", "internal_boundary_f1"):
        require(0 <= actual[key] <= 1, "Metric outside unit interval")
    denom = actual["predicted_count"] + actual["reference_count"]
    same(actual["instance_f1"], 2.0 * actual["tp"] / denom if denom else 1.0, label + ".instance_f1")
    same(actual["relative_count_error"],
         abs(actual["predicted_count"] - actual["reference_count"]) / max(1, actual["reference_count"]),
         label + ".relative_count_error")
    return actual


def target_rank(summary, recipe):
    bearing = summary["mean_boundary_f1_on_reference_boundary_bearing_fields"]
    return (-bearing if bearing is not None else float("inf"), -summary["mean_internal_boundary_f1"],
            -summary["mean_foreground_dice"], summary["mean_relative_count_error"], recipe)


def rebuild_orders(history, summaries, donor, criteria):
    fixed = sorted(RECIPE_DICTS, key=lambda rid: (
        RECIPE_DICTS[rid]["background"] != "opening", RECIPE_DICTS[rid]["threshold"] != "li",
        RECIPE_DICTS[rid]["watershed_surface"] != "intensity", -RECIPE_DICTS[rid]["seed_distance"]))
    covers = {rid: set() for rid in RECIPE_DICTS}
    for row in history:
        one = {"mean_" + key: row[key] for key in MEANS}
        if qualified(one, "nuclei", criteria):
            covers[row["recipe_id"]].add(row["field"])
    uncovered = {row["field"] for row in history}
    remaining = set(RECIPE_DICTS)
    ordering, steps = [], []
    while remaining:
        rid = min(remaining, key=lambda name: (-len(covers[name] & uncovered),
            -summaries[name]["mean_instance_f1"], -summaries[name]["mean_foreground_dice"],
            summaries[name]["mean_relative_count_error"], name))
        new = sorted(covers[rid] & uncovered)
        steps.append(dict(recipe_id=rid, newly_covered_fields=new, newly_covered_count=len(new),
                          remaining_before=len(uncovered)))
        ordering.append(rid)
        uncovered -= covers[rid]
        remaining.remove(rid)
    learned = dict(schema="learning-to-build/finite-coverage-order/v1", order=ordering, steps=steps,
                   uncovered_fields=sorted(uncovered), source_rows=len(history),
                   source_fields=len({row["field"] for row in history}),
                   operator_grammar_supplied=True, learned_object="ordering_parameter",
                   new_algorithm_discovery=False)
    empirical = sorted(RECIPE_DICTS, key=lambda rid: (-summaries[rid]["mean_instance_f1"],
        -summaries[rid]["mean_foreground_dice"], summaries[rid]["mean_relative_count_error"], rid))
    first = lambda sequence: [donor] + [rid for rid in sequence if rid != donor]
    return dict(fixed_no_history=fixed, ordinary_reuse=first(fixed), updated_no_artifact=ordering,
                updated_with_artifact=first(ordering), same_content_empirical=empirical,
                full_enumeration=fixed), learned


def validate_runtime(actual, expected, label):
    require(set(actual) == set(expected), label + " runtime keys differ")
    for key, value in expected.items():
        if key == "python":
            require(type(actual[key]) is str and actual[key].split(".")[:2] == value.split(".")[:2],
                    label + " Python minor version differs")
        else:
            same(actual[key], value, label + " runtime " + key)


def validate_attempts(e, state):
    require(isinstance(state["attempts"], list) and state["attempts"], "Missing attempt history")
    pairs, paths, completed = set(), set(), set()
    for attempt in state["attempts"]:
        stage, number = attempt["stage"], attempt["attempt"]
        require(stage in ("donor", "source", "successor") and type(number) is int and number > 0,
                "Invalid attempt identity")
        require((stage, number) not in pairs and attempt["path"] not in paths, "Duplicate attempt/path")
        pairs.add((stage, number))
        paths.add(attempt["path"])
        status = attempt["status"]
        require(status in ("COMPLETE", "FAILED", "INTERRUPTED_WITH_UNMEASURED_REMAINDER"),
                "Completed run retains an unclosed/unknown attempt")
        if status == "COMPLETE":
            require(attempt["path"] == stage and stage not in completed, "Invalid completed attempt identity")
            completed.add(stage)
            for key in ("actual_cpu_seconds", "actual_wall_seconds"):
                same(attempt[key], state["stages"][stage][key], "checkpoint measured time")
        else:
            prefix = attempt["path"]
            require(prefix.startswith("attempts/") and ".." not in PurePosixPath(prefix).parts,
                    "Invalid retained attempt path")
            require(any(name.startswith(prefix + "/") for name in e.actual), "Missing retained unsuccessful work")
            if status == "FAILED":
                failure = e.json(prefix + "/FAILURE.json")
                require(type(failure.get("traceback")) is str, "Missing retained failure diagnostic")
                for key, value in attempt.items():
                    same(failure[key], value, "failed attempt receipt." + key)
            else:
                same(attempt.get("unmeasured_work_is_not_zero"), True, "interruption uncertainty")
            for name in e.actual:
                if name.startswith(prefix + "/"):
                    e.used.add(name)
        if status != "INTERRUPTED_WITH_UNMEASURED_REMAINDER":
            nonnegative_times(attempt, ("actual_cpu_seconds", "actual_wall_seconds"), "attempt")
    require(completed == {"donor", "source", "successor"}, "Missing successful attempt denominator")
    for orphan in state.get("uncommitted_stage_directories", []):
        prefix = orphan["path"]
        require(prefix.startswith("attempts/") and ".." not in PurePosixPath(prefix).parts,
                "Invalid orphan evidence path")
        same(orphan["files"], e.tree(prefix), "retained uncommitted output")
        same(orphan["unmeasured_work_is_not_zero"], True, "uncommitted cost uncertainty")
        e.used.update(name for name in e.actual if name.startswith(prefix + "/"))
    require(isinstance(state["invocations"], list) and state["invocations"], "Missing invocation receipts")
    for invocation in state["invocations"]:
        nonnegative_times(invocation, ("actual_cpu_seconds", "actual_wall_seconds"), "invocation")
        require(invocation["status"] in ("PARTIAL", "FAILED", "COMPLETE"), "Invalid invocation status")
        require(len(invocation["completed_stages"]) == len(set(invocation["completed_stages"]))
                and set(invocation["completed_stages"]) <= {"donor", "source", "successor"},
                "Invalid invocation completed-stage list")


def verify_incumbent(verifier, root):
    """All stored neural predictions are rescored; neural inference is not hidden."""
    e = Evidence(root)
    protocol = load_json(BASE / "INCUMBENT_PROTOCOL-amendment-2.json")
    registration = load_json(BASE / "INCUMBENT_REGISTRATION-amendment-2.json")
    identity = e.json("IDENTITY.json")
    result = e.json("RESULTS.json")
    same(result.get("schema"), "learning-to-build/incumbent-results/v1", "incumbent schema")
    same(result.get("status"), "COMPLETE", "incumbent completion")
    runtime = identity["runtime_versions"]
    validate_runtime(runtime, registration["runtime_versions"], "incumbent")
    expected_identity = dict(
        protocol_sha256=PINNED["INCUMBENT_PROTOCOL-amendment-2.json"],
        registration_sha256=PINNED["INCUMBENT_REGISTRATION-amendment-2.json"],
        primary_protocol_sha256=PINNED["PROTOCOL-amendment-2.json"],
        primary_registration_sha256=PINNED["REGISTRATION-amendment-2.json"],
        primary_amendment=verifier.registration["amendment"],
        implementation_files={name: PINNED[name] for name in ("incumbent.py", "data.py", "builder.py", "instrument.py")},
        model=protocol["model"], configuration=protocol["configuration"], cohorts=protocol["cohorts"],
        cohort_specification=protocol["cohort_specification"], runtime_versions=runtime,
        upstream_python_sha256=registration["upstream_python_sha256"], archives=verifier.public.archives)
    same(identity, expected_identity, "incumbent externally pinned identity")
    same(result["identity"], expected_identity, "incumbent final identity")
    cohorts = protocol["cohorts"]
    for split in ("validation", "test"):
        same(cohorts["source_" + split], verifier.public.names039(split), "incumbent official " + split)
    for split in ("calibration", "test"):
        same(cohorts["successor_" + split], verifier.protocol["data"]["bbbc007"][split + "_ids"],
             "incumbent registered successor " + split)
    splits = {}
    for split in ("source_validation", "source_test", "successor_calibration", "successor_test"):
        specification = protocol["cohort_specification"][split]
        names = cohorts[split]
        if specification["dataset"] == "bbbc039":
            case_for = lambda name, kind=specification["split"]: verifier.public.case039(kind, name)
        else:
            case_for = verifier.public.case007
        _, summary, _ = verifier.saved_cohort(
            e, specification["directory"], names, case_for, protocol["model"]["name"],
            specification["task"], replay=False, incumbent=True)
        splits[split] = dict(field_ids=names, directory=specification["directory"],
                            task=specification["task"], summary=summary,
                            accepted=qualified(summary, specification["task"], verifier.protocol["criteria"],
                                               heldout=specification["heldout"]))
    same(result["splits"], splits, "incumbent all-cohort scores/acceptance")
    sessions = e.json("SESSIONS.json")
    require(isinstance(sessions, list) and sessions and sessions[-1]["status"] == "COMPLETE",
            "Missing completed incumbent session")
    for session in sessions:
        require(session["status"] in ("COMPLETE", "INTERRUPTED_OR_FAILED")
                and type(session["new_fields"]) is int and session["new_fields"] >= 0,
                "Invalid incumbent session")
        nonnegative_times(session, ("actual_cpu_seconds", "actual_wall_seconds"), "incumbent session")
    fields = sum(len(x) for x in cohorts.values())
    recorded_new = sum(session["new_fields"] for session in sessions)
    require(recorded_new <= fields, "Sessions claim more unique predictions than the registered cohort")
    same(result["sessions"], sessions, "incumbent session reconciliation")
    same(e.json("STATUS.json"), dict(status="COMPLETE", fields=fields), "incumbent completed denominator")
    loading = result["model_loading"]
    preparation = protocol["preparation_receipt"]
    require(file_hash(BASE / preparation["path"]) == preparation["sha256"]
            == registration["preparation_sha256"], "Incumbent preparation binding differs")
    expected_loading = load_json(BASE / preparation["path"])["loading"]
    nonnegative_times(loading, ("load_cpu_seconds", "load_wall_seconds"), "incumbent loading")
    for key in ("load_cpu_seconds", "load_wall_seconds"):
        expected_loading[key] = loading[key]
    same(loading, expected_loading, "incumbent model-loading identity")
    require(type(result["peak_rss_kib"]) is int and result["peak_rss_kib"] > 0, "Invalid peak-memory receipt")
    expected_result = dict(
        schema="learning-to-build/incumbent-results/v1", status="COMPLETE", identity=expected_identity,
        model_loading=loading, splits=splits, sessions=sessions, peak_rss_kib=result["peak_rss_kib"],
        comparison_role="Pretrained practical alternative with different learned stock; outside the six equal-content causal arms.",
        comparison_selection_timing="The pretrained comparison was selected after classical source outcomes. Its RGB observation adapter was separately registered after classical calibration outcomes and RGB-format inspection, before any target-test prediction/score or neural inference. Model weights, channels, numerical hyperparameters and gates were unchanged.",
        pretraining_overlap_with_evaluation_data="Unknown; not excluded.",
        cost_scope="Measured process CPU/wall and published model bytes. Upstream training, authoring, development, host/inference billing and unrecorded interruption intervals are unknown, not zero. No financial transactions.",
        rights_scope="Research operation only. Cellpose code is BSD-3-Clause; model-card metadata says BSD-3-Clause, its documented training data are CC-BY-NC, and DINOv3 has separate custom terms. Commercial permissions are not established. No upstream source or weights redistributed.",
        new_physical_acquisitions=0, real_customer_acceptance=False, receipts_or_profit_established=False)
    same(result, expected_result, "complete incumbent result")
    seal = e.json("COMPLETION.json")
    require(seal.get("schema") == "learning-to-build/incumbent-completion/v1", "Missing/invalid completion seal")
    entries = [dict(path=name, bytes=path.stat().st_size, sha256=file_hash(path))
               for name, path in sorted(e.actual.items()) if name != "COMPLETION.json"]
    same(seal["files"], entries, "incumbent sealed complete tree")
    same(seal["tree_sha256"], hashlib.sha256(canonical(entries).encode()).hexdigest(), "incumbent sealed-tree digest")
    nonnegative_times(seal, ("seal_cpu_seconds", "seal_wall_seconds"), "incumbent seal")
    same(seal["scope"], "Exact saved-file identity. Independent scientific verification uses check.py; this is not an external signature.",
         "incumbent seal scope")
    same(set_to_list(seal), sorted(["schema", "files", "tree_sha256", "seal_cpu_seconds",
                                   "seal_wall_seconds", "scope"]), "incumbent seal fields")
    inventory = e.inventory()
    return dict(
        status="VERIFIED_SAVED_PREDICTIONS", inventory=inventory,
        registered_fields=fields, all_saved_masks_independently_rescored=True,
        original_reference_archives_independently_decoded=True,
        neural_predictor_reexecuted_by_this_check=False,
        source_qualified=bool(splits["source_validation"]["accepted"] and splits["source_test"]["accepted"]),
        successor_qualified=bool(splits["successor_calibration"]["accepted"] and splits["successor_test"]["accepted"]),
        measured_session_new_fields=recorded_new,
        fields_without_completed_session_attribution=fields - recorded_new,
        results_sha256=e.hash("RESULTS.json"),
        scope="Verifies scores, masks, source identity, border policy, coverage and reported verdicts. It does not establish model generation from hashes; retain the separately observed source-matched model operation/replay.")


def set_to_list(value):
    require(isinstance(value, dict), "Expected object")
    return sorted(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--classical", type=Path, required=True)
    parser.add_argument("--incumbent", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--saved-masks-only", action="store_true",
                        help="LIMITED mode: do not regenerate donor/calibration predictions whose masks were not retained")
    args = parser.parse_args(argv)
    if args.output is not None:
        require(not args.output.exists(), "Verification output exists; choose a new file")
        out = args.output.resolve()
        for source in (args.classical, args.incumbent):
            require(source is None or not out.is_relative_to(source.resolve()),
                    "Keep verification receipts outside the sealed evidence tree")
    start, cpu = time.perf_counter(), time.process_time()
    try:
        protocol, registration, runtime = source_contract()
        public = PublicData(args.cache, protocol)
        verifier = Verifier(public, protocol, registration, replay_search=not args.saved_masks_only)
        classical = verifier.classical(args.classical)
        incumbent = verify_incumbent(verifier, args.incumbent) if args.incumbent is not None else None
        require(file_hash(Path(__file__)) == VERIFIER_SOURCE_SHA256,
                "Verifier source changed during execution; this run cannot bind the new bytes")
        receipt = dict(
            schema="learning-to-build/independent-evidence-check/v1",
            status="VERIFIED" if not args.saved_masks_only else "LIMITED",
            verifier_sha256=VERIFIER_SOURCE_SHA256, protocol_sha256=PINNED["PROTOCOL-amendment-2.json"],
            source_bindings=PINNED, runtime_versions=runtime, public_archives=public.archives,
            classical=classical, incumbent=incumbent,
            incumbent_coverage="ALL_116_SAVED_PREDICTIONS" if incumbent is not None else "NOT_CHECKED",
            saved_prediction_fields_rescored=verifier.saved_fields,
            unique_classical_predictions_regenerated=len(verifier.replayed),
            actual_cpu_seconds=time.process_time() - cpu, actual_wall_seconds=time.perf_counter() - start,
            scientific_confirmation="EXPOSED_DATA_REPRODUCTION_NOT_NEW_CONFIRMATION",
            independence="Separate reference decoder, scorer, coverage/selection verifier. Classical prediction replay uses the frozen generator. Common project authorship; no external laboratory certification.",
            limits=["Runtime and historical execution are recorded claims, not recoverable from hashes.",
                    "Neural saved-mask scores are verified; generating-model inference is separately operated.",
                    "No biological, clinical, commercial, general learning or novel task-population claim is established."])
    except Exception as error:
        receipt = dict(schema="learning-to-build/independent-evidence-check/v1", status="REJECTED",
                       error_type=type(error).__name__, error=str(error),
                       actual_cpu_seconds=time.process_time() - cpu, actual_wall_seconds=time.perf_counter() - start)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
        print(json.dumps(receipt, sort_keys=True, allow_nan=False))
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
