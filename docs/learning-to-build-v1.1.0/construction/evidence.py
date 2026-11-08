#!/usr/bin/env python3
"""Create or verify the compact, complete public reproduction evidence.

The archive contains generated masks, measurements and execution receipts, not
the public image archives or third-party model weights. Its manifest is a file
identity check. Scientific acceptance is independently recomputed by check.py.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / "evidence"
REQUIRED = {
    "REPRODUCTION.json", "classical/RESULTS.json", "classical/RUN_STATE.json",
    "classical/STATUS.json", "incumbent/RESULTS.json", "incumbent/STATUS.json",
    "incumbent/COMPLETION.json", "incumbent/IDENTITY.json",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate manifest key: " + key)
        result[key] = value
    return result


def name_check(name):
    require(isinstance(name, str) and name and "\\" not in name,
            "Invalid evidence member name")
    p = PurePosixPath(name)
    require(not p.is_absolute() and ".." not in p.parts and
            p.as_posix() == name and not any(x.startswith(".") for x in p.parts),
            "Unsafe evidence member: " + name)
    return p


def create(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    require(source.is_dir() and not destination.is_relative_to(source),
            "Archive destination must be outside its evidence source")
    require(not destination.exists(), "Evidence destination already exists; preserve it")
    files = []
    for path in sorted(source.rglob("*")):
        require(not path.is_symlink(), "Evidence source cannot contain symlinks")
        if path.is_file():
            name = path.relative_to(source).as_posix()
            name_check(name)
            files.append({"path": name, "bytes": path.stat().st_size, "sha256": digest(path)})
    require(REQUIRED <= {row["path"] for row in files}, "Incomplete reproduction source")
    destination.mkdir(parents=True)
    archive_path = destination / "REPRODUCTION.tar.gz"
    with archive_path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for row in files:
                    contents = (source / row["path"]).read_bytes()
                    require(len(contents) == row["bytes"] and hashlib.sha256(contents).hexdigest() == row["sha256"],
                            "Evidence changed during packaging: " + row["path"])
                    info = tarfile.TarInfo(row["path"])
                    info.size, info.mode, info.mtime = len(contents), 0o644, 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(contents))
    manifest = {
        "schema": "learning-to-build/reproduction-archive/v1",
        "evidence_role": "Reproduction of an exposed, previously registered comparison; not a fresh confirmation",
        "archive": {"file": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": digest(archive_path)},
        "files": files,
        "file_count": len(files), "uncompressed_bytes": sum(row["bytes"] for row in files),
        "scope": "Exact inventory and byte identity only. Use check.py for independent scientific rescoring and classical replay.",
        "excluded_inputs": "The five public image archives and third-party model weights are retrieved separately by frozen identity.",
    }
    (destination / "EVIDENCE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return verify(destination)


def verify(directory=DEFAULT, output=None):
    directory = Path(directory).resolve()
    manifest_path = directory / "EVIDENCE_MANIFEST.json"
    require(manifest_path.is_file() and not manifest_path.is_symlink(), "Missing regular evidence manifest")
    manifest = json.loads(manifest_path.read_text(), object_pairs_hook=unique_object)
    require(manifest["schema"] == "learning-to-build/reproduction-archive/v1", "Unknown evidence manifest")
    require(manifest["archive"]["file"] == "REPRODUCTION.tar.gz", "Unexpected evidence archive name")
    archive_path = directory / manifest["archive"]["file"]
    require(archive_path.is_file() and not archive_path.is_symlink(), "Missing regular evidence archive")
    require(archive_path.stat().st_size == manifest["archive"]["bytes"] and
            digest(archive_path) == manifest["archive"]["sha256"], "Evidence archive identity differs")
    expected = {}
    for row in manifest["files"]:
        name_check(row["path"])
        require(row["path"] not in expected, "Duplicate evidence manifest path")
        require(type(row["bytes"]) is int and row["bytes"] >= 0 and
                isinstance(row["sha256"], str) and len(row["sha256"]) == 64 and
                all(c in "0123456789abcdef" for c in row["sha256"]), "Invalid evidence file identity")
        expected[row["path"]] = row
    require(REQUIRED <= set(expected), "Required evidence is missing")
    require(type(manifest["file_count"]) is int and manifest["file_count"] == len(expected) and
            type(manifest["uncompressed_bytes"]) is int and
            manifest["uncompressed_bytes"] == sum(row["bytes"] for row in expected.values()),
            "Evidence inventory totals differ")
    if output is not None:
        output = Path(output).expanduser()
        require(output.is_absolute() and not output.exists() and not output.is_symlink(),
                "Extraction output must be a new absolute path")
        require(not output.resolve().is_relative_to(directory), "Do not extract into canonical evidence source")
        output.mkdir(parents=True)
    seen = set()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            name_check(member.name)
            require(member.isfile() and member.name not in seen and member.name in expected,
                    "Unexpected, duplicate or nonregular evidence member: " + member.name)
            row = expected[member.name]
            require(member.size == row["bytes"], "Evidence member length differs: " + member.name)
            stream = archive.extractfile(member)
            require(stream is not None, "Unreadable evidence member")
            h, count = hashlib.sha256(), 0
            target = None
            try:
                if output is not None:
                    path = output / member.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    target = path.open("xb")
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    count += len(block)
                    h.update(block)
                    if target is not None:
                        target.write(block)
            finally:
                if target is not None:
                    target.close()
            require(count == row["bytes"] and h.hexdigest() == row["sha256"],
                    "Evidence member content differs: " + member.name)
            seen.add(member.name)
    require(seen == set(expected), "Evidence archive coverage differs from manifest")
    return {"status": "VERIFIED", "files": len(seen), "archive_sha256": manifest["archive"]["sha256"],
            "evidence_role": manifest["evidence_role"], "scientific_acceptance_checked": False,
            "extracted_to": str(output) if output is not None else None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT)
    parser.add_argument("--extract", type=Path)
    parser.add_argument("--create", type=Path, help="Authoring only: package this complete evidence directory")
    args = parser.parse_args()
    require(not (args.create and args.extract), "Choose creation or extraction")
    result = create(args.create, args.directory) if args.create else verify(args.directory, args.extract)
    print(json.dumps(result, indent=2, sort_keys=True))
