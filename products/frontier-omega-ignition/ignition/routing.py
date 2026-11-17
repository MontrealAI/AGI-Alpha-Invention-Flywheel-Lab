"""Choose execution using the operator's contract, available means and marginal decision value."""
from __future__ import annotations

from math import isfinite
import re

from . import construction


def validate_options(resources):
    strategy = resources.get("execution_strategy", "adaptive")
    if strategy not in ("adaptive", "direct", "research"):
        raise ValueError("execution_strategy must be adaptive, direct or research")
    if "direct_method" in resources and resources["direct_method"] not in ("specialist", "model"):
        raise ValueError("direct_method must be specialist or model")
    if "direct_after_research" in resources and type(resources["direct_after_research"]) is not bool:
        raise ValueError("direct_after_research must be a boolean")
    for name in ("max_repairs", "max_model_calls"):
        if name in resources and (type(resources[name]) is not int or resources[name] < 0):
            raise ValueError(f"{name} must be a nonnegative integer")
    estimate = resources.get("research_economics")
    if "research_economics" in resources:
        if (type(estimate) is not dict or set(estimate) != {"unit", "decision_value", "marginal_cost"}
                or not isinstance(estimate["unit"], str) or not estimate["unit"].strip()
                or any(type(estimate[k]) not in (float, int) or (type(estimate[k]) is float and not isfinite(estimate[k])) or estimate[k] < 0
                       for k in ("decision_value", "marginal_cost"))):
            raise ValueError("research_economics needs a shared unit, nonnegative decision_value and marginal_cost")


# These are observable effects the two data-only languages cannot perform. This
# deliberately conservative detector is not a general natural-language verifier.
EXTERNAL_EFFECT = re.compile(
    r"\b(?:physically (?:qualify|measure|test|inspect)|"
    r"(?:measure|qualify|test|certify) (?:the |actual |real |physical |calibrated )*"
    r"(?:force|load capacity|physical wear|blood pressure|temperature in the field)|"
    r"(?:send|email|publish|deploy|purchase|charge|pay|sign) "
    r"(?:the |a |an |all |our |each |every )*(?:customer|vendor|supplier|email|invoice|"
    r"payment|release to production|artifact to production|contract))\b", re.I)


def uncovered_effect(mission):
    for field in [*mission["requirements"], mission["purpose"]]:
        for clause in re.split(r"[.;!?]|\b(?:and|but|then)\b", field):
            match = EXTERNAL_EFFECT.search(clause)
            if match and not re.search(r"\b(?:not|never|avoid|without)\b", clause[:match.start()], re.I):
                return match.group(0)
    return None


def route(mission):
    resources = mission["resources"]
    strategy = resources.get("execution_strategy", "adaptive")
    spec = mission.get("construction_spec", {})
    kind = spec.get("kind")
    supported = kind in construction.KINDS
    # An invalid supplied contract must never trigger paid effort or an unrelated reconstruction.
    if supported:
        construction.freeze_contract(spec)
    exact = supported and "demonstrations" not in spec["definition"]
    method = resources.get("direct_method") or ("specialist" if exact and strategy == "adaptive" else "model")
    estimate = resources.get("research_economics")
    constraints = {k: v for k, v in resources.items() if k in ("max_model_calls", "max_repairs", "budget", "assets")}
    baseline = {"record_migration": "A conventional schema mapping or example-based enumerator",
                "manifest_audit": "A pinned digest inventory and a standard file comparison"}.get(kind)
    interpretation = {"outcome": mission["purpose"], "beneficiary": mission["beneficiary"],
                      "requirements": mission["requirements"], "permissions": mission["authority"],
                      "constraints": constraints, "time": mission["time"], "existing_alternative": baseline,
                      "acceptance_cases": len(spec["cases"]) if supported else 0,
                      "acceptance_scope": "Frozen software cases and declared operations. Additional free-text objectives require separately established coverage.",
                      "obstruction": None if supported else "No frozen supported software contract for this objective."}
    uncovered = uncovered_effect(mission) if supported else None
    if uncovered:
        interpretation["obstruction"] = f"The bounded software cannot observe the requested action: {uncovered}."
        action = "clarify"
        reason = interpretation["obstruction"] + " Clarify the intended software-only outcome or supply independent evidence for a different investigation."
    elif strategy == "research":
        action = "research"
        reason = "The operator requested a frontier investigation and comparison of complete routes."
    elif supported and (method != "specialist" or exact):
        action = "direct"
        reason = ("The operator supplied exact executable operations. Compile them locally without model inference."
                  if method == "specialist" else "The supplied software contract can be attempted and checked directly.")
    elif strategy == "direct" or (supported and method == "specialist"):
        action = "clarify"
        reason = ("The exact-specification specialist needs declared operations. Select the model to infer a mapping."
                  if supported else "Supply a supported, purpose-bound specification with independent acceptance cases, or select frontier research.")
    elif estimate and estimate["decision_value"] <= estimate["marginal_cost"]:
        action = "clarify"
        reason = "The operator's estimated decision value does not cover the stated marginal research cost. Clarify a cheaper decisive test."
    elif not mission["requirements"] and not mission["beneficiary"] and not spec:
        action = "clarify"
        reason = "Who will use the result, and what observation would show that their objective was met?"
    else:
        action = "research"
        reason = "The available contract does not yet determine a verified construction. Investigate missing means, alternatives and a decisive test."
    return {"strategy": strategy, "route": action, "method": method if action == "direct" else None,
            "reason": reason, "interpretation": interpretation, "research_economics": estimate,
            "cost_basis": "Operator estimate" if estimate else "Complete marginal cost and monetary decision value unmeasured"}


def direct_selection(mission, choice):
    return {"decision": "build", "decision_reason": choice["reason"], "kind": mission["construction_spec"]["kind"],
            "selected": {"title": "Direct construction", "outcome": mission["purpose"],
                         "alternative": choice["interpretation"]["existing_alternative"]},
            "candidates": [], "signals": [], "objections": [], "fit": [],
            "mechanisms": [{"name": "strategic invention", "action": "Use the specified outcome as the direct acceptance target",
                            "result": {"discovery_calls": 0, "method": choice["method"]}}],
            "frontier": {"status": "unresolved", "reason": "No earlier/later capability comparison was run."},
            "research_performed": False}


def diagnostic(contract, artifact, receipt):
    """Expose actionable development evidence while keeping all held-out names, answers and inputs private."""
    failed = {}
    for case in receipt["cases"]:
        if not case["candidate_pass"]:
            group = case["group"]
            failed[group] = failed.get(group, 0) + 1
    details = {"failed_check_counts": failed,
               "declared_program_conforms": receipt["declared_program_conforms"],
               "oracles_agree": receipt["comparison"]["oracles_agree"]}
    if not details["declared_program_conforms"]:
        if artifact["kind"] == "manifest_audit":
            pinned = contract["spec"]["definition"]["manifest"]
            proposed = artifact["program"]["manifest"]
            details["public_specification_mismatches"] = sorted(k for k in pinned if pinned[k] != proposed.get(k))
            details["repair_instruction"] = "Use the trusted manifest binding from the supplied definition."
        else:
            details["repair_instruction"] = "Compare every declared source, target, conversion and extra-field rule with the public definition."
    elif failed:
        details["repair_instruction"] = "Check the development mapping, types, field policy and refusal behavior against the public specification."
    return details
