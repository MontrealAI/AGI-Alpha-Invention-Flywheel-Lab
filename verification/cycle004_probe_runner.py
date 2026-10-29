"""Deterministic interruption probes; never edits the runner under test."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest import mock


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(runner, stage, output):
    runner = Path(runner).resolve()
    spec = importlib.util.spec_from_file_location("cycle004_runner_probe", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_write = module.write
    invoked = []

    def interrupted_write(path, data):
        if stage == "during_started_creation" and Path(path).name == "STARTED.json":
            invoked.append(stage)
            with Path(path).open("x"):
                raise KeyboardInterrupt("deterministic verifier interruption during STARTED creation")
        return original_write(path, data)

    def interrupted_run(*args, **kwargs):
        invoked.append("before_worker_launch")
        raise KeyboardInterrupt("deterministic verifier interruption before worker launch")

    error = None
    with mock.patch.object(module, "write", interrupted_write), mock.patch.object(module.subprocess, "run", interrupted_run), mock.patch.object(sys, "argv", [str(runner), "--output", str(output)]):
        try:
            module.main()
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
    before = {p.name: sha(p) for p in output.iterdir() if p.is_file()} if output.exists() else {}
    restart_error = None
    with mock.patch.object(sys, "argv", [str(runner), "--output", str(output)]):
        try:
            module.main()
        except BaseException as exc:
            restart_error = type(exc).__name__ + ": " + str(exc)
    after = {p.name: sha(p) for p in output.iterdir() if p.is_file()} if output.exists() else {}
    return {
        "runner_sha256": sha(runner), "stage": stage, "invoked": invoked,
        "error": error, "interrupted_marker": "INTERRUPTED.json" in before,
        "complete_absent": "COMPLETE.json" not in before,
        "restart_refused": bool(restart_error), "restart_error": restart_error,
        "evidence_unchanged": before == after, "files_sha256": before,
        "passed": bool(invoked) and "INTERRUPTED.json" in before and "COMPLETE.json" not in before and bool(restart_error) and before == after,
        "scope": "Deterministic KeyboardInterrupt at an existing side-effect boundary, using a verifier-only monkeypatch. This is fault injection of the actual initialization window, not evidence of host-crash durability."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = [probe(args.runner, stage, args.output / stage) for stage in ("during_started_creation", "before_worker_launch")]
    report = {"schema": "agi-alpha-cycle004-runner-interruption-v1", "checks": records, "all_passed": all(r["passed"] for r in records), "confirmation_alpha_spent": 0}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_passed": report["all_passed"], "checks": len(records), "output": str(args.output)}))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
