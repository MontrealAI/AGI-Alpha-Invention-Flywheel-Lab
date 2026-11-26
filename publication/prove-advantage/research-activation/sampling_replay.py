# SPDX-License-Identifier: Apache-2.0
"""Compare fixed metadata sampling policies on two published scored panels."""

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations, product
import json
from math import ceil
from pathlib import Path
from statistics import mean


STUDY = Path(__file__).resolve().parent
PANELS = ("PRIMARY", "CONFIRMATION")
ARMS = ("base_direct", "base_retrieval", "base_word_lookup", "adapted_direct")
INPUTS = {
    "PRIMARY-BRIEFS.json": "caa9bd9596b36bded98d84c26f54bbfbd329587de1dee2c14c08a9d3a3db9529",
    "PRIMARY-ADJUDICATION.json": "951506c89269baf3a4f39e3b6a1bda63aebfbac42d9fc11a805b958e8d617154",
    "CONFIRMATION-BRIEFS.json": "2acf5f20f86bfd0c1cc2680a03ecc2f205f645d8d29ee13e817f51ec735dbf6d",
    "CONFIRMATION-ADJUDICATION.json": "df9aeaa8948f3a4815b2db93f8dc318d3a3f761c2a6c44ee4dbfa535f080b0d9",
}
CASE_BUDGET = 8
TOTAL_QUERIES = 50


@dataclass(frozen=True)
class Case:
    identity: str
    panel: str
    language: str
    rule_chars: int
    queries: int


def read_input(filename):
    raw = (STUDY.parent / "game-theory" / filename).read_bytes()
    if sha256(raw).hexdigest() != INPUTS[filename]:
        raise ValueError(f"Input differs from registration: {filename}")
    return json.loads(raw)


def metadata():
    cases = {}
    strata = defaultdict(list)
    for panel in PANELS:
        for brief in read_input(f"{panel}-BRIEFS.json"):
            case = Case(
                brief["id"],
                panel,
                brief["language"],
                sum(len(rule) for rule in brief["rules"]),
                len(brief["queries"]),
            )
            if case.identity in cases:
                raise ValueError("Duplicate case identity")
            cases[case.identity] = case
            strata[(panel, case.language)].append(case.identity)
    if (len(cases) != 18 or sum(case.queries for case in cases.values()) != TOTAL_QUERIES
            or set(strata) != set(product(PANELS, ("en", "fr")))
            or sorted(map(len, strata.values())) != [4, 4, 5, 5]):
        raise ValueError("Case, query or sampling stratum counts differ from registration")
    return cases, dict(sorted(strata.items()))


def policies(cases, strata):
    strata = list(strata.values())
    by_length = [sorted(group, key=lambda cid: (cases[cid].rule_chars, cid))
                 for group in strata]
    halves = []
    for group in by_length:
        middle = len(group) // 2
        halves.extend((group[:middle], group[middle:]))

    longest = [
        tuple(sorted(group, key=lambda cid: (-cases[cid].rule_chars, cid))[:2])
        for group in strata
    ]
    largest_query_count = [
        tuple(sorted(group, key=lambda cid: (-cases[cid].queries, cid))[:2])
        for group in strata
    ]
    return {
        "simple_random": ([list(cases)], CASE_BUDGET, None),
        "stratified_random": (strata, 2, None),
        "length_balanced": (halves, 1, None),
        "longest_rule_priority": (strata, 2, longest),
        "query_count_priority": (strata, 2, largest_query_count),
    }


def outcomes(cases):
    hits = {arm: {} for arm in ARMS}
    for panel in PANELS:
        adjudication = read_input(f"{panel}-ADJUDICATION.json")
        expected = {cid for cid, case in cases.items() if case.panel == panel}
        for arm in ARMS:
            results = adjudication["arms"][arm]["cases"]
            if len(results) != len(expected) or {row["id"] for row in results} != expected:
                raise ValueError(f"Case coverage differs for {arm} in {panel}")
            for row in results:
                cid = row["id"]
                total, correct = cases[cid].queries, row["cited_correct"]
                if (row["queries"] != total or type(correct) is not int
                        or not 0 <= correct <= total or len(row["misses"]) != total - correct):
                    raise ValueError(f"Inconsistent query counts for {cid}")
                hits[arm][cid] = correct
    totals = {arm: sum(hits[arm].values()) for arm in ARMS}
    if sum(5 <= total <= TOTAL_QUERIES - 5 for total in totals.values()) < 2:
        raise ValueError("Fewer than two eligible arms with mixed outcome counts")
    return hits, totals


