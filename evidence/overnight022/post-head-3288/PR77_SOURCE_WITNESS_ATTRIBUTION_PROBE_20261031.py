"""Read-only PR77 synthetic source falsifier; never reads a native account or private key."""
import ast
import hashlib
import json
import sys
from pathlib import Path

PINNED_SOURCE_BLOB = "890d989a2f639f66aa3486bfcb30f86fee7ddda3"
PINNED_FUNCTION_SHA256 = "d947c7ee835f2deb9b180c09f08cc3f7db4a4180ccb98dd52a7d2931f2f3efa5"

def source_function(path):
    s = Path(path).read_text()
    p = s.index("def _margin(order):")
    q = s.index("\ndef _observed(result):", p)
    excerpt = s[p:q].rstrip()
    if hashlib.sha256(excerpt.encode()).hexdigest() != PINNED_FUNCTION_SHA256:
        raise ValueError("EXACT_PR77_WITNESS_SOURCE_CHANGED: do not silently adopt this probe")
    nodes = [n for n in ast.parse(excerpt).body if isinstance(n, ast.FunctionDef)]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["find_native_successor"]

def order(ident, buyer, service, price, cost, collected, access=None, capacity=None):
    return {"id": ident, "customer_id": buyer, "offer": {"service_id": service},
            "price": price, "complete_cost": cost, "outcome": "SETTLED",
            "qualified_time": collected-40, "acceptance_time": collected-30,
            "collection_time": collected, "acquisition_source_plan_id": access,
            "capacity_source_plan_id": capacity}

def investment(ident, plan, kind, cost):
    return {"id": ident, "plan_id": plan, "kind": kind, "cost": cost,
            "purchased_time": 80, "activation_time": 96, "expiry_time": 300,
            "funding_receipt": {"funding": "EARNED"}}

def fixture():
    first = order("first", "buyer0", "reconciliation", 20, 10, 40)
    good = order("good", "buyer1", "kpi_variance", 40, 12, 160, "a")
    loss = order("loss", "buyer2", "kpi_variance", 20, 45, 180, "a")
    both = order("both", "buyer1", "kpi_variance", 42, 20, 160, "a", "b")
    return {
        "loss_making_settled_order_omitted": {
            "orders": [first, good, loss],
            "investments": [investment("access", "a", "acquisition", 4)]},
        "two_joint_enabler_invoices_counted_as_one": {
            "orders": [first, both],
            "investments": [investment("access", "a", "acquisition", 15),
                            investment("slot", "b", "capacity", 15)]}}

def conservative_net(case, witness):
    plans = {p["plan_id"]: p for p in case["investments"]}
    key = witness["native_plan_id"]
    linked = [o for o in case["orders"] if o["outcome"] == "SETTLED"
              and o["collection_time"] is not None and
              (o.get("acquisition_source_plan_id") == key or
               o.get("capacity_source_plan_id") == key)]
    required = {p for o in linked for p in (
        o.get("acquisition_source_plan_id"), o.get("capacity_source_plan_id")
    ) if p in plans}
    return sum(o["price"] - o["complete_cost"] for o in linked) - sum(
        plans[p]["cost"] for p in required)

def main(source):
    find = source_function(source)
    rows = {}
    for label, case in fixture().items():
        witness = find(case)
        if not witness or not witness["positive_incremental_collected_contribution"]:
            raise AssertionError(label + " did not reproduce the current positive witness")
        net = conservative_net(case, witness)
        if net >= 0:
            raise AssertionError(label + " did not reproduce negative joint attribution")
        rows[label] = {"source_claim_net_microUSD": witness["net_after_native_investment_microUSD"],
                       "source_claim_positive": True, "conservative_net_microUSD": net,
                       "source_plan": witness["native_plan_id"]}
    print(json.dumps({
        "source_function_sha256": PINNED_FUNCTION_SHA256,
        "verdict": "TWO_SOURCE_LEVEL_FALSE_POSITIVE_ATTRIBUTION_CASES",
        "scope": "Synthetic pure-function inputs; NOT canonical Account/audit or a real economic result",
        "cases": rows}, sort_keys=True, indent=2))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python probe.py path/to/connected_enterprise/design_flywheel.py")
    main(sys.argv[1])
