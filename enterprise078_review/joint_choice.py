"""Source-pinned read-only joint buyer choice challenge, not a sale or native admission."""
import hashlib
import json
from pathlib import Path

from enterprise078.transactional_admission.intent import evaluate, money

INCUMBENT = {
    "enterprise078/transactional_admission/intent.py": "bce149a60f112f28950e2e81151a29df304cceff",
    "enterprise078/transactional_admission/offer.py": "8ae507346f2c798794c444a338cb90b2ca0fd47e",
}
ALTERNATIVES = frozenset(("human", "competitor_ai", "self_service", "no_purchase"))


def pinned_source(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    for name, expected in INCUMBENT.items():
        path = root / name
        if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError("INCUMBENT_SOURCE_UNAVAILABLE")
        raw = path.read_bytes()
        actual = hashlib.sha1(("blob " + str(len(raw)) + "\0").encode() + raw).hexdigest()
        if actual != expected:
            raise ValueError("INCUMBENT_SOURCE_CHANGED_REQUALIFY")
    return dict(INCUMBENT)


def subset_key(ids):
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_OFFER_IN_BUYER_SUBSET")
    return json.dumps(sorted(ids), separators=(",", ":"), ensure_ascii=True)


def review(rows, bundles, *, wallets, available, earned, sunk_acquisition, scenarios):
    """Compare complete-cost incumbent with registered joint buyer/rival/refusal states.

    The caller must supply each buyer's joint bundle valuation and complete
    alternatives in each scenario; missing entries fail closed. All receipts,
    consent, accepted output and partner participation are explicit authored
    inputs. No demand, price, collection, native account or authority is created.
    """
    source = pinned_source()
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError("REGISTERED_SCENARIOS_REQUIRED")
    base = evaluate(rows, bundles, wallets=wallets, available=available,
                    earned=earned, sunk_acquisition=sunk_acquisition)
    by_id = {r["id"]: r for r in rows}
    checked = []
    for outcome in base["outcomes"]:
        ids = outcome["bundle"]
        if not ids:
            checked.append({"bundle": [], "feasible": True,
                            "robust_net_microUSD": -sunk_acquisition, "reasons": []})
            continue
        reasons = set(outcome["reasons"])
        nets = []
        by_buyer = {}
        for ident in ids:
            row = by_id[ident]
            by_buyer.setdefault(row["buyer"], []).append(ident)
        for case_name, case in sorted(scenarios.items()):
            if not isinstance(case_name, str) or not case_name:
                raise ValueError("SCENARIO_ID_REQUIRED")
            if not isinstance(case, dict):
                raise ValueError("EXPLICIT_SCENARIO_REQUIRED")
            vals = case.get("buyers")
            collections = case.get("collections")
            consents = case.get("consents")
            acceptances = case.get("acceptances")
            partners = case.get("partners")
            if not all(isinstance(v, dict) for v in (vals, collections, consents, acceptances, partners)):
                reasons.add("INCOMPLETE_SCENARIO:" + case_name)
                continue
            receipts = 0
            for ident in ids:
                row = by_id[ident]
                collected = collections.get(ident)
                if collected is None:
                    reasons.add("COLLECTION_UNESTABLISHED:" + case_name)
                else:
                    money(collected)
                    if collected > row["price"]:
                        raise ValueError("COLLECTION_CANNOT_EXCEED_QUOTE")
                    receipts += collected
                if consents.get(ident) is not True or acceptances.get(ident) is not True:
                    reasons.add("VOLUNTARY_OR_ACCEPTANCE_REFUSED:" + case_name)
                partner = row.get("partner")
                if partner is not None and partners.get(partner) != "accepted":
                    reasons.add("PARTNER_PARTICIPATION_UNESTABLISHED:" + case_name)
            for buyer, buyer_ids in by_buyer.items():
                entry = vals.get(buyer, {}).get(subset_key(buyer_ids))
                if not isinstance(entry, dict) or set(entry) != {"joint_value", "outside"}:
                    reasons.add("JOINT_VALUE_OR_OUTSIDE_UNESTABLISHED:" + case_name + ":" + buyer)
                    continue
                outside = entry["outside"]
                if not isinstance(outside, dict) or set(outside) != ALTERNATIVES:
                    reasons.add("COMPLETE_OUTSIDE_OPTIONS_UNESTABLISHED:" + case_name + ":" + buyer)
                    continue
                money(entry["joint_value"])
                for value in outside.values():
                    money(value)
                price = sum(by_id[i]["price"] for i in buyer_ids)
                if entry["joint_value"] - price <= max(outside.values()):
                    reasons.add("BUYER_PREFERS_OUTSIDE_OR_TIES:" + case_name + ":" + buyer)
            if all(i in collections for i in ids):
                nets.append(receipts - outcome["incremental_cost_microUSD"] - sunk_acquisition
                            if outcome["incremental_cost_microUSD"] is not None else None)
        robust = min(nets) if len(nets) == len(scenarios) and all(n is not None for n in nets) else None
        checked.append({"bundle": list(ids), "feasible": not reasons and robust is not None,
                        "robust_net_microUSD": robust, "reasons": sorted(reasons)})
    winner = checked[0]
    for item in checked[1:]:
        if item["feasible"] and item["robust_net_microUSD"] > winner["robust_net_microUSD"]:
            winner = item
    return {"incumbent_selected_bundle": base["selected_bundle"],
            "robust_selected_bundle": winner["bundle"],
            "robust_net_microUSD": winner["robust_net_microUSD"],
            "outcomes": checked, "source_git_blobs": source,
            "native_catalog_admitted": False, "native_mutations": 0,
            "observed_customer_evidence": False, "paid_commerce": False,
            "scope": "preregistered authored choice counterexample; no market calibration, equilibrium, native execution or profit"}
