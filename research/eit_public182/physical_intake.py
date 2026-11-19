"""One exact physical EIT archive: verified public bytes, exhaustive measured-array inventory.

Registered before downloading data: campaign/eit-public-observatory182/PHASE2_ARCHIVE_PROTOCOL.md.
No patient data, physical actuation, financial operations, model APIs or paid services.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

ARCHIVE_NAME = "AgarCylinderPhantom.zip"
URL = "https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content"
EXPECTED_SIZE = 12482688
EXPECTED_MD5 = "658694f69f64075b6fefec2e2c597131"
MAX_TOTAL_UNCOMPRESSED = 1_000_000_000  # specific declared one-archive safety bound, not a business limit
MAX_MEMBER_BYTES = 250_000_000
MAX_FILES = 2000
MAX_NUMERIC_ELEMENTS = 20_000_000


class PhysicalIntakeRefusal(ValueError):
    pass


def check_names(archive: ZipFile):
    infos = archive.infolist()
    if not infos or len(infos) > MAX_FILES:
        raise PhysicalIntakeRefusal("INVALID_ZIP_FILE_COUNT")
    names, selected = set(), []
    total = 0
    for info in infos:
        name = info.filename
        parts = PurePosixPath(name).parts
        if (not parts or name.startswith("/") or "\\" in name or
                any(p in ("", ".", "..") for p in parts) or
                any(ord(c) < 32 for c in name)):
            raise PhysicalIntakeRefusal("UNSAFE_ZIP_MEMBER")
        if name.casefold() in names:
            raise PhysicalIntakeRefusal("DUPLICATE_ZIP_MEMBER")
        names.add(name.casefold())
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode) or info.flag_bits & 0x1:
            raise PhysicalIntakeRefusal("LINK_OR_ENCRYPTED_ZIP_MEMBER")
        total += info.file_size
        if info.file_size > MAX_MEMBER_BYTES or total > MAX_TOTAL_UNCOMPRESSED:
            raise PhysicalIntakeRefusal("UNBOUNDED_ZIP_EXPANSION")
        if not info.is_dir() and name.lower().endswith(".mat") and any(p.lower() == "data" for p in parts[:-1]):
            basename = parts[-1].lower()
            if not basename.startswith(("mesh_", "j_")):
                selected.append(info)
    if len(selected) < 2:
        raise PhysicalIntakeRefusal("INSUFFICIENT_REGISTERED_MEASUREMENTS")
    return sorted(selected, key=lambda i: i.filename)


def fetch_verified(destination: Path) -> dict:
    if destination.exists() or destination.is_symlink():
        raise PhysicalIntakeRefusal("SOURCE_ARCHIVE_ALREADY_EXISTS")
    request = Request(URL, headers={"User-Agent": "AGI-ALPHA-EIT182-public-research/1.0"})
    md5, sha256 = hashlib.md5(), hashlib.sha256()
    length = 0
    with urlopen(request, timeout=45) as response:
        if urlparse(response.url).scheme != "https" or urlparse(response.url).hostname not in {"zenodo.org", "www.zenodo.org"}:
            raise PhysicalIntakeRefusal("UNTRUSTED_ARCHIVE_REDIRECT")
        with destination.open("xb") as out:
            while True:
                chunk = response.read(262144)
                if not chunk:
                    break
                length += len(chunk)
                if length > EXPECTED_SIZE:
                    raise PhysicalIntakeRefusal("ARCHIVE_SIZE_CHANGED")
                md5.update(chunk)
                sha256.update(chunk)
                out.write(chunk)
    if length != EXPECTED_SIZE or md5.hexdigest() != EXPECTED_MD5:
        raise PhysicalIntakeRefusal("SOURCE_DECLARED_SIZE_OR_MD5_MISMATCH")
    return {"archive": ARCHIVE_NAME, "observed_archive_bytes": length,
            "observed_md5": md5.hexdigest(), "independently_observed_sha256": sha256.hexdigest()}


def array_metrics(dataset):
    # lazy imports keep offline safety tests usable on basic Python
    import numpy as np
    if not hasattr(dataset, "dtype") or dataset.size == 0 or dataset.size > MAX_NUMERIC_ELEMENTS:
        raise PhysicalIntakeRefusal("MISSING_OR_OVERSIZED_NUMERIC_ARRAY")
    d = dataset.dtype
    if d.fields:
        if not {"real", "imag"} <= set(d.fields):
            raise PhysicalIntakeRefusal("UNSUPPORTED_COMPOUND_NUMERIC")
        v = dataset[()]
        a = np.asarray(v["real"], dtype=np.float64) + 1j * np.asarray(v["imag"], dtype=np.float64)
    elif d.kind in "iufc":
        a = np.asarray(dataset[()])
    else:
        raise PhysicalIntakeRefusal("NONNUMERIC_ARRAY")
    if not np.isfinite(a).all():
        raise PhysicalIntakeRefusal("NONFINITE_MEASUREMENT")
    real = np.real(a)
    modulus = np.abs(a)
    metrics = {
        "shape": list(a.shape),
        "source_dtype": str(d),
        "element_count": int(a.size),
        "mean_real": float(np.mean(real)),
        "min_real": float(np.min(real)),
        "max_real": float(np.max(real)),
        "rms_magnitude": float(np.sqrt(np.mean(np.square(modulus)))),
    }
    if not all(math.isfinite(v) for v in (metrics["mean_real"], metrics["min_real"], metrics["max_real"], metrics["rms_magnitude"])):
        raise PhysicalIntakeRefusal("OVERFLOWED_NUMERIC_SUMMARY")
    return metrics


def inventory(archive: ZipFile, working: Path) -> list:
    import h5py
    result = []
    for info in check_names(archive):
        temporary = working / "measurement.mat"
        if temporary.exists():
            raise PhysicalIntakeRefusal("TEMPORARY_MEASUREMENT_COLLISION")
        h = hashlib.sha256()
        size = 0
        try:
            with archive.open(info) as input_file, temporary.open("xb") as output:
                while True:
                    chunk = input_file.read(262144)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > info.file_size or size > MAX_MEMBER_BYTES:
                        raise PhysicalIntakeRefusal("MEASUREMENT_EXPANSION_CHANGED")
                    h.update(chunk)
                    output.write(chunk)
            if size != info.file_size:
                raise PhysicalIntakeRefusal("MEASUREMENT_LENGTH_CHANGED")
            if not h5py.is_hdf5(temporary):
                with temporary.open("rb") as handle:
                    prefix = handle.read(16).hex()
                raise PhysicalIntakeRefusal("NON_HDF5_MATLAB_MEMBER:" + info.filename + ":prefix=" + prefix)
            with h5py.File(temporary, "r") as mat:
                if "currents_matrix" not in mat or "voltages_matrix" not in mat:
                    raise PhysicalIntakeRefusal("MISSING_REQUIRED_MATLAB_MATRIX:" + info.filename)
                result.append({
                    "source_member": info.filename,
                    "member_bytes": size,
                    "member_sha256": h.hexdigest(),
                    "currents_matrix": array_metrics(mat["currents_matrix"]),
                    "voltages_matrix": array_metrics(mat["voltages_matrix"]),
                    "units_info_present": "units_info" in mat,
                })
        finally:
            temporary.unlink(missing_ok=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    destination = Path(args.out)
    if destination.exists() or destination.is_symlink():
        raise PhysicalIntakeRefusal("OUTPUT_ALREADY_EXISTS")
    with tempfile.TemporaryDirectory(prefix="eit182-") as tmp:
        working = Path(tmp)
        archive_path = working / ARCHIVE_NAME
        archive_receipt = fetch_verified(archive_path)
        with ZipFile(archive_path) as z:
            measures = inventory(z, working)
        receipt = {
            "schema": "blue-sky182-physical-archive-byte-inventory-v1",
            "record_id": 24120439,
            "source_url": URL,
            "source_expected_md5": EXPECTED_MD5,
            **archive_receipt,
            "measured_cases_count": len(measures),
            "all_eligible_measurement_members_included": True,
            "measurements": measures,
            "reconstruction_performed": False,
            "physical_new_observability_or_clinical_utility_proved": False,
            "commercial_revenue_or_profit": None,
            "decision": "BYTE_VERIFIED_MEASURED_ARRAYS_ONLY__HOLD_NO_DEPLOY",
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": receipt["decision"], "case_count": len(measures),
                      "archive_sha256": archive_receipt["independently_observed_sha256"],
                      "receipt": str(destination)}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (PhysicalIntakeRefusal, OSError, ValueError) as error:
        print(json.dumps({"decision": "FAIL_CLOSED__HOLD_NO_DEPLOY", "error": str(error)}))
        raise SystemExit(2)
