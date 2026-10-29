"""Trusted harmless source-set and package-initializer regression probes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(root, case, scratch):
    clone = scratch / case
    shutil.copytree(root, clone, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "evidence"))
    relative = "campaign/unexpected_added.py" if case == "unexpected-python-source" else "campaign/__init__.py"
    leaf = clone / relative
    marker = clone / "CLAIM_AUDIT_MARKER.txt"
    harmless = "\nfrom pathlib import Path\nPath(__file__).resolve().parents[1].joinpath('CLAIM_AUDIT_MARKER.txt').write_text('harmless source probe executed')\nraise RuntimeError('CLAIM_AUDIT_MARKER')\n"
    if case == "unexpected-python-source":
        with leaf.open("x") as stream:
            stream.write(harmless)
    else:
        with leaf.open("a") as stream:
            stream.write(harmless)
    result = subprocess.run([sys.executable, "-I", str(clone / "reproduce.py"), "--output", str(scratch / (case + "-run"))],
                            capture_output=True, text=True, timeout=30)
    log = scratch / (case + "-run") / "WORKER.log"
    worker_log = log.read_text() if log.exists() else ""
    expected = "SOURCE_SET_MISMATCH" if case == "unexpected-python-source" else "SOURCE_IDENTITY_MISMATCH"
    passed = result.returncode != 0 and expected in worker_log and not marker.exists()
    return {"name": case, "changed_source": relative, "expected_refusal": expected,
            "returncode": result.returncode, "marker_executed": marker.exists(), "passed": passed,
            "fixture_sha256": sha(leaf), "stdout": result.stdout, "stderr": result.stderr, "worker_log": worker_log}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="lab-source-set-probe-") as temporary:
        scratch = Path(temporary)
        checks = [probe(root, name, scratch) for name in ["unexpected-python-source", "package-initializer-modified"]]
    receipt = {"schema": "lab/added-source-refusal/v1", "runner_sha256": sha(root / "reproduce.py"),
               "probe_sha256": sha(Path(__file__)), "checks": checks, "passed": all(x["passed"] for x in checks),
               "scope": "Harmless trusted fixtures in temporary copies; no original candidate edits, no scientific confirmation, no effect sandbox claim"}
    (args.output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": receipt["passed"], "checks": len(checks)}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
