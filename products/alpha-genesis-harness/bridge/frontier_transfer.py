# SPDX-License-Identifier: Apache-2.0
"""Frozen, distinct-objective transfer comparisons for FRONTIER Ω.

This is an evidence audit, not an executor, source of financial authority, or
provenance attestation. Existing HARNESS executors supply candidate execution.
Hashes bind the recorded experiment; they cannot establish that an operator's
semantic review, claimed human baseline, or economic observations are true.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re

from .workflows import digest, encoded, equivalent, portable_digest, require

SCHEMA = "frontier-transfer/v1"
SHA = re.compile(r"[a-f0-9]{64}\Z")
STAGES = ("acquisition", "discovery", "construction", "failed_attempts",
          "integration", "verification", "execution", "maintenance")
METRICS = ("model_calls", "input_tokens", "output_tokens", "wall_seconds",
           "cpu_seconds", "human_seconds")
ARMS = ("first", "with_asset", "without_asset", "conventional",
        "first_conventional", "ordinary_reuse")
IDENTITIES = ("source_sha256", "environment_sha256", "information_sha256")
SCOPE = ("Recorded, source-bound comparison only. Semantic distinctness and real "
         "productive use require attributed independent review. Hashes do not "
         "attest provenance. No commerce, spendable balance, general novelty, "
         "statistical generalization or inventor improvement is certified.")


def _need(ok, message):
    require(ok, message, "FRONTIER_TRANSFER")


def _text(value, label, maximum=4000):
    _need(isinstance(value, str) and 0 < len(value.strip()) <= maximum,
          label + " must be bounded nonempty text.")
    return value


def _sha(value, label):
    _need(isinstance(value, str) and SHA.fullmatch(value), label + " needs a SHA-256 identity.")
    return value


def _number(value, label):
    finite = type(value) is int or (type(value) is float and math.isfinite(value))
    _need(finite and value >= 0,
          label + " must be finite and nonnegative.")
    return value


def _normal(value):
    return " ".join(value.casefold().split())


def _contract(value):
    _need(isinstance(value, dict) and set(value) == {
        "objective", "family", "acceptance", "development", "qualification"},
        "A contract needs objective, family, acceptance, development and qualification.")
    for key in ("objective", "family", "acceptance"):
        _text(value[key], key, 6000 if key == "acceptance" else 4000)
    inputs = set()
    for group in ("development", "qualification"):
        cases = value[group]
        _need(isinstance(cases, list) and 0 < len(cases) <= 10000,
              "Each frozen case cohort must be nonempty and fit the processing envelope.")
        for case in cases:
            _need(isinstance(case, dict) and set(case) == {"input", "expected"},
                  "Each case needs exactly input and expected output.")
            identity = digest(case["input"])
            _need(identity not in inputs, "Development and qualification inputs must be distinct.")
            inputs.add(identity)


def register(spec):
    """Freeze two outcomes before constructing the second capability.

    A distinct family and different tests are necessary, never sufficient, for
    semantic novelty. ``adjudicate`` separately checks attributed review.
    Qualification remains private to the caller; use ``public_contract`` for a
    builder, never serialize the complete registration into its prompt.
    """
    _need(isinstance(spec, dict) and set(spec) == {"first", "second", "comparison"},
          "Register first and second contracts plus a comparison policy.")
    try:
        _need(len(encoded(spec)) <= 4 * 1024 * 1024, "Registration exceeds its processing envelope.")
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError("Registration must contain finite JSON data.") from error
    for stage in ("first", "second"):
        _contract(spec[stage])
    _need(_normal(spec["first"]["objective"]) != _normal(spec["second"]["objective"]),
          "A renamed or repeated objective is not a second invention.")
    _need(_normal(spec["first"]["family"]) != _normal(spec["second"]["family"]),
          "Fresh inputs for the same task family are not a second invention.")
    _need(digest(spec["first"]["qualification"]) != digest(spec["second"]["qualification"]),
          "The second qualification cannot simply repeat the first test.")
    comparison = spec["comparison"]
    _need(isinstance(comparison, dict) and set(comparison) == {
        "inventor", *IDENTITIES, "budget", "metric", "currency"},
        "Comparison needs inventor, source/environment/information identities, budget, metric and currency.")
    _text(comparison["inventor"], "Inventor", 500)
    for key in IDENTITIES:
        _sha(comparison[key], key)
    budget = comparison["budget"]
    _need(isinstance(budget, dict) and budget and not set(budget) - set(METRICS),
          "Use explicitly registered resource limits, not an implied universal budget.")
    for key, value in budget.items():
        _number(value, "Budget " + key)
    _need(comparison["metric"] in METRICS, "Choose a measured resource comparison metric.")
    _need(isinstance(comparison["currency"], str) and re.fullmatch(r"[A-Z]{3}", comparison["currency"]),
          "Use a three-letter currency identifier.")
    record = {"schema": SCHEMA, "spec": copy.deepcopy(spec), "contracts": {
        stage: {"sha256": digest(spec[stage]), "qualification_sha256": digest(spec[stage]["qualification"])}
        for stage in ("first", "second")}, "budget_sha256": digest(budget)}
    return {**record, "sha256": digest(record)}


def _registration(record):
    _need(isinstance(record, dict) and record.get("schema") == SCHEMA,
          "Unsupported transfer registration.")
    _sha(record.get("sha256"), "Registration")
    payload = {key: value for key, value in record.items() if key != "sha256"}
    _need(digest(payload) == record["sha256"], "Frozen transfer registration changed.")
    _need(register(record["spec"]) == record, "Transfer registration identities are inconsistent.")
    return record


def public_contract(registration, stage):
    """Return an isolated builder view; no withheld inputs, answers or hashes."""
    record = _registration(registration)
    _need(stage in ("first", "second"), "Select first or second construction.")
    return {key: copy.deepcopy(value) for key, value in record["spec"][stage].items()
            if key != "qualification"}


def qualify(registration, stage, candidate_sha256, execute, *, checker_sha256):
    """Run a previously frozen candidate through an existing safe executor.

    ``execute`` receives only a fresh input, never the expected answer. The caller
    owns isolation, source binding, execution limits and resource accounting.
    This helper compares outputs independently of the candidate and does not
    expose expected answers in its receipt. Failures remain in the denominator.
    """
    record = _registration(registration)
    _need(stage in ("first", "second"), "Select a registered qualification stage.")
    _sha(candidate_sha256, "Candidate")
    _sha(checker_sha256, "Checker")
    _need(callable(execute), "Qualification requires the existing candidate executor.")
    results = []
    for index, case in enumerate(record["spec"][stage]["qualification"]):
        row = {"index": index, "input_sha256": digest(case["input"]), "passed": False,
               "output_sha256": None, "error": None}
        try:
            output = execute(copy.deepcopy(case["input"]))
            row["output_sha256"] = portable_digest(output)
            row["passed"] = equivalent(output, case["expected"])
        except Exception as error:
            # Arbitrary exception strings can leak qualification answers/data.
            row["error"] = type(error).__name__
        results.append(row)
    receipt = {"registration_sha256": record["sha256"], "stage": stage,
               "contract_sha256": record["contracts"][stage]["sha256"],
               "qualification_sha256": record["contracts"][stage]["qualification_sha256"],
               "candidate_sha256": candidate_sha256, "checker_sha256": checker_sha256,
               "checks": results, "total": len(results), "passed": sum(row["passed"] for row in results)}
    return {**receipt, "sha256": digest(receipt)}


def summarize_costs(rows):
    """Aggregate disjoint incurred costs; missing/unknown values stay unknown.

    Include failed attempts exactly once, under ``failed_attempts``. Numeric
    resource values are measured telemetry; monetary assumptions require an
    explicit ``basis`` and never become observed bills. A reported zero must
    itself have a basis. This record neither spends nor amortizes anything.
    """
    _need(isinstance(rows, list) and len(rows) <= len(STAGES), "Costs need at most one disjoint row per stage.")
    seen, known_money, assumptions, unknown_money = set(), 0, [], []
    metric_values = {key: [] for key in METRICS}
    unknown_metrics = {key: [] for key in METRICS}
    for row in rows:
        _need(isinstance(row, dict) and set(row) == {"stage", "metrics", "amount_minor", "basis", "note"},
              "A cost row needs stage, metrics, amount_minor, basis and note.")
        stage = row["stage"]
        _need(stage in STAGES and stage not in seen, "Cost stages must be valid and disjoint.")
        seen.add(stage)
        _text(row["note"], "Cost basis")
        _need(row["basis"] in {"measured", "assumed", "unknown"}, "Distinguish measured, assumed and unknown money.")
        amount = row["amount_minor"]
        _need(amount is None or (type(amount) is int and amount >= 0),
              "Money must be unknown or an exact nonnegative number of minor units.")
        _need((amount is None) == (row["basis"] == "unknown"),
              "Unknown monetary cost cannot silently become zero or a measured amount.")
        if amount is None:
            unknown_money.append(stage)
        else:
            known_money += amount
        if row["basis"] == "assumed":
            assumptions.append(stage)
        metrics = row["metrics"]
        _need(isinstance(metrics, dict) and not set(metrics) - set(METRICS), "Unknown resource metric.")
        for key in METRICS:
            value = metrics.get(key)
            if value is None:
                unknown_metrics[key].append(stage)
            else:
                _number(value, key)
                _need(key not in {"model_calls", "input_tokens", "output_tokens"} or type(value) is int,
                      "Call and token counts must be exact integers.")
                metric_values[key].append(value)
    missing = sorted(set(STAGES) - seen)
    for key in METRICS:
        unknown_metrics[key].extend(missing)
        _number(sum(metric_values[key]), "Total " + key)
    unknown_money.extend(missing)
    return {"known_cost_minor": known_money, "total_cost_minor": None if unknown_money else known_money,
            "measured_cost_minor": None if unknown_money or assumptions else known_money,
            "unknown_cost_stages": sorted(unknown_money), "assumed_cost_stages": sorted(assumptions),
            "missing_stages": missing,
            "resources": {key: None if unknown_metrics[key] else sum(metric_values[key]) for key in METRICS},
            "known_resources": {key: sum(metric_values[key]) for key in METRICS},
            "unknown_resource_stages": unknown_metrics}


def _qualification(record, stage, arm, *, passing=True):
    value = arm.get("qualification")
    if not isinstance(value, dict):
        return False
    payload = {key: item for key, item in value.items() if key != "sha256"}
    if value.get("sha256") != digest(payload):
        return False
    checks = value.get("checks")
    cases = record["spec"][stage]["qualification"]
    return (value.get("registration_sha256") == record["sha256"]
            and value.get("stage") == stage
            and value.get("contract_sha256") == record["contracts"][stage]["sha256"]
            and value.get("qualification_sha256") == record["contracts"][stage]["qualification_sha256"]
            and value.get("candidate_sha256") == arm.get("candidate_sha256")
            and isinstance(value.get("checker_sha256"), str) and bool(SHA.fullmatch(value["checker_sha256"]))
            and type(value.get("total")) is int and value["total"] == len(cases)
            and type(value.get("passed")) is int and 0 <= value["passed"] <= len(cases)
            and isinstance(checks, list) and len(checks) == len(cases)
            and value["passed"] == sum(row.get("passed") is True for row in checks if isinstance(row, dict))
            and (not passing or value["passed"] == len(cases))
            and all(isinstance(row, dict) and type(row.get("index")) is int and row["index"] == index
                    and type(row.get("passed")) is bool
                    and row.get("input_sha256") == digest(case["input"])
                    and row["passed"] == (row.get("error") is None
                                          and row.get("output_sha256") == portable_digest(case["expected"]))
                    and (row.get("error") is None or isinstance(row["error"], str))
                    and (row.get("output_sha256") is None or
                         (isinstance(row["output_sha256"], str) and SHA.fullmatch(row["output_sha256"])))
                    for index, (row, case) in enumerate(zip(checks, cases))))


def _review(value, record, *, distinct=False, stage=None):
    if not isinstance(value, dict):
        return False
    reviewer, builder = value.get("reviewer"), record["spec"]["comparison"]["inventor"]
    valid = (isinstance(reviewer, str) and reviewer.strip() and reviewer != builder
             and isinstance(value.get("evidence_sha256"), str) and SHA.fullmatch(value["evidence_sha256"])
             and isinstance(value.get("rationale"), str) and value["rationale"].strip()
             and value.get("origin") == "independent_review")
    if distinct:
        return bool(valid and value.get("different_objective") is True
                    and all(value.get(which + "_contract_sha256") == record["contracts"][which]["sha256"]
                            for which in ("first", "second")))
    return bool(valid and value.get("contract_sha256") == record["contracts"][stage]["sha256"]
                and value.get("observed_productive_use") is True)


def _sum(left, right):
    return None if left is None or right is None else left + right


def _difference(reference, candidate):
    return None if reference is None or candidate is None else reference - candidate


def adjudicate(registration, evidence, *, current_asset_sha256=None, current_source_sha256=None):
    """Audit complete denominators and report the narrowest supported claims.

    Missing conventional/human execution cannot be replaced by invented wages.
    One paired task can support an observed resource difference, not a general
    statistical claim. Monetary and productive-value findings remain separate.
    """
    record = _registration(registration)
    _need(isinstance(evidence, dict) and not set(evidence) - {"arms", "distinctness_review", "value_reviews"},
          "Provide arm receipts and attributed objective/value reviews.")
    arms = evidence.get("arms", {})
    _need(isinstance(arms, dict) and not set(arms) - set(ARMS), "Unknown comparison arm.")
    comparison, costs, issues, accepted, matched, live = record["spec"]["comparison"], {}, [], {}, {}, {}
    source_current = current_source_sha256 == comparison["source_sha256"]
    if not source_current:
        issues.append("Source identity is changed or has not been checked against current bytes.")
    for name, arm in arms.items():
        _need(isinstance(arm, dict), "An arm receipt must be an object.")
        _need(arm.get("origin") in {"live", "fixture", "developer"}, "Attribute live, fixture or developer construction.")
        _need(arm.get("status") in {"complete", "failed", "abstained", "interrupted"}, "Unknown arm status.")
        _sha(arm.get("trace_sha256"), "Arm trace")
        _need(type(arm.get("all_attempts_recorded")) is bool, "Report the complete attempt denominator.")
        _need(type(arm.get("human_interventions")) is int and arm["human_interventions"] >= 0,
              "Human interventions must be an explicit nonnegative count.")
        candidate = arm.get("candidate_sha256")
        _need(candidate is None or (isinstance(candidate, str) and SHA.fullmatch(candidate)), "Invalid candidate identity.")
        inherited = arm.get("retained_asset_sha256")
        _need(inherited is None or (isinstance(inherited, str) and SHA.fullmatch(inherited)), "Invalid retained asset identity.")
        stage = "first" if name in {"first", "first_conventional"} else "second"
        costs[name] = summarize_costs(arm.get("costs", []))
        accepted[name] = arm["status"] == "complete" and _qualification(record, stage, arm)
        matched[name] = (all(arm.get(key) == comparison[key] for key in IDENTITIES)
                         and arm.get("budget_sha256") == record["budget_sha256"]
                         and arm["all_attempts_recorded"])
        if name not in {"conventional", "first_conventional"}:
            matched[name] = matched[name] and arm.get("inventor") == comparison["inventor"]
        else:
            matched[name] = matched[name] and arm.get("inventor") == "human+conventional-software"
        for metric, bound in comparison["budget"].items():
            used = costs[name]["resources"][metric]
            if used is None or used > bound:
                matched[name] = False
        live[name] = arm["origin"] == "live"
        if not matched[name]:
            issues.append(name + ": comparison identity, denominator or registered resource bound does not match.")
        if not accepted[name]:
            issues.append(name + ": frozen independent qualification is not passed.")
        if arm["human_interventions"]:
            issues.append(name + ": includes human intervention; strict autonomous construction is unestablished.")
    first = arms.get("first", {})
    first_sha = first.get("candidate_sha256")
    asset_current = bool(first_sha and current_asset_sha256 == first_sha)
    if not asset_current:
        issues.append("Retained asset is missing, changed, or has not been checked against current bytes.")
    with_arm, without_arm = arms.get("with_asset", {}), arms.get("without_asset", {})
    inheritance = (bool(first_sha) and with_arm.get("retained_asset_sha256") == first_sha
                   and without_arm.get("retained_asset_sha256") is None
                   and bool(with_arm.get("candidate_sha256")) and with_arm["candidate_sha256"] != first_sha)
    if not inheritance:
        issues.append("Retained/no-retained isolation or a newly constructed second artifact is missing.")
    distinct = _review(evidence.get("distinctness_review"), record, distinct=True)
    if not distinct:
        issues.append("Different task names or test outputs do not establish a distinct useful objective; review remains missing.")
    value_reviews = evidence.get("value_reviews", {})
    _need(isinstance(value_reviews, dict) and not set(value_reviews) - {"first", "second"}, "Invalid value review stages.")
    useful = {stage: _review(value_reviews.get(stage), record, stage=stage) for stage in ("first", "second")}
    metric = comparison["metric"]
    resources = {name: value["resources"][metric] for name, value in costs.items()}
    first_plus_second = _sum(resources.get("first"), resources.get("with_asset"))
    incremental_gain = _difference(resources.get("without_asset"), resources.get("with_asset"))
    acquisition_gain = _difference(resources.get("without_asset"), first_plus_second)
    human_gain = _difference(resources.get("conventional"), resources.get("with_asset"))
    required_pair = ("first", "with_asset", "without_asset")
    matched_pair = all(matched.get(name) and live.get(name) for name in required_pair)
    qualified_pair = matched_pair and all(accepted.get(name) for name in required_pair)
    causal_ready = (matched_pair and accepted.get("first") and accepted.get("with_asset")
                    and source_current and asset_current and inheritance and distinct)
    # A failed control can support only an observed finite-budget difference,
    # after using its registered allowance. It is never assigned infinite cost.
    exhausted_control = (without_arm.get("status") == "failed"
                         and _qualification(record, "second", without_arm, passing=False)
                         and not _qualification(record, "second", without_arm)
                         and any(bound > 0 and costs.get("without_asset", {}).get("resources", {}).get(key) == bound
                                 for key, bound in comparison["budget"].items()))
    resource_gain = qualified_pair and incremental_gain is not None and incremental_gain > 0
    transfer = causal_ready and (resource_gain or exhausted_control)
    conventional = (accepted.get("conventional", False) and matched.get("conventional", False)
                    and live.get("conventional", False) and arms["conventional"].get("retained_asset_sha256") is None)
    monetary = {name: value["measured_cost_minor"] for name, value in costs.items()}
    episode_cost = _sum(monetary.get("first"), monetary.get("with_asset"))
    conventional_episode = _sum(monetary.get("first_conventional"), monetary.get("conventional"))
    episode_gain = _difference(conventional_episode, episode_cost)
    first_conventional = (accepted.get("first_conventional", False) and matched.get("first_conventional", False)
                          and live.get("first_conventional", False)
                          and arms["first_conventional"].get("retained_asset_sha256") is None)
    economic = (causal_ready and conventional and first_conventional and all(useful.values())
                and episode_gain is not None and episode_gain > 0)
    if "conventional" not in arms:
        issues.append("The competent human with conventional software comparison has not been run.")
    if "first_conventional" not in arms:
        issues.append("Complete two-outcome conventional acquisition costs are missing.")
    autonomy = (qualified_pair and source_current and all(arms[name]["human_interventions"] == 0 for name in required_pair)
                and all(costs[name]["resources"]["human_seconds"] == 0 for name in required_pair))
    verdicts = {
        "ENGINEERING_CORRECTNESS": "passed_recorded_checks" if all(accepted.get(name) for name in ("first", "with_asset")) else "not_established",
        "DISTINCT_SECOND_OBJECTIVE": "supported_by_recorded_review" if distinct else "not_established",
        "FIRST_USEFUL_OUTCOME": "supported_by_recorded_review" if accepted.get("first") and live.get("first") and useful["first"] else "not_established",
        "CAPABILITY_TRANSFER": "supported_by_recorded_comparison" if transfer else "not_established",
        "ACQUISITION_INCLUSIVE_RESOURCE_ADVANTAGE": "supported_by_recorded_comparison" if causal_ready and qualified_pair and acquisition_gain is not None and acquisition_gain > 0 else "not_established",
        "HUMAN_PRODUCTIVITY_COMPARISON": "supported_by_recorded_comparison" if causal_ready and conventional and human_gain is not None and human_gain > 0 else "not_established",
        "NET_MONETARY_BENEFIT": "supported_by_recorded_comparison" if economic else "not_established",
        "STRICT_AUTONOMOUS_CONSTRUCTION": "supported_by_recorded_trace" if autonomy else "not_established",
        "MONETIZATION": "not_established", "INVENTOR_IMPROVEMENT": "not_established",
    }
    return {"schema": SCHEMA + "/assessment", "registration_sha256": record["sha256"],
            "evidence_sha256": digest(evidence), "registered_arms": list(ARMS), "observed_arms": sorted(arms),
            "accepted": accepted, "matched": matched, "costs": costs, "verdicts": verdicts,
            "resource_comparison": {"metric": metric, "arm_totals": resources,
                "first_plus_second": first_plus_second, "incremental_second_saving": incremental_gain,
                "acquisition_inclusive_saving": acquisition_gain, "second_vs_human_saving": human_gain,
                "control_exhausted_registered_budget": bool(exhausted_control)},
            "monetary_comparison": {"currency": comparison["currency"], "measured_arm_totals_minor": monetary,
                "first_plus_second_minor": episode_cost, "conventional_two_outcomes_minor": conventional_episode,
                "two_outcome_saving_minor": episode_gain}, "issues": issues, "scope": SCOPE}


def mission_registration(state):
    """Freeze the mission's two independently registered contracts for comparison."""
    _need(isinstance(state, dict) and isinstance(state.get("runtime_identity"), dict),
          "The mission needs its recorded runtime identity before freezing comparison.")
    contracts = state.get("contracts", {})
    _need(all(stage in contracts for stage in ("first", "second")), "Register both mission contracts first.")
    clean = {stage: {key: copy.deepcopy(contracts[stage][key]) for key in
                    ("objective", "family", "acceptance", "development", "qualification")}
             for stage in ("first", "second")}
    route = state.get("route", {})
    _need(isinstance(route.get("provider"), str) and isinstance(route.get("model"), str), "Mission route is missing.")
    public_second = {key: value for key, value in clean["second"].items() if key != "qualification"}
    comparison = {"inventor": route["provider"] + ":" + route["model"],
        "source_sha256": digest(state.get("source_identity")),
        "environment_sha256": digest(state["runtime_identity"]),
        "information_sha256": digest(public_second), "budget": {"model_calls": state.get("max_attempts")},
        "metric": "model_calls", "currency": "CAD"}
    return register({**clean, "comparison": comparison})


