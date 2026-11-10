#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Probe official local Codex isolation without login, real tokens or model calls."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.codex import CodexService
from bridge.codex_permissions import verify_profile_protocol, verify_runtime_sandbox


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", default=shutil.which("codex"))
    parser.add_argument("--work-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if not args.executable:
        parser.error("Install official Codex or supply --executable.")
    binary = str(Path(args.executable).resolve())
    results = []
    try:
        verify_profile_protocol(binary)
        args.work_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="harness-sandbox-probe-", dir=args.work_root) as temporary:
            root = Path(temporary)
            for writable in (False, True):
                directory = root / ("write" if writable else "read")
                home = root / ("runtime-write" if writable else "runtime-read")
                directory.mkdir(); home.mkdir()
                service = CodexService({"executable": binary})
                result = verify_runtime_sandbox(service._command(directory, writable), directory, home, writable)
                results.append({"workspace_write": writable, **result})
        print(json.dumps({"status": "PASS", "inference_calls": 0, "real_credentials_used": False, "results": results}, indent=2))
        return 0
    except BridgeError as error:
        print(json.dumps({"status": "BLOCKED", "code": error.code, "message": error.message,
                          "inference_calls": 0, "real_credentials_used": False, "results": results}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
