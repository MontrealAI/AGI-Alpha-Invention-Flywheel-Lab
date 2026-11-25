#!/usr/bin/env python3
"""Compare retained and conventional claim checks with original and control inputs."""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import resource
import shutil
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter


HERE = Path(__file__).resolve().parent
ARMS = {"retained": "claim_check.py", "ordinary": "ordinary_control.py"}


def compare(source, plan, order):
    rows = []
    for arm in order:
        initial_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = perf_counter()
        result = subprocess.run([sys.executable, str(HERE / ARMS[arm]), str(plan), str(source)],
                                check=False, capture_output=True, cwd=HERE)
        wall = perf_counter() - start
        final_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        if result.returncode not in (0, 1) or result.stderr:
            raise RuntimeError(f"{arm} did not deliver a bounded decision: {result.stderr.decode()}")
        report = json.loads(result.stdout)
        rows.append({
            "arm": arm, "wall_seconds": round(wall, 6),
            "process_cpu_seconds": round(final_cpu.ru_utime - initial_cpu.ru_utime +
                                         final_cpu.ru_stime - initial_cpu.ru_stime, 6),
            "report_sha256": sha256(result.stdout).hexdigest(), "report": report,
        })
    return rows


def use(directory, label):
    plan = HERE / f"{label}-PLAN.json"
    capture = json.loads((directory / "capture.json").read_bytes())
    samples = []
    accepted = {}
    for cycle in range(5):
        order = list(ARMS) if cycle % 2 == 0 else list(reversed(ARMS))
        for row in compare(directory, plan, order):
            report = row.pop("report")
            arm = row["arm"]
            if arm in accepted and report != accepted[arm]:
                raise RuntimeError("identical input generated different evidence")
            accepted[arm] = report
            samples.append(row)
    decisions = {arm: {f"{item['id']}:{item['language']}": item["decision"] for item in result["claims"]}
                 for arm, result in accepted.items()}
    if decisions["retained"] != decisions["ordinary"] or len(set(decisions["retained"].values())) != 1:
        raise RuntimeError(f"unsupported live result for {label}")
    if accepted["retained"]["decision"] != "PASS" or accepted["ordinary"]["decision"] != "PASS":
        raise RuntimeError(f"declared live claims failed {label}")
    per_arm = defaultdict(list)
    for row in samples:
        per_arm[row["arm"]].append(row)
    common = capture["elapsed_seconds"]
    timing = {}
    for arm, rows in per_arm.items():
        local_wall = median(row["wall_seconds"] for row in rows)
        timing[arm] = {
            "median_local_wall_seconds": local_wall,
            "median_local_cpu_seconds": median(row["process_cpu_seconds"] for row in rows),
            "common_capture_plus_local_wall_seconds": round(common + local_wall, 6),
            "capture_response_bytes": capture["response_bytes"],
        }
    return {"capture": capture, "plan_sha256": sha256(plan.read_bytes()).hexdigest(),
            "arm_source_sha256": {name: sha256((HERE / filename).read_bytes()).hexdigest()
                                   for name, filename in ARMS.items()},
            "timing": timing, "samples": samples, "outputs": accepted}


def change_text(path, original, replacement):
    raw = path.read_text(encoding="utf-8")
    if raw.count(original) != 1:
        raise ValueError("control failed to select a unique original")
    path.write_text(raw.replace(original, replacement), encoding="utf-8")


def duplicate_fragment(directory):
    path = directory / "fr.html"
    raw = path.read_text(encoding="utf-8")
    fragment = re.search(r'<template id="mission-public-runs">[^<]*</template>', raw).group()
    change_text(path, fragment, fragment + fragment)


def changed_certificate(directory):
    path = directory / "example-verification.json"
    payload = json.loads(path.read_bytes())
    payload["lower_numerator"] += 1
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def evaluate_controls(first, repeat):
    controls = {
        "reversed-payoff-sign": (
            first, "FIRST", lambda p: change_text(p / "fr.html",
                                                "la stratégie aléatoire garantit −49,5",
                                                "la stratégie aléatoire garantit +49,5")),
        "ambiguous-duplicate-mission": (first, "FIRST", duplicate_fragment),
        "altered-authority": (first, "FIRST", changed_certificate),
        "interchanged-site-counts": (
            repeat, "REPEAT", lambda p: change_text(p / "fr.html",
                                                  "10 produits à Montréal et 11 à Québec",
                                                  "11 produits à Montréal et 10 à Québec")),
        "changed-denominator": (
            repeat, "REPEAT", lambda p: change_text(p / "fr.html",
                                                  "attendus dans 8 passages sur 8",
                                                  "attendus dans 8 passages sur 9")),
    }
    evidence = {}
    for name, (original, label, change) in controls.items():
        with TemporaryDirectory(prefix="frontier-approved-public-") as directory:
            target = Path(directory) / "pages"
            shutil.copytree(original, target)
            change(target)
            results = compare(target, HERE / f"{label}-PLAN.json", ARMS)
        for result in results:
            if result["report"]["decision"] != "HOLD":
                raise RuntimeError(f"{result['arm']} accepted a faulty claim in {name}")
            result["report"]["held_claims"] = [
                (row["id"], row["language"]) for row in result["report"].pop("claims", [])
                if row["decision"] == "HOLD"
            ]
        evidence[name] = results
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("repeat", type=Path)
    args = parser.parse_args()
    first, repeat = args.first.resolve(), args.repeat.resolve()
    print(json.dumps({"schema": "frontier/production-claim-comparison-v1",
                      "first": use(first, "FIRST"), "repeat": use(repeat, "REPEAT"),
                      "controlled_failures": evaluate_controls(first, repeat)}, ensure_ascii=False, indent=2))