def _recorded_qualification(registration, stage, build, *, frozen=True):
    """Recheck recorded actual answers, without executing or exposing holdouts."""
    raw = build.get("qualification")
    if not isinstance(raw, dict):
        return None
    cases = registration["spec"][stage]["qualification"]
    candidate = build.get("source_sha256")
    if (not isinstance(candidate, str) or not SHA.fullmatch(candidate)
            or raw.get("source_sha256") != candidate or raw.get("cases_sha256") != digest(cases)
            or type(raw.get("total")) is not int or raw["total"] != len(cases)
            or not isinstance(raw.get("cases"), list) or len(raw["cases"]) != len(cases)):
        return None
    source = build.get("source")
    if frozen and not isinstance(source, str):
        return None
    if source is not None and (not isinstance(source, str) or hashlib.sha256(source.encode()).hexdigest() != candidate):
        return None
    if frozen:
        freeze = build.get("frozen") or {}
        if (freeze.get("source_sha256") != candidate
                or freeze.get("qualification_sha256") != registration["contracts"][stage]["qualification_sha256"]):
            return None
    results = []
    for index, (observed, case) in enumerate(zip(raw["cases"], cases)):
        if (not isinstance(observed, dict) or observed.get("input_sha256") != digest(case["input"])
                or observed.get("expected_sha256") != digest(case["expected"])):
            return None
        error = observed.get("error")
        output_hash = portable_digest(observed["actual"]) if "actual" in observed else None
        passed = error is None and "actual" in observed and equivalent(observed["actual"], case["expected"])
        if observed.get("passed") is not passed:
            return None
        results.append({"index": index, "input_sha256": digest(case["input"]), "output_sha256": output_hash,
                        "passed": passed, "error": None if error is None else str(error.get("code", "EXECUTION_ERROR"))
                        if isinstance(error, dict) else "EXECUTION_ERROR"})
    count = sum(row["passed"] for row in results)
    if (type(raw.get("passed_count")) is not int or raw["passed_count"] != count
            or raw.get("passed") is not (count == len(cases))):
        return None
    receipt = {"registration_sha256": registration["sha256"], "stage": stage,
        "contract_sha256": registration["contracts"][stage]["sha256"],
        "qualification_sha256": registration["contracts"][stage]["qualification_sha256"],
        "candidate_sha256": candidate, "checker_sha256": digest(build.get("sources", {"origin": "recorded conventional check"})),
        "checks": results, "total": len(results), "passed": count}
    return {**receipt, "sha256": digest(receipt)}


