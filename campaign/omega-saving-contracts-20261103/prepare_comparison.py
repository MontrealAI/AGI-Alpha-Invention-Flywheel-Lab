#!/usr/bin/env python3
"""Freeze the registered 76 independent accounts before opening any account.

The default is explicitly a reproduction, not another independent confirmation.
This orchestration file is outside the monetary implementation's source closure;
its own hash is recorded alongside that closure. It performs no paid/external work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--role", choices=("confirmation", "reproduction"), default="reproduction")
    args = p.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError("FRESH_COMPARISON_DIRECTORY_REQUIRED")
    sys.path.insert(0, str(root))
    from omega_savings.runner import freeze, registration, save
    from omega_savings.experiment import protocol

    output.mkdir(parents=True)
    rows = []
    for variant, changes in (
        ("primary", {}),
        ("cadence7", {"cadence_days": 7}),
        ("cadence30", {"cadence_days": 30}),
        ("cost50", {"cost_surcharge": 50_000_000}),
        ("cost200", {"cost_surcharge": 200_000_000}),
    ):
        axes = {} if variant == "primary" else {"worlds": ["positive", "adverse"], "policies": ["adaptive"]}
        reg = registration(role=args.role, variant=variant, **axes, **changes)
        record = freeze(root, output / variant, reg)
        rows.append({"variant": variant, "directory": variant, "cases": len(reg["cases"]),
                     "source_sha256": record["sha256"], "registration_sha256": record["registration_sha256"]})
    technical = protocol((701, 702, 703), role=args.role)
    save(output / "TECHNICAL.json", technical)
    matrix = {"schema": "omega-savings/comparison-matrix/v1", "role": args.role,
              "variants": rows, "registered_financial_accounts": sum(row["cases"] for row in rows),
              "technical_protocol_sha256": hashlib.sha256((output / "TECHNICAL.json").read_bytes()).hexdigest(),
              "orchestrator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "no_accounts_opened_by_registration": True,
              "accounts_independent_never_pooled": True}
    save(output / "MATRIX.json", matrix)
    print(json.dumps(matrix, sort_keys=True))


if __name__ == "__main__":
    main()
