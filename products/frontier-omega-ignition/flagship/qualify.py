"""Recompute the registered comparisons against an independent exhaustive SQL search."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import conventional
import pairing_lab

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualification():
    raw = (HERE / "runs.csv").read_bytes()
    if pairing_lab.digest(raw) != pairing_lab.PUBLIC_HASH:
        raise ValueError("registered input changed; run the recipient CLI for a new study")
    grid, _ = pairing_lab.read_grid(raw)
    train, audit = pairing_lab.split_tasks(grid)
    arms = {}
    exercises = [(f"{budget}/{width}", budget, width, None, None)
                 for budget in (500000, 2000000, 5000000) for width in (1, 2)]
    exercises.append(("successor", 2000000, 2, "devstral", "django__django"))
    for key, budget, width, model, repo in exercises:
        report = pairing_lab.analyze(raw, budget=budget, width=width, model=model,
                                    repository=repo, witnesses=False)
        selected, scores = conventional.enumerate_sql(raw, budget, width, model, repo)
        stacks = sorted(s for s in next(iter(grid.values())) if not model or s.split("/")[0] == model)
        universe = {p for size in range(1, width + 1) for p in itertools.combinations(stacks, size)}
        if (list(selected) if selected else None) != report["selected"]:
            raise AssertionError(f"{key}: conventional selection differs")
        for phase, tasks in (("calibration", train), ("audit", audit)):
            ids = [t for t in tasks if not repo or t.rpartition("-")[0] == repo]
            if set(scores[phase]) != universe:
                raise AssertionError(f"{key}: feasible populations differ")
            for policy, reference in scores[phase].items():
                if pairing_lab.measure(grid, ids, policy) != reference:
                    raise AssertionError(f"{key}: score differs for {policy} in {phase}")
        report["conventional_sql"] = {"agreement": True, "policies_compared": len(universe),
                                      "score_rows_compared": 2 * len(universe)}
        arms[key] = report
    return {"schema": "pairing-lab-cohort/1", "study": {"rows": 1800, "tasks": 100,
            "configurations": 18, "source": pairing_lab.SOURCE,
            "archive": "https://doi.org/10.6084/m9.figshare.34744362.v1",
            "data_sha256": pairing_lab.digest(raw),
            "registration_sha256": sha(HERE / "REGISTRATION.md"),
            "source_sha256": {p: sha(HERE / p) for p in
                              ("pairing_lab.py", "conventional.py", "qualify.py", "test_pairing_lab.py")},
            "mode": "reanalysis of recorded grader outcomes", "original_inference_reexecuted": False},
            "arms": arms}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path, help="verify an existing recorded receipt")
    opt = parser.parse_args()
    computed = qualification()
    if opt.check:
        if json.loads(opt.check.read_bytes()) != computed:
            raise SystemExit("receipt differs from independently recomputed result")
        print("Matched every registered receipt and both split scores for every allowed policy.")
    else:
        print(json.dumps(computed, indent=2))
