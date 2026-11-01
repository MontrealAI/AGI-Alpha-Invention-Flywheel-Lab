"""Current active-worker qualification of the unchanged frozen cycle-001 runner.

This checker does not repair or qualify interruption during STARTED publication.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

PINS = {
    "reproduce.py": "1e812332d6b8ed91d38970ae07fffde0cca0047730a1a8e3d5c9665f7de254e3",
    "verification/probe_worker_bounds.py": "970ddeb3e419880e4561d697367e0145395353b76d21ed79a4e467af23eba4c0",
    "campaign/cycle-001/CLOSURE.json": "a06a4f7630184b54205173e1f271e6af7ae5396687fd64deb575ae4de13b3252",
    "campaign/cycle-001/EDITION_SHA256.json": "e968d63bd2c4b22d635216f8d2df5b80a92db253cdfe3982c5cbbaf5b639f920",
}
LEGACY_FAILURE = {
    "main_commit": "99769a8a4d19a8cfc1b3c6d05084d7ed99b76849",
    "workflow_run_id": 41300637969,
    "artifact_id": 13082132066,
    "artifact_sha256": "a8bcbe0d49b1184a5058b97d5a965000b1efc18ad507a0d75dd0dde371b0f0fd",
    "early_started_interruption": "PRESERVED_NOT_REPAIRED",
}
ENV = {"PATH": os.defpath, "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def verify_sources(root):
    for name, expected in PINS.items():
        if (root / name).is_symlink() or sha(root / name) != expected:
            raise ValueError("FROZEN_SOURCE_IDENTITY_MISMATCH " + name)
    expected = {**json.loads((root / "campaign/cycle-001/EDITION_SHA256.json").read_text()),
                **json.loads((root / "campaign/cycle-001/CLOSURE.json").read_text()), **PINS}
    if {str(path.relative_to(root)) for path in root.rglob("*.py")} != {name for name in expected if name.endswith(".py")}:
        raise ValueError("FROZEN_PYTHON_SOURCE_SET_MISMATCH")
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or sha(path) != digest:
            raise ValueError("FROZEN_SOURCE_IDENTITY_MISMATCH " + name)
    return len(expected)


def snapshot(root):
    return {str(path.relative_to(root)): sha(path) for path in sorted(root.rglob("*")) if path.is_file()}


def proc_state(host_pid):
    try:
        fields = Path("/proc", str(host_pid), "stat").read_text().rsplit(")", 1)[1].split()
        return {"state": fields[0], "parent_host_pid": int(fields[1]), "start_ticks": int(fields[19])}
    except FileNotFoundError:
        return None


def fd_identity(pidfd):
    fields = dict(line.split(":", 1) for line in Path("/proc/self/fdinfo", str(pidfd)).read_text().splitlines())
    ids = [int(value) for value in fields["NSpid"].split()]
    return int(fields["Pid"]), ids


def direct_children(parent_host_pid):
    """Read only this owned, single-threaded reproduction parent's child list."""
    path = Path("/proc", str(parent_host_pid), "task", str(parent_host_pid), "children")
    try:
        return [int(value) for value in path.read_text().split()]
    except FileNotFoundError as exc:
        raise RuntimeError("DIRECT_CHILD_OBSERVATION_UNAVAILABLE") from exc


