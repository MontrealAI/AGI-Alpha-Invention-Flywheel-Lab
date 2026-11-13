"""Deterministic, audited, self-contained *research* distribution.

This is a separate offline Accessibility148/149 package, NOT a Connected014
financial/source archive and NOT a certified accessibility service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from research.accessible_output148 import gate

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "agi-alpha/accessibility149/portable-source-v1"
MANIFEST = "SOURCE_MANIFEST.json"
MAX_BYTES = 2_000_000
SOURCES = (
    "research/accessible_output148/gate.py",
    "research/accessible_output148/PROTOCOL.md",
    "research/accessible_output148/fixtures/baseline.json",
    "research/accessible_output148/fixtures/candidate.json",
    "research/accessible_output149/review.py",
    "research/accessible_output149/standalone.py",
    "research/accessible_output149/README.md",
    "tests/test_accessible_output148.py",
    "tests/test_accessible_output149.py",
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def payload():
    files = {}
    for name in SOURCES:
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("NONREGULAR_SOURCE_FILE:" + name)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("SOURCE_FILE_BOUND")
        files[name] = path.read_bytes()
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("SOURCE_PACKAGE_BOUND")
    identity = {name: digest(files[name]) for name in sorted(files)}
    manifest = {"schema": SCHEMA, "files": identity,
                "source_root_sha256": digest(gate.canonical(identity)),
                "scope": "offline_structural_and_authored_content_research_only",
                "native_account_included": False,
                "credentials_included": False,
                "wcag_or_buyer_certification": False}
    return files, gate.canonical(manifest)


def build(path):
    destination = Path(path)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("CREATE_ONLY_ARCHIVE_REQUIRED")
    files, manifest = payload()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted({**files, MANIFEST: manifest}.items()):
            member = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_DEFLATED
            member.external_attr = (stat.S_IFREG | 0o644) << 16
            member.create_system = 3
            archive.writestr(member, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    return verify(destination)


def verify(path):
    archive_path = Path(path)
    if not archive_path.is_file() or archive_path.is_symlink():
        raise ValueError("REGULAR_ARCHIVE_REQUIRED")
    if archive_path.stat().st_size > MAX_BYTES:
        raise ValueError("ARCHIVE_SIZE_BOUND")
    with ZipFile(archive_path) as archive:
        members = archive.infolist()
        names = [entry.filename for entry in members]
        if len(names) != len(set(names)) or set(names) != set(SOURCES) | {MANIFEST}:
            raise ValueError("EXACT_SOURCE_MEMBER_SET_REQUIRED")
        if sum(entry.file_size for entry in members) > MAX_BYTES:
            raise ValueError("UNCOMPRESSED_ARCHIVE_BOUND")
        for entry in members:
            name = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (name.is_absolute() or ".." in name.parts or "\\" in entry.filename
                    or not stat.S_ISREG(mode)):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
        if archive.testzip() is not None:
            raise ValueError("CRC_FAILURE")
        manifest_raw = archive.read(MANIFEST)
        manifest = gate.strict_load(manifest_raw)
        if (not isinstance(manifest, dict)
                or set(manifest) != {"schema", "files", "source_root_sha256",
                                    "scope", "native_account_included",
                                    "credentials_included", "wcag_or_buyer_certification"}
                or manifest.get("schema") != SCHEMA
                or manifest.get("scope") != "offline_structural_and_authored_content_research_only"
                or manifest.get("native_account_included") is not False
                or manifest.get("credentials_included") is not False
                or manifest.get("wcag_or_buyer_certification") is not False
                or set(manifest["files"]) != set(SOURCES)
                or manifest_raw != gate.canonical(manifest)):
            raise ValueError("SOURCE_MANIFEST_INVALID")
        identities = {name: digest(archive.read(name)) for name in sorted(SOURCES)}
        if manifest["files"] != identities or manifest["source_root_sha256"] != digest(gate.canonical(identities)):
            raise ValueError("SOURCE_ARCHIVE_HASH_MISMATCH")
    return {"accepted": True, "schema": SCHEMA,
            "archive_sha256": digest(archive_path.read_bytes()),
            "source_root_sha256": manifest["source_root_sha256"],
            "source_files": len(SOURCES),
            "scope": manifest["scope"]}


def smoke(path):
    """Run from only independently verified extracted ZIP, never source checkout."""
    receipt = verify(path)
    with TemporaryDirectory(prefix="accessibility149-clean-") as temp:
        root = Path(temp) / "source"
        root.mkdir()
        with ZipFile(path) as archive:
            archive.extractall(root)
        expected = set(SOURCES) | {MANIFEST}
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        if actual != expected:
            raise ValueError("EXTRACTED_FILE_SET_CHANGED")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root))
        base = [sys.executable, "-B", "-m"]
        def run(args):
            return subprocess.check_output(base + args, cwd=root, env=env, text=True)
        run(["unittest", "-v", "tests.test_accessible_output148",
             "tests.test_accessible_output149"])
        initial = root / "research/accessible_output148/fixtures"
        result_dir = Path(temp)
        for label, name in (("base", "baseline.json"), ("candidate", "candidate.json")):
            run(["research.accessible_output148.gate", "compile",
                 "--record", str(initial / name),
                 "--output", str(result_dir / label)])
            run(["research.accessible_output148.gate", "audit",
                 "--output", str(result_dir / label)])
        result = gate.strict_load(run(["research.accessible_output149.review",
                                      "--baseline", str(result_dir / "base"),
                                      "--candidate", str(result_dir / "candidate")]).encode())
        if (result.get("continuity_verdict") != "HOLD_AUTHORED_CONTENT_CHANGED_REVIEW_REQUIRED"
                or result.get("deployment_authorized") is not False
                or result.get("automatic_content_carryforward") is not False):
            raise ValueError("SYNTHETIC_CHANGED_CONTENT_MUST_HOLD")
    return {**receipt, "clean_extracted_test_and_cli": "PASS",
            "registered_fixture_continuity_verdict": result["continuity_verdict"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify", "smoke"))
    parser.add_argument("--archive", required=True)
    args = parser.parse_args(argv)
    operation = {"build": build, "verify": verify, "smoke": smoke}[args.command]
    print(json.dumps(operation(args.archive), sort_keys=True))


if __name__ == "__main__":
    main()
