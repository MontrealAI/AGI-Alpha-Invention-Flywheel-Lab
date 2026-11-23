"""Exact identities and durable, private checkpoints for the registered experiment."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import resource

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REGISTRATION = HERE / "registration.json"
SANDBOX = ROOT / "flywheel" / "sandbox.py"
LEGACY = HERE.parent / "possibility_observatory" / "endpoint_study" / "decision.py"
CONSTRUCTOR = HERE / "constructor.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def decode(data):
    def object_pairs(pairs):
        result = dict(pairs)
        require(len(result) == len(pairs), "DUPLICATE_JSON_KEY")
        return result

    def bad_constant(_):
        raise ValueError("NONFINITE_JSON")

    return json.loads(data, object_pairs_hook=object_pairs, parse_constant=bad_constant)


def read(path):
    return decode(path.read_bytes())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def atomic(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pending-", delete=False) as out:
        temp = Path(out.name)
        try:
            out.write(encode(value))
            out.flush()
            os.fsync(out.fileno())
            os.replace(temp, path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            temp.unlink(missing_ok=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clock():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def child_cpu_ns():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return round((usage.ru_utime + usage.ru_stime) * 1_000_000_000)


@contextmanager
def measure(into, name):
    wall, cpu, children = time.perf_counter_ns(), time.process_time_ns(), child_cpu_ns()
    try:
        yield
    finally:
        into[name] = {"wall_ns": time.perf_counter_ns() - wall,
                      "process_cpu_ns": time.process_time_ns() - cpu,
                      "child_cpu_ns": child_cpu_ns() - children}


def checked(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout
