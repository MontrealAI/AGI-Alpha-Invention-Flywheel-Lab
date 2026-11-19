"""EIT190: one independent real chest-phantom archive, source-only acceptance gate.

No scoring, physical property inference, MATLAB execution, accounts or commerce.
Official Zenodo source and all reported per-member hashes are bound to the
receipt; Stage 2 can only be registered after the actual archive hash is known.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from zipfile import ZipFile, BadZipFile

RECORD_ID = "24120439"
TARGET = "AgarChestPhantom.zip"
MANIFEST_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
ARCHIVE_URL = f"https://zenodo.org/api/records/{RECORD_ID}/files/{TARGET}/content"
MAX_ARCHIVE = 256_000_000
MAX_UNCOMPRESSED = 1_500_000_000
MAX_MEMBER = 250_000_000
MAX_ENTRIES = 2000
MAX_MAT_VARIABLES = 100
MAX_MATLAB_SCRIPT = 100_000


class Refusal(ValueError):
    """A recorded negative qualification, not a reason to choose a new arm."""


def member_checksum(metadata: dict) -> tuple[int, str]:
    if not isinstance(metadata, dict):
        raise Refusal("EIT190_MANIFEST_ENTRY_NOT_OBJECT")
    size = metadata.get("size")
    checksum = metadata.get("checksum")
    if (type(size) is not int or size < 1 or size > MAX_ARCHIVE):
        raise Refusal("EIT190_MANIFEST_SIZE_UNSUPPORTED")
    if (not isinstance(checksum, str) or not checksum.startswith("md5:") or
            len(checksum) != 36 or not all(x in "0123456789abcdef" for x in checksum[4:].lower())):
        raise Refusal("EIT190_MANIFEST_MD5_MISSING_OR_UNSUPPORTED")
    return size, checksum[4:].lower()


def choose_exact_file(record: dict) -> tuple[int, str]:
    if not isinstance(record, dict) or str(record.get("id")) != RECORD_ID:
        raise Refusal("EIT190_WRONG_ZENODO_RECORD_ID")
    files = record.get("files")
    if isinstance(files, dict):
        entries = files.get("entries")
        if not isinstance(entries, dict) or TARGET not in entries:
            raise Refusal("EIT190_REQUIRED_CHEST_ARCHIVE_ABSENT")
        entry = entries[TARGET]
        if not isinstance(entry, dict) or entry.get("key", TARGET) != TARGET:
            raise Refusal("EIT190_ARCHIVE_KEY_MISMATCH")
        return member_checksum(entry)
    if isinstance(files, list):
        hits = [item for item in files if isinstance(item, dict) and item.get("key") == TARGET]
        if len(hits) != 1:
            raise Refusal("EIT190_CHEST_FILE_MISSING_OR_DUPLICATE")
        return member_checksum(hits[0])
    raise Refusal("EIT190_MANIFEST_SCHEMA_UNSUPPORTED")


def _read_json_source():
    with urlopen(Request(MANIFEST_URL, headers={"User-Agent": "AGI-ALPHA-EIT190-public-research/1"}),
                 timeout=60) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise Refusal("EIT190_UNSAFE_RECORD_TRANSPORT")
        payload = response.read(5_000_001)
        if len(payload) > 5_000_000:
            raise Refusal("EIT190_RECORD_MANIFEST_OVERSIZE")
    return json.loads(payload)


def download_pinned_named_archive(destination: Path, expected_size: int, expected_md5: str) -> str:
    digest, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    total = 0
    with urlopen(Request(ARCHIVE_URL, headers={"User-Agent": "AGI-ALPHA-EIT190-public-research/1"}),
                 timeout=90) as response:
        if urlsplit(response.geturl()).scheme != "https":
            raise Refusal("EIT190_UNSAFE_ARCHIVE_TRANSPORT")
        with destination.open("xb") as f:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > expected_size or total > MAX_ARCHIVE:
                    raise Refusal("EIT190_ARCHIVE_EXCEEDS_MANIFEST_SIZE")
                f.write(chunk)
                digest.update(chunk)
                md5.update(chunk)
    if total != expected_size or md5.hexdigest() != expected_md5:
        raise Refusal("EIT190_ARCHIVE_SIZE_OR_MANIFEST_CHECKSUM_MISMATCH")
    return digest.hexdigest()


def safe_zip_members(z: ZipFile):
    all_members = z.infolist()
    if not all_members or len(all_members) > MAX_ENTRIES:
        raise Refusal("EIT190_ZIP_ENTRY_COUNT_UNSAFE")
    seen = set()
    total = 0
    safe = []
    for member in all_members:
        name = member.filename
        path = PurePosixPath(name)
        if (not name or "\\" in name or name.startswith("/") or
                any(part in ("", ".", "..") for part in name.split("/")) and not
                (member.is_dir() and name.endswith("/") and
                 all(part not in ("", ".", "..") for part in name[:-1].split("/")))):
            raise Refusal("EIT190_UNSAFE_MEMBER_PATH")
        if member.is_dir():
            continue
        normalized = str(path).casefold()
        if normalized in seen:
            raise Refusal("EIT190_DUPLICATE_ZIP_MEMBER_PATH")
        seen.add(normalized)
        mode = member.external_attr >> 16
        if stat.S_IFMT(mode) == stat.S_IFLNK:
            raise Refusal("EIT190_ZIP_SYMLINK_REJECTED")
        if member.file_size < 0 or member.file_size > MAX_MEMBER:
            raise Refusal("EIT190_MEMBER_TOO_LARGE")
        total += member.file_size
        if total > MAX_UNCOMPRESSED:
            raise Refusal("EIT190_TOTAL_UNCOMPRESSED_TOO_LARGE")
        safe.append(member)
    return safe


def mat_variables(raw: bytes):
    if raw.startswith(b"MATLAB 5.0 MAT-file"):
        from scipy.io import whosmat
        try:
            objects = whosmat(io.BytesIO(raw))
        except (OSError, TypeError, ValueError, IndexError) as error:
            raise Refusal("EIT190_MAT5_PARSE_FAILED") from error
        if len(objects) > MAX_MAT_VARIABLES:
            raise Refusal("EIT190_TOO_MANY_MAT_VARIABLES")
        return {"format": "MATLAB5", "variables": [
            {"name": str(name), "shape": [int(x) for x in shape], "type": str(tp)}
            for name, shape, tp in objects
        ]}
    if (raw.startswith(b"MATLAB 7.3 MAT-file") or
            raw.startswith(bytes((0x89, 0x48, 0x44, 0x46, 0x0d, 0x0a, 0x1a, 0x0a)))):
        import h5py
        entries = []
        try:
            with h5py.File(io.BytesIO(raw), "r") as f:
                def visitor(name, obj):
                    if isinstance(obj, h5py.Dataset):
                        if len(entries) >= MAX_MAT_VARIABLES:
                            raise Refusal("EIT190_TOO_MANY_HDF5_DATASETS")
                        entries.append({"name": name, "shape": list(obj.shape),
                                        "type": str(obj.dtype)})
                f.visititems(visitor)
        except Refusal:
            raise
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise Refusal("EIT190_HDF5_PARSE_FAILED") from error
        return {"format": "HDF5-v7.3", "variables": entries}
    raise Refusal("EIT190_UNKNOWN_MAT_SOURCE_FORMAT")


def inventory_archive(path: Path, sha256: str, size: int, md5: str):
    members = []
    with ZipFile(path) as z:
        inspected = safe_zip_members(z)
        for m in inspected:
            name = m.filename
            if not (name.lower().endswith(".mat") or name.lower().endswith(".m")):
                continue
            raw = z.read(m)
            if len(raw) != m.file_size:
                raise Refusal("EIT190_ZIP_UNCOMPRESSED_LENGTH_MISMATCH")
            item = {"member": name, "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest()}
            if name.lower().endswith(".mat"):
                item.update(mat_variables(raw))
            else:
                if len(raw) > MAX_MATLAB_SCRIPT:
                    raise Refusal("EIT190_MATLAB_SCRIPT_OVERSIZE")
                # MATLAB examples are historical source bytes and may use
                # non-UTF8 encodings (e.g., a legacy local single-byte codepage).
                # Do NOT parse, transcode, or execute them in the source inventory:
                # pin the raw bytes, disclose unknown encoding, and require a
                # separately registered semantic review before any Stage 2 use.
                try:
                    raw.decode("utf-8")
                    encoding_scope = "UTF8-decodes; semantics-not-checked"
                except UnicodeDecodeError:
                    encoding_scope = "nonUTF8-source; semantics-unverified"
                item.update({"format": "MATLAB-source-bytes-not-executed",
                             "encoding_scope": encoding_scope,
                             "raw_newline_count": raw.count(bytes((10,)))})
            members.append(item)
        if z.testzip() is not None:
            raise Refusal("EIT190_ZIP_CRC_VALIDATION_FAILED")
    names = [m["member"].rsplit("/", 1)[-1] for m in members]
    scripts = [n for n in names if n == "Example_ChestPhantom_LinearDifferenceImaging.m"]
    jacobians = [n for n in names if n == "J_AgarChestPhantom.mat"]
    meshes = [n for n in names if n.startswith("mesh_AgarChestPhantom") and n.endswith(".mat")]
    data = [m for m in members if m["member"].lower().endswith(".mat") and
            "AgarChestPhantom" in m["member"] and
            m["member"].rsplit("/", 1)[-1] not in (jacobians + meshes)]
    if len(scripts) != 1 or len(jacobians) != 1 or not meshes or not data:
        raise Refusal("EIT190_REQUIRED_ORIGINAL_CHEST_COMPONENTS_NOT_FOUND")
    return {
        "schema": "agi-alpha/eit190-independent-chest-source-manifest/v1",
        "source": {"publication_arxiv": "2611.17225", "zenodo_record_id": RECORD_ID,
                   "target": TARGET, "archive_bytes": size,
                   "archive_md5_from_record": md5, "actual_archive_sha256": sha256},
        "mat_and_matlab_source_members": members,
        "all_data_mat_members_count": len(data),
        "original_jacobian_count": len(jacobians),
        "original_mesh_count": len(meshes),
        "original_example_count": len(scripts),
        "paper_reported_material_mS_per_cm": {
            "saline": 1.35, "white_agar": 0.61, "pink_agar": 3.23,
            "scope": "reported instrument-measured nominal material values, NOT pixel truth"},
        "candidate_physical_states": ["saline_reference", "healthy_lung",
                                      "damaged_lung", "effusion"],
        "external_source_examined": True,
        "independent_conductivity_reconstructed": False,
        "physical_uncertainty_calibrated": False,
        "buyer_acceptance_or_payment_observed": False,
        "complete_cost_or_frontier_model_bill_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }


def write_create_only(path: Path, report: dict):
    if path.exists() or path.is_symlink():
        raise Refusal("EIT190_RECEIPT_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "w", encoding="utf-8") as out:
        json.dump(report, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    output = Path(parser.parse_args(argv).out)
    if output.exists() or output.is_symlink():
        raise Refusal("EIT190_RECEIPT_EXISTS")
    with tempfile.TemporaryDirectory(prefix="eit190-independent-chest-") as directory:
        metadata = _read_json_source()
        bytecount, checksum = choose_exact_file(metadata)
        target = Path(directory) / TARGET
        source_digest = download_pinned_named_archive(target, bytecount, checksum)
        report = inventory_archive(target, source_digest, bytecount, checksum)
    write_create_only(output, report)
    print(json.dumps({"source_sha256": source_digest, "source_bytes": bytecount,
                      "data_members": report["all_data_mat_members_count"],
                      "property_reconstructed": False,
                      "decision": report["decision"]}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, ValueError, TypeError, BadZipFile) as error:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "error": str(error)},
                         sort_keys=True))
        raise SystemExit(2)
