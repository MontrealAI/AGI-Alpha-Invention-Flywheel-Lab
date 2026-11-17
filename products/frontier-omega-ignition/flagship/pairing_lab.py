"""Compare self-hosted coding stacks on matched, independently graded issue attempts."""
import argparse
import csv
import hashlib
import io
import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COLUMNS = ["task", "model", "harness", "solved", "tokens"]
LABEL = re.compile(r"[a-zA-Z0-9_.-]{1,180}")
PUBLIC_HASH = "c60d0b58ab109ba900e36465a0ffadaaeb4c8a2743abc744eb17f3f596842118"
SOURCE = "https://github.com/lisazhao-gz/pairing-matters/tree/48444d3aa8383c90de0135c55138528c90eeb8e0"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_grid(raw):
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
    if rows.fieldnames != COLUMNS:
        raise ValueError("expected CSV columns " + ",".join(COLUMNS))
    grid = {}
    all_stacks = set()
    for row in rows:
        if None in row or any(not LABEL.fullmatch(row[k] or "") for k in COLUMNS[:3]):
            raise ValueError("invalid or incomplete input row")
        if row["solved"] not in ("0", "1") or not re.fullmatch(r"[0-9]{1,18}", row["tokens"] or ""):
            raise ValueError("require binary resolved status and nonnegative integer token count")
        stack = row["model"] + "/" + row["harness"]
        task = grid.setdefault(row["task"], {})
        if stack in task:
            raise ValueError("duplicate task/configuration observation")
        task[stack] = (int(row["solved"]), int(row["tokens"]))
        all_stacks.add(stack)
    if len(grid) < 2 or any(task.keys() != all_stacks for task in grid.values()):
        raise ValueError("need a complete paired grid with at least two distinct tasks")
    return grid, sorted(all_stacks)


def split_tasks(grid):
    ordered = sorted(grid, key=lambda task: (digest(("pairing-lab-v1/" + task).encode()), task))
    cut = 3 * len(ordered) // 5
    return ordered[:cut], ordered[cut:]


def measure(grid, task_ids, stacks, with_witnesses=False):
    successes = 0
    tokens = 0
    details = []
    for task in task_ids:
        results = [grid[task][stack] for stack in stacks]
        solved = max(result[0] for result in results)
        charged = sum(result[1] for result in results)
        successes += solved
        tokens += charged
        if with_witnesses:
            details.append({"task": task, "solved": solved, "tokens": charged,
                            "attempts": [{"stack": stack, "solved": result[0], "tokens": result[1]}
                                         for stack, result in zip(stacks, results)]})
    answer = {"tasks": len(task_ids), "solved": successes, "tokens": tokens}
    if with_witnesses:
        answer["witnesses"] = details
    return answer


def best_policy(grid, tasks, policies, budget):
    candidates = []
    for policy in policies:
        score = measure(grid, tasks, policy)
        if budget is None or score["tokens"] <= budget * score["tasks"]:
            candidates.append((-score["solved"], score["tokens"], policy))
    return min(candidates)[2] if candidates else None


def analyze(raw, *, budget=2000000, width=2, min_percent=45, model=None, repository=None,
            witnesses=True):
    if type(budget) is not int or budget < 0 or type(width) is not int or width not in (1, 2):
        raise ValueError("budget must be a nonnegative integer and width must be 1 or 2")
    if type(min_percent) is not int or not 0 <= min_percent <= 100:
        raise ValueError("minimum accepted percentage must be a whole number between 0 and 100")
    if model is not None and not LABEL.fullmatch(model):
        raise ValueError("invalid model identifier")
    if repository is not None and not re.fullmatch(r"[\w.-]+__[\w.-]+", repository, re.ASCII):
        raise ValueError("repository must use the benchmark owner__name identifier")
    grid, stacks = read_grid(raw)
    train, audit = split_tasks(grid)
    if repository is not None:
        # Benchmark IDs are '<owner>__<repo>-<integer issue>'.
        train, audit = ([t for t in group if t.rpartition("-")[0] == repository] for group in (train, audit))
    if not train or not audit:
        raise ValueError("need at least one calibration and one audit issue in this repository")
    if model is not None:
        stacks = [s for s in stacks if s.split("/", 1)[0] == model]
    if not stacks:
        raise ValueError("no matching configurations")
    policies = [p for count in range(1, width + 1) for p in itertools.combinations(stacks, count)]
    selected = best_policy(grid, train, policies, budget)
    hindsight = best_policy(grid, audit, policies, budget)
    uncapped = best_policy(grid, train, [(s,) for s in stacks], None)
    result = {
        "schema": "pairing-lab/1", "method": "retrospective task-disjoint audit",
        "data_sha256": digest(raw), "public_source": SOURCE if digest(raw) == PUBLIC_HASH else None,
        "program_sha256": digest(Path(__file__).read_bytes()),
        "parameters": {"budget": budget, "width": width, "min_percent": min_percent,
                       "model": model, "repository": repository},
        "split": {"calibration_count": len(train), "audit_count": len(audit),
                  "calibration_ids_sha256": digest("\n".join(train).encode()),
                  "audit_ids_sha256": digest("\n".join(audit).encode())},
        "policies_considered": len(policies), "selected": list(selected) if selected else None,
        "calibration": None, "audit": None, "qualifies": False,
        "verdict": "no_feasible_calibration_policy",
        "hindsight_best": list(hindsight) if hindsight else None,
        "hindsight_audit": measure(grid, audit, hindsight) if hindsight else None,
        "uncapped_single": {"selected": list(uncapped), "audit": measure(grid, audit, uncapped)},
        "scope": "Historical benchmark. Paired coverage assumes independent executable acceptance. "
                 "Metered token volume excludes hardware, grader overhead and commercial cost.",
    }
    if selected:
        result["calibration"] = measure(grid, train, selected)
        held = measure(grid, audit, selected, witnesses)
        within = held["tokens"] <= budget * held["tasks"]
        meets = held["solved"] * 100 >= min_percent * held["tasks"]
        result.update(audit=held, qualifies=within and meets, budget_pass=within, resolution_pass=meets,
                      verdict="audit_pass" if within and meets else "audit_failed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "runs.csv", help="matched five-column CSV")
    parser.add_argument("--budget", type=int, default=2000000, help="mean charged tokens per attempted issue")
    parser.add_argument("--width", type=int, choices=[1, 2], default=2, help="maximum simultaneous attempts")
    parser.add_argument("--min-percent", type=int, default=45, help="required percent of audit issues resolved")
    parser.add_argument("--model", help="restrict to one observed model ID")
    parser.add_argument("--repository", help="restrict to one repository using owner__name")
    parser.add_argument("--summary", action="store_true", help="omit per-issue witnesses")
    opts = parser.parse_args()
    try:
        output = analyze(opts.data.read_bytes(), budget=opts.budget, width=opts.width,
                         min_percent=opts.min_percent, model=opts.model, repository=opts.repository,
                         witnesses=not opts.summary)
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(2, f"Invalid study: {exc}\n")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