def _observed_sum(items, key):
    values = [item.get(key) for item in items]
    return (sum(values) if all(type(value) in (int, float) and value >= 0 and math.isfinite(value)
                               for value in values) else None)


def _mission_costs(state, name, build):
    """Keep unmeasured work unknown; allocate each measured attempt only once."""
    rows = {stage: {"stage": stage, "metrics": {}, "amount_minor": None, "basis": "unknown",
                    "note": "This stage's complete resources and actual monetary cost are unmeasured."}
            for stage in STAGES}
    attempts = build.get("attempts", [])
    if not isinstance(attempts, list):
        return list(rows.values())
    successful = [attempt for attempt in attempts if attempt.get("status") == "development_passed"]
    failed = [attempt for attempt in attempts if attempt.get("status") != "development_passed"]
    for stage, group in (("construction", successful), ("failed_attempts", failed)):
        dispatches_known = all(attempt.get("dispatch") in {"completed", "not_dispatched"} for attempt in group)
        metrics = {"model_calls": sum(attempt.get("dispatch") == "completed" for attempt in group) if dispatches_known else None,
                   "input_tokens": _observed_sum([attempt.get("usage") or {} for attempt in group], "input_tokens"),
                   "output_tokens": _observed_sum([attempt.get("usage") or {} for attempt in group], "output_tokens")}
        model_wall = _observed_sum(group, "model_wall_seconds")
        development_wall = _observed_sum([attempt.get("development") or {} for attempt in group], "wall_seconds")
        metrics["wall_seconds"] = _sum(model_wall, development_wall)
        rows[stage].update(metrics=metrics, note="Recorded dispatches and model/development work only; model-host CPU, human work and money are unknown.")
    stage = "first" if name == "first" else "second"
    discoveries = [event for event in state.get("events", []) if event.get("kind") == "discovery" and event.get("stage") == stage]
    if discoveries:
        rows["discovery"]["metrics"] = {
            "model_calls": len(discoveries) if all(event.get("status") == "completed" for event in discoveries) else None,
            "input_tokens": _observed_sum([event.get("model_usage") or {} for event in discoveries], "input_tokens"),
            "output_tokens": _observed_sum([event.get("model_usage") or {} for event in discoveries], "output_tokens"),
            "wall_seconds": _observed_sum(discoveries, "wall_seconds")}
        rows["discovery"]["note"] = ("Recorded discovery work. Shared second discovery is charged equally to each comparison route; "
                                      "arm totals are counterfactual allocations, not an additive financial ledger.")
    qualification = build.get("qualification")
    if isinstance(qualification, dict):
        rows["verification"].update(metrics={"wall_seconds": qualification.get("wall_seconds"),
            "cpu_seconds": qualification.get("cpu_seconds"), "model_calls": 0, "input_tokens": 0, "output_tokens": 0},
            note="Recorded isolated qualification calls only; no model calls occur inside this verifier. Useful production remains separate.")
    return list(rows.values())


