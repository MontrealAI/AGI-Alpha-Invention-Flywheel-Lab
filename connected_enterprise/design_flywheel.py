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
    """Find earned-funded, source-linked successor delivery in ONE account.

    Does not assert causality or reconstruct a hypothetical cash balance.
    Actual funding and acceptance are independently checked before calling.
    """
    settled = sorted((o for o in result["orders"]
                      if o["outcome"] == "SETTLED" and o["collection_time"] is not None
                      and o["acceptance_time"] is not None and _margin(o) > 0),
                     key=lambda o: (o["collection_time"], o["id"]))
    witnesses = []
    for investment in result["investments"]:
        if investment["kind"] not in ("acquisition", "capacity"):
            continue
        receipt = investment["funding_receipt"]
        if receipt.get("funding") != "EARNED":
            continue
        for first in settled:
            if first["collection_time"] >= investment["purchased_time"]:
                continue
            for second in settled:
                link = (second.get("acquisition_source_plan_id") == investment["plan_id"]
                        if investment["kind"] == "acquisition"
                        else second.get("capacity_source_plan_id") == investment["plan_id"]
                        or investment["plan_id"] in second.get("capacity_source_plan_ids", []))
                if (not link or second["qualified_time"] < investment["activation_time"]
                        or second["collection_time"] <= investment["purchased_time"]):
                    continue
                new_outcome = (second["customer_id"] != first["customer_id"]
                               or second["offer"]["service_id"] != first["offer"]["service_id"])
                better = _margin(second) > _margin(first)
                if not new_outcome:
                    continue
                witnesses.append({
                    "first_paid_order": first["id"], "first_service": first["offer"]["service_id"],
                    "first_collection_hour": first["collection_time"],
                    "first_margin_microUSD": _margin(first),
                    "binding_constraint_changed": "customer_access" if investment["kind"] == "acquisition" else "productive_capacity",
                    "native_investment": investment["id"], "native_plan_id": investment["plan_id"],
                    "investment_time": investment["purchased_time"], "investment_cost_microUSD": investment["cost"],
                    "funding": "EARNED", "successor_paid_order": second["id"],
                    "successor_service": second["offer"]["service_id"],
                    "successor_customer": second["customer_id"],
                    "successor_collection_hour": second["collection_time"],
                    "successor_margin_microUSD": _margin(second),
                    "distinct_opportunity": new_outcome,
                    "strictly_better_per_order_margin": better,
                    "source_link_type": investment["kind"]
                })
    witnesses.sort(key=lambda w: (
        not w["strictly_better_per_order_margin"], -w["successor_margin_microUSD"],
        w["investment_time"], w["first_paid_order"], w["successor_paid_order"]))
    return witnesses[0] if witnesses else None


def _observed(result):
    s = result["summary"]
    return {"audit_required": True, "complete": result["complete"], "obligations_covered": _covered(result),
            "profit_microUSD": s["profit"], "available_microUSD": s["available"],
            "unrestricted_earned_microUSD": s["unrestrictedEarned"],
            "settled_orders": result["paid_jobs"], "accepted_orders": result["accepted_jobs"],
            "customers": result["customers"], "repeat_customers": result["repeat_customers"],
            "source_linked_successor": find_native_successor(result)}


def choose_from_development(spec, development):
    """Use ONLY recorded native development results to choose an incumbent or challenger.

    No optimistic forecast, invented demand or promotion from unqualified accounts.
    """
    rows = []
    for d in spec["designs"]:
        r = development[d["id"]]["observed"]
        if not development[d["id"]]["audit_accepted"]:
            raise ValueError("INDEPENDENT_NATIVE_AUDIT_REQUIRED_FOR_SELECTION")
        feasible = r["obligations_covered"] and r["profit_microUSD"] > 0
        rows.append((r["profit_microUSD"] if feasible else None, d["id"]))
    incumbent = spec["incumbent"]
    candidates = [(profit, name) for profit, name in rows if profit is not None]
    if not candidates:
        return {"selected": None, "reason": "NO_FUNDED_POSITIVE_PROFIT_DESIGN",
                "observed_ranking": sorted(rows, key=lambda r: r[1])}
    candidates.sort(key=lambda r: (-r[0], 0 if r[1] == incumbent else 1, r[1]))
    return {"selected": candidates[0][1],
            "reason": "MAXIMUM_OBSERVED_PROTECTED_COMPLETE_COST_PROFIT_IN_DECLARED_DEVELOPMENT_WORLD",
            "observed_ranking": sorted(rows, key=lambda r: (r[0] is None, -(r[0] or 0), r[1]))}


