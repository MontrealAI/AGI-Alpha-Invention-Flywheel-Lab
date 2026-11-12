"""Bounded Linux seccomp worker for JSON strategy interpreters.

Only reviewed, hash-pinned interpreter source is accepted. Its initialization and
the strategy both execute after confinement. The JSON program is data, not Python.
No fallback runs without the filter. Qualification is host-specific, not external
security certification; the Linux kernel and libseccomp remain trusted.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import socket
import subprocess
import sys
import time

DEFAULT_LIMITS = {"wall_seconds": 5, "cpu_seconds": 2, "memory_bytes": 256 * 1024**2,
                  "output_bytes": 1024 * 1024, "input_bytes": 4 * 1024**2}


def _filter():
    try:
        lib = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise RuntimeError("SANDBOX_UNAVAILABLE: libseccomp.so.2") from exc
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    lib.seccomp_rule_add.restype = ctypes.c_int
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_load.restype = ctypes.c_int
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = lib.seccomp_init(0x00050000 | errno.EPERM)
    if not ctx:
        raise RuntimeError("SANDBOX_UNAVAILABLE: seccomp_init")
    allow = 0x7FFF0000
    calls = ("brk mmap mmap2 munmap mremap mprotect madvise futex futex_time64 "
             "clock_gettime clock_gettime64 gettimeofday rt_sigaction rt_sigprocmask "
             "rt_sigreturn sigaltstack exit exit_group close getpid gettid getrandom "
             "sched_yield getrusage restart_syscall")
    for call in calls.split():
        number = lib.seccomp_syscall_resolve_name(call.encode())
        if number >= 0 and lib.seccomp_rule_add(ctx, allow, number, 0) != 0:
            raise RuntimeError("SANDBOX_UNAVAILABLE: rule " + call)
    class Compare(ctypes.Structure):
        _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                    ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                         ctypes.c_uint, ctypes.POINTER(Compare)]
    lib.seccomp_rule_add_array.restype = ctypes.c_int
    for fd in (1, 2):
        comparison = Compare(0, 4, fd, 0)
        if lib.seccomp_rule_add_array(ctx, allow, lib.seccomp_syscall_resolve_name(b"write"),
                                     1, ctypes.byref(comparison)) != 0:
            raise RuntimeError("SANDBOX_UNAVAILABLE: stdout rule")
    if lib.seccomp_load(ctx) != 0:
        raise RuntimeError("SANDBOX_UNAVAILABLE: seccomp_load")
    lib.seccomp_release(ctx)


def _limits(values):
    limits = DEFAULT_LIMITS | (values or {})
    if set(limits) != set(DEFAULT_LIMITS):
        raise ValueError("Unknown sandbox limit")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0 for v in limits.values()):
        raise ValueError("Limits must be positive")
    if any(not isinstance(limits[k], int) for k in ("cpu_seconds", "memory_bytes", "output_bytes", "input_bytes")):
        raise ValueError("CPU seconds and byte limits must be integers")
    if limits["wall_seconds"] > 60 or limits["cpu_seconds"] > 30 or limits["memory_bytes"] > 1024**3:
        raise ValueError("Sandbox hard allocation exceeded")
    if limits["output_bytes"] > 10 * 1024**2 or limits["input_bytes"] > 10 * 1024**2:
        raise ValueError("Sandbox byte allocation exceeded")
    return limits


def _child(request):
    limits = _limits(request.get("limits"))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise RuntimeError("SANDBOX_UNAVAILABLE: parent-death signal")
    if os.getppid() != request["supervisor_pid"]:
        raise RuntimeError("SUPERVISOR_DISAPPEARED")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (int(limits["cpu_seconds"]), int(limits["cpu_seconds"]) + 1))
    resource.setrlimit(resource.RLIMIT_AS, (int(limits["memory_bytes"]), int(limits["memory_bytes"])))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_FSIZE, (int(limits["output_bytes"]), int(limits["output_bytes"])))
    source = request.get("source")
    code = None
    if source is not None:
        if hashlib.sha256(source.encode()).hexdigest() != request["source_sha256"]:
            raise ValueError("SOURCE_IDENTITY_MISMATCH")
        code = compile(source, "<pinned-strategy-interpreter>", "exec")
    # All potentially inherited descriptors except bounded output are closed.
    os.close(0)
    os.closerange(3, 65536)
    os.environ.clear()
    _filter()
    started = time.monotonic()
    if code is not None:
        namespace = {"__name__": "_confined_interpreter", "__file__": "<pinned-strategy-interpreter>"}
        exec(code, namespace)
        result = namespace[request["function"]](request["payload"])
    else:
        result = _probe(request["probe"], request.get("path"))
    return {"state": "COMPLETE", "result": result, "confinement": "linux-seccomp-default-deny",
            "worker_wall_seconds": time.monotonic() - started,
            "worker_cpu_seconds": time.process_time(),
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def _probe(kind, path):
    operations = {
        "read": lambda: open(path, "rb").read(),
        "write": lambda: open(path, "wb").write(b"forbidden"),
        "network": lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
        "exec": lambda: os.execve("/usr/bin/true", ["true"], {}),
        "fork": os.fork,
    }
    if kind in operations:
        try:
            operations[kind]()
        except OSError as exc:
            return {"denied": exc.errno == errno.EPERM, "errno": exc.errno}
        return {"denied": False}
    if kind == "environment":
        return {"empty": not os.environ}
    if kind == "memory":
        try:
            bytearray(2 * 1024**3)
        except MemoryError:
            return {"bounded": True}
        return {"bounded": False}
    if kind == "output":
        while True:
            os.write(1, b"x" * 65536)
    if kind in ("cpu", "wall"):
        while True:
            pass
    raise ValueError("Unknown qualification probe")


def _invoke(request, limits):
    limits = _limits(limits)
    request["limits"] = limits
    request["supervisor_pid"] = os.getpid()
    encoded = json.dumps(request, allow_nan=False).encode()
    if len(encoded) > limits["input_bytes"]:
        raise ValueError("INPUT_LIMIT")
    started = time.monotonic()
    proc = subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--worker"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            close_fds=True, env={"LANG": "C.UTF-8", "PYTHONHASHSEED": "0"},
                            start_new_session=True)
    assert proc.stdin and proc.stdout and proc.stderr
    proc.stdin.write(encoded)
    proc.stdin.close()
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    selector.register(proc.stderr, selectors.EVENT_READ)
    output, errors = bytearray(), bytearray()
    state = None
    try:
        while selector.get_map():
            remaining = limits["wall_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                state = "WALL_LIMIT"
                break
            for key, _ in selector.select(min(remaining, 0.05)):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                if len(output) + len(errors) + len(block) > limits["output_bytes"]:
                    state = "OUTPUT_LIMIT"
                    break
                (output if key.fileobj is proc.stdout else errors).extend(block)
            if state:
                break
        if state:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=2)
    finally:
        selector.close()
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=2)
        proc.stdout.close()
        proc.stderr.close()
    receipt = {"state": state or ("COMPLETE" if proc.returncode == 0 else "FAILED"),
               "returncode": proc.returncode, "limits": limits,
               "wall_seconds": time.monotonic() - started,
               "stdout_bytes": len(output), "stderr_bytes": len(errors),
               "stdout_sha256": hashlib.sha256(output).hexdigest(),
               "stderr": errors.decode(errors="replace")}
    if not state and proc.returncode == 0:
        try:
            receipt["worker"] = json.loads(output)
        except ValueError:
            receipt["state"] = "INVALID_OUTPUT"
    return receipt


def run(interpreter_path, function, payload, expected_sha256, limits=None):
    """Execute exact interpreter bytes plus JSON data; initialization is confined."""
    path = Path(interpreter_path)
    if path.is_symlink():
        raise ValueError("SOURCE_SYMLINK")
    source = path.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    if actual != expected_sha256:
        raise ValueError("SOURCE_IDENTITY_MISMATCH")
    receipt = _invoke({"source": source.decode(), "source_sha256": actual,
                       "function": function, "payload": payload}, limits)
    receipt["interpreter_sha256"] = actual
    receipt["input_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return receipt


def qualify():
    """Run real effect and resource probes on this host; refuse positive gaps."""
    marker = Path(__file__).resolve()
    receipts = {}
    for kind in ("read", "write", "network", "exec", "fork", "environment", "memory", "output", "cpu", "wall"):
        limits = {"wall_seconds": 0.2 if kind == "wall" else (20 if kind == "cpu" else 4),
                  "cpu_seconds": 1 if kind == "cpu" else 2,
                  "output_bytes": 4096 if kind == "output" else 1024**2}
        # Write targets a never-created sibling, not the source marker.
        path = str(marker) + ".forbidden-probe" if kind == "write" else str(marker)
        receipt = _invoke({"probe": kind, "path": path}, limits)
        result = receipt.get("worker", {}).get("result", {})
        if kind in ("read", "write", "network", "exec", "fork"):
            passed = receipt["state"] == "COMPLETE" and result.get("denied") is True
        elif kind == "environment":
            passed = receipt["state"] == "COMPLETE" and result.get("empty") is True
        elif kind == "memory":
            passed = receipt["state"] == "COMPLETE" and result.get("bounded") is True
        elif kind == "output":
            passed = receipt["state"] == "OUTPUT_LIMIT"
        elif kind == "cpu":
            passed = receipt["returncode"] in (-signal.SIGXCPU, -signal.SIGKILL) and receipt["state"] == "FAILED"
        else:
            passed = receipt["state"] == "WALL_LIMIT"
        receipts[kind] = {"passed": passed, "receipt": receipt}
    return {"schema": "agi-alpha-sandbox-qualification/v1",
            "qualified": all(x["passed"] for x in receipts.values()), "probes": receipts,
            "boundary": "This host, this Python and Linux seccomp; no external certification. No host files, network, processes or privilege effects after filtering.",
            "trusted": ["Linux kernel", "libseccomp", "Python runtime", "sandbox supervisor"],
            "sandbox_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--qualify", action="store_true")
    arguments = parser.parse_args()
    if arguments.worker:
        try:
            request = json.loads(sys.stdin.buffer.read(10 * 1024**2 + 1))
            result = _child(request)
            print(json.dumps(result, allow_nan=False), flush=True)
        except BaseException as exc:
            print(type(exc).__name__ + ": " + str(exc), file=sys.stderr, flush=True)
            raise SystemExit(1)
    elif arguments.qualify:
        print(json.dumps(qualify(), indent=2))
