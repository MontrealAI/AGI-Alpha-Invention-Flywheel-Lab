"""P0-246: source-pinned negative trust-boundary witness; NO account or key access.

This script downloads a public source file as inert bytes and never imports or
executes that downloaded file. The only dynamic execution is the authored
SYNTHETIC_NO_KEY demonstration below.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPOSITORY = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
OWNER_COMMIT = "ced6c1cb004887dcdafaea59a2976020be649f8e"
OWNER_BLOB = "9866d004c412fc05c9f6292cf898307f177359df"
OWNER_PATH = "connected_enterprise/upgrades.py"
OWNER_URL = (
    f"https://raw.githubusercontent.com/{REPOSITORY}/{OWNER_COMMIT}/{OWNER_PATH}"
)
MAX_BYTES = 100_000


def pinned_owner_source():
    request = urllib.request.Request(
        OWNER_URL, headers={"User-Agent": "agi-alpha-independent-source-audit/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("BOUNDED_PUBLIC_OWNER_SOURCE_REQUIRED")
    blob = hashlib.sha1(f"blob {len(data)}\\0".encode() + data).hexdigest()
    if blob != OWNER_BLOB:
        raise ValueError("EXACT_OWNER_GIT_BLOB_MISMATCH")
    return data


def inspect_owner_source(data):
    """Source-only semantics. No source code obtained here is executed."""
    tree = ast.parse(data.decode("utf-8"), filename=OWNER_PATH)
    methods = {
        n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    fn = methods.get("authorize_upgrade")
    if fn is None:
        raise ValueError("OWNER_AUTHORIZER_MISSING")
    tree_text = ast.unparse(fn)
    if not all(x in tree_text for x in (
        "target_root / 'connected_enterprise/transition_evidence.py'",
        "'codec_source'",
        ".read_text()",
        "subprocess.run",
        "PYTHONPATH",
        "historical_root",
        "json.dumps(payload)",
    )):
        raise ValueError("TARGET_TO_HISTORICAL_SIGNER_DATAFLOW_CHANGED")
    snippets = [
        n.value for n in ast.walk(fn)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "exec(p['codec_source'],codec)" in n.value
    ]
    if len(snippets) != 1:
        raise ValueError("TARGET_CODEC_EXECUTION_SITE_CHANGED")
    snippet = snippets[0]
    program = ast.parse(snippet)
    exec_calls = [
        n for n in ast.walk(program)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "exec"
    ]
    signer_context = [
        n for n in ast.walk(program)
        if isinstance(n, ast.With) and any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "JournalAccount"
            for item in n.items
            for call in ast.walk(item.context_expr)
        )
    ]
    if len(exec_calls) != 1 or len(signer_context) != 1:
        raise ValueError("SIGNER_CONTEXT_OR_INTERPRETER_SITE_CHANGED")
    interpreter = exec_calls[0]
    context = signer_context[0]
    if not (context.lineno < interpreter.lineno < context.end_lineno):
        raise ValueError("EXECUTION_NOT_IN_SIGNER_CONTEXT")
    expected = "exec(p['codec_source'], codec)"
    if ast.unparse(interpreter) != expected:
        raise ValueError("TARGET_SOURCE_NOT_DIRECTLY_EXECUTED")
    key_refs = [
        n for n in ast.walk(context)
        if isinstance(n, ast.Attribute) and n.attr == "_key"
    ]
    if not key_refs or not any(n.lineno > interpreter.lineno for n in key_refs):
        raise ValueError("KEY_BEARING_SIGNER_SCOPE_NOT_ESTABLISHED")
    return {
        "source_blob_git_sha1": OWNER_BLOB,
        "source_commit": OWNER_COMMIT,
        "source_path": OWNER_PATH,
        "target_supplied_python_interpreted": True,
        "historical_signer_active_at_exec": True,
        "key_bearing_scope_present": True,
        "scope": "SOURCE_STATIC_NEGATIVE_WITNESS_NOT_ACTUAL_KEY_READ_OR_COMPROMISE",
    }


class _SyntheticAccount:
    """Contains no key, token, authority or account state."""
    marker = "SYNTHETIC_NO_KEY"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def synthetic_caller_visibility():
    """Show Python interpreter semantics with a harmless synthetic marker ONLY."""
    payload = (
        "import sys\\n"
        "result=sys._getframe(1).f_locals['a'].marker\\n"
    )

    def historical_like_signer():
        a = _SyntheticAccount()
        with a:
            codec = {}
            exec(payload, codec)  # No remotely supplied code; constant authored above.
            return codec["result"]

    return historical_like_signer()


def report():
    data = pinned_owner_source()
    source = inspect_owner_source(data)
    observed = synthetic_caller_visibility()
    if observed != "SYNTHETIC_NO_KEY":
        raise ValueError("SYNTHETIC_INTERPRETER_MECHANISM_NOT_REPRODUCED")
    return {
        "schema": "agi-alpha/p0-246-negative-signer-boundary/v1",
        "owner_source": source,
        "synthetic_marker_only": observed,
        "actual_secret_read": False,
        "actual_compromise_observed": False,
        "actual_task_custody_known": False,
        "historical_migration_qualified": False,
        "release_go": False,
        "advice": (
            "Do not execute target-tree codec Python within historical key-bearing "
            "JournalAccount. Transform outside the signer under separately verified "
            "source/manifest binding and have historical authority validate and sign "
            "only canonical fixed-schema data. Keep old history, queues, HMAC and writer."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = report()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\\n")
    print(json.dumps({"negative_witness": True, "report": str(args.report)}, sort_keys=True))


if __name__ == "__main__":
    main()
