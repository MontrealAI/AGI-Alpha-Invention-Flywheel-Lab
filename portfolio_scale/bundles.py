"""Possible customer-level programs; no bundle sale or customer demand has been observed."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from .engine import SOURCE, SEGMENTS, TIERS, offer_pricing, validate, target_math, digest

# A customer bundle is a distinct alternative to selling the same tasks separately.
# The catalog permits additional bundles and more job types; these are only examples.
PROGRAMS = (
    {"name":"Autonomous software reliability","families":("software_engineering","it_operations","product_operations","data_engineering")},
    {"name":"Autonomous revenue office","families":("revenue_operations","proposals_rfp","marketing_research","customer_operations")},
    {"name":"Autonomous finance operations","families":("finance_backoffice","business_intelligence","procurement","research_operations")},
    {"name":"Autonomous customer care","families":("customer_operations","localization_media","content_publishing","product_operations")},
    {"name":"Autonomous product documentation","families":("product_operations","software_engineering","content_publishing","localization_media")},
    {"name":"Autonomous enterprise proposals","families":("proposals_rfp","legal_document_ops","research_operations","procurement")},
    {"name":"Autonomous data and analytics","families":("data_engineering","business_intelligence","software_engineering","research_operations")},
    {"name":"Autonomous supplier operations","families":("procurement","logistics_ops","finance_backoffice","business_intelligence")},
    {"name":"Autonomous multilingual publishing","families":("content_publishing","marketing_research","localization_media","product_operations")},
    {"name":"Autonomous property office","families":("real_estate_admin","finance_backoffice","customer_operations","procurement")},
    {"name":"Autonomous people operations","families":("people_operations","localization_media","research_operations","customer_operations")},
    {"name":"Autonomous regulated-admin preparation","families":("insurance_admin","healthcare_admin","legal_document_ops","research_operations")},
)


def evaluate_programs(data:dict, *,monthly_units_per_family:int=3) -> dict:
    validate(data)
    if type(monthly_units_per_family) is not int or monthly_units_per_family<=0:
        raise ValueError("Monthly units must be positive integer")
    index={}
    for row in data["jobs"]:
        index.setdefault(row["family"],[]).append(row)
    # Chosen customer class is a research assumption, not a source that buyers will pay.
    segment=SEGMENTS[2]
    tier=TIERS[0]
    rows=[]
    for program in PROGRAMS:
        if not all(f in index for f in program["families"]):
            continue
        # Two distinct predeclared work products per family, no overlap in this program.
        services=[r for family in program["families"] for r in index[family][:2]]
        offers=[offer_pricing(r,data,segment,tier) for r in services]
        viable=[x for x in offers if x["price_usd"] is not None]
        all_available=(len(viable)==len(offers))
        if all_available:
            gross_annual=sum(x["price_usd"]*monthly_units_per_family*12 for x in viable)
            annual_attempt_cost=sum(x["ai_attempt_resource_scenario_usd"]*monthly_units_per_family*12 for x in viable)
            # Agents reuse an already-authorized connection only if it actually serves every workflow.
            # This is optimistic; no permission or savings is inferred from the document.
            onboarding_once=sum(x["ai_onboarding_resource_scenario_usd"] for x in viable)
        else:gross_annual=annual_attempt_cost=onboarding_once=0
        rows.append({"program":program["name"],"job_ids":[x["id"] for x in services],
                     "job_count":len(services),"monthly_deliveries_assumed":len(services)*monthly_units_per_family,
                     "annualized_full_utilization_revenue_usd":round(gross_annual,2),
                     "annual_attempt_resource_cost_scenario_usd":round(annual_attempt_cost,2),
                     "autonomous_first_customer_onboarding_scenario_usd":round(onboarding_once,2),
                     "permission_sensitive":any(x["risk"]!="LOW_TO_MODERATE" for x in services),
                     "full_quality_validated":False,"paid_customer_evidence":"NONE",
                     "comparable_competitor_bundle_cost":"UNKNOWN",
                     "purchase_probability":"UNMEASURED",
                     "annualized_scale_is_not_earned_revenue":True})
    return {"schema":"alpha-autonomous-bundles-planning/v1","source_sha256":digest(data),
            "accounting_policy":"A sold bundle replaces those individual job sales; NEVER add bundle + component revenue",
            "customer_data_permission_assumed":False,
            "sample_enterprise_programs":rows,
            "observed_customers":0,"annualized_actual_revenue":0,
            "fixed_capability_commercial_flywheel":"UNESTABLISHED",
            "scale_targets":target_math([1e9,10e9,100e9],[25000,100000,500000,1000000]),
            "time_to_scale":"UNIDENTIFIABLE_WITHOUT_ACTUAL_FUNNEL_AND_CASH_DATA"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=SOURCE)
    parser.add_argument("--monthly-units-per-family",type=int,default=3)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output exists; do not overwrite")
    if args.input.stat().st_size>2_000_000:parser.error("File exceeds scoped parser limit")
    data=json.loads(args.input.read_text())
    report=evaluate_programs(data,monthly_units_per_family=args.monthly_units_per_family)
    with args.output.open("x") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
        f.write("\n")
    print(json.dumps({"program_count":len(report["sample_enterprise_programs"]),
                      "actual_revenue":0,"scope":"PLANNING_ONLY"},indent=2))

if __name__=="__main__": main()
