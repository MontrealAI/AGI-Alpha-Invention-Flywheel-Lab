"""Actual parent SIGINT during a live worker; no builder source modification."""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def snapshot(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


def children(pid):
    path = Path("/proc") / str(pid) / "task" / str(pid) / "children"
    try:
        direct = [int(p) for p in path.read_text().split()]
    except FileNotFoundError:
        return []
    return direct + [descendant for child in direct for descendant in children(child)]


def running(pid):
    try:
        return Path("/proc", str(pid), "stat").read_text().split(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def host_child_for_output(output):
    host_self = int(Path('/proc/self/stat').read_text().split()[0])
    for pid in children(host_self):
        try:
            command = Path('/proc', str(pid), 'cmdline').read_bytes()
            if str(output).encode() in command and b'run_cycle.py' in command:
                return pid
        except FileNotFoundError:
            pass
    return None


def probe(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    actual = output / "actual-run"
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError("VERIFIER_SUBREAPER_UNAVAILABLE")
    command = [sys.executable, "-I", str(root / "run_cycle.py"), "--output", str(actual)]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env={"PATH": os.defpath, "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"})
    deadline = time.monotonic() + 10
    triggered = False
    while time.monotonic() < deadline and proc.poll() is None:
        if (actual / "SANDBOX.json").exists() and not (actual / "REPORT.json").exists():
            triggered = True
            break
        time.sleep(.002)
    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
    stdout, stderr = proc.communicate(timeout=10)
    deadline, reaped, no_children = time.monotonic() + 3, [], False
    while time.monotonic() < deadline:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid:
                reaped.append({"pid": pid, "wait_status": status})
            else:
                time.sleep(.02)
        except ChildProcessError:
            no_children = True
            break
    before = snapshot(actual)
    restart = subprocess.run(command, capture_output=True, text=True, timeout=10,
                             env={"PATH": os.defpath, "LANG": "C.UTF-8"})
    after = snapshot(actual)
    result = {"schema": "agi-alpha-cycle004-active-worker-interruption/v1",
              "runner_sha256": hashlib.sha256((root / "run_cycle.py").read_bytes()).hexdigest(),
              "pid_namespace_note": "No proc PID assumption: verifier is a Linux child subreaper and reaps adopted worker descendants after parent exit.",
              "triggered_after_worker_sandbox_receipt_before_report": triggered,
              "parent_returncode": proc.returncode, "adopted_descendants_reaped": reaped,
              "no_children_after_reaping": no_children,
              "interrupted_marker": (actual / "INTERRUPTED.json").exists(),
              "complete_absent": not (actual / "COMPLETE.json").exists(),
              "restart_refused_unchanged": restart.returncode != 0 and before == after,
              "files_sha256": before, "stdout": stdout, "stderr": stderr,
              "restart_stderr": restart.stderr,
              "passed": triggered and bool(reaped) and no_children and (actual / "INTERRUPTED.json").exists()
                        and not (actual / "COMPLETE.json").exists() and restart.returncode != 0 and before == after,
              "scope": "SIGINT sent to reproduction parent after real worker wrote sandbox receipt but before its report. Adopted descendants are reaped and ECHILD proves none remain; Linux procedural qualification, not host-crash durability."}
    with (output / "REPORT.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": result["passed"], "reaped_descendants": len(reaped), "no_children": no_children}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = probe(args.root, args.output)
    raise SystemExit(0 if result["passed"] else 1)
