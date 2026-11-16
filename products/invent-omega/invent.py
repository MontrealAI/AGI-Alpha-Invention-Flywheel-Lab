#!/usr/bin/env python3
"""INVENT Ω: candidate vs the fastest buyer-supplied *correct* incumbent.

The existing UNLOCK Ω verifier checks hidden correctness, reference timing and
larger exact-oracle feasibility. This independent gate disallows weak-baseline
sales claims by requiring a prospective win against competent alternatives.
"""
from __future__ import annotations
import argparse
import json
import math
import shutil
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "unlock-omega"
sys.path.insert(0, str(ENGINE))
import unlock

class FrontierError(ValueError):
    pass

def pairs(items):
    d = {}
    for k, v in items:
        if k in d: raise FrontierError("duplicate frontier field: " + k)
        d[k] = v
    return d

def number(val, name, floor):
    if type(val) not in (int, float, str): raise FrontierError(name + " cannot be bool/unknown")
    try: out = Decimal(str(val))
    except InvalidOperation as exc: raise FrontierError(name + " is not decimal") from exc
    if not out.is_finite() or out < Decimal(str(floor)): raise FrontierError(name + " must be finite and >= " + str(floor))
    return out

def configuration(project):
    path = Path(project) / "frontier.json"
    if not path.is_file() or path.is_symlink(): raise FrontierError("buyer frontier.json is required, no symlinks")
    data = path.read_bytes()
    if len(data) > 100000: raise FrontierError("frontier configuration too large")
    c = json.loads(data, object_pairs_hook=pairs,
                   parse_constant=lambda _: (_ for _ in ()).throw(FrontierError("nonfinite JSON")))
    if not isinstance(c, dict) or set(c) - {"min_best_speedup", "max_worst_regression", "economics"} or not {"min_best_speedup", "max_worst_regression"} <= set(c):
        raise FrontierError("invalid frontier contract")
    win = float(number(c["min_best_speedup"], "min_best_speedup", "1.01"))
    regress = float(number(c["max_worst_regression"], "max_worst_regression", "1"))
    if not 1.01 <= win <= 100000 or not 1 <= regress <= 2: raise FrontierError("frontier thresholds out of bounds")
    econ = c.get("economics")
    if econ is not None:
        required = {"annual_invocations", "compute_cost_per_hour", "year_one_integration_cost", "annual_maintenance_cost"}
        if not isinstance(econ, dict) or set(econ) != required: raise FrontierError("economic scenario requires four fields")
        econ = {k: number(v, k, 0) for k, v in econ.items()}
        if econ["annual_invocations"] > Decimal("1e15") or econ["compute_cost_per_hour"] > Decimal("1e9"):
            raise FrontierError("unrealistic economic input bound")
    return path, win, regress, econ

def incumbent_sources(project):
    folder = Path(project) / "incumbents"
    if not folder.is_dir() or folder.is_symlink(): raise FrontierError("buyer must supply incumbents/*.py")
    files = sorted(folder.glob("*.py"))
    if not 1 <= len(files) <= 8 or any(f.is_symlink() or not f.is_file() for f in files):
        raise FrontierError("1–8 actual non-symlink competitor programs required")
    return files

def by_id(rows, cases, label):
    ids = [row.get("id") for row in rows]
    expected = [c["id"] for c in cases]
    if len(ids) != len(expected) or len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise FrontierError(label + ": incomplete/misaligned benchmark")
    for row in rows:
        v = row.get("median_ns")
        if type(v) not in (int, float) or not math.isfinite(v) or v <= 0 or type(row.get("response")) is not str:
            raise FrontierError(label + ": invalid benchmark evidence")
    return {row["id"]: row for row in rows}

def economics(econ, rows):
    if econ is None: return {"status": "NO_BUYER_ECONOMIC_INPUT"}
    # Equal-weight synthetic measurement is NOT a production workload distribution.
    saved = sum(Decimal(str(r["best_incumbent_ms"])) - Decimal(str(r["candidate_ms"])) for r in rows) / Decimal(len(rows))
    gross = saved / Decimal(1000) / Decimal(3600) * econ["annual_invocations"] * econ["compute_cost_per_hour"]
    net = gross - econ["year_one_integration_cost"] - econ["annual_maintenance_cost"]
    return {"status": "HYPOTHETICAL_EQUAL_WEIGHT_NOT_REVENUE",
            "annual_compute_savings": str(gross.quantize(Decimal("0.01"))),
            "buyer_year_one_net_scenario": str(net.quantize(Decimal("0.01"))),
            "currency": "CUSTOMER_SUPPLIED_NOT_VERIFIED"}

