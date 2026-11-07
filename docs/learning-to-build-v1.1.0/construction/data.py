#!/usr/bin/env python3
"""Acquire pinned public microscopy archives; decode only on an explicit load.

``fetch`` and ``inspect`` never decode image pixels.  Archives remain outside
the publication package.  The experiment runner binds their complete SHA256s
to the registered protocol before invoking either loader.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
import zipfile


ARCHIVES = {
    "bbbc039_images": "https://data.broadinstitute.org/bbbc/BBBC039/images.zip",
    "bbbc039_masks": "https://data.broadinstitute.org/bbbc/BBBC039/masks.zip",
    "bbbc039_metadata": "https://data.broadinstitute.org/bbbc/BBBC039/metadata.zip",
    "bbbc007_images": "https://data.broadinstitute.org/bbbc/BBBC007/BBBC007_v1_images.zip",
    "bbbc007_outlines": "https://data.broadinstitute.org/bbbc/BBBC007/BBBC007_v1_outlines.zip",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def archive_path(cache: Path, key: str) -> Path:
    if key not in ARCHIVES:
        raise ValueError(f"Unknown public archive: {key}")
    return Path(cache) / f"{key}.zip"


def archive_manifest(cache: Path) -> dict:
    result = {}
    for key, url in ARCHIVES.items():
        path = archive_path(cache, key)
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; run data.py fetch --cache PATH")
        result[key] = {"url": url, "bytes": path.stat().st_size, "sha256": sha256(path)}
    return result


def verify_archives(cache: Path, expected: dict) -> dict:
    actual = archive_manifest(cache)
    if set(expected) != set(ARCHIVES):
        raise ValueError("Protocol must pin exactly the five registered public archives")
    for key, row in actual.items():
        want = expected[key]
        digest = want if isinstance(want, str) else want["sha256"]
        if row["sha256"] != digest:
            raise ValueError(f"Archive SHA256 mismatch: {key}")
        if isinstance(want, dict):
            for label in ("url", "bytes"):
                if label in want and row[label] != want[label]:
                    raise ValueError(f"Archive {label} mismatch: {key}")
    return actual


def acquire(cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    receipts = []
    for key, url in ARCHIVES.items():
        path = archive_path(cache, key)
        if path.exists():
            if not zipfile.is_zipfile(path):
                raise ValueError(f"Existing cache is not a ZIP archive: {path}")
            print(f"Reusing {key}: {path.stat().st_size} bytes", flush=True)
            continue
        partial = path.with_suffix(".zip.part")
        started = time.perf_counter()
        try:
            request = Request(url, headers={"User-Agent": "Learning-to-Build-public-data/1.1"})
            count = 0
            with urlopen(request, timeout=45) as response, partial.open("xb") as target:
                status = response.status
                if status != 200:
                    raise ValueError(f"Expected complete HTTP 200 archive, got {status}: {url}")
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    count += len(block)
                    if count > 128 * 1024 * 1024:
                        raise ValueError("Archive exceeds the declared 128 MiB download bound")
                    target.write(block)
            if not zipfile.is_zipfile(partial):
                raise ValueError(f"Response is not a complete ZIP archive: {key}")
            partial.rename(path)
            receipt = {"archive": key, "http_status": status, "bytes": count,
                       "sha256": sha256(path), "wall_seconds": time.perf_counter() - started}
            receipts.append(receipt)
            print(json.dumps(receipt, sort_keys=True), flush=True)
        except Exception as exc:
            failure = {"archive": key, "url": url, "error": f"{type(exc).__name__}: {exc}",
                       "wall_seconds": time.perf_counter() - started,
                       "partial_bytes": partial.stat().st_size if partial.exists() else 0}
            (cache / f"{key}_FETCH_FAILURE.json").write_text(json.dumps(failure, indent=2) + "\n")
            raise
    result = {"archives": archive_manifest(cache), "new_downloads": receipts,
              "pixel_decoding_performed": False}
    (cache / "FETCH.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def member_names(archive: zipfile.ZipFile) -> list[str]:
    names = [i.filename for i in archive.infolist()
             if not i.is_dir() and not i.filename.startswith("__MACOSX/")
             and not Path(i.filename).name.startswith(".")]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate ZIP members are unsupported")
    return sorted(names)


def by_stem(archive: zipfile.ZipFile, suffixes: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for name in member_names(archive):
        path = Path(name)
        if path.suffix.lower() not in suffixes:
            continue
        if path.stem in result:
            raise ValueError(f"Ambiguous image stem: {path.stem}")
        result[path.stem] = name
    return result


def metadata039(cache: Path) -> dict:
    with zipfile.ZipFile(archive_path(cache, "bbbc039_metadata")) as archive:
        result = {split: archive.read(f"metadata/{split}.txt").decode("utf-8").splitlines()
                  for split in ("training", "validation", "test")}
        result["plates"] = dict(line.split(",") for line in
                                archive.read("metadata/filenames_and_plates.csv").decode().splitlines())
        result["expert_pipeline_sha256"] = hashlib.sha256(
            archive.read("metadata/segmentation_cp3.cppipe")).hexdigest()
    all_names = result["training"] + result["validation"] + result["test"]
    if len(all_names) != len(set(all_names)) or set(all_names) != set(result["plates"]):
        raise ValueError("Invalid BBBC039 split partition")
    return result


def inspect_archives(cache: Path) -> dict:
    result = {"archives": archive_manifest(cache), "members": {}, "pixel_decoding_performed": False}
    for key in ARCHIVES:
        with zipfile.ZipFile(archive_path(cache, key)) as archive:
            result["members"][key] = member_names(archive)
    result["metadata039"] = metadata039(cache)
    return result


@dataclass
class Case:
    name: str
    dna: object
    truth: object
    actin: object | None = None
    nucleus_truth: object | None = None
    sources: dict = field(default_factory=dict)
    decoder_diagnostics: dict = field(default_factory=dict)


def _pixels(archive: zipfile.ZipFile, member: str, include_mode: bool = False):
    import numpy as np
    from PIL import Image
    raw = archive.read(member)
    with Image.open(io.BytesIO(raw)) as image:
        value = np.asarray(image).copy()
        mode = image.mode
    source = {"member": member, "sha256": hashlib.sha256(raw).hexdigest(),
              "shape": list(value.shape), "dtype": str(value.dtype)}
    if include_mode:
        source["mode"] = mode
    return value, source


def canonicalize_raw_pixels(array, *, mode: str):
    """Apply the declared scalar-observation convention to RAW channels only.

    RGB-to-L is the supplied Pillow 13 luma projection. It is generally lossy
    and does not recover original radiometric fluorescence. This function
    must never be applied to reference masks, RGB instance encodings or
    annotation outlines. No spatial transformation is performed.
    """
    import numpy as np
    import PIL
    from PIL import Image
    value = np.asarray(array)
    if value.dtype.kind not in "uif" or not np.isfinite(value).all() or np.any(value < 0):
        raise ValueError("Raw observation pixels must be finite nonnegative numeric values")
    if mode == "RGB":
        if value.ndim != 3 or value.shape[2] != 3 or value.dtype != np.uint8:
            raise ValueError("The registered RGB adapter accepts only 8-bit three-channel RGB arrays")
        if PIL.__version__ != "13.0.0":
            raise ValueError("The registered RGB observation adapter requires Pillow 13.0.0")
        canonical = np.asarray(Image.fromarray(value).convert("L")).copy()
        conversion = "Pillow.Image.convert(L)"
        lossy = True
    elif value.ndim == 2:
        canonical = value
        conversion = "none_scalar"
        lossy = False
    else:
        raise ValueError("Unsupported raw observation encoding; no implicit color or geometry conversion")
    def pixel_hash(pixels):
        header = json.dumps({"shape": list(pixels.shape), "dtype": str(pixels.dtype)},
                            sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(header + b"\n" + pixels.tobytes(order="C")).hexdigest()
    receipt = {"schema": "learning-to-build/raw-observation-adapter/v1",
               "input_mode": mode, "input_shape": list(value.shape), "input_dtype": str(value.dtype),
               "output_shape": list(canonical.shape), "output_dtype": str(canonical.dtype),
               "conversion": conversion, "lossy_color_projection": lossy,
               "spatial_transform": "none", "library_version": PIL.__version__,
               "original_pixel_sha256": pixel_hash(value), "canonical_pixel_sha256": pixel_hash(canonical)}
    return canonical, receipt


def load039(cache: Path, split: str, names: list[str] | None = None) -> list[Case]:
    """Decode only the explicitly requested official split / subset.

    The original authors' decoder labels equal-valued connected components of
    the first PNG channel.  Treating its RGB triplets as global instance IDs
    would incorrectly merge spatially separated nuclei of the same color.
    """
    from skimage.measure import label
    metadata = metadata039(cache)
    if split not in ("training", "validation", "test"):
        raise ValueError("Unknown BBBC039 official split")
    chosen = list(metadata[split] if names is None else names)
    if len(chosen) != len(set(chosen)) or not set(chosen) <= set(metadata[split]):
        raise ValueError("Requested fields must be a unique subset of the named official split")
    cases = []
    with zipfile.ZipFile(archive_path(cache, "bbbc039_images")) as images, \
            zipfile.ZipFile(archive_path(cache, "bbbc039_masks")) as masks:
        image_members = by_stem(images, (".tif", ".tiff", ".png"))
        mask_members = by_stem(masks, (".png",))
        for name in chosen:
            stem = Path(name).stem
            dna, source = _pixels(images, image_members[stem])
            mask, truth_source = _pixels(masks, mask_members[stem])
            if dna.ndim != 2 or mask.ndim != 3 or mask.shape[:2] != dna.shape:
                raise ValueError(f"Unexpected BBBC039 input shape: {name}")
            truth = label(mask[:, :, 0], background=0, connectivity=2).astype("int32")
            cases.append(Case(name=stem, dna=dna, truth=truth,
                              sources={"dna": source, "truth": truth_source,
                                       "plate": metadata["plates"][name], "official_split": split}))
    return cases


def pairs007(cache: Path) -> dict[str, dict[str, str]]:
    """Pair source members without decoding pixels; reject incomplete fields."""
    image_fields = {}
    with zipfile.ZipFile(archive_path(cache, "bbbc007_images")) as images, \
            zipfile.ZipFile(archive_path(cache, "bbbc007_outlines")) as outlines:
        outline_names = set(member_names(outlines))
        for member in member_names(images):
            path = Path(member)
            if path.suffix.lower() != ".tif":
                raise ValueError(f"Unexpected BBBC007 member: {member}")
            relative = Path(*path.parts[1:])
            stem = relative.stem
            if relative.parent.as_posix() == "A9":
                if stem[-1] not in "df":
                    raise ValueError(f"Unknown A9 channel: {member}")
                channel = "dna" if stem[-1] == "d" else "actin"
                base = stem[:-1]
            elif relative.parent.as_posix() == "f113":
                if not stem.endswith(("d0", "d1")):
                    raise ValueError(f"Unknown f113 channel: {member}")
                channel = "dna" if stem.endswith("d0") else "actin"
                base = stem[:-2]
            else:
                match = re.fullmatch(r"(.+)_([DF])_[12]UL", stem)
                if not match:
                    raise ValueError(f"Unknown BBBC007 channel naming: {member}")
                base, code = match.groups()
                channel = "dna" if code == "D" else "actin"
            field_id = (relative.parent / base).as_posix()
            target = image_fields.setdefault(field_id, {})
            if channel in target:
                raise ValueError(f"Duplicate BBBC007 field/channel: {field_id}/{channel}")
            target[channel] = member
            outline = "BBBC007_v1_outlines/" + relative.as_posix()
            if outline not in outline_names:
                raise ValueError(f"Missing manual outline: {outline}")
            target["nucleus_outline" if channel == "dna" else "cell_outline"] = outline
        expected = {"dna", "actin", "nucleus_outline", "cell_outline"}
        if not image_fields or any(set(value) != expected for value in image_fields.values()):
            raise ValueError("Incomplete BBBC007 channel/reference pairing")
    return dict(sorted(image_fields.items()))


def decode_outline(value):
    """The preregistered, unsmoothed closed-interior interpretation of outlines.

    This is a computational interpretation of manual contours, not a supplied
    object-count table.  Unclosed or frame-touching interiors are excluded.
    """
    import numpy as np
    from scipy import ndimage as ndi
    from skimage.segmentation import relabel_sequential
    array = np.asarray(value)
    # Format amendment 1: Pillow mode-1 TIFFs are Boolean, not integer arrays.
    # Preserve their exact two-valued geometry with a lossless representation.
    if array.dtype.kind == "b":
        array = array.astype(np.uint8)
    unique = np.unique(array)
    if array.ndim != 2 or min(array.shape, default=0) < 3 or array.dtype.kind not in "iu" or len(unique) > 2:
        raise ValueError("Manual outlines must be two-dimensional monochrome rasters with <=2 values")
    frame = np.concatenate((array[0], array[-1], array[:, 0], array[:, -1]))
    values, counts = np.unique(frame, return_counts=True)
    background = values[np.argmax(counts)]
    lines = array != background
    regions, _ = ndi.label(~lines, structure=ndi.generate_binary_structure(2, 1))
    outside = np.unique(np.concatenate((regions[0], regions[-1], regions[:, 0], regions[:, -1])))
    regions[np.isin(regions, outside)] = 0
    regions = relabel_sequential(regions)[0].astype(np.int32)
    eligible = np.zeros(lines.shape, dtype=bool)
    if regions.any():
        distances, indices = ndi.distance_transform_edt(regions == 0, return_indices=True)
        eligible = lines & (distances <= np.sqrt(2.0))
        regions[eligible] = regions[tuple(indices[:, eligible])]
    # A closed contour may itself lie on the frame although its interior did
    # not. Apply the same complete-in-frame scope after assigning its lines.
    frame_ids = np.unique(np.concatenate((regions[0], regions[-1], regions[:, 0], regions[:, -1])))
    frame_ids = frame_ids[frame_ids > 0]
    regions[np.isin(regions, frame_ids)] = 0
    regions = relabel_sequential(regions)[0].astype(np.int32)
    assigned = lines & (regions > 0)
    diagnostics = {
        "shape": list(array.shape), "outline_values": [int(x) for x in unique],
        "frame_background_value": int(background), "outline_pixels": int(lines.sum()),
        "assigned_outline_pixels_before_frame_exclusion": int(eligible.sum()),
        "frame_touching_decoded_regions_excluded": int(len(frame_ids)),
        "assigned_outline_pixels": int(assigned.sum()),
        "assigned_outline_fraction": float(assigned.sum() / max(1, lines.sum())),
        "decoded_instances": int(regions.max(initial=0)),
        "decoded_foreground_pixels": int(np.count_nonzero(regions)),
        "interpretation": "closed_4_connected_interiors_frame_excluded_nearest_line_pixels_within_sqrt2",
    }
    return regions, diagnostics


def load007(cache: Path, names: list[str] | None = None) -> list[Case]:
    mapping = pairs007(cache)
    chosen = list(mapping if names is None else names)
    if len(chosen) != len(set(chosen)) or not set(chosen) <= set(mapping):
        raise ValueError("BBBC007 fields must be a unique subset of complete paired fields")
    cases = []
    with zipfile.ZipFile(archive_path(cache, "bbbc007_images")) as images, \
            zipfile.ZipFile(archive_path(cache, "bbbc007_outlines")) as outlines:
        for name in chosen:
            row = mapping[name]
            dna, dna_source = _pixels(images, row["dna"], include_mode=True)
            actin, actin_source = _pixels(images, row["actin"], include_mode=True)
            dna, dna_source["observation_adapter"] = canonicalize_raw_pixels(dna, mode=dna_source["mode"])
            actin, actin_source["observation_adapter"] = canonicalize_raw_pixels(actin, mode=actin_source["mode"])
            nucleus_outline, nucleus_source = _pixels(outlines, row["nucleus_outline"])
            cell_outline, cell_source = _pixels(outlines, row["cell_outline"])
            if dna.ndim != 2 or any(value.shape != dna.shape for value in
                                    (actin, nucleus_outline, cell_outline)):
                raise ValueError(f"BBBC007 channel/reference shape mismatch: {name}")
            cells, cell_diagnostics = decode_outline(cell_outline)
            nuclei, nucleus_diagnostics = decode_outline(nucleus_outline)
            cases.append(Case(name=name, dna=dna, actin=actin, truth=cells, nucleus_truth=nuclei,
                              sources={"dna": dna_source, "actin": actin_source,
                                       "cell_outline": cell_source, "nucleus_outline": nucleus_source},
                              decoder_diagnostics={"cell": cell_diagnostics, "nucleus": nucleus_diagnostics,
                                                   "counts_agree": cell_diagnostics["decoded_instances"] ==
                                                   nucleus_diagnostics["decoded_instances"]}))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "inspect", "canonicalize"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "canonicalize":
        if args.input is None or args.output is None:
            parser.error("canonicalize requires --input RAW_TIFF --output SCALAR_TIFF")
        receipt_path = args.output.with_name(args.output.name + ".json")
        if args.output.exists() or receipt_path.exists():
            raise ValueError("Canonicalized outputs must use a fresh destination")
        import numpy as np
        from PIL import Image
        with Image.open(args.input) as image:
            value = np.asarray(image).copy()
            mode = image.mode
        canonical, receipt = canonicalize_raw_pixels(value, mode=mode)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(canonical).save(args.output, format="TIFF")
        result = {"input_path": str(args.input), "input_file_sha256": sha256(args.input),
                  "output_path": str(args.output), "output_file_sha256": sha256(args.output),
                  "observation_adapter": receipt}
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))
        return
    if args.cache is None:
        parser.error("fetch and inspect require --cache PATH")
    result = acquire(args.cache) if args.command == "fetch" else inspect_archives(args.cache)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
