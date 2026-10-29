"""Check interruption of actual completion-file publication, preserving originals."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wrapper_probe(path, destination):
    spec = importlib.util.spec_from_file_location("completion_boundary_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_open = Path.open
    invoked = []

    def open_boundary(self, mode="r", *args, **kwargs):
        stream = original_open(self, mode, *args, **kwargs)
        if "COMPLETE" in self.name and "x" in mode:
            invoked.append(self.name)
            stream.close()
            raise KeyboardInterrupt("verifier interruption at actual exclusive completion-file creation")
        return stream

    def successful_worker(*args, **kwargs):
        (destination / "REPORT.json").write_text('{"scope":"verifier worker stub; completion boundary only"}\n')
        return SimpleNamespace(returncode=0)

    error = None
    with mock.patch.object(Path, "open", open_boundary), mock.patch.object(module.subprocess, "run", successful_worker), mock.patch.object(sys, "argv", [str(path), "--output", str(destination)]):
        try:
            module.main()
        except BaseException as exc:
            error = type(exc).__name__ + ": " + str(exc)
    files = {p.name: sha(p) for p in destination.iterdir() if p.is_file()}
    return {"source_sha256": sha(path), "invoked_actual_filenames": invoked, "error": error,
            "files_sha256": files, "passed": bool(invoked) and "COMPLETE.json" not in files and "INTERRUPTED.json" in files,
            "mock_scope": "Only worker successful return/report is stubbed; actual wrapper file publication and exception path execute."}


def evaluate(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    old = wrapper_probe(root / "reproduce.py", output / "legacy-wrapper")
    repaired = wrapper_probe(root / "run_cycle.py", output / "repaired-wrapper")
    sys.path.insert(0, str(root))
    from flywheel.evidence_executor import execute
    task = {"id": "same-completion-objective", "phases": ["reserve", "start", "work", "complete"],
            "dependencies": [["reserve", "start"], ["start", "work"], ["work", "complete"]]}
    broker_output = output / "repaired-broker"
    actual = execute(task, {"body": task["phases"], "protected_from": 1}, broker_output, interrupt_at="complete")
    files = {p.name: sha(p) for p in broker_output.iterdir() if p.is_file()}
    broker = {"source_sha256": sha(root / "flywheel/evidence_executor.py"), "actual_execution": actual,
              "files_sha256": files, "passed": "COMPLETE.json" not in files and "INTERRUPTED.json" in files}
    report = {"schema": "agi-alpha-cycle004-completion-publication-verification/v1", "legacy": old,
              "repaired_wrapper": repaired, "repaired_broker": broker,
              "repair_passed_unchanged_spec": not old["passed"] and repaired["passed"] and broker["passed"],
              "confirmation_alpha_spent": 0,
              "limitation": "Catchable interruption during pending completion write; not SIGKILL or host/storage crash durability."}
    with (output / "REPORT.json").open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"repair_passed_unchanged_spec": report["repair_passed_unchanged_spec"]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = evaluate(args.root, args.output)
    raise SystemExit(0 if report["repair_passed_unchanged_spec"] else 1)
