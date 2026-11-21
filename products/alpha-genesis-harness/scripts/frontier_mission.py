#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Operate source-led FRONTIER missions with the existing local HARNESS runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import Runtime, strict_json
from bridge.frontier_mission import FrontierMissionService
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService, _atomic, encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "extract", "register", "get", "observe", "discover", "contract", "build", "compare", "export"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--config", type=Path, help="Existing private local-model configuration; never credentials")
    parser.add_argument("--input", type=Path, help="JSON action data or mission registration")
    parser.add_argument("--id", help="Mission ID (overrides input ID)")
    parser.add_argument("--stage", choices=("first", "second"))
    parser.add_argument("--arm", choices=("first", "with_asset", "without_asset"))
    parser.add_argument("--output", type=Path, help="Write result JSON atomically")
    args = parser.parse_args()
    config = strict_json(args.config.read_bytes()) if args.config else {"local_only": True, "allow_paid_requests": False}
    data = strict_json(args.input.read_bytes()) if args.input else {}
    for key in ("id", "stage", "arm"):
        if getattr(args, key) is not None:
            data[key] = getattr(args, key)
    runtime = AccessRuntime(Runtime(config), config, private_root=args.workspace)
    workflows = WorkflowService(runtime, args.workspace)
    try:
        service = FrontierMissionService(workflows)
        result = service.status() if args.action == "status" else getattr(service, args.action)(data)
        if args.output:
            _atomic(args.output, encoded(result) + b"\n")
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    finally:
        workflows.close()
        runtime.close()


if __name__ == "__main__":
    main()