def _mission_origin(state, build):
    runtime = state.get("runtime_identity", {})
    if (build.get("provenance") == "fixture" or build.get("execution_provenance") == "fixture"
            or runtime.get("origin") == "fixture"):
        return "fixture"
    if (build.get("execution_provenance") == "live_local_model" and runtime.get("origin") == "live_local_model"
            and build.get("runtime_identity_sha256") == digest(runtime)
            and all(isinstance(runtime.get(key), str) and SHA.fullmatch(runtime[key])
                    for key in ("model_weights_sha256", "server_sha256"))):
        return "live"
    return "developer"


def mission_assessment(state, conventional=None, distinctness_review=None):
    """Convert actual HARNESS mission results into the common transfer audit.

    Generic configured-model responses do not attest live model provenance.
    Live attribution needs an explicit runtime weights identity and execution
    receipt; otherwise the engineering result remains developer/fixture evidence.
    Independent semantic/value review, missing resource stages, and a competent
    human baseline remain explicit gaps rather than hardcoded success flags.
    """
    fresh = mission_registration(state)
    registration = _registration(state.get("transfer_registration", fresh))
    _need(registration == fresh, "Mission contracts, runtime, source or comparison changed after registration.")
    comparison = registration["spec"]["comparison"]
    arms = {}
    for name, build in state.get("builds", {}).items():
        _need(name in {"first", "with_asset", "without_asset"}, "Unknown mission construction arm.")
        stage = "first" if name == "first" else "second"
        totals, attempts = build.get("totals", {}), build.get("attempts", [])
        qualification = _recorded_qualification(registration, stage, build)
        interrupted = build.get("status") in {"running", "registered", "model_pending", "qualification_pending", "interrupted_or_error"}
        identity = {key: comparison[key] for key in IDENTITIES}
        recorded_sources = build.get("sources")
        if (not isinstance(recorded_sources, dict) or not recorded_sources
                or any(state.get("source_identity", {}).get(key) != value for key, value in recorded_sources.items())):
            identity["source_sha256"] = digest({"unmatched_construction_sources": recorded_sources})
        if build.get("contract_sha256") != digest(state["contracts"][stage]):
            identity["information_sha256"] = digest({"unmatched_construction_contract": build.get("contract_sha256")})
        if build.get("route") != state.get("route"):
            identity["environment_sha256"] = digest({"unmatched_construction_route": build.get("route")})
        allocation = build.get("allocation", {})
        budget_sha = registration["budget_sha256"]
        if (allocation.get("max_attempts") != state.get("max_attempts")
                or allocation.get("max_output_tokens") != state.get("max_output_tokens")):
            budget_sha = digest({"unmatched_construction_allocation": allocation})
        arms[name] = {"origin": _mission_origin(state, build),
            "status": "interrupted" if interrupted else "complete" if build.get("qualified") is True else "failed",
            "inventor": comparison["inventor"], **identity,
            "budget_sha256": budget_sha, "candidate_sha256": build.get("source_sha256"),
            "retained_asset_sha256": build.get("retained_sha256"), "trace_sha256": digest(build),
            "all_attempts_recorded": isinstance(attempts, list) and type(totals.get("model_calls")) is int
                and totals["model_calls"] == len(attempts) and not interrupted
                and totals.get("unknown_dispatches") == 0,
            "human_interventions": len(build.get("interventions", [])), "qualification": qualification,
            "costs": _mission_costs(state, name, build)}
    if conventional is not None:
        _need(isinstance(conventional, dict), "Conventional result must be an object.")
        raw_costs = conventional.get("costs", {})
        rows = raw_costs.get("stages", []) if isinstance(raw_costs, dict) else []
        qualification = _recorded_qualification(registration, "second", conventional, frozen=False)
        arms["conventional"] = {"origin": "developer", "status": "complete" if qualification
            and qualification["passed"] == qualification["total"] else "failed",
            "inventor": "human+conventional-software", **{key: comparison[key] for key in IDENTITIES},
            "budget_sha256": registration["budget_sha256"], "candidate_sha256": conventional.get("source_sha256"),
            "retained_asset_sha256": None, "trace_sha256": digest(conventional), "all_attempts_recorded": False,
            "human_interventions": 0, "qualification": qualification, "costs": rows,
            "attribution": conventional.get("provenance"), "operator_recorded_costs": raw_costs}
    evidence = {"arms": arms, "distinctness_review": distinctness_review, "value_reviews": {}}
    first = state.get("builds", {}).get("first", {})
    asset = first.get("source")
    asset_sha = hashlib.sha256(asset.encode()).hexdigest() if isinstance(asset, str) else None
    # The service checks this before dispatch too; re-read current code rather
    # than treating the mission's stored source identity as current evidence.
    from .frontier_mission import source_identity
    result = adjudicate(registration, evidence, current_asset_sha256=asset_sha,
                        current_source_sha256=digest(source_identity()))
    result["recorded_evidence"] = evidence
    result["qualification_replay"] = "Recorded actual outputs checked against frozen answers; no candidate rerun."
    result["mission_cost_scope"] = ("Acquisition, integration, production, maintenance and complete human/model-host costs remain unknown. "
        "Shared discovery is allocated equally per comparison, never summed as revenue or account spending.")
    return result
