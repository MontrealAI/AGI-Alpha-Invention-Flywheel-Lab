"""Execution-only import trace for an unchanged public scientific entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
parser.add_argument("--entry", required=True)
parser.add_argument("--trace", required=True)
args, forwarded = parser.parse_known_args()
root = Path(args.source_root).resolve()
entry = (root / args.entry).resolve()
trace = Path(args.trace)
if trace.exists() or not entry.is_relative_to(root):
    raise ValueError("new trace and source-contained entry required")
imports = []


def observe(event, values):
    if event == "import":
        name = str(values[0])
        imports.append(name)
        # None of these financial/operating modules belongs to this replay.
        forbidden = {"economics", "native", "dispatch_case", "recovery_run",
                     "recovery_fast", "finalize_run", "qualification_run"}
        if forbidden.intersection(name.split(".")):
            raise RuntimeError("financial/operating import forbidden: " + name)
    if event in {"socket.connect", "socket.bind", "subprocess.Popen", "os.system"}:
        raise RuntimeError("network or subprocess operation forbidden during scientific replay")


sys.addaudithook(observe)
sys.path.insert(0, str(entry.parent))
sys.path.insert(0, str(root))
sys.argv = [str(entry)] + forwarded
exit_code = 0
exception = None
try:
    runpy.run_path(str(entry), run_name="__main__")
except SystemExit as exc:
    exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
except BaseException as exc:
    exception = type(exc).__name__ + ": " + str(exc)
    exit_code = 2
finally:
    repository_modules = {}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(root) and path.is_file():
                repository_modules[name] = {
                    "path": str(path.relative_to(root)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
    trace.write_text(json.dumps({
        "schema": "scientific-replay-import-trace/v1",
        "entry": str(entry.relative_to(root)),
        "entry_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
        "wrapper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "exit_code": exit_code,
        "exception": exception,
        "imports": sorted(set(imports)),
        "repository_modules": repository_modules,
    }, indent=2, allow_nan=False) + "\n")
if exception:
    print(exception, file=sys.stderr)
raise SystemExit(exit_code)
