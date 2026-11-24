"""P0-269: key-free development, not native qualification.
Frozen comparison: fresh verified disk replay, sealed replay, sealed DAG replay.
One fixed diamond graph, then one changed graph and one cycle; no resampling.
Acceptance: all nine named checks, exact output 14, launch counts 5/5/4,
changed graph output 16, changed-context digest rejection, write/truncate
rejection, negative control distinguishes pre/post hashing from byte binding.
No native account, keys, authority or financial receipts. Stop after one run.
Linux memfd sealing binds one synthetic verifier, not its interpreter, imports,
data, OS, or native audit closure. No timing/safety extrapolation.
"""
import errno
import fcntl
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SOURCE = b"def verify(value, children):\n    return value + sum(children)\n"
ALTERED = SOURCE.replace(b"value + sum", b"value - sum")
GRAPH = {"root": (1, ("left", "right")), "left": (2, ("leaf",)),
         "right": (3, ("leaf",)), "leaf": (4, ())}
CHILD = """import hashlib,json,os,sys
p=json.load(sys.stdin)
raw=open(p['path'],'rb').read()
if p['expected'] is not None and hashlib.sha256(raw).hexdigest()!=p['expected']:
    sys.exit(19)
scope={}
exec(compile(raw,'<synthetic-verifier>','exec'),scope)
print(json.dumps(scope['verify'](p['value'],p['children'])))
"""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def child(path, value, children, expected, fd=None):
    p = dict(path=str(path), value=value, children=children, expected=expected)
    result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", CHILD],
                            input=json.dumps(p), text=True, capture_output=True,
                            pass_fds=() if fd is None else (fd,))
    if result.returncode:
        raise ValueError("CHILD_EXIT_" + str(result.returncode))
    return json.loads(result.stdout)


def replay(graph, path, fd=None, reuse=False):
    # All inputs are copied into immutable primitive tuples before execution.
    fixed = {k: (v, tuple(edges)) for k, (v, edges) in graph.items()}
    active, checked = set(), set()
    def preflight(node):
        if node in active:
            raise ValueError("CYCLE")
        if node in checked:
            return
        active.add(node)
        for dep in fixed[node][1]:
            preflight(dep)
        active.remove(node)
        checked.add(node)
    preflight("root")
    memo, launches = {}, 0
    def visit(node):
        nonlocal launches
        if reuse and node in memo:
            return memo[node]
        value, deps = fixed[node]
        result = child(path, value, [visit(d) for d in deps], sha(SOURCE), fd)
        launches += 1
        if reuse:
            memo[node] = result
        return result
    return visit("root"), launches


def rejected(call, expected):
    try:
        call()
    except ValueError as e:
        return str(e) == expected
    return False


def sealed_denial(call):
    try:
        call()
    except OSError as e:
        return e.errno == errno.EPERM
    return False


def main():
    start = time.monotonic()
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    checks = {}
    with tempfile.TemporaryDirectory() as temp:
        disk = Path(temp) / "verifier.py"
        disk.write_bytes(SOURCE)
        fd = os.memfd_create("p0269-synthetic", os.MFD_ALLOW_SEALING)
        try:
            os.write(fd, SOURCE)
            seals = (fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW |
                     fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
            path = "/proc/self/fd/" + str(fd)
            arms = dict(disk=replay(GRAPH, disk),
                        sealed=replay(GRAPH, path, fd),
                        dag=replay(GRAPH, path, fd, True))
            checks["fresh_disk"] = arms["disk"] == (14, 5)
            checks["sealed_full"] = arms["sealed"] == (14, 5)
            checks["sealed_dag"] = arms["dag"] == (14, 4)
            before = sha(disk.read_bytes())
            disk.write_bytes(ALTERED)
            try:
                negative = child(disk, 1, [2], None)
                checks["child_digest_rejects"] = rejected(
                    lambda: child(disk, 1, [2], sha(SOURCE)), "CHILD_EXIT_19")
                checks["sealed_during_disk_mutation"] = child(
                    path, 1, [2], sha(SOURCE), fd) == 3
            finally:
                disk.write_bytes(SOURCE)
            checks["prepost_only_negative_control"] = (
                before == sha(disk.read_bytes()) and negative == -1)
            checks["sealed_write_and_truncate"] = (
                sealed_denial(lambda: os.pwrite(fd, ALTERED, 0)) and
                sealed_denial(lambda: os.ftruncate(fd, 0)))
            changed = dict(GRAPH, leaf=(5, ()))
            checks["fresh_context"] = (
                replay(changed, path, fd, True) == (16, 4) and rejected(
                    lambda: child(path, 1, [], sha(ALTERED), fd), "CHILD_EXIT_19"))
            cyclic = dict(GRAPH, leaf=(4, ("root",)))
            checks["cycle_rejected"] = rejected(
                lambda: replay(cyclic, path, fd, True), "CYCLE")
        finally:
            os.close(fd)
    end = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = dict(scope="SYNTHETIC_DEVELOPMENT_ONLY", checks=checks, arms=arms,
                  accepted=len(checks)==9 and all(checks.values()),
                  source_sha256=sha(Path(__file__).read_bytes()),
                  waited_child_cpu_seconds=end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                  wall_seconds=time.monotonic()-start, actual_billing_usd=None,
                  native_qualification=False, actual_commerce=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
