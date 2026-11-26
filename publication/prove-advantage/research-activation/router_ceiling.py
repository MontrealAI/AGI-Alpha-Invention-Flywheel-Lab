"""Bound the acceptance gain available to a selector over frozen outputs."""

from hashlib import sha256
import json
from pathlib import Path
import runpy


STUDY = Path(__file__).resolve().parents[1]
DPP = STUDY / "dpp-replay"
GAME_THEORY = STUDY / "game-theory"
SOURCE_REVISION = "b35f937fcb77199334e267360e9a0c9e438a74ad"
SOURCE_URL = "https://arxiv.org/abs/2611.34825v1"
DPP_MANIFEST = "3619470cd0a1499efd5c2b9d77a3bffe2613a50234832e8c8153f2f6834c7113"
GAME_THEORY_MANIFEST = "6ca2d09dfe0d5f8e69a94487efc91beb4ae1182aa6dfc141363f67c0b1a6d801"


def case_aligned_ceiling(case_ids, arms):
    """Compare each fixed arm and the optimistic union over exact matched cases."""
    cases = tuple(case_ids)
    if not cases or any(not isinstance(case, str) or not case.strip() for case in cases):
        raise ValueError("Case IDs must be non-empty strings")
    if len(set(cases)) != len(cases):
        raise ValueError("Duplicate case ID")
    if len(arms) < 2:
        raise ValueError("A portfolio needs at least two arms")
    for arm, outcomes in arms.items():
        if set(outcomes) != set(cases) or any(type(value) is not bool for value in outcomes.values()):
            raise ValueError(f"Expected one Boolean acceptance result per case for {arm}")

    accepted_by_arm = {arm: sum(outcomes.values()) for arm, outcomes in arms.items()}
    best_fixed = max(accepted_by_arm.values())
    winners = {
        case: [arm for arm, outcomes in arms.items() if outcomes[case]]
        for case in cases
    }
    uncovered = [case for case, winning_arms in winners.items() if not winning_arms]
    oracle = len(cases) - len(uncovered)
    return {
        "cases": len(cases),
        "accepted_by_arm": accepted_by_arm,
        "best_fixed_arms": sorted(arm for arm, total in accepted_by_arm.items() if total == best_fixed),
        "best_fixed_accepted": best_fixed,
        "oracle_accepted": oracle,
        "oracle_gain_cases": oracle - best_fixed,
        "all_arms_accepted": sum(len(winning_arms) == len(arms) for winning_arms in winners.values()),
        "discordant_cases": sum(0 < len(winning_arms) < len(arms) for winning_arms in winners.values()),
        "uncovered_case_ids": uncovered,
    }


def frozen_files(folder, manifest_hash, names):
    manifest = (folder / "SHA256SUMS").read_bytes()
    if sha256(manifest).hexdigest() != manifest_hash:
        raise ValueError(f"Frozen manifest differs in {folder.name}")
    checksums = {name: digest for digest, name in (line.split() for line in manifest.decode().splitlines())}
    contents = {}
    for name in names:
        raw = (folder / name).read_bytes()
        if sha256(raw).hexdigest() != checksums[name]:
            raise ValueError(f"Frozen input differs in {folder.name}/{name}")
        contents[name] = raw
    return contents


def by_case(rows, key, accepted):
    indexed = {}
    for row in rows:
        case = row[key]
        if case in indexed:
            raise ValueError(f"Duplicate outcome for {case}")
        indexed[case] = accepted(row)
    return indexed


def dpp_panels():
    stages = ("PRIMARY", "CONFIRMATION")
    names = ("OBSERVATIONS", "REFERENCE", "DIRECT", "PREDICTIONS")
    files = frozen_files(DPP, DPP_MANIFEST, [
        "score.py",
        *(f"{stage}-{name}.json" for stage in stages for name in names),
    ])
    grade = runpy.run_path(str(DPP / "score.py"))["grade"]

    cohorts = {}
    for stage in stages:
        cases, reference, direct, frontier = (json.loads(files[f"{stage}-{name}.json"]) for name in names)
        cases = cases["cases"]
        case_ids = [case["id"] for case in cases]
        predictions = {
            arm: by_case(outputs, "id", lambda row: row)
            for arm, outputs in (("direct", direct), ("frontier", frontier))
        }
        if any(set(outputs) != set(case_ids) for outputs in predictions.values()):
            raise ValueError(f"Frozen predictions do not cover all {stage} cases")
        grades = {
            arm: grade(cases, reference, outputs)
            for arm, outputs in predictions.items()
        }
        accepted = {
            arm: by_case(receipt["scores"], "id", lambda row: row["fully_accepted"])
            for arm, receipt in grades.items()
        }
        cohorts[stage.lower()] = (tuple(case_ids), accepted)
    return cohorts


def exact_game_case(row):
    if row["cases"] != 1 or type(row["exact_cases"]) is not int or row["exact_cases"] not in (0, 1):
        raise ValueError("Expected a single frozen Game Theory case result")
    return bool(row["exact_cases"])


def game_theory_panels():
    names = (
        "PRIMARY-ADJUDICATION.json", "QWEN-ADJUDICATION.json", "PRIMARY-ORACLE.json",
        "CONFIRMATION-INDEPENDENT-EVALUATION.json", "CONFIRMATION-ORACLE.json",
    )
    files = frozen_files(GAME_THEORY, GAME_THEORY_MANIFEST, names)
    primary, qwen, primary_oracle, confirmation, confirmation_oracle = (
        json.loads(files[name]) for name in names
    )
    primary_arms = {
        arm: by_case(receipt["cases"], "id", exact_game_case)
        for arm, receipt in {**primary["arms"], "qwen_4b": qwen}.items()
    }
    confirmation_arms = {
        arm: by_case(receipt["per_case"], "case", lambda row: row["exact_case"])
        for arm, receipt in confirmation["arms"].items()
    }
    return {
        "game_theory_primary": (tuple(primary_oracle), primary_arms),
        "game_theory_confirmation": (tuple(confirmation_oracle), confirmation_arms),
    }


def matched_panels():
    """Load the case order and verdicts from the registered public byte sets."""
    return {**dpp_panels(), **game_theory_panels()}


def main():
    print(json.dumps({
        "schema": "frontier/routeability-ceiling-v1",
        "source_revision": SOURCE_REVISION,
        "source_url": SOURCE_URL,
        "execution": "retrospective_public_replay",
        "matched_complete_cost_available": False,
        "paid_requests": 0,
        "cohorts": {
            panel: case_aligned_ceiling(case_ids, arms)
            for panel, (case_ids, arms) in matched_panels().items()
        },
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
