"""Freeze a fresh local pilot, then audit externally graded attempts against that commitment."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path

from pairing_lab import LABEL, ROOT, analyze, digest

FIELDS = ["task", "model", "harness", "solved", "tokens", "grader_sha256", "run_id"]
HEX = re.compile(r"[0-9a-f]{64}")


def register(data, tasks, grader, *, budget, width, min_percent, model=None, repository=None):
    if (not isinstance(tasks, list) or not tasks or any(not isinstance(t, str) or not LABEL.fullmatch(t) for t in tasks)
            or len(set(tasks)) != len(tasks)):
        raise ValueError("pilot task IDs must be nonempty, distinct local identifiers")
    if not isinstance(grader, str) or not HEX.fullmatch(grader):
        raise ValueError("need SHA-256 of the approved independent grading procedure")
    report = analyze(data, budget=budget, width=width, min_percent=min_percent, model=model,
                     repository=repository, witnesses=False)
    if not report["qualifies"]:
        raise ValueError("historical cohort did not qualify for this pilot specification")
    training_tasks = {r["task"] for r in csv.DictReader(io.StringIO(data.decode()))}
    if set(tasks) & training_tasks:
        raise ValueError("fresh pilot identifiers must be distinct from the study tasks")
    return {"schema": "pairing-local-pilot/1", "tasks": sorted(tasks), "required_stacks": report["selected"],
            "selection_data_sha256": report["data_sha256"], "selector_sha256": report["program_sha256"],
            "pilot_program_sha256": digest(Path(__file__).read_bytes()), "grader_sha256": grader,
            "parameters": report["parameters"], "authority": "offline analysis of operator-supplied grades"}


def canonical(plan):
    return (json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def audit(plan_bytes, commitment, observations, *, data=None):
    if not HEX.fullmatch(commitment) or digest(plan_bytes) != commitment:
        raise ValueError("plan bytes differ from the separately retained pre-run commitment")
    plan = json.loads(plan_bytes)
    if not isinstance(plan, dict) or plan.get("schema") != "pairing-local-pilot/1":
        raise ValueError("unrecognized pilot contract")
    params = plan.get("parameters")
    if not isinstance(params, dict) or set(params) != {"budget", "width", "min_percent", "model", "repository"}:
        raise ValueError("incomplete or unknown decision parameters")
    # A consumer may supply a freshly authored file and its matching digest.
    # Reconstruct the eligible stacks, input identities, frozen limits and task list independently.
    raw = (ROOT / "runs.csv").read_bytes() if data is None else data
    try:
        original = register(raw, plan.get("tasks"), plan.get("grader_sha256"), **params)
    except (TypeError, KeyError) as exc:
        raise ValueError("invalid pilot contract fields") from exc
    if canonical(original) != plan_bytes:
        raise ValueError("pilot differs from a currently reproducible registered decision")
    expected = {(task, stack) for task in plan["tasks"] for stack in plan["required_stacks"]}
    rows = csv.DictReader(io.StringIO(observations.decode(), newline=""), strict=True)
    if rows.fieldnames != FIELDS:
        raise ValueError("unexpected observation columns")
    seen, run_ids, successes = set(), set(), set()
    tokens = 0
    for row in rows:
        if None in row or None in row.values():
            raise ValueError("invalid observation row length")
        key = row["task"], row["model"] + "/" + row["harness"]
        if key not in expected or key in seen or not LABEL.fullmatch(row["run_id"]) or row["run_id"] in run_ids:
            raise ValueError("unexpected/duplicate task, configuration or run identity")
        if row["grader_sha256"] != plan["grader_sha256"]:
            raise ValueError("reported grader differs from registered procedure")
        if row["solved"] not in ("0", "1") or not re.fullmatch(r"[0-9]{1,18}", row["tokens"]):
            raise ValueError("invalid grade or token meter")
        seen.add(key)
        run_ids.add(row["run_id"])
        tokens += int(row["tokens"])
        if row["solved"] == "1":
            successes.add(row["task"])
    missing = sorted(expected - seen)
    n = len(plan["tasks"])
    params = plan["parameters"]
    meets = not missing and tokens <= n * params["budget"] and 100 * len(successes) >= n * params["min_percent"]
    return {"schema": "pairing-local-pilot-audit/1", "plan_sha256": commitment,
            "observations_sha256": digest(observations), "required_attempts": len(expected),
            "reported_attempts": len(seen), "missing_attempts": [list(v) for v in missing],
            "tasks": n, "tasks_with_reported_success": len(successes), "reported_tokens": tokens,
            "verdict": "incomplete" if missing else ("criteria_met" if meets else "criteria_failed"),
            "scope": "Operator-supplied evidence. Reported grader identity and grades have not been independently reexecuted."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("--data", type=Path, default=ROOT / "runs.csv")
    reg.add_argument("--tasks", type=Path, required=True, help="one new issue ID per line")
    reg.add_argument("--grader-sha", required=True)
    reg.add_argument("--out", type=Path, required=True)
    reg.add_argument("--budget", type=int, default=2000000)
    reg.add_argument("--width", type=int, choices=[1,2], default=2)
    reg.add_argument("--min-percent", type=int, default=45)
    reg.add_argument("--model")
    reg.add_argument("--repository")
    check = sub.add_parser("audit")
    check.add_argument("--plan", type=Path, required=True)
    check.add_argument("--commitment", required=True)
    check.add_argument("--observations", type=Path, required=True)
    check.add_argument("--data", type=Path, default=ROOT / "runs.csv", help="exact data used to register this pilot")
    args = p.parse_args()
    try:
        if args.action == "register":
            doc = register(args.data.read_bytes(), args.tasks.read_text().splitlines(), args.grader_sha,
                           budget=args.budget, width=args.width, min_percent=args.min_percent,
                           model=args.model, repository=args.repository)
            body = canonical(doc)
            with args.out.open("xb") as output:
                output.write(body)
            print(hashlib.sha256(body).hexdigest())
        else:
            report = audit(args.plan.read_bytes(), args.commitment, args.observations.read_bytes(), data=args.data.read_bytes())
            print(json.dumps(report,indent=2))
    except (KeyError, TypeError, ValueError, OSError, csv.Error) as exc:
        p.exit(2, f"Pilot error: {exc}\n")


if __name__ == "__main__":
    main()
