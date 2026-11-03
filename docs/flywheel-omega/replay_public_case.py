#!/usr/bin/env python3
"""Replay one pinned public mechanism; no account or commercial execution.

Supply an extracted source tree at the commit named in sources.json. Every
Python source imported by the replay is checked before import. NumPy and SciPy
are optional dependencies for this historical solver replay; the new exact
companion needs neither. See README.md for an isolated checkout recipe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def replay(source_dir: Path) -> dict:
    source_dir = source_dir.resolve(strict=True)
    manifest = json.loads(Path(__file__).with_name("sources.json").read_text())
    expected = manifest["semantic_replay"]
    commit = expected["source_commit"]
    sources = [s for s in manifest["sources"]
               if s["commit"] == commit and s["path"].endswith(".py")]
    require(len(sources) == 11, "Expected the complete eleven-file import boundary")
    for source in sources:
        data = (source_dir / source["path"]).read_bytes()
        require(hashlib.sha256(data).hexdigest() == source["sha256"],
                "Pinned source differs: " + source["path"])
    require(not any(k.split(".")[0] in {"mechanism_harness", "commercial", "experiments"}
                    for k in sys.modules), "Use a fresh Python process for the replay")
    sys.path.insert(0, str(source_dir))
    import numpy
    import scipy
    from commercial.ledger import digest
    from mechanism_harness.market_cases import market
    from mechanism_harness import mechanism_synthesis as synthesis
    from mechanism_harness import market_program

    instance = market(391103, "competitive")
    result = synthesis.synthesize(instance, mode="full")
    require(result["status"] == "VERIFIED_FINITE_MECHANISM", "Historical solver did not verify")
    program = result["program"]
    certificate = market_program.verify(instance, program)
    require(certificate == result["verification"], "Independent verification differs")
    require(certificate["accepted"] and certificate["deviation_checks"] == 72,
            "The recorded single-report verification did not reproduce")
    require(digest(instance) == expected["market_sha256"], "Market identity differs")
    require(digest(program) == expected["program_sha256"],
            "The recorded program identity differs; inspect solver/version/tie behavior")

    offers = sorted({(r["outcome_id"], r["price_cents"]) for r in program["rules"]})
    nonempty = {o["id"]: frozenset(o["services"]) for o in instance["outcomes"] if o["services"]}
    components = sorted((name, price) for name, price in offers if len(nonempty.get(name, ())) == 1)
    joint = [(name, price) for name, price in offers if len(nonempty.get(name, ())) == 2]
    require(len(components) == 2 and len(joint) == 1, "Unexpected outcome menu")
    joint_name, joint_price = joint[0]
    require(nonempty[components[0][0]] | nonempty[components[1][0]] == nonempty[joint_name],
            "The service-union premise does not hold")
    cart_price = sum(p for _, p in components)
    require(sorted(p for _, p in components) == expected["component_prices_cents"], "Component prices differ")
    require(joint_price == 1554 and cart_price == 1341, "Public arithmetic witness differs")
    types = {t["id"]: t for t in instance["types"]}
    eligible = sorted(r["type_id"] for r in program["rules"]
                      if r["outcome_id"] == joint_name and types[r["type_id"]]["budget_cents"] >= cart_price)
    require(len(eligible) == 4, "Budget-eligible assigned joint-type count differs")
    return {
        "schema_version": 1,
        "scope": "Exact public single-mechanism replay and conditional service-union arithmetic; no native account execution or actual revenue.",
        "source_commit": commit,
        "verified_source_files": len(sources),
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
        "market_sha256": digest(instance),
        "program_sha256": digest(program),
        "single_report_certificate": certificate,
        "offers_cents": [{"outcome": name, "price": p} for name, p in offers],
        "component_cart_cents": cart_price,
        "joint_price_cents": joint_price,
        "same_output_saving_cents": joint_price - cart_price,
        "budget_eligible_assigned_joint_types": eligible,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("Output exists; choose a new path to preserve evidence")
    data = json.dumps(replay(args.source_dir), indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(data)
        print("Verified pinned semantic replay; wrote " + str(args.output))
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
