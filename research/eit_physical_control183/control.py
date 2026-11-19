"""Read-only, source-pinned physical EIT pair: competent ordinary direct difference only."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

URL = "https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content"
EXPECTED_SIZE = 12482688
EXPECTED_MD5 = "658694f69f64075b6fefec2e2c597131"
EXPECTED_SHA256 = "42fa038c0c1b4d5bb5769f4d8a8575eef300e8eef559137767e5ab0bb1bd9f70"
MEMBERS = {
    "AgarCylinderPhantom/Data/1o0_AgarCylinderPhantom_NoInc.mat": "79c43b785433d63e8d1e7eed36348843799bb38825ac885da46b21b41e0a7739",
    "AgarCylinderPhantom/Data/1o1_AgarCylinderPhantom_2Incs.mat": "db85fed3dc66973373a4e26a3ed33f9d0cc43d51b8367ff893a357487a5b1ddf",
}
SHAPE = (79, 16)

class Refusal(ValueError):
    """Fail closed without claiming physical detection or an economic outcome."""

def validate_zip(archive: ZipFile):
    infos = archive.infolist()
    if not 1 <= len(infos) <= 2000:
        raise Refusal("INVALID_ARCHIVE_INVENTORY")
    seen, expanded = set(), 0
    for item in infos:
        name = item.filename
        plain = name[:-1] if item.is_dir() else name
        parts = plain.split("/")
        if (not plain or name.startswith("/") or "\\" in name or
                any(p in ("", ".", "..") for p in parts) or
                any(ord(c) < 32 for c in name)):
            raise Refusal("UNSAFE_ARCHIVE_PATH")
        if plain.casefold() in seen:
            raise Refusal("DUPLICATE_ARCHIVE_MEMBER")
        seen.add(plain.casefold())
        mode = (item.external_attr >> 16) & 0xffff
        if stat.S_ISLNK(mode) or item.flag_bits & 1:
            raise Refusal("LINK_OR_ENCRYPTED_MEMBER")
        expanded += item.file_size
        if item.file_size > 250_000_000 or expanded > 1_000_000_000:
            raise Refusal("ARCHIVE_EXPANSION_LIMIT")
    if not set(MEMBERS).issubset({i.filename for i in infos}):
        raise Refusal("FROZEN_SOURCE_MEMBERS_MISSING")

def parse_member(raw: bytes):
    import numpy as np
    import h5py
    if len(raw) > 250_000_000:
        raise Refusal("NOT_BOUNDED_HDF5")
    try:
        h = h5py.File(io.BytesIO(raw), "r")
    except (OSError, ValueError) as exc:
        raise Refusal("NOT_BOUNDED_HDF5") from exc
    with h:
        arrays = []
        for name in ("currents_matrix", "voltages_matrix"):
            if name not in h or not isinstance(h[name], h5py.Dataset):
                raise Refusal("MISSING_NUMERIC_MEASUREMENT:" + name)
            ds = h[name]
            if ds.shape != SHAPE or ds.dtype.kind != "f" or ds.dtype.itemsize != 8:
                raise Refusal("INCOMPATIBLE_ARRAY_SHAPE_OR_TYPE:" + name)
            arr = np.asarray(ds[()], dtype=np.float64)
            if not np.isfinite(arr).all():
                raise Refusal("NONFINITE_ARRAY:" + name)
            arrays.append(arr)
        return tuple(arrays)

def paired_control(currents0, voltages0, currents1, voltages1):
    import numpy as np
    for x in (currents0, voltages0, currents1, voltages1):
        if not isinstance(x, np.ndarray) or x.shape != SHAPE or not np.isfinite(x).all():
            raise Refusal("UNMATCHED_OR_NONFINITE_INPUT_SHAPE")
    if not np.array_equal(currents0, currents1):
        raise Refusal("EXCITATIONS_NOT_IDENTICAL")
    baseline = float(np.linalg.norm(voltages0.ravel()))
    if not math.isfinite(baseline) or baseline == 0:
        raise Refusal("NO_FINITE_BASELINE")
    d = voltages1 - voltages0
    if not np.isfinite(d).all():
        raise Refusal("NONFINITE_CONTRAST")
    contrast = float(np.linalg.norm(d.ravel()))
    if not math.isfinite(contrast) or contrast == 0:
        raise Refusal("NO_NONZERO_MEASURED_CONTRAST")
    per_column = np.sqrt(np.mean(np.square(d), axis=0))
    out = {
        "exact_matched_current_patterns": True,
        "reading_shape": list(SHAPE),
        "reading_count_per_case": int(d.size),
        "baseline_l2": baseline,
        "ordinary_direct_difference_l2": contrast,
        "ordinary_direct_difference_rms": float(np.sqrt(np.mean(np.square(d)))),
        "ordinary_direct_difference_max_absolute": float(np.max(np.abs(d))),
        "ordinary_direct_difference_to_baseline_l2_ratio": float(contrast / baseline),
        "all_16_column_rms_differences": [float(x) for x in per_column],
        "hypothetical_per_reading_error_bound_strictly_below": float(contrast / (2 * math.sqrt(d.size))),
    }
    if not all(math.isfinite(x) for x in [
            *out["all_16_column_rms_differences"],
            *[v for v in out.values() if type(v) is float]]):
        raise Refusal("NONFINITE_SUMMARY")
    return out

def download_exact(destination: Path):
    md5, sha, length = hashlib.md5(), hashlib.sha256(), 0
    req = Request(URL, headers={"User-Agent": "AGI-ALPHA-EIT183-independent-public-control/1.0"})
    with urlopen(req, timeout=45) as response:
        final = urlparse(response.url)
        if final.scheme != "https" or final.hostname not in ("zenodo.org", "www.zenodo.org"):
            raise Refusal("SOURCE_REDIRECT_CHANGED")
        with destination.open("xb") as out:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                length += len(chunk)
                if length > EXPECTED_SIZE:
                    raise Refusal("ARCHIVE_TOO_LARGE")
                md5.update(chunk)
                sha.update(chunk)
                out.write(chunk)
    if length != EXPECTED_SIZE or md5.hexdigest() != EXPECTED_MD5 or sha.hexdigest() != EXPECTED_SHA256:
        raise Refusal("ARCHIVE_BYTES_DIFFER_FROM_PINNED_PUBLIC_SOURCE")
    return sha.hexdigest()

def execute(archive_path: Path):
    with ZipFile(archive_path) as z:
        validate_zip(z)
        raw = []
        for name, expected_hash in MEMBERS.items():
            info = z.getinfo(name)
            if info.file_size > 250_000_000:
                raise Refusal("OVERSIZED_FROZEN_MEMBER")
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != expected_hash:
                raise Refusal("FROZEN_MEMBER_SHA256_CHANGED:" + name)
            raw.append(parse_member(data))
    return paired_control(*raw[0], *raw[1])

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    dest = Path(args.out)
    if dest.exists() or dest.is_symlink():
        raise Refusal("OUTPUT_MUST_BE_NEW")
    with tempfile.TemporaryDirectory(prefix="eit183-source-") as root:
        archive = Path(root) / "source.zip"
        sha = download_exact(archive)
        observed = execute(archive)
    receipt = {
        "schema": "blue-sky-eit183-ordinary-physical-pair-control-v1",
        "source_url": URL,
        "verified_zip_sha256": sha,
        "member_sha256": dict(MEMBERS),
        "observed_ordinary_control": observed,
        "independent_physical_error_calibration_available": False,
        "physical_property_reconstruction_performed": False,
        "strong_inverse_method_beaten": False,
        "beneficiary_accepted": False,
        "revenue_collected_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": receipt["decision"], "ordinary_pair_contrast_l2": observed["ordinary_direct_difference_l2"],
                      "hypothetical_epsilon_star": observed["hypothetical_per_reading_error_bound_strictly_below"],
                      "verified_zip_sha256": sha, "receipt": str(dest)}, sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except (Refusal, OSError, ValueError) as e:
        print(json.dumps({"decision": "FAILED_HOLD_NO_DEPLOY", "reason": str(e)}))
        raise SystemExit(2)
