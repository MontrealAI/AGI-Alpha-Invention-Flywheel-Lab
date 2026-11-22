"""Independent REVIEW-ONLY synthetic falsifier for PR77 plan-linked cost claims.

Pinned source executes the original witness unchanged. This small, intentionally
conservative package calculator is NOT a financial ledger or production verifier.
Its fixture permits only explicitly registered statuses and incurred costs.
"""
import copy
import json
from collections import defaultdict, deque

from connected_enterprise.design_flywheel import find_native_successor
from tests.test_connected_design_flywheel041 import case, order

SCHEMA = "agi-alpha/native-design-attribution143/v1"


def _nonnegative_integer(value, label):
    if type(value) is not int or value < 0:
        raise ValueError("UNKNOWN_OR_INVALID_INCURREDCOST:" + label)
    return value


def connected_package_net(result, target_plan):
    """Charge a synthetic connected plan component once; never authorize spending."""
    investments, orders = result["investments"], result["orders"]
    if not isinstance(investments, list) or not isinstance(orders, list):
        raise ValueError("COMPLETE_SOURCE_LINKED_LISTS_REQUIRED")
    invoice = {}
    for p in investments:
        plan = p.get("plan_id")
        if not isinstance(plan, str) or not plan or plan in invoice:
            raise ValueError("UNIQUE_PLAN_IDS_REQUIRED")
        if p.get("funding_receipt", {}).get("funding") != "EARNED":
            raise ValueError("NON_EARNED_OR_UNVERIFIED_PLAN")
        _nonnegative_integer(p.get("cost"), "invoice")
        invoice[plan] = p
    if target_plan not in invoice:
        raise ValueError("REGISTERED_TARGET_PLAN_REQUIRED")
    item_ids, refs, plan_orders = set(), {}, defaultdict(set)
    for o in orders:
        ident = o.get("id")
        if not isinstance(ident, str) or not ident or ident in item_ids:
            raise ValueError("UNIQUE_ORDER_IDS_REQUIRED")
        item_ids.add(ident)
        _nonnegative_integer(o.get("complete_cost"), "order")
        linked = set()
        for field in ("acquisition_source_plan_id", "capacity_source_plan_id"):
            v = o.get(field)
            if v is not None:
                if not isinstance(v, str) or not v:
                    raise ValueError("VALID_PLAN_REFERENCE_REQUIRED")
                linked.add(v)
        many = o.get("capacity_source_plan_ids", [])
        if not isinstance(many, list) or any(not isinstance(x, str) or not x for x in many):
            raise ValueError("VALID_PLAN_REFERENCE_LIST_REQUIRED")
        linked.update(many)
        if not linked <= set(invoice):
            raise ValueError("UNREGISTERED_SOURCE_PLAN_REFERENCE")
        refs[ident] = linked
        for p in linked:
            plan_orders[p].add(ident)

    # Orders touching both A and B make A and B one connected investment package.
    component, encountered_orders, pending = set(), set(), deque([target_plan])
    by_id = {o["id"]: o for o in orders}
    while pending:
        p = pending.popleft()
        if p in component:
            continue
        component.add(p)
        for oid in plan_orders[p]:
            encountered_orders.add(oid)
            pending.extend(refs[oid] - component)

    invoice_cost = sum(invoice[p]["cost"] for p in component)
    collected_margin, failed_cost = 0, 0
    for oid in encountered_orders:
        o = by_id[oid]
        if o["outcome"] == "SETTLED" and o.get("collection_time") is not None and o.get("acceptance_time") is not None:
            collected_margin += _nonnegative_integer(o.get("price"), "settled_price") - o["complete_cost"]
        elif o["outcome"] in ("QUALITY_REJECTED", "REFUNDED") and o.get("collection_time") is None:
            # This fixture explicitly has no retained collections; loss is incurred.
            failed_cost += o["complete_cost"]
        else:
            raise ValueError("UNCLASSIFIED_COLLECTION_OR_REFUND_STATE")
    return {
        "plans": sorted(component), "orders": sorted(encountered_orders),
        "settled_collected_margin_microUSD": collected_margin,
        "failed_uncollected_cost_microUSD": failed_cost,
        "earned_invoice_cost_microUSD": invoice_cost,
        "source_connected_net_microUSD": collected_margin - failed_cost - invoice_cost,
    }


