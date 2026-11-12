"""Bounded business-design search driving the authoritative connected enterprise.

This is an opt-in, conditional SIMULATED policy experiment, not another ledger.
All deliveries, buyer decisions, receipts, investments and obligations come from
connected_enterprise.engine.run_world and its independent native audit.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from .engine import default_config, validate_config

SCHEMA = "agi-alpha/native-design-search041/v1"
ALLOWED_ARMS = ("baseline", "channel", "growth", "competitive_growth")
POLICY_KEYS = frozenset(("strategic_policy", "strategic_allocation_policy",
                         "mechanism_policy", "channel_menu_policy"))
MICRO = 1_000_000


def example_spec():
    """Fixed exposed engineering fixture; no inferred real customer demand."""
    cfg = default_config()
    cfg.update(horizon_days=14, customer_pool=8, setup_cost=10*MICRO,
               arrival_bps=10000, retention_bps=10000, nonpayment_bps=0)
    cfg["channels"]["pilot"].update(price_microUSD=MICRO,
        activation_reliability_bps=10000, realization_bps=10000, overlap_bps=0)
    return {"schema": SCHEMA, "evidence_role": "exposed_development",
            "development_seed": 341014, "confirmation_seed": 341015,
            "service_cohort_seed": 341014, "config": cfg,
            "designs": [
                {"id": "incumbent", "arm": "baseline", "policies": {}},
                {"id": "earned_distribution", "arm": "growth", "policies": {}},
                {"id": "competitive_distribution", "arm": "competitive_growth", "policies": {}}
            ], "incumbent": "incumbent"}


def validate(spec):
    if not isinstance(spec, dict) or set(spec) != {
        "schema", "evidence_role", "development_seed", "confirmation_seed",
        "service_cohort_seed", "config", "designs", "incumbent"
    } or spec["schema"] != SCHEMA or spec["evidence_role"] not in {
        "exposed_development", "finite_authored_comparison"
    }:
        raise ValueError("EXACT_REGISTERED_DESIGN_EXPERIMENT_REQUIRED")
    seeds = [spec[k] for k in ("development_seed", "confirmation_seed", "service_cohort_seed")]
    if any(type(v) is not int or v < 0 for v in seeds) or seeds[0] == seeds[1]:
        raise ValueError("DISTINCT_NONNEGATIVE_DEVELOPMENT_AND_CONFIRMATION_SEEDS_REQUIRED")
    base = validate_config(spec["config"])
    if base != spec["config"]:
        raise ValueError("CANONICAL_UNMODIFIED_MARKET_CONFIGURATION_REQUIRED")
    if POLICY_KEYS.intersection(base):
        raise ValueError("DESIGN_POLICIES_MUST_BE_EXPLICIT_PER_CANDIDATE")
    ds = spec["designs"]
    if not isinstance(ds, list) or not 2 <= len(ds) <= 8:
        raise ValueError("BOUNDED_DESIGN_SEARCH_REQUIRED")
    names = set()
    for d in ds:
        if not isinstance(d, dict) or set(d) != {"id", "arm", "policies"}:
            raise ValueError("EXACT_DESIGN_OBJECT_REQUIRED")
        name = d["id"]
        if not isinstance(name, str) or not name.isascii() or not name or len(name) > 48 or not all(
            c.islower() or c.isdigit() or c in "-_" for c in name
        ) or name in names:
            raise ValueError("UNIQUE_SAFE_DESIGN_ID_REQUIRED")
        names.add(name)
        if d["arm"] not in ALLOWED_ARMS or not isinstance(d["policies"], dict) or not set(d["policies"]) <= POLICY_KEYS:
            raise ValueError("ONLY_AUTHORIZED_NATIVE_POLICY_ALTERNATIVES")
        cfg = copy.deepcopy(base)
        cfg.update(copy.deepcopy(d["policies"]))
        validate_config(cfg)
    if spec["incumbent"] not in names or next(d for d in ds if d["id"] == spec["incumbent"])["arm"] != "baseline":
        raise ValueError("STRONG_EXPLICIT_NATIVE_INCUMBENT_REQUIRED")
    canonical(spec)
    return copy.deepcopy(spec)


def _config(spec, design):
    cfg = copy.deepcopy(spec["config"])
    cfg.update(copy.deepcopy(design["policies"]))
    return validate_config(cfg)


def _covered(result):
    s = result["summary"]
    return (result["complete"] and s["payables"] == 0 and not s["investmentStopped"]
            and s["cash"] >= s["custodyReserve"] + s["tailReserve"] + s["workingCapital"])


def _margin(order):
    return order["price"] - order["complete_cost"]


def find_native_successor(result):
    """Find a profitable, earned-funded, source-linked successor in ONE account.

    Incremental value is actually collected *order contribution* less the native
    acquisition/capacity invoice, not an assumed better first-order margin.
    Enterprise-wide complete-cost profit and independent audit are separate gates.
    """
    settled = sorted((o for o in result["orders"]
                      if o["outcome"] == "SETTLED" and o["collection_time"] is not None
                      and o["acceptance_time"] is not None and _margin(o) > 0),
                     key=lambda o: (o["collection_time"], o["id"]))
    relevant_investments = [i for i in result["investments"]
                            if i["kind"] in ("acquisition", "capacity")]
    by_plan = {i["plan_id"]: i for i in relevant_investments}
    if len(by_plan) != len(relevant_investments):
        raise ValueError("DUPLICATE_NATIVE_PLAN_INVENTORY")
    # Attribute a joint native enabling package over its entire connected
    # source-plan component, including failed work using a shared enabler.
    # Charging a companion invoice but silently omitting its other losses
    # can otherwise convert a losing joint arrangement into a positive witness.
    links_by_order = []
    orders_for_plan = {}
    for index, order in enumerate(result["orders"]):
        extra = order.get("capacity_source_plan_ids", [])
        if not isinstance(extra, list):
            raise ValueError("INVALID_NATIVE_ORDER_PLAN_LINKS")
        raw = [order.get("acquisition_source_plan_id"),
               order.get("capacity_source_plan_id"), *extra]
        if any(p is not None and (not isinstance(p, str) or not p) for p in raw):
            raise ValueError("INVALID_NATIVE_ORDER_PLAN_LINKS")
        plans = frozenset(p for p in raw if p is not None)
        links_by_order.append(plans)
        for plan in sorted(plans):
            orders_for_plan.setdefault(plan, []).append(index)
    witnesses = []
    for investment in relevant_investments:
        if investment["kind"] not in ("acquisition", "capacity"):
            continue
        if investment["funding_receipt"].get("funding") != "EARNED":
            continue
        def linked(order):
            if investment["kind"] == "acquisition":
                return order.get("acquisition_source_plan_id") == investment["plan_id"]
            return (order.get("capacity_source_plan_id") == investment["plan_id"]
                    or investment["plan_id"] in order.get("capacity_source_plan_ids", []))
        direct_orders = [o for o in result["orders"] if linked(o)]
        successors = [o for o in settled if linked(o)
                      and o["qualified_time"] >= investment["activation_time"]
                      and o["collection_time"] > investment["purchased_time"]]
        if not successors or any(o["qualified_time"] < investment["activation_time"]
                                 for o in direct_orders):
            continue
        required_plans = set()
        reached_order_indices = set()
        pending = [investment["plan_id"]]
        while pending:
            plan = pending.pop()
            if plan in required_plans:
                continue
            required_plans.add(plan)
            for index in orders_for_plan.get(plan, ()):
                if index in reached_order_indices:
                    continue
                reached_order_indices.add(index)
                pending.extend(sorted(links_by_order[index] - required_plans))
        linked_orders = [result["orders"][i] for i in sorted(reached_order_indices)]
        if any(p not in by_plan or by_plan[p]["funding_receipt"].get("funding") != "EARNED"
               for p in required_plans):
            continue
        paid_contribution = sum(_margin(o) for o in linked_orders
                                if o["outcome"] == "SETTLED" and o["collection_time"] is not None)
        uncollected_cost = sum(o["complete_cost"] for o in linked_orders
                               if o["outcome"] != "SETTLED" or o["collection_time"] is None)
        scoped_contribution = paid_contribution - uncollected_cost
        total_invoices = sum(by_plan[p]["cost"] for p in required_plans)
        net = scoped_contribution - total_invoices
        for first in settled:
            if first["collection_time"] >= investment["purchased_time"]:
                continue
            new = [o for o in successors
                   if o["customer_id"] != first["customer_id"]
                   or o["offer"]["service_id"] != first["offer"]["service_id"]]
            if not new:
                continue
            second = new[0]
            witnesses.append({
                "first_paid_order": first["id"], "first_service": first["offer"]["service_id"],
                "first_collection_hour": first["collection_time"],
                "first_margin_microUSD": _margin(first),
                "binding_constraint_changed": "customer_access" if investment["kind"] == "acquisition" else "productive_capacity",
                "native_investment": investment["id"], "native_plan_id": investment["plan_id"],
                "investment_time": investment["purchased_time"], "investment_cost_microUSD": investment["cost"],
                "all_required_native_plan_ids": sorted(required_plans),
                "source_link_scope": "COMPLETE_CONNECTED_NATIVE_ENABLER_COMPONENT",
                "all_required_invoices_microUSD": total_invoices,
                "funding": "EARNED", "successor_paid_order": second["id"],
                "successor_service": second["offer"]["service_id"],
                "successor_customer": second["customer_id"],
                "successor_collection_hour": second["collection_time"],
                "successor_margin_microUSD": _margin(second),
                "source_linked_paid_order_ids": [o["id"] for o in linked_orders if o["outcome"] == "SETTLED"],
                "source_linked_uncollected_order_ids": [o["id"] for o in linked_orders if o["outcome"] != "SETTLED"],
                "source_linked_total_order_contribution_microUSD": scoped_contribution,
                "net_after_native_investment_microUSD": net,
                "distinct_opportunity": True,
                "positive_incremental_collected_contribution": net > 0,
                "strictly_better_per_order_margin": _margin(second) > _margin(first),
                "source_link_type": investment["kind"],
                "scope": "CONSERVATIVE_SOURCE_LINKED_CONTRIBUTION_NOT_CAUSAL_UPLIFT"
            })
    witnesses.sort(key=lambda w: (
        not w["positive_incremental_collected_contribution"],
        -w["net_after_native_investment_microUSD"],
        w["investment_time"], w["first_paid_order"], w["successor_paid_order"]))
    return witnesses[0] if witnesses else None


def _observed(result):
    s = result["summary"]
    constraints = {
        "unreached_buyers": sum(not b["known"] for b in result["buyers"]),
        "unserved_buyers": sum(b["purchases"] == 0 for b in result["buyers"]),
        "capacity_declines": sum(d.get("kind") == "capacity_decline" for d in result["decisions"]),
        "inventory_declines": sum(d.get("kind") == "inventory_decline" for d in result["decisions"]),
        "rival_choices": sum(d.get("buyer_choice") == "rival" for d in result["decisions"]),
        "nonpayment_or_rejected": sum(o["outcome"] in ("REFUNDED", "QUALITY_REJECTED") for o in result["orders"]),
    }
    return {"audit_required": True, "constraints": constraints, "complete": result["complete"], "obligations_covered": _covered(result),
            "profit_microUSD": s["profit"], "available_microUSD": s["available"],
            "unrestricted_earned_microUSD": s["unrestrictedEarned"],
            "settled_orders": result["paid_jobs"], "accepted_orders": result["accepted_jobs"],
            "customers": result["customers"], "repeat_customers": result["repeat_customers"],
            "source_linked_successor": find_native_successor(result)}



def discover_applicable_designs(spec, baseline):
    """Discover a binding constraint from independently audited, actual native results.

    This constructs an executable *subset* of the registered design grammar.
    A marketing hypothesis, solver forecast, or hidden buyer draw cannot nominate
    an intervention. Existing policy capabilities are not claimed novel inventions.
    """
    if baseline.get("audit_accepted") is not True:
        raise ValueError("AUDITED_INCUMBENT_REQUIRED_FOR_DISCOVERY")
    observed = baseline["observed"]
    conditions = observed["constraints"]
    required = {"unreached_buyers", "unserved_buyers", "capacity_declines",
                "inventory_declines", "rival_choices", "nonpayment_or_rejected"}
    if set(conditions) != required or any(type(v) is not int or v < 0 for v in conditions.values()):
        raise ValueError("COMPLETE_NONNEGATIVE_AUDITED_CONSTRAINTS_REQUIRED")
    profitable = (observed["obligations_covered"] and observed["settled_orders"] > 0
                  and observed["profit_microUSD"] > 0
                  and observed["unrestricted_earned_microUSD"] > 0)
    diagnosed = []
    if conditions["unreached_buyers"] and profitable:
        diagnosed.append("customer_access")
    if conditions["capacity_declines"] and profitable:
        diagnosed.append("production_capacity")
    if conditions["rival_choices"]:
        diagnosed.append("competitive_buyer_choice")
    if conditions["inventory_declines"]:
        diagnosed.append("finite_qualified_work_inventory")
    if conditions["nonpayment_or_rejected"]:
        diagnosed.append("acceptance_or_collection_risk")
    if not profitable:
        diagnosed.append("unproven_funded_surplus")
    if not diagnosed:
        diagnosed.append("no_demonstrated_binding_constraint")
    admitted = [spec["incumbent"]]
    evidence = []
    for d in spec["designs"]:
        if d["id"] == spec["incumbent"]:
            continue
        arm = d["arm"]
        remedy = None
        if arm in ("growth", "channel") and (
            "customer_access" in diagnosed or "production_capacity" in diagnosed
        ):
            remedy = ("costed_earned_funded_customer_access" if "customer_access" in diagnosed
                      else "costed_earned_funded_productive_capacity")
        elif arm == "competitive_growth" and (
            "competitive_buyer_choice" in diagnosed or "customer_access" in diagnosed
            or "production_capacity" in diagnosed
        ):
            remedy = "buyer_response_plus_earned_constraint_removal"
        elif "strategic_policy" in d["policies"] and "competitive_buyer_choice" in diagnosed:
            remedy = "finite_public_price_and_execution_method"
        if remedy is not None:
            admitted.append(d["id"])
            evidence.append({"design": d["id"], "native_arm": arm, "proposed_remedy": remedy})
    return {
        "schema": "agi-alpha/native-constraint-discovery041/v1",
        "incumbent_observed_sha256": digest(observed),
        "diagnosed_constraints": diagnosed,
        "declared_candidate_remedies": evidence,
        "selected_development_ids": admitted,
        "bounded_method": "Causal opportunity diagnosis over actually audited public native state; only pre-authorized executable native interventions.",
        "limits": "No new market demand, unknown customer valuation, solver invention, claim of universally binding cause, or current action authority created."
    }

def choose_from_development(spec, development):
    """Use ONLY recorded native development results to choose an incumbent or challenger.

    No optimistic forecast, invented demand or promotion from unqualified accounts.
    """
    if spec["incumbent"] not in development or set(development) - {d["id"] for d in spec["designs"]}:
        raise ValueError("REGISTERED_AUDITED_DEVELOPMENT_REQUIRED")
    rows = []
    for d in spec["designs"]:
        if d["id"] not in development:
            continue
        r = development[d["id"]]["observed"]
        if not development[d["id"]]["audit_accepted"]:
            raise ValueError("INDEPENDENT_NATIVE_AUDIT_REQUIRED_FOR_SELECTION")
        feasible = r["obligations_covered"] and r["profit_microUSD"] > 0
        rows.append((r["profit_microUSD"] if feasible else None, d["id"]))
    incumbent = spec["incumbent"]
    candidates = [(profit, name) for profit, name in rows if profit is not None]
    if not candidates:
        return {"selected": None, "reason": "NO_FUNDED_POSITIVE_PROFIT_DESIGN",
                "observed_ranking": [list(row) for row in sorted(rows, key=lambda r: r[1])]}
    candidates.sort(key=lambda r: (-r[0], 0 if r[1] == incumbent else 1, r[1]))
    return {"selected": candidates[0][1],
            "reason": "MAXIMUM_OBSERVED_PROTECTED_COMPLETE_COST_PROFIT_IN_DECLARED_DEVELOPMENT_WORLD",
            "observed_ranking": [list(row) for row in sorted(rows, key=lambda r: (r[0] is None, -(r[0] or 0), r[1]))]}


def _heldout_recommendation(spec, selected, challenger, incumbent, delta):
    """Holdout veto for a development winner; never authorizes a native action."""
    distinct = selected is not None and selected != spec["incumbent"]
    incumbent_viable = bool(incumbent and incumbent["observed"]["obligations_covered"]
                            and incumbent["observed"]["profit_microUSD"] > 0)
    challenger_accepted = bool(
        distinct and challenger and challenger["observed"]["obligations_covered"]
        and challenger["observed"]["profit_microUSD"] > 0
        and delta is not None and delta > 0)
    recommended = (selected if challenger_accepted else
                   spec["incumbent"] if incumbent_viable else None)
    return {
        "development_candidate": selected if distinct else None,
        "recommended_policy": recommended,
        "challenger_accepted": challenger_accepted,
        "reason": ("POSITIVE_MATCHED_HOLDOUT_CHALLENGER" if challenger_accepted else
                   "KEEP_VIABLE_INCUMBENT" if incumbent_viable else
                   "NO_SUPPORTED_PROFITABLE_POLICY"),
        "evidence_scope": "ONE_FROZEN_SIMULATED_HOLDOUT_NO_GENERAL_CAUSAL_CLAIM",
        "native_financial_action_authority": [],
    }


def _public(spec, source, development, selection, confirmation, discovery):
    selected = selection["selected"]
    challenger = confirmation.get(selected) if selected else None
    incumbent = confirmation.get(spec["incumbent"])
    if challenger is not None and incumbent is not None:
        delta = challenger["observed"]["profit_microUSD"] - incumbent["observed"]["profit_microUSD"]
    else:
        delta = None
    witness = challenger["observed"]["source_linked_successor"] if challenger else None
    holdout = _heldout_recommendation(spec, selected, challenger, incumbent, delta)
    funded_successor_exists = bool(witness and witness["positive_incremental_collected_contribution"] and
                                   challenger["observed"]["obligations_covered"] and
                                   challenger["observed"]["profit_microUSD"] > 0)
    retained_successor = funded_successor_exists and holdout["challenger_accepted"]
    return {
        "schema": SCHEMA, "status": "CONDITIONAL_SIMULATED_EXECUTION",
        "source_sha256": source["sha256"], "spec_sha256": digest(spec),
        "discovered_binding_constraints": discovery,
        "development": {d["id"]: development[d["id"]]["observed"] for d in spec["designs"] if d["id"] in development},
        "selection": selection,
        "heldout_recommendation": holdout,
        "confirmation": {k: v["observed"] for k, v in sorted(confirmation.items())},
        "matched_confirmation_profit_delta_microUSD": delta,
        "connected_earned_successor_witness": witness,
        "confirmed_positive_funded_successor_opportunity": funded_successor_exists,
        "comparative_advantage_on_one_fresh_seed": holdout["challenger_accepted"],
        "retained_mechanism": ({
            "id": "observed-funded-channel-or-capacity",
            "applicability": "Positive collected native margin, available earned funds, eligible unserved buyer or unmet capacity, checked current obligations",
            "avoid": "No profitable proven demand, inadequate available cash, exhausted contacts, negative net expansion or unresolved obligations",
            "native_evidence": witness, "diagnostic_provenance_sha256": digest(discovery),
            "selected_executable_policy": selected,
            "execution_authority": [], "current_proof": None,
            "scope": "Candidate lesson, not qualified autonomous invention or general causal strategy advantage"
        } if retained_successor else None),
        "limits": [
            "Exposed/finitely authored buyer values, costs, demand, channel and competitor assumptions; no real buyers or collections.",
            "Three current native digital services; only enumerated executable native policies, not open-ended business design invention.",
            "Development selection is adaptive; one fresh confirmation seed does not establish statistical superiority or an equilibrium.",
            "The native successor linkage is a funding/access mechanism witness, not a causal ablation or proof of generative invention.",
            "Experimenter compute, provider/host billing and generalization costs are not all measured; no complete real-world profitability claim.",
            "Each world owns its own native account; development/holdout accounts and revenues are never pooled.",
            "No arbitrary revenue annualization or simulated money authorizes external spending."
        ]
    }


def _store(path, data):
    atomic_bytes(path, canonical(data) + b"\n")


def _load(path):
    return strict_json(path.read_bytes())


def _run_one(root, manifest, source, config, seed, arm, output):
    from .engine import run_world
    from .verify import audit
    result = run_world(root, manifest, config, seed, arm, output, source=source)
    if not result["complete"]:
        raise ValueError("FULL_NATIVE_OPERATING_HORIZON_REQUIRED")
    receipt = audit(root, manifest, result)
    if not receipt.get("accepted"):
        raise ValueError("INDEPENDENT_NATIVE_AND_SERVICE_AUDIT_FAILED")
    _store(output / "AUDIT.json", receipt)
    return {"audit_accepted": True, "result_sha256": digest(result), "observed": _observed(result)}


def execute(spec, root, output):
    """Run development, select from observations, then independently execute fresh cases."""
    from .runner import identity
    from adaptive_enterprise.instruments import prepare_services
    spec = validate(spec)
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise FileExistsError("FRESH_NON_SYMLINK_OUTPUT_REQUIRED")
    output.mkdir(parents=True)
    source = identity(root)
    _store(output / "SPEC.json", spec)
    _store(output / "SOURCE.json", source)
    manifest = prepare_services(root, "service-inputs", cohort_seed=spec["service_cohort_seed"])
    _store(output / "SERVICES.json", manifest)
    incumbent = next(d for d in spec["designs"] if d["id"] == spec["incumbent"])
    development = {spec["incumbent"]: _run_one(root, manifest, source, _config(spec, incumbent),
        spec["development_seed"], incumbent["arm"], output / ("dev-" + incumbent["id"]))}
    discovery = discover_applicable_designs(spec, development[spec["incumbent"]])
    for name in discovery["selected_development_ids"][1:]:
        d = next(x for x in spec["designs"] if x["id"] == name)
        development[name] = _run_one(root, manifest, source, _config(spec, d),
            spec["development_seed"], d["arm"], output / ("dev-" + name))
    selection = choose_from_development(spec, development)
    confirmation = {}
    if selection["selected"] is not None:
        names = sorted(set((spec["incumbent"], selection["selected"])))
        for name in names:
            d = next(x for x in spec["designs"] if x["id"] == name)
            confirmation[name] = _run_one(root, manifest, source, _config(spec, d),
                spec["confirmation_seed"], d["arm"], output / ("confirm-" + name))
    public = _public(spec, source, development, selection, confirmation, discovery)
    _store(output / "PUBLIC.json", public)
    _store(output / "INDEX.json", {"schema": SCHEMA,
        "source_sha256": source["sha256"], "spec_sha256": digest(spec),
        "discovery_sha256": digest(discovery),
        "development": development, "confirmation": confirmation,
        "public_sha256": digest(public)})
    return public


def verify(root, output):
    """Re-audit exact native accounts and recalculate the whole selection and witness."""
    from .runner import identity
    from .verify import audit
    root, output = Path(root).resolve(), Path(output).resolve()
    spec = validate(_load(output / "SPEC.json"))
    source, index = _load(output / "SOURCE.json"), _load(output / "INDEX.json")
    if source != identity(root) or index.get("source_sha256") != source["sha256"] or index.get("spec_sha256") != digest(spec):
        raise ValueError("EXECUTING_SOURCE_OR_SPEC_CHANGED")
    manifest = _load(output / "SERVICES.json")

    def one(label, entry, d, seed):
        result = _load(output / label / "RESULT.json")
        if (result["source"] != source or result["config"] != _config(spec, d) or
                result["seed"] != seed or result["arm"] != d["arm"] or not result["complete"] or
                entry["result_sha256"] != digest(result)):
            raise ValueError("FROZEN_NATIVE_RESULT_BINDING_CHANGED")
        receipt = audit(root, manifest, result)
        if not receipt.get("accepted") or _load(output / label / "AUDIT.json") != receipt:
            raise ValueError("INDEPENDENT_NATIVE_AUDIT_RECEIPT_CHANGED")
        expected = {"audit_accepted": True, "result_sha256": digest(result), "observed": _observed(result)}
        if entry != expected:
            raise ValueError("OBSERVED_DESIGN_RESULT_CHANGED")
        return expected

    incumbent = next(d for d in spec["designs"] if d["id"] == spec["incumbent"])
    development = {spec["incumbent"]: one("dev-" + incumbent["id"],
        index["development"][incumbent["id"]], incumbent, spec["development_seed"])}
    discovery = discover_applicable_designs(spec, development[spec["incumbent"]])
    if (index.get("discovery_sha256") != digest(discovery) or
            set(index["development"]) != set(discovery["selected_development_ids"])):
        raise ValueError("DISCOVERED_INTERVENTION_SET_CHANGED")
    for name in discovery["selected_development_ids"][1:]:
        d = next(x for x in spec["designs"] if x["id"] == name)
        development[name] = one("dev-" + name, index["development"][name], d,
                                spec["development_seed"])
    selection = choose_from_development(spec, development)
    names = sorted(set((spec["incumbent"], selection["selected"]))) if selection["selected"] else []
    if set(index["confirmation"]) != set(names):
        raise ValueError("REQUIRED_MATCHED_NATIVE_WORLDS_CHANGED")
    confirmation = {}
    for name in names:
        d = next(x for x in spec["designs"] if x["id"] == name)
        confirmation[name] = one("confirm-" + name, index["confirmation"][name], d,
                                 spec["confirmation_seed"])
    public = _public(spec, source, development, selection, confirmation, discovery)
    if public != _load(output / "PUBLIC.json") or index["public_sha256"] != digest(public):
        raise ValueError("STRATEGIC_SELECTION_OR_SUCCESSOR_WITNESS_CHANGED")
    return public


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run the fixed exposed native-design experiment")
    demo.add_argument("--output", required=True)
    run = sub.add_parser("run", help="Run an explicitly registered design experiment")
    run.add_argument("--spec", required=True)
    run.add_argument("--output", required=True)
    check = sub.add_parser("verify", help="Independently re-audit and rederive the report")
    check.add_argument("--output", required=True)
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    if args.command == "verify":
        public = verify(root, args.output)
    else:
        public = execute(example_spec() if args.command == "demo" else _load(Path(args.spec)),
                         root, args.output)
    print(json.dumps({
        "source_sha256": public["source_sha256"], "selected": public["selection"]["selected"],
        "heldout_recommendation": public["heldout_recommendation"]["recommended_policy"],
        "heldout_profit_delta_microUSD": public["matched_confirmation_profit_delta_microUSD"],
        "funded_successor": public["connected_earned_successor_witness"],
        "better_opportunity": public["confirmed_positive_funded_successor_opportunity"],
        "actual_commerce": False, "scope": public["status"]
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