def worker_identity(parent_host_pid, actual, runner, child_observer=None):
    child_observer = direct_children if child_observer is None else child_observer
    own_ids = [int(value) for value in next(line for line in Path("/proc/self/status").read_text().splitlines()
                                          if line.startswith("NSpid:")).split()[1:]]
    namespace_index = len(own_ids) - 1
    expected_command = [sys.executable, "-I", str(runner), "--worker", "--output", str(actual)]
    for host_pid in child_observer(parent_host_pid):
        state = proc_state(host_pid)
        if not state or state["parent_host_pid"] != parent_host_pid or state["state"] == "Z":
            continue
        try:
            command = Path("/proc", str(host_pid), "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
            if command != [part.encode() for part in expected_command]:
                continue
            if Path("/proc", str(host_pid), "ns/pid").stat().st_ino != Path("/proc/self/ns/pid").stat().st_ino:
                continue
            ids = [int(value) for value in next(line for line in Path("/proc", str(host_pid), "status").read_text().splitlines()
                                              if line.startswith("NSpid:")).split()[1:]]
            return {"host_pid": host_pid, "namespace_pid": ids[namespace_index], "command": expected_command, **state}
        except FileNotFoundError:
            continue
    return None


def same_worker(identity):
    current = proc_state(identity["host_pid"])
    return current if current and all(current[key] == identity[key] for key in ("parent_host_pid", "start_ticks")) else None


def wait_ready(process, parent_host_pid, actual, runner, timeout=15, child_observer=None):
    """Return an exact, stopped live worker. Never signal a mere STARTED marker."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (actual / "COMPLETE.json").exists() or (actual / "REPORT.json").exists():
            raise RuntimeError("WORKER_ALREADY_COMPLETED")
        if process.poll() is not None:
            raise RuntimeError("PARENT_EXITED_BEFORE_READINESS")
        if (actual / "WORKER.log").exists():
            identity = worker_identity(parent_host_pid, actual, runner, child_observer)
            if identity:
                pidfd = os.pidfd_open(identity["namespace_pid"])
                try:
                    host_pid, _ = fd_identity(pidfd)
                    if host_pid != identity["host_pid"] or not same_worker(identity):
                        raise RuntimeError("WORKER_IDENTITY_CHANGED")
                    signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                    stop_deadline = time.monotonic() + 2
                    while time.monotonic() < stop_deadline:
                        current = same_worker(identity)
                        if current and current["state"] in ("T", "t"):
                            if process.poll() is not None or (actual / "REPORT.json").exists() or (actual / "COMPLETE.json").exists():
                                raise RuntimeError("PARENT_OR_WORKER_COMPLETED_DURING_READINESS")
                            started = json.loads((actual / "STARTED.json").read_text())
                            if started.get("state") != "STARTED":
                                raise RuntimeError("STARTED_RECORD_INVALID")
                            # In this pinned single-threaded parent the sole timed
                            # sleep is Popen's timeout wait loop, after construction.
                            # A live exec'd child alone could still precede the
                            # constructor's error-pipe return and cleanup ownership.
                            wait_phase = Path("/proc", str(parent_host_pid), "wchan").read_text().strip()
                            if wait_phase != "hrtimer_nanosleep":
                                time.sleep(.002)
                                continue
                            return pidfd, {"identity": identity, "stopped_state": current,
                                           "protected_worker_log_exists": True, "parent_live": True,
                                           "report_absent": True, "complete_absent": True,
                                           "parent_protected_wait_wchan": wait_phase}
                        if not current or current["state"] == "Z":
                            raise RuntimeError("WORKER_EXITED_DURING_READINESS")
                        time.sleep(.002)
                    raise RuntimeError("WORKER_STOP_NOT_CONFIRMED")
                except BaseException:
                    try:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.close(pidfd)
                    raise
        time.sleep(.002)
    raise RuntimeError("LIVE_WORKER_READINESS_TIMEOUT")


def terminate_worker(pidfd, identity):
    """Observe parent cleanup first; forced checker cleanup can never pass."""
    polling = select.poll()
    polling.register(pidfd, select.POLLIN)
    events = polling.poll(3000)
    exit_ready = any(bits & select.POLLIN for _, bits in events)
    forced_cleanup = not exit_ready
    if forced_cleanup:
        try:
            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
        except ProcessLookupError:
            pass
        events = polling.poll(3000)
        exit_ready = any(bits & select.POLLIN for _, bits in events)
    reaped = False
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            pid, _ = os.waitpid(identity["namespace_pid"], os.WNOHANG)
            if pid:
                reaped = True
                break
        except ChildProcessError:
            break  # Frozen parent may already have reaped its own worker.
        time.sleep(.002)
    current = proc_state(identity["host_pid"])
    not_live = current is None or current["start_ticks"] != identity["start_ticks"] or current["state"] == "Z"
    if not exit_ready or not not_live:
        raise RuntimeError("IDENTIFIED_WORKER_NOT_QUIESCENT")
    return {"identity_bound_pidfd_exit_ready": exit_ready, "identified_worker_not_live": not_live,
            "identity_bound_pidfd_events": events,
            "identified_worker_reaped_by_checker": reaped, "final_worker_proc_state": current,
            "forced_checker_cleanup": forced_cleanup,
            "parent_sigint_terminated_worker": not forced_cleanup and exit_ready}


def active_interrupt(root, output, *, command=None, child_observer=None, timeout=15):
    runner, actual = root / "reproduce.py", output / "interrupted-run"
    canonical = [sys.executable, "-I", str(runner), "--output", str(actual)]
    command = canonical if command is None else command
    if child_observer is None:
        # Establish platform support before starting a worker we could not observe.
        direct_children(int(Path("/proc/self/stat").read_text().split()[0]))
    libc = ctypes.CDLL(None, use_errno=True)
    prior_subreaper = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(prior_subreaper), 0, 0, 0) or libc.prctl(36, 1, 0, 0, 0):
        raise RuntimeError("CHILD_SUBREAPER_UNAVAILABLE")
    process, parent_fd, worker_fd, handshake = None, None, None, None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENV)
        parent_fd = os.pidfd_open(process.pid)
        parent_host, _ = fd_identity(parent_fd)
        if Path("/proc", str(parent_host), "cmdline").read_bytes().rstrip(b"\0").split(b"\0") != [part.encode() for part in command]:
            raise RuntimeError("OWNED_PARENT_COMMAND_MISMATCH")
        worker_fd, handshake = wait_ready(process, parent_host, actual, runner, timeout, child_observer)
        signal.pidfd_send_signal(parent_fd, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=10)
        termination = terminate_worker(worker_fd, handshake["identity"])
        before = snapshot(actual)  # Only after the identified writer is quiescent.
        restart = subprocess.run(canonical, capture_output=True, text=True, timeout=10, env=ENV)
        after = snapshot(actual)
        interrupted = actual / "INTERRUPTED.json"
        marker = json.loads(interrupted.read_text()) if interrupted.exists() else None
        passed = (process.returncode != 0 and marker is not None and marker.get("state") == "INCOMPLETE"
                  and str(marker.get("reason", "")).startswith("KeyboardInterrupt")
                  and termination["parent_sigint_terminated_worker"]
                  and not (actual / "COMPLETE.json").exists() and restart.returncode != 0 and before == after)
        return {"schema": "lab/frozen-active-worker-interruption054/v1", "passed": passed,
                "handshake": handshake, "parent_sigint_sent": True, "interrupt_returncode": process.returncode,
                "interruption_record_exists": interrupted.exists(), "complete_record_exists": (actual / "COMPLETE.json").exists(),
                "restart_returncode": restart.returncode, "partial_evidence_preserved": before == after,
                "files_sha256": before, "stdout": stdout, "stderr": stderr, "restart_stderr": restart.stderr,
                **termination, "legacy_failure": LEGACY_FAILURE,
                "scope": "Real parent SIGINT after exact direct worker command/output identity, confirmed SIGSTOP, and protected parent timeout-wait observation. That SIGINT must terminate the worker; any forced checker cleanup fails qualification. Exact worker is quiescent before hashing. No host-crash or all-initialization-phase claim. Early STARTED interruption remains PRESERVED_NOT_REPAIRED."}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        if worker_fd is not None:
            try:
                terminate_worker(worker_fd, handshake["identity"])
            finally:
                os.close(worker_fd)
        if parent_fd is not None:
            os.close(parent_fd)
        libc.prctl(36, prior_subreaper.value, 0, 0, 0)


def resource_probe(root, output):
    # Execute the original three attempted overruns with the frozen runner's limits.
    code = """import importlib.util,json,resource,sys
s=importlib.util.spec_from_file_location('trusted_runner',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.limits()
r={'effective_limits':{n:resource.getrlimit(getattr(resource,n)) for n in ['RLIMIT_CPU','RLIMIT_AS','RLIMIT_FSIZE','RLIMIT_NOFILE']}}
try:bytearray(2*1024**3)
except MemoryError:r['memory_limit_enforced']=True
try:
 with open(sys.argv[2],'wb') as f:
  for i in range(20):f.write(b'x'*(1024**2))
except OSError as e:r['file_limit_enforced']=e.errno==27
files=[]
try:
 for i in range(200):files.append(open('/dev/null','rb'))
except OSError as e:r['fd_limit_enforced']=e.errno==24
for f in files:f.close()
print(json.dumps(r))
"""
    data = output / "file-limit.bin"
    child = subprocess.run([sys.executable, "-I", "-c", code, str(root / "reproduce.py"), str(data)], capture_output=True, text=True, timeout=10, env=ENV)
    record = {"returncode": child.returncode, "stdout": child.stdout, "stderr": child.stderr,
              "runner_sha256": sha(root / "reproduce.py"), "file_bytes_at_stop": data.stat().st_size if data.exists() else None}
    if child.returncode == 0:
        record.update(json.loads(child.stdout))
    data.unlink(missing_ok=True)
    write(output / "resources.json", record)
    return record


def probe(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    count = verify_sources(root)
    output.mkdir(parents=True, exist_ok=False)
    resources = resource_probe(root, output)
    try:
        interruption = active_interrupt(root, output)
    except Exception as exc:
        write(output / "interruption.json", {"passed": False, "error": str(exc), "legacy_failure": LEGACY_FAILURE})
        raise
    write(output / "interruption.json", interruption)
    resource_checks = all(resources.get(name) is True for name in ("memory_limit_enforced", "file_limit_enforced", "fd_limit_enforced"))
    report = {"schema": "lab/frozen-worker-bounds054/v1", "passed": resources["returncode"] == 0 and resource_checks and interruption["passed"],
              "frozen_files_verified": count, "source_pins": PINS, "checker_sha256": sha(__file__), "legacy_failure": LEGACY_FAILURE,
              "resource_checks": resource_checks, "active_worker_interruption": interruption["passed"]}
    verify_sources(root)
    write(output / "REPORT.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.root, args.output)
    print(json.dumps(result))
    raise SystemExit(0 if result["passed"] else 1)