def _loss(source_plan):
    loss = order("rejected-linked", "SIM-customer-006", "kpi_variance", 40, 90, 121, None, source_plan)
    loss["outcome"] = "QUALITY_REJECTED"
    return loss


def _extra_plan(plan_id="capacity-9", cost=5, kind="capacity"):
    return {
        "kind": kind, "id": "costed-" + plan_id, "plan_id": plan_id,
        "purchased_time": 82, "activation_time": 96, "expiry_time": 300,
        "cost": cost, "funding_receipt": {"funding": "EARNED"}
    }


def _expect_invalid(source, mutation):
    bad = copy.deepcopy(source)
    mutation(bad)
    try:
        connected_package_net(bad, "earned-plan-4")
    except ValueError:
        return
    raise AssertionError("ADVERSE_INVALID_SOURCE_ACCEPTED")


def main():
    baseline = case()
    first = find_native_successor(baseline)
    assert first and first["positive_incremental_collected_contribution"]
    assert first["net_after_native_investment_microUSD"] == 26
    positive = connected_package_net(baseline, "earned-plan-4")
    assert positive["source_connected_net_microUSD"] == 26

    adverse = copy.deepcopy(baseline)
    adverse["orders"].append(_loss("earned-plan-4"))
    unchanged = find_native_successor(adverse)
    assert unchanged and unchanged["positive_incremental_collected_contribution"]
    assert unchanged["net_after_native_investment_microUSD"] == 26
    adverse_net = connected_package_net(adverse, "earned-plan-4")
    assert adverse_net["source_connected_net_microUSD"] == -64

    unrelated = copy.deepcopy(baseline)
    unrelated["investments"].append(_extra_plan("other-plan", 5, "acquisition"))
    unrelated["orders"].append(_loss("other-plan"))
    assert connected_package_net(unrelated, "earned-plan-4")["source_connected_net_microUSD"] == 26

    two_plans = copy.deepcopy(baseline)
    two_plans["investments"].append(_extra_plan())
    two_plans["orders"][1]["capacity_source_plan_id"] = "capacity-9"
    assert connected_package_net(two_plans, "earned-plan-4")["source_connected_net_microUSD"] == 21
    two_plans["orders"].append(_loss("earned-plan-4"))
    assert connected_package_net(two_plans, "capacity-9")["source_connected_net_microUSD"] == -69

    _expect_invalid(baseline, lambda r: r["orders"].append(copy.deepcopy(r["orders"][1])))
    _expect_invalid(baseline, lambda r: r["investments"].append(copy.deepcopy(r["investments"][0])))
    _expect_invalid(baseline, lambda r: r["orders"][1].update(complete_cost=None))
    _expect_invalid(baseline, lambda r: r["orders"][1].update(complete_cost=-1))
    _expect_invalid(baseline, lambda r: r["investments"][0].update(cost=True))
    _expect_invalid(baseline, lambda r: r["orders"][1].update(acquisition_source_plan_id="unknown"))
    _expect_invalid(baseline, lambda r: r["orders"][1].update(outcome="REFUNDED"))
    _expect_invalid(baseline, lambda r: r["investments"][0]["funding_receipt"].update(funding="SEED"))

    print(json.dumps({
        "schema": SCHEMA,
        "status": "ADVERSE_COUNTEREXAMPLE_REPRODUCED",
        "scope": "EXPOSED_SYNTHETIC_ORDERS_ONLY_NOT_NATIVE_ACCOUNT_AUDIT",
        "original_pinned_witness_collected_margin_net_microUSD": unchanged["net_after_native_investment_microUSD"],
        "shared_plan_full_cost_net_microUSD": adverse_net["source_connected_net_microUSD"],
        "positive_control_full_cost_net_microUSD": positive["source_connected_net_microUSD"],
        "unrelated_loss_control_net_microUSD": 26,
        "two_invoices_control_net_microUSD": 21,
        "two_invoices_and_shared_failure_net_microUSD": -69,
        "invalid_case_rejections": 8,
        "claim_refuted": "positive collected settled linkage entails profitable COMPLETE connected package",
        "claim_not_refuted": "positive collected settled linkage on the subset of settled orders",
        "original_account_modified": False, "original_candidate_modified": False,
        "external_commerce": False, "economic_target_achieved": False
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
