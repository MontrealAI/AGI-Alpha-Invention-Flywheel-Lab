"""Retrospective, integer-only, read-only supplier contracting impossibility certificate."""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "campaign/omega-paid-reach-20261104/PAIRED_EVIDENCE.json"
DIGEST = "b646d9ec901f6c71ff6ebe2ee6717387b55f47aa9f60a623a2b2c16cfc3acbcb"
CASES = ("central", "weak", "copycat", "no_demand", "failed_activation")
DELTAS = (205112000, -7160000, -7160000, -7160000, -5000000)
OPENING = 100000000000


def unique(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def i(v):
    if type(v) is not int:
        raise ValueError("INTEGER_REQUIRED")
    return v


def account(r, case):
    if r.get("native_audit_accepted") is not True or not r.get("audit_receipt_sha256") or not r.get("artifact_file_sha256"):
        raise ValueError("UNAUDITED_ACCOUNT:" + case)
    f, costs = r["financial_microUSD"], r["incurred_expense_breakdown_microUSD"]
    if any(i(v) < 0 for v in costs.values()) or sum(costs.values()) != i(f["incurred_expenses_including_tax"]):
        raise ValueError("EXPENSE_MISMATCH:" + case)
    if i(f["recognized_revenue"]) + i(f["recovery_income"]) - i(f["incurred_expenses_including_tax"]) != i(f["profit_after_modeled_tax"]):
        raise ValueError("PROFIT_MISMATCH:" + case)
    if OPENING + i(f["collections"]) + i(f["recovery_income"]) - i(f["cash_expenses_paid"]) != i(f["cash"]):
        raise ValueError("CASH_MISMATCH:" + case)
    if i(f["cash"]) - sum(i(f[x]) for x in ("tail_reserve","working_capital","custody_reserve","custody_restricted","reserved_investment")) != i(f["available_cash"]):
        raise ValueError("LIQUIDITY_MISMATCH:" + case)
    return f


def certify(source: bytes, expected_digest: str = DIGEST):
    digest = hashlib.sha256(source).hexdigest()
    if digest != expected_digest:
        raise ValueError("SOURCE_SHA256_MISMATCH")
    d = json.loads(source.decode("utf-8"), object_pairs_hook=unique,
                   parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    if d.get("schema") != "omega/earned-paid-reach-paired-evidence/v1" or d.get("window_days") != [0,365] or d.get("end_day_exclusive") is not True:
        raise ValueError("SOURCE_SCOPE_CHANGED")
    if i(d["opening_microUSD_each"]) != OPENING or d.get("actual_revenue_usd") != 0 or d.get("actual_complete_lifecycle_cost_usd") is not None:
        raise ValueError("CAPITAL_OR_REAL_SCOPE_CHANGED")
    if type(d.get("pairs")) is not dict or set(d["pairs"]) != set(CASES):
        raise ValueError("REGISTERED_CASES_CHANGED")
    rows = {}
    for case, expected in zip(CASES, DELTAS):
        p = d["pairs"][case]
        o, n = account(p["organic"],case+":organic"), account(p["pilot"],case+":pilot")
        if "paid_reach" in p["organic"]["incurred_expense_breakdown_microUSD"]:
            raise ValueError("ORGANIC_INVOICE")
        paid = i(p["pilot"]["incurred_expense_breakdown_microUSD"]["paid_reach"])
        if paid != sum(i(t["invoice_microUSD"]) for t in p["pilot"]["tranches"]) or paid < 0:
            raise ValueError("PAID_INVOICE_MISMATCH")
        comp = p["comparison"]["pilot_minus_organic_financial_microUSD"]
        for field in ("profit_after_modeled_tax","cash","available_cash","collections","recognized_revenue","incurred_expenses_including_tax","tail_reserve"):
            if i(n[field])-i(o[field]) != i(comp[field]):
                raise ValueError("PAIRED_DELTA_MISMATCH:"+case+":"+field)
        delta = i(comp["profit_after_modeled_tax"])
        if delta != expected:
            raise ValueError("FROZEN_RESULT_CHANGED:"+case)
        before_tax = delta + i(p["pilot"]["incurred_expense_breakdown_microUSD"]["modeled_tax"]) - i(p["organic"]["incurred_expense_breakdown_microUSD"]["modeled_tax"])
        upper = before_tax + paid
        rows[case] = {
            "historical_pilot_minus_organic_after_tax_microUSD": delta,
            "historical_available_cash_delta_microUSD": i(comp["available_cash"]),
            "original_prepay_invoice_microUSD": paid,
            "historical_pretax_delta_microUSD": before_tax,
            "fee_removed_unchanged_actions_pretax_bound_microUSD": upper,
            "nonnegative_partner_payment_can_eliminate_seller_loss": upper >= 0,
            "partner_term_was_executed": False,
        }
    adverse = [k for k, v in rows.items() if v["fee_removed_unchanged_actions_pretax_bound_microUSD"] < 0]
    if adverse != ["weak","copycat","no_demand"]:
        raise ValueError("FROZEN_BOUND_CHANGED")
    return {
        "schema":"agi-alpha/supplier-risk093/v1","source_sha256":digest,
        "existing_audited_accounts":10,"new_native_accounts":0,"cases":rows,
        "adverse_fee_free_negative_cases":adverse,
        "min_prepaid_aftertax_delta_microUSD":min(v["historical_pilot_minus_organic_after_tax_microUSD"] for v in rows.values()),
        "seller_supplier_robust_pareto_via_fee_only":False,
        "current_decision":"KEEP_ORGANIC_NO_NEW_PARTNER_CONTRACT",
        "next_missing_means":"VALIDATED_PREQUOTE_SCREEN_OR_COSTED_NEW_PRODUCTIVE_ARRANGEMENT",
        "partner_cost_and_outside_option":"UNKNOWN","real_buyer_demand":"UNKNOWN",
        "actual_revenue_usd":0,"actual_full_cost_usd":None,"real_trailing_365_profit_usd":None,
        "target_3b_reached":False,
        "scope":"HISTORICAL_SAME_ACTION_FEE_REMOVAL_BOUND_NOT_CAUSAL_OR_AUTHORIZED_NATIVE_COMMERCE",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=SOURCE)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.resolve()==args.source.resolve():
        raise ValueError("NO_SOURCE_OVERWRITE")
    result=certify(args.source.read_bytes())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
