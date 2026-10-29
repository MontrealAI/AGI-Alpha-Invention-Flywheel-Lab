"""Independent clean ZIP/no-git reproducibility and historical-input refusal checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(command, cwd, log):
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=150,
                                env={"PATH": os.defpath, "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    return {"returncode": result.returncode, "log_sha256": sha(log.read_bytes()), "log": log.name}


def check(archive, output):
    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=False)
    prefix = "AGI_ALPHA_Mechanism_Completion/"
    with zipfile.ZipFile(archive) as source:
        entries = source.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError("DUPLICATE_ARCHIVE_ENTRY")
        data = {name[len(prefix):]: source.read(name) for name in entries if name.startswith(prefix)}
        if len(data) != len(entries):
            raise ValueError("ARCHIVE_PREFIX")
    manifest = json.loads(data.pop("ARCHIVE_MANIFEST.json"))
    verified = set(data) == set(manifest["files"]) and all(sha(raw) == manifest["files"][name] for name, raw in data.items())
    if not verified:
        raise ValueError("INDEPENDENT_MANIFEST_MISMATCH")
    checks = {}
    with tempfile.TemporaryDirectory(prefix="cycle005-independent-archive-") as temporary:
        root = Path(temporary) / "source"
        root.mkdir()
        for name, raw in data.items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts:
                raise ValueError("ARCHIVE_PATH_OR_GIT_ENTRY")
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        checks["no_git_source_tree"] = not (root / ".git").exists()
        checks["unit"] = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], root, output / "clean-unit.log")
        legacy = Path(temporary) / "cycle004"
        checks["historical_materialization"] = run([sys.executable, "-I", str(root / "flywheel/archive_v2.py"), "cycle004", str(root), str(legacy)], root, output / "cycle004-materialize.log")
        if checks["historical_materialization"]["returncode"] == 0:
            checks["unchanged_cycle004_replay"] = run([sys.executable, "-I", str(legacy / "run_cycle.py"), "--output", str(Path(temporary) / "replay")], root, output / "cycle004-replay.log")
        changed = Path(temporary) / "corrupt"
        shutil.copytree(root, changed)
        source_leaf = changed / "historical/cycle-004/files/flywheel/strategy.py.txt"
        source_leaf.write_bytes(source_leaf.read_bytes() + b"\n# verifier corruption\n")
        refused_destination = Path(temporary) / "corrupt-refused"
        checks["corrupted_historical_source"] = run([sys.executable, "-I", str(changed / "flywheel/archive_v2.py"), "cycle004", str(changed), str(refused_destination)], changed, output / "corrupt-historical.log")
        checks["corrupted_refused_before_destination"] = checks["corrupted_historical_source"]["returncode"] != 0 and not refused_destination.exists()
        source_leaf.unlink()
        missing_destination = Path(temporary) / "missing-refused"
        checks["missing_historical_source"] = run([sys.executable, "-I", str(changed / "flywheel/archive_v2.py"), "cycle004", str(changed), str(missing_destination)], changed, output / "missing-historical.log")
        checks["missing_refused_before_destination"] = checks["missing_historical_source"]["returncode"] != 0 and not missing_destination.exists()
    passed = checks["no_git_source_tree"] and checks["unit"]["returncode"] == 0 and checks["historical_materialization"]["returncode"] == 0 and checks.get("unchanged_cycle004_replay", {}).get("returncode") == 0 and checks["corrupted_refused_before_destination"] and checks["missing_refused_before_destination"]
    report = {"schema": "agi-alpha-cycle005-independent-clean-archive/v1", "archive_sha256": sha(archive.read_bytes()),
              "archive_bytes": archive.stat().st_size, "manifest_sha256": sha(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()),
              "independently_verified_payload_files": len(data), "checks": checks, "passed": passed,
              "verifier_sha256": sha(Path(__file__).read_bytes()), "wall_seconds": time.monotonic()-started,
              "scope": "This exact ZIP and installed Python/dependencies. Provisional archive does not qualify later source. No .git, Git/network fallback or private working-tree source is used for replay.",
              "confirmation_alpha_spent": 0}
    with (output / "REPORT.json").open("x") as stream:
        json.dump(report, stream, indent=2); stream.write("\n")
    print(json.dumps({"passed": passed, "files": len(data), "archive_sha256": report["archive_sha256"]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check(args.archive, args.output)
    raise SystemExit(0 if report["passed"] else 1)
