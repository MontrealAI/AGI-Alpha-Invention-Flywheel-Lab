# SPDX-License-Identifier: Apache-2.0
"""Fresh, IO-free Linux worker for generated numerical Python instruments."""
from __future__ import annotations

import builtins
import collections
import ctypes
import decimal
import fractions
import functools
import heapq
import itertools
import json
import math
import operator
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

MAX_SOURCE = 32_768
MAX_INPUT = 262_144
MAX_RESULT = 65_536
SUPPORT = ("Linux x86_64 or aarch64 with libseccomp.so.2 required. "
           "Linux x86_64 ou aarch64 avec libseccomp.so.2 requis.")
MODULES = {m.__name__: m for m in (collections, decimal, fractions, functools,
                                    heapq, itertools, math, operator)}


class SandboxError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(detail or code)


class Comparison(ctypes.Structure):
    _fields_ = [("argument", ctypes.c_uint), ("operator", ctypes.c_int),
                ("mask", ctypes.c_uint64), ("value", ctypes.c_uint64)]


def rational_affine(matrix, readings, width):
    """Particular solution and a null-space basis of an exact linear system."""
    rows = [[fractions.Fraction(item) for item in list(row) + [reading]]
            for row, reading in zip(matrix, readings, strict=True)]
    pivots = []
    for col in range(width):
        pos = len(pivots)
        pivot = next((index for index in range(pos, len(rows)) if rows[index][col]), None)
        if pivot is None:
            continue
        rows[pos], rows[pivot] = rows[pivot], rows[pos]
        scale = rows[pos][col]
        rows[pos] = [item / scale for item in rows[pos]]
        for other, row in enumerate(rows):
            factor = row[col]
            if other != pos and factor:
                rows[other] = [a - factor * b for a, b in zip(row, rows[pos])]
        pivots.append(col)
    if any(row[-1] for row in rows[len(pivots):]):
        return None
    point = [fractions.Fraction(0)] * width
    for row, column in zip(rows, pivots):
        point[column] = row[-1]
    kernel = []
    for free in sorted(set(range(width)) - set(pivots)):
        direction = [fractions.Fraction(0)] * width
        direction[free] = fractions.Fraction(1)
        for row, column in zip(rows, pivots):
            direction[column] = -row[free]
        kernel.append(direction)
    return point, kernel


def _restrict():
    import resource
    from platform import machine

    if sys.platform != "linux" or machine() not in {"x86_64", "aarch64"}:
        raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (192 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_RESULT,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))

    library = ctypes.CDLL("libseccomp.so.2")
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                              ctypes.c_uint, ctypes.POINTER(Comparison)]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    library.seccomp_release.restype = None
    kill_process, allow = 0x80000000, 0x7FFF0000
    equal, masked_equal = 4, 7
    context = library.seccomp_init(kill_process)
    if not context:
        raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)

    def permit(name, comparisons=()):
        number = library.seccomp_syscall_resolve_name(name.encode())
        array = (Comparison * len(comparisons))(*comparisons)
        if number < 0 or library.seccomp_rule_add_array(context, allow, number, len(array), array):
            raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)

    # No open, socket, exec, process creation, shared memory, ptrace or filesystem
    # syscalls. The only writable descriptor is the size-limited result file.
    for call in ("brk", "munmap", "mremap", "madvise", "futex", "clock_gettime",
                 "rt_sigreturn", "exit", "exit_group"):
        permit(call)
    permit("write", ((0, equal, 1, 0),))
    # Allow anonymous, non-executable, private mappings with no fixed mapping.
    permit("mmap", ((2, masked_equal, 4, 0), (3, equal, 0x22, 0)))
    if library.seccomp_attr_set(context, 3, 1) or library.seccomp_load(context):
        raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)
    library.seccomp_release(context)


def _import_module(name, _globals=None, _locals=None, _fromlist=(), level=0):
    if level or name not in MODULES:
        raise ImportError("Only preloaded numerical standard-library modules are available.")
    return MODULES[name]


def _worker():
    data = json.loads(sys.stdin.buffer.read(MAX_SOURCE + MAX_INPUT * 2))
    # Initialize standard streams and serializers before loading the filter.
    sys.stdout.buffer.write(b"")
    json.dumps(None)
    try:
        _restrict()
    except (SandboxError, OSError, ValueError):
        os._exit(78)
    safe_builtins = dict(vars(builtins), __import__=_import_module)
    namespace = {"__builtins__": safe_builtins, "__name__": "candidate",
                 "rational_affine": rational_affine}
    try:
        exec(compile(data["source"], "<candidate>", "exec", dont_inherit=True), namespace)
        answer = namespace["solve"](data["input"])
        output = {"answer": answer}
        payload = json.dumps(output, allow_nan=False, ensure_ascii=True).encode()
    except Exception as error:
        payload = json.dumps({"exception": type(error).__name__, "message": str(error)[:300]},
                             ensure_ascii=True).encode()
    if len(payload) >= MAX_RESULT:
        os._exit(65)
    while payload:
        payload = payload[os.write(1, payload):]
    os._exit(0)


def execute(source, inputs):
    if not isinstance(source, str) or not 0 < len(source.encode()) <= MAX_SOURCE:
        raise SandboxError("SOURCE_SIZE")
    data = json.dumps({"source": source, "input": inputs}, allow_nan=False,
                      ensure_ascii=False).encode()
    if len(data) > MAX_INPUT:
        raise SandboxError("INPUT_SIZE")
    if sys.platform != "linux":
        raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="forge-tool-") as work, tempfile.TemporaryFile(dir=work) as out:
        try:
            process = subprocess.run(
                [sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--worker"],
                input=data, stdout=out, stderr=subprocess.DEVNULL, close_fds=True,
                cwd=work, env={"LC_ALL": "C.UTF-8"}, timeout=5, check=False,
            )
        except subprocess.TimeoutExpired:
            raise SandboxError("WALL_LIMIT") from None
        except OSError:
            raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT) from None
        if process.returncode == 78:
            raise SandboxError("SANDBOX_UNAVAILABLE", SUPPORT)
        if process.returncode == -signal.SIGSYS:
            raise SandboxError("SYSCALL_REFUSED")
        if process.returncode:
            raise SandboxError("PROCESS_LIMIT_OR_FAILURE", str(process.returncode))
        out.seek(0)
        try:
            output = json.loads(out.read(MAX_RESULT))
        except (ValueError, RecursionError):
            raise SandboxError("INVALID_RESULT") from None
        if isinstance(output, dict) and set(output) == {"exception", "message"}:
            raise SandboxError("CANDIDATE_ERROR", str(output["exception"]) + ": " + str(output["message"]))
        if not isinstance(output, dict) or set(output) != {"answer"}:
            raise SandboxError("INVALID_RESULT")
        return {"answer": output["answer"], "wall_seconds": time.perf_counter() - started}


def main():
    if sys.argv[1:] == ["--worker"]:
        _worker()
    if len(sys.argv) != 3:
        raise SystemExit("python3 forge_sandbox.py CANDIDATE INPUT.json")
    try:
        with Path(sys.argv[1]).open(encoding="utf-8") as source, Path(sys.argv[2]).open("rb") as inputs:
            result = execute(source.read(MAX_SOURCE + 1), json.loads(inputs.read(MAX_INPUT + 1)))
    except (SandboxError, ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