def results_for_policy(policy, cases, hits, totals):
    groups, take, fixed = policy
    options = [tuple(combinations(group, take)) for group in groups] if fixed is None else []
    draws = product(*options) if fixed is None else iter([fixed])
    weights = [len(group) / take for group in groups]
    queries_visited = []
    failures = {arm: [] for arm in ARMS}
    rates = {arm: [] for arm in ARMS}
    errors = {arm: [] for arm in ARMS}
    for draw in draws:
        selected = [cid for group in draw for cid in group]
        if len(selected) != CASE_BUDGET or len(set(selected)) != CASE_BUDGET:
            raise ValueError("Selected case set violates the fixed budget")
        queries = sum(cases[cid].queries for cid in selected)
        queries_visited.append(queries)
        for arm in ARMS:
            positives = [sum(hits[arm][cid] for cid in group) for group in draw]
            misses = queries - sum(positives)
            failures[arm].append(misses)
            rates[arm].append(misses / queries)
            if fixed is None:
                estimate = sum(count * weight for count, weight in zip(positives, weights, strict=True))
                errors[arm].append(100 * abs(estimate - totals[arm]) / TOTAL_QUERIES)
    output = {
        "case_budget": CASE_BUDGET,
        "eligible_batches": len(queries_visited),
        "mean_queries_visited": mean(queries_visited),
        "min_queries_visited": min(queries_visited),
        "max_queries_visited": max(queries_visited),
        "arms": {},
    }
    for arm in ARMS:
        row = {
            "mean_citation_failures_found": mean(failures[arm]),
            "mean_failure_precision_pp": 100 * mean(rates[arm]),
            "mean_failure_recall_pp": 100 * mean(failures[arm]) / (TOTAL_QUERIES - totals[arm]),
        }
        if fixed is None:
            error = sorted(errors[arm])
            row["success_rate_mae_pp"] = mean(error)
            row["success_rate_p90_error_pp"] = error[ceil(0.9 * len(error)) - 1]
        output["arms"][arm] = row
    return output


def compare(policy_results):
    def pooled(name, metric):
        return mean(row[metric] for row in policy_results[name]["arms"].values())

    mae = "success_rate_mae_pp"
    estimate_controls = ("simple_random", "stratified_random")
    estimate_control = min(estimate_controls, key=lambda name: pooled(name, mae))
    estimation_reduction = 1 - pooled("length_balanced", mae) / pooled(estimate_control, mae)
    worst_p90 = max(row["success_rate_p90_error_pp"]
                    for row in policy_results["length_balanced"]["arms"].values())

    precision = "mean_failure_precision_pp"
    diagnosis_controls = (*estimate_controls, "query_count_priority")
    diagnosis_control = max(diagnosis_controls, key=lambda name: pooled(name, precision))
    diagnosis_gain = pooled("longest_rule_priority", precision) - pooled(diagnosis_control, precision)
    worst_diagnosis_delta = min(
        policy_results["longest_rule_priority"]["arms"][arm][precision]
        - policy_results[diagnosis_control]["arms"][arm][precision]
        for arm in ARMS
    )
    return {
        "estimation": {
            "best_random_control": estimate_control,
            "relative_mae_reduction": estimation_reduction,
            "worst_p90_error_pp": worst_p90,
            "advance": estimation_reduction >= 0.10 and worst_p90 <= 5,
        },
        "early_failure_detection": {
            "best_control": diagnosis_control,
            "mean_precision_gain_pp": diagnosis_gain,
            "worst_arm_precision_gain_pp": worst_diagnosis_delta,
            "advance": diagnosis_gain >= 5 and worst_diagnosis_delta >= -5,
        },
    }


def replay():
    cases, strata = metadata()
    fixed_policies = policies(cases, strata)
    hits, totals = outcomes(cases)
    policy_results = {
        name: results_for_policy(policy, cases, hits, totals)
        for name, policy in fixed_policies.items()
    }
    return {
        "schema": "frontier/evaluation-sampling-replay-v1",
        "scope": "retrospective policy replay on published adjudicated outcomes",
        "research_source": "https://arxiv.org/abs/2611.34617v1",
        "registration_sha256": sha256((STUDY / "sampling-registration.md").read_bytes()).hexdigest(),
        "input_sha256": INPUTS,
        "strata": {f"{panel.lower()}_{language}": len(group)
                   for (panel, language), group in strata.items()},
        "complete_reference": {
            "cases": len(cases),
            "queries": TOTAL_QUERIES,
            "arms": {arm: {"cited_successes": count, "cited_failures": TOTAL_QUERIES - count}
                     for arm, count in totals.items()},
        },
        "policies": policy_results,
        "registered_decisions": compare(policy_results),
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True, allow_nan=False))