def _public(spec, source, development, selection, confirmation):
    selected = selection["selected"]
    challenger = confirmation.get(selected) if selected else None
    incumbent = confirmation.get(spec["incumbent"])
    if challenger is not None and incumbent is not None:
        delta = challenger["observed"]["profit_microUSD"] - incumbent["observed"]["profit_microUSD"]
    else:
        delta = None
    witness = challenger["observed"]["source_linked_successor"] if challenger else None
    return {
        "schema": SCHEMA, "status": "CONDITIONAL_SIMULATED_EXECUTION",
        "source_sha256": source["sha256"], "spec_sha256": digest(spec),
        "development": {d["id"]: development[d["id"]]["observed"] for d in spec["designs"]},
        "selection": selection,
        "confirmation": {k: v["observed"] for k, v in sorted(confirmation.items())},
        "matched_confirmation_profit_delta_microUSD": delta,
        "connected_earned_successor_witness": witness,
        "confirmed_strictly_better_funded_opportunity":
            bool(witness and witness["strictly_better_per_order_margin"] and
                 challenger["observed"]["obligations_covered"] and
                 challenger["observed"]["profit_microUSD"] > 0),
        "comparative_advantage_on_one_fresh_seed":
            bool(delta is not None and delta > 0 and
                 challenger["observed"]["obligations_covered"]),
        "retained_mechanism": ({
            "id": "observed-funded-channel-or-capacity",
            "applicability": "Positive collected native margin, available earned funds, eligible unserved buyer or unmet capacity, checked current obligations",
            "avoid": "No profitable proven demand, inadequate available cash, exhausted contacts, negative net expansion or unresolved obligations",
            "native_evidence": witness, "execution_authority": [], "current_proof": None,
            "scope": "Candidate lesson, not qualified autonomous invention or general causal strategy advantage"
        } if witness else None),
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
    development = {}
    for d in spec["designs"]:
        name = d["id"]
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
    public = _public(spec, source, development, selection, confirmation)
    _store(output / "PUBLIC.json", public)
    _store(output / "INDEX.json", {"schema": SCHEMA,
        "source_sha256": source["sha256"], "spec_sha256": digest(spec),
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

    development = {}
    for d in spec["designs"]:
        key = d["id"]
        development[key] = one("dev-" + key, index["development"][key], d, spec["development_seed"])
    selection = choose_from_development(spec, development)
    names = sorted(set((spec["incumbent"], selection["selected"]))) if selection["selected"] else []
    if set(index["confirmation"]) != set(names) or set(index["development"]) != {d["id"] for d in spec["designs"]}:
        raise ValueError("REQUIRED_MATCHED_NATIVE_WORLDS_CHANGED")
    confirmation = {}
    for name in names:
        d = next(x for x in spec["designs"] if x["id"] == name)
        confirmation[name] = one("confirm-" + name, index["confirmation"][name], d,
                                 spec["confirmation_seed"])
    public = _public(spec, source, development, selection, confirmation)
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
        "heldout_profit_delta_microUSD": public["matched_confirmation_profit_delta_microUSD"],
        "funded_successor": public["connected_earned_successor_witness"],
        "better_opportunity": public["confirmed_strictly_better_funded_opportunity"],
        "actual_commerce": False, "scope": public["status"]
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
