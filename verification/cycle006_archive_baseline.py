"""Independent reproduction of the ordinary-extraction defect in released cycle005."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

EXPECTED = "9e80e3708f430b0a5ac18c8580eb2320febb213cbda63cc7eaa00be81b78e95d"
PREFIX = "AGI_ALPHA_Mechanism_Completion/"
MANIFEST = "ARCHIVE_MANIFEST.json"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def restrict():
    resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024**2, 20 * 1024**2))


def run(command, cwd, log):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    with log.open("xb") as stream:
        completed = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
            timeout=90, preexec_fn=restrict,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1",
                 "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"command": command, "returncode": completed.returncode,
            "wall_seconds": time.monotonic() - started,
            "child_cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            "log": log.name, "log_sha256": sha(log.read_bytes())}


def check(archive_path, output):
    started, cpu = time.monotonic(), time.process_time()
    output.mkdir(parents=True, exist_ok=False)
    raw = archive_path.read_bytes()
    if sha(raw) != EXPECTED:
        raise ValueError("RELEASE_ZIP_IDENTITY_MISMATCH")
    with zipfile.ZipFile(archive_path) as archive:
        records = archive.infolist()
        if len(records) > 10001 or sum(item.file_size for item in records) > 250 * 1024**2:
            raise ValueError("RELEASE_RESOURCE_BOUND")
        data = {}
        for item in records:
            if not item.filename.startswith(PREFIX) or item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("RELEASE_ENTRY_SCOPE")
            name = item.filename[len(PREFIX):]
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or path.as_posix() != name or name in data:
                raise ValueError("RELEASE_PATH_OR_DUPLICATE")
            data[name] = archive.read(item)
    manifest = json.loads(data[MANIFEST])
    payloads = {key: value for key, value in data.items() if key != MANIFEST}
    if manifest["schema"] != "lab/self-contained-source-archive/v2" or set(payloads) != set(manifest["files"]):
        raise ValueError("RELEASE_MANIFEST_SET")
    if any(sha(value) != manifest["files"][key] for key, value in payloads.items()):
        raise ValueError("RELEASE_PAYLOAD_IDENTITY")
    checks = {}
    with tempfile.TemporaryDirectory(prefix="cycle006-independent-baseline-", dir="/tmp") as temporary:
        staging = Path(temporary)
        for mode, selected in (("ordinary", data), ("validated", payloads)):
            root = staging / mode
            root.mkdir()
            if any((parent / ".git").exists() for parent in (root, *root.parents)):
                raise ValueError("GIT_ANCESTRY_PRESENT")
            for name, value in selected.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
            if mode == "validated":
                command += ["-p", "test_archive_v2.py"]
            command += ["-v"]
            result = run(command, root, output / (mode + ".log"))
            log = (output / (mode + ".log")).read_text()
            result["all_original_payload_hashes_unchanged"] = all(sha((root / name).read_bytes()) == expected for name, expected in manifest["files"].items())
            if mode == "ordinary":
                result["established_original_defect"] = result["returncode"] != 0 and "Ran 94 tests" in log and "FAILED (errors=1)" in log and "ARCHIVE_RESERVED_MANIFEST" in log
                result["metadata_retained"] = (root / MANIFEST).exists()
            else:
                result["supported_payload_extraction_passed"] = result["returncode"] == 0 and "Ran 3 tests" in log
                result["metadata_consumed_after_validation"] = not (root / MANIFEST).exists()
            checks[mode] = result
    report = {"schema": "agi-alpha-cycle006-independent-archive-baseline/v1",
        "archive_sha256": EXPECTED, "archive_bytes": len(raw), "payloads_verified": len(payloads),
        "verifier_sha256": sha(Path(__file__).read_bytes()), "checks": checks,
        "established": checks["ordinary"]["established_original_defect"] and checks["validated"]["supported_payload_extraction_passed"],
        "resources": {"wall_seconds": time.monotonic() - started, "verifier_cpu_seconds": time.process_time() - cpu,
                      "child_cpu_seconds": sum(result["child_cpu_seconds"] for result in checks.values())},
        "provenance": "New verifier-owned execution of exact cached public ZIP. Distinct from cycle005 owner sixteen-gate receipt and cycle006 archive-builder reproduction.",
        "limits": ["Procedural separation shares host, model family, libraries and filesystem; not independent external certification.",
                   "Original full94 suite run only on ordinary extraction; validated branch rechecks three archive tests, not a new full94 qualification.",
                   "No candidate changes or scientific/commercial conclusion. Original archive and all source payloads remain unchanged."]}
    write(output / "REPORT.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = check(args.archive, args.output)
    print(json.dumps({"established": report["established"], "output": str(args.output)}))
    raise SystemExit(0 if report["established"] else 1)