def evaluate(project, candidate, mode="docker"):
    project = Path(project).expanduser().resolve()
    candidate = Path(candidate).expanduser().resolve()
    root, cases, _ = unlock.read_project(project)
    if not candidate.is_file() or candidate.suffix != ".py": raise FrontierError("existing candidate .py required")
    config, win, regress, econ = configuration(root)
    others = incumbent_sources(root)
    out = {"product": "INVENT Ω / buyer best-incumbent admission",
           "status": "HOLD", "qualification": "LOCAL_TEST_NOT_EXTERNAL_CUSTOMER_SIGNOFF",
           "mode": mode, "candidate_sha256": unlock.digest(candidate),
           "reference_sha256": unlock.digest(root / "reference.py"),
           "heldout_sha256": unlock.digest(root / "heldout.json"),
           "acceptance_sha256": unlock.digest(root / "acceptance.json"),
           "frontier_sha256": unlock.digest(config),
           "incumbents": [{"name": p.name, "sha256": unlock.digest(p)} for p in others],
           "thresholds": {"min_best_speedup": win, "max_worst_regression": regress}}
    base = unlock.verify(root, candidate, mode)
    out["reference_and_frontier_gate"] = base
    if base["status"] != "PASS":
        out["reason"] = "original reference correctness, performance or independently-oracled frontier gate failed"
        return out
    ordinary = [c for c in cases if c["kind"] != "frontier"]
    reference = by_id(unlock.execute(root / "reference.py", ordinary, mode, "reference"), ordinary, "reference")
    proposed = by_id(unlock.execute(candidate, ordinary, mode, "candidate"), ordinary, "candidate")
    controls = [("reference", reference)]
    for file in others:
        rows = by_id(unlock.execute(file, ordinary, mode, "incumbent"), ordinary, file.name)
        for case in ordinary:
            k = case["id"]
            if rows[k]["response"] != reference[k]["response"]:
                out["reason"] = "INCUMBENT_ORACLE_MISMATCH / " + file.name + " / " + k
                return out
        controls.append((file.name, rows))
    for case in ordinary:
        k = case["id"]
        if proposed[k]["response"] != reference[k]["response"]:
            out["reason"] = "CANDIDATE_ORACLE_MISMATCH / " + k
            return out
    results, ratios = [], []
    for case in ordinary:
        if case["kind"] != "performance": continue
        k = case["id"]
        incumbent, fast_ns = min(((name, rows[k]["median_ns"]) for name, rows in controls), key=lambda t: t[1])
        candidate_ns = proposed[k]["median_ns"]
        ratios.append(fast_ns / candidate_ns)
        results.append({"id": k, "fastest_incumbent": incumbent,
                        "best_incumbent_ms": round(fast_ns / 1e6, 6),
                        "candidate_ms": round(candidate_ns / 1e6, 6),
                        "speedup": round(fast_ns / candidate_ns, 6)})
    if len(ratios) < 2: raise FrontierError("two performance cases required")
    geometric = math.exp(sum(math.log(v) for v in ratios) / len(ratios))
    worst = min(ratios)
    out["performance"] = {"cases": results, "geomean_vs_fastest": round(geometric, 6),
                          "worst_case_vs_fastest": round(worst, 6)}
    out["economics"] = economics(econ, results)
    if geometric >= win and worst >= 1 / regress:
        out["status"] = "PASS_LAB"
        out["reason"] = "all local gates passed; frontier, commercial sale and net profit not independently established"
    else:
        out["reason"] = "NO_QUALIFIED_ADVANTAGE_OVER_FASTEST_INCUMBENT"
    return out

def main(argv=None):
    app = argparse.ArgumentParser(description="INVENT Ω — candidate algorithm vs buyer's best alternative")
    s = app.add_subparsers(dest="action", required=True)
    p = s.add_parser("verify"); p.add_argument("project"); p.add_argument("candidate")
    p = s.add_parser("invent"); p.add_argument("project")
    p = s.add_parser("demo")
    for cmd in (app._subparsers._group_actions[0].choices.values()):
        cmd.add_argument("--unsafe-local", action="store_true", help="trusted sample code ONLY")
    args = app.parse_args(argv)
    mode = "local" if args.unsafe_local else "docker"
    try:
        if args.action == "demo":
            from make_demo import make_demo
            with tempfile.TemporaryDirectory() as temp:
                project = make_demo(Path(temp))
                folder = project / "incumbents"; folder.mkdir()
                (folder / "reference_incumbent.py").write_text((project / "reference.py").read_text())
                (project / "frontier.json").write_text(json.dumps({"min_best_speedup": 1.05, "max_worst_regression": 1.1}))
                weak = evaluate(project, project / "candidate.py", mode)
                shutil.copy2(project / "candidate.py", folder / "reference_incumbent.py")
                strong = evaluate(project, project / "candidate.py", mode)
                good = weak["status"] == "PASS_LAB" and strong["status"] == "HOLD"
                result = {"status": "DEMO_PASS" if good else "HOLD",
                          "weak_reference_incumbent": weak["status"], "strong_correct_incumbent": strong["status"],
                          "disclosure": "constructed classic two-pointer algorithm, no original breakthrough"}
        elif args.action == "invent":
            proposal = unlock.invent(args.project, mode)
            if proposal["status"] == "PASS":
                final = evaluate(args.project, proposal["candidate"], mode)
                result = {"status": final["status"], "proposal": proposal, "strong_incumbent": final}
            else: result = {"status": "HOLD", "proposal": proposal}
        else:
            result = evaluate(args.project, args.candidate, mode)
    except (OSError, ValueError, RuntimeError, TypeError, OverflowError, ZeroDivisionError) as exc:
        result = {"status": "HOLD", "reason": str(exc)[:500]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in ("PASS_LAB", "DEMO_PASS") else 2

if __name__ == "__main__":
    sys.exit(main())
