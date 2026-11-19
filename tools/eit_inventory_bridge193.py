"""EIT193: read-only exact-source bridge; never substitutes a scientific verifier.

A frozen EIT192 classifier identifies metadata; the original EIT190 mat_variables
parser independently reads every retained genuine MATLAB matrix. No MATLAB code
is executed, no physics or commercial score is produced.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

SOURCE_ARCHIVE_SHA256 = "ad193cd88288e3d6f8ea87f76d8ed2f06382291ab494d55efe08806c65ff994c"
SOURCE_ARCHIVE_BYTES = 24539080
PINNED_MODULES = (
    ("tools.eit_zip_metadata192", "530648069d83bafa23b7f93c9dec7f1d4cc7e97e",
     "tools/eit_zip_metadata192.py", "83edfec308caaa5d29429b68c0a7857ccb4a1110"),
    ("tools.eit_live_source192", "530648069d83bafa23b7f93c9dec7f1d4cc7e97e",
     "tools/eit_live_source192.py", "e0858652b3be690a28dec3d6050c4a68b035c353"),
    ("research.eit_independent190.inspect", "be79c33ed6371800ce4e7881505397780448838e",
     "research/eit_independent190/inspect.py", "ead0351ea3c7235b5de533510474a7b16d899784"),
)
MAX_SOURCE_MODULE = 256_000
REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"


class BridgeRefusal(ValueError):
    """A held-out, original-source or original-parser acceptance failure."""


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify_source_bytes(data: bytes, blob_sha: str) -> None:
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SOURCE_MODULE:
        raise BridgeRefusal("EIT193_PINNED_SOURCE_SIZE_REJECTED")
    if git_blob_sha1(data) != blob_sha:
        raise BridgeRefusal("EIT193_PINNED_SOURCE_BLOB_CHANGED")


def get_pinned_source(commit: str, path: str, blob_sha: str) -> bytes:
    url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{path}"
    with urlopen(Request(url, headers={"User-Agent": "AGI-ALPHA-EIT193-source-bridge/1"}),
                 timeout=60) as response:
        target = urlsplit(response.geturl())
        if target.scheme != "https" or target.hostname != "raw.githubusercontent.com":
            raise BridgeRefusal("EIT193_PINNED_SOURCE_HOST_CHANGED")
        raw = response.read(MAX_SOURCE_MODULE + 1)
    verify_source_bytes(raw, blob_sha)
    return raw


def load_exact_modules(root: Path):
    """Check three exact public Git blobs *before* importing any of them."""
    payloads = []
    for label, commit, path, sha in PINNED_MODULES:
        raw = get_pinned_source(commit, path, sha)
        payloads.append((label, path, sha, raw))
    loaded = {}
    for label, path, sha, raw in payloads:
        output = root / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(raw)
    # The repository already has a tools namespace. Install the exact frozen
    # modules explicitly so no local/current-main module shadows them.
    for label, path, sha, raw in payloads:
        spec = importlib.util.spec_from_file_location(label, root / path)
        if spec is None or spec.loader is None:
            raise BridgeRefusal("EIT193_MODULE_IMPORT_SPEC_REJECTED")
        module = importlib.util.module_from_spec(spec)
        sys.modules[label] = module
        spec.loader.exec_module(module)
        loaded[label] = module
    return loaded


def analyze_genuine_members(archive_path: Path, typed_receipt: dict, mat_parser):
    """No second classifier: parse precisely the genuine names EIT192 retained."""
    genuine = typed_receipt.get("genuine_members")
    candidates = typed_receipt.get("genuine_matlab_candidates")
    if not isinstance(genuine, list) or not isinstance(candidates, list):
        raise BridgeRefusal("EIT193_TYPED_SOURCE_MISSING")
    expected = sorted(n for n in genuine if
                      isinstance(n, str) and n.lower().endswith((".mat", ".m")))
    if candidates != expected or len(candidates) != len(set(candidates)):
        raise BridgeRefusal("EIT193_TYPED_CANDIDATE_SET_CHANGED")
    if any(n.startswith("__MACOSX/") for n in candidates):
        raise BridgeRefusal("EIT193_SIDECAR_CANDIDATE_LEAK")
    records = []
    with ZipFile(archive_path) as source:
        for name in candidates:
            try:
                info = source.getinfo(name)
                raw = source.read(info)
            except (KeyError, OSError, ValueError) as exc:
                raise BridgeRefusal("EIT193_GENUINE_MEMBER_NOT_READABLE:" + name) from exc
            if len(raw) != info.file_size:
                raise BridgeRefusal("EIT193_GENUINE_MEMBER_LENGTH_MISMATCH:" + name)
            item = {"member": name, "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest()}
            if name.lower().endswith(".mat"):
                try:
                    result = mat_parser(raw)
                except Exception as exc:
                    raise BridgeRefusal("EIT193_ORIGINAL_MAT_PARSER_REJECTED:" +
                                        name + ":" + type(exc).__name__ + ":" + str(exc)) from exc
                if not isinstance(result, dict) or not isinstance(result.get("variables"), list):
                    raise BridgeRefusal("EIT193_ORIGINAL_MAT_PARSER_BAD_RESULT:" + name)
                item.update(result)
            else:
                if len(raw) > 100_000:
                    raise BridgeRefusal("EIT193_MATLAB_SCRIPT_OVERSIZE:" + name)
                item.update({"format": "MATLAB-source-not-executed",
                             "encoding": "UTF8-decoding-only" if is_utf8(raw)
                             else "nonUTF8-encoding-unknown",
                             "newline_count": raw.count(b"\n")})
            records.append(item)
    basenames = [r["member"].rsplit("/", 1)[-1] for r in records]
    jacobians = [n for n in basenames if n == "J_AgarChestPhantom.mat"]
    meshes = [n for n in basenames if n.startswith("mesh_AgarChestPhantom") and n.endswith(".mat")]
    scripts = [n for n in basenames if n == "Example_ChestPhantom_LinearDifferenceImaging.m"]
    data = [r for r in records if r["member"].lower().endswith(".mat") and
            "AgarChestPhantom" in r["member"] and
            r["member"].rsplit("/", 1)[-1] not in jacobians + meshes]
    if len(jacobians) != 1 or not meshes or len(scripts) != 1 or not data:
        raise BridgeRefusal("EIT193_REQUIRED_ORIGINAL_CHEST_COMPONENTS_MISSING")
    return {"matlab_members": records, "jacobians": len(jacobians),
            "meshes": len(meshes), "scripts": len(scripts),
            "data_matrices": len(data)}


def is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def run(out: Path, failure_out: Path):
    if out.exists() or out.is_symlink() or failure_out.exists() or failure_out.is_symlink():
        raise BridgeRefusal("EIT193_RECEIPT_EXISTS")
    with tempfile.TemporaryDirectory(prefix="eit193-original-chest-") as scratch:
        root = Path(scratch)
        loaded = load_exact_modules(root)
        live = loaded["tools.eit_live_source192"]
        inspector = loaded["research.eit_independent190.inspect"]
        manifest = live.read_manifest()
        size, md5 = live.choose_target(manifest)
        if size != SOURCE_ARCHIVE_BYTES or md5 != "8514af69c0277f339d5576dd4eb9a598":
            raise BridgeRefusal("EIT193_OFFICIAL_ARCHIVE_MANIFEST_CHANGED")
        archive = root / "original-chest.zip"
        digest = live.get_exact_archive(archive, size, md5)
        if digest != SOURCE_ARCHIVE_SHA256:
            raise BridgeRefusal("EIT193_ORIGINAL_ARCHIVE_SHA256_CHANGED")
        typed = live.qualify_archive(archive)
        bridge = analyze_genuine_members(archive, typed, inspector.mat_variables)
    result = {
        "schema": "agi-alpha/eit193-original-mat-source-bridge/v1",
        "preregistered_source": "campaign/eit-inventory-193/PREREGISTRATION.md",
        "original_archive": {"record": "24120439", "name": "AgarChestPhantom.zip",
                             "size": size, "md5": md5, "sha256": digest},
        "pinned_git_blobs": [
            {"module": label, "commit": commit, "path": path, "git_blob_sha1": sha}
            for label, commit, path, sha in PINNED_MODULES
        ],
        "source_crc_validated": typed["full_zip_crc_validated"],
        "sidecars_classified": len(typed["sidecars"]),
        "historical_failed_sidecar_preserved": typed["historical_original_failure_member_preserved"],
        "original_matlab_variable_tables": bridge,
        "scientific_inference_completed": False,
        "physical_property_validated": False,
        "commercial_buyers_or_payments_observed": False,
        "native_account_or_liabilities_modified": False,
        "complete_host_model_billing_usd": None,
        "decision": "HOLD_NO_DEPLOY_NO_BID",
    }
    with out.open("x", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--failure-out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        summary = run(args.out, args.failure_out)
        print(json.dumps({"decision": summary["decision"],
                          "parsed_original_members": len(
                              summary["original_matlab_variable_tables"]["matlab_members"]),
                          "archive_sha256": summary["original_archive"]["sha256"]},
                         sort_keys=True))
        return 0
    except Exception as exc:
        failure = {"decision": "FAILED_HOLD_NO_DEPLOY_NO_BID",
                   "error_type": type(exc).__name__, "error": str(exc),
                   "source": SOURCE_ARCHIVE_SHA256,
                   "physical_property_validated": False,
                   "commercial_buyers_or_payments_observed": False}
        if not args.failure_out.exists() and not args.failure_out.is_symlink():
            with args.failure_out.open("x", encoding="utf-8") as f:
                json.dump(failure, f, indent=2, sort_keys=True)
                f.write("\n")
        print(json.dumps(failure, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
