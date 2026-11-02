from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from commercial.ledger import canonical, digest
from connected_enterprise.finance import audit_journal
from connected_enterprise.scale import aggregate_native, trailing_profit
from experiments.public_portfolio_20261102.native import BusinessAccount
from experiments.public_portfolio_20261102 import service


PREFIX = "experiments/public_portfolio_20261102/"
PROTOCOL = PREFIX + "ECONOMICS_PROTOCOL.json"
MICRO = 1_000_000
ROUTES = ("purpose", "interface", "complementarity", "arrangement", "foundry")


def micro(value):
    result = Decimal(str(value))*MICRO
    if not result.is_finite() or result < 0:
        raise ValueError("NONNEGATIVE_FINITE_COST_REQUIRED")
    return int(result.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value)+b"\n")


def prepare_manifest(root, products, delivery_prefix):
    return service.prepare_manifest(root, products, delivery_prefix)


def quote_actions(prices, *, value, budget, adoption, outside_costs, fulfillment, acquisition, fee, available, overhead_buffer=0):
    numbers = [value,budget,adoption,fulfillment,acquisition,fee,available,overhead_buffer,*prices,*outside_costs.values()]
    if any(type(v) is not int or v < 0 for v in numbers):
        raise ValueError("INTEGER_NONNEGATIVE_FINITE_GAME_REQUIRED")
    outside_utilities = {key:max(0,value-cost) for key,cost in outside_costs.items()}
    best_outside = max([0,*outside_utilities.values()])
    actions = [{"price_microUSD":None,"chosen_by_buyer":False,"funding_feasible":True,"contribution_microUSD":0,"reason":"NON_ENTRY"}]
    for price in sorted(set(prices)):
        utility = value-price-adoption
        buyer = price >= 200_000 and price+adoption <= budget and utility > best_outside
        needed = fulfillment+acquisition+fee+price+overhead_buffer
        funded = available >= needed
        contribution = price-fulfillment-acquisition-fee
        actions.append({"price_microUSD":price,"buyer_utility_microUSD":utility,"chosen_by_buyer":buyer,"funding_feasible":funded,"required_company_cash_microUSD":needed,"contribution_microUSD":contribution,"eligible":buyer and funded and contribution>0})
    eligible = [a for a in actions[1:] if a["eligible"]]
    selected = max(eligible,key=lambda a:(a["contribution_microUSD"],-a["price_microUSD"])) if eligible else actions[0]
    best = max([0,*[a["contribution_microUSD"] for a in eligible]])
    achieved = selected["contribution_microUSD"]
    return {"actions":actions,"selected":selected,"outside_utilities_microUSD":outside_utilities,"outside_costs_microUSD":outside_costs,"best_outside_utility_microUSD":best_outside,"enumerated_one_step_optimum_microUSD":best,"one_step_regret_microUSD":best-achieved,"scope":"Complete-information posted-price grid for one current order and cash state; not enterprise or global equilibrium optimality"}


def _profile(protocol, route, scenario):
    profile = copy.deepcopy(protocol["profiles_usd"][route])
    multiplier = scenario.get("maintenance_multiplier",1)
    for name in ("support_term","compatibility_maintenance_term","monthly_fixed_overhead"):
        profile[name] = Decimal(str(profile[name]))*multiplier
    return {key:[micro(v) for v in value] if key=="price_grid" else micro(value) for key,value in profile.items()}


def _fulfillment(profile):
    return sum(profile[key] for key in ("onboarding","compute","verification","correction","delivery_storage_isolation","support_term","compatibility_maintenance_term"))


def _capital(protocol, profile, scenario):
    if scenario["capital_usd"] == "stress-formula":
        return profile["research_and_failed_work"]+profile["rights_and_setup"]+max(profile["price_grid"])+3*(_fulfillment(profile)+profile["acquisition"])+3*profile["monthly_fixed_overhead"]
    return micro(scenario["capital_usd"])


def _calendar(epoch, hour):
    origin = datetime.fromisoformat(epoch.replace("Z","+00:00"))
    return (origin+timedelta(hours=hour)).astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def _outside(profile, scenario, hour, protocol):
    costs = {"free_source_self_service":profile["free_source_integration"],"competent_human_conventional":profile["conventional"],"hybrid":profile["hybrid"],"autonomous_rival":profile["rival"]}
    compression = scenario.get("compression_month",18)*protocol["month_hours"]
    if hour >= compression:
        costs["autonomous_rival"] = min(costs["autonomous_rival"],profile["compressed_outside_floor"])
        costs["free_source_self_service"] = min(costs["free_source_self_service"],profile["compressed_outside_floor"])
    return costs


def _buyer_value(profile, scenario, index):
    multiplier = Decimal(str(scenario.get("demand_multiplier",1)))
    return int(Decimal(profile["buyer_base_value"])*(80+5*index)*multiplier/100)


def _quote(protocol, profile, scenario, index, hour, remaining, available):
    return quote_actions(profile["price_grid"],value=_buyer_value(profile,scenario,index),budget=remaining,adoption=profile["adoption"],outside_costs=_outside(profile,scenario,hour,protocol),fulfillment=_fulfillment(profile),acquisition=profile["acquisition"],fee=protocol["obligations"]["native_fee_microUSD"],available=available,overhead_buffer=profile["monthly_fixed_overhead"])


def _buyer_remaining(account, buyer, original_budget, adoption_spent):
    ledger = account.export()["ledger"]
    wallets = ledger.get("wallets",[])
    matches = [row for row in wallets if row.get("buyer")==buyer]
    if matches:
        row = matches[0]
        balance = int(row["balance"])
    else:
        provisions = [a for a in ledger["actions"] if a["op"]=="wallet" and a["args"]["buyer"]==buyer]
        if provisions:
            initial = provisions[0]["args"]["amount"]
            orders = [row for row in ledger["orders"] if row["buyer"]==buyer]
            spent = sum(int(row["price"]) if row["state"] in {"funded","verified","released"} else int(row["refund_due"]) if row["state"]=="breached" else 0 for row in orders)
            balance = initial-spent
        else:
            balance = original_budget
    return max(0,balance-adoption_spent)


def _run_case(root, output, products, protocol, route, scenario):
    case_id = route+"-"+scenario["id"]
    profile = _profile(protocol,route,scenario)
    available_products = [p for p in products if p["route"]==route]
    stages = {p["stage"]:p for p in available_products}
    manifest = prepare_manifest(root,available_products,case_id)
    opening = _capital(protocol,profile,scenario)
    folder = output/"public"/case_id
    private = output/"private"/case_id
    private.mkdir(parents=True,exist_ok=False)
    _save(folder/"manifest.json",manifest)
    state = {"case_id":case_id,"route":route,"scenario":copy.deepcopy(scenario),"opening_microUSD":opening,"scenario_scope":"AUTHORED_CONDITIONAL_COMPUTATIONAL_SUPPORT_BUSINESS","rights_qualified_hypothesis":scenario.get("rights",True),"physical_deployment_qualified":False,"observed_market_calibration":False,"actual_revenue_usd":0,"decisions":[],"orders":[],"k2_investment":None,"monthly":[],"cost_profile_microUSD":profile,"product_ids":[p["id"] for p in available_products],"actual_host_model_billing":None,"internal_human_time_measured":False,"capital_is_secured":False}
    match_world = {"route":route,"profile":profile,"opening":opening,"prospects":protocol["finite_market"]["prospects_per_route"],"scenario":{k:v for k,v in scenario.items() if k not in {"id","policy"}}}
    state["matched_world_sha256"] = digest(match_world)
    events = []
    sequence = 0
    def schedule(hour,kind,data=None):
        nonlocal sequence
        heapq.heappush(events,(hour,sequence,kind,data))
        sequence += 1
    active = scenario.get("entry",True) and not scenario.get("financing_refused",False)
    count = protocol["finite_market"]["prospects_per_route"]
    buyers = {i:{"id":route+"-p"+str(i).zfill(2),"budget":profile["buyer_base_value"]*3,"adoption_spent":0,"k1_collected":False,"failed":False,"last_k1":None} for i in range(count)}
    orders = {}
    tax_assessed = 0
    k2_available = False
    end = protocol["operating_end_hour_exclusive"]
    with BusinessAccount(root,manifest,private/"account.sqlite",opening=opening,working=0,contract="public-portfolio-"+case_id) as account:
        account.cost("registered-observation-origin",0,0)
        setup = profile["research_and_failed_work"]+profile["rights_and_setup"]
        if active:
            receipt = account.spend("full-research-failures-rights-setup","research_and_rights",setup,0,{"route":route,"research_including_failures_microUSD":profile["research_and_failed_work"],"rights_and_business_setup_microUSD":profile["rights_and_setup"],"source":"uncalibrated registered full lifecycle cost envelope"},expected_net=1,allow_seed=True)
            state["startup_receipt"] = receipt
            if receipt is None:
                active = False
                state["startup_refusal"] = "INITIAL_COMMITTED_CAPITAL_INSUFFICIENT_NO_UNFUNDED_RESEARCH_COMMISSIONED"
        if scenario.get("financing_refused"):
            state["startup_refusal"] = "MODELED_INITIAL_EQUITY_FINANCIER_REFUSED_NO_CASH_RECEIVED"
        if active and scenario.get("policy")=="greedy":
            surplus = account.snapshot()["summary"]["available"]
            cost = max(0,surplus-micro(50))
            state["greedy_unused_capacity_receipt"] = account.spend("greedy-reach-capacity","prepaid_unused_service_capacity",cost,0,{"route":route,"kind":"legacy reach/capacity heuristic buys before reserving fulfillment and collateral","unused_capacity_is_not_installed_physical_capacity":True,"cash_limit_microUSD":surplus},expected_net=1,allow_seed=True)
        for month in range(protocol["months"]):
            schedule(month*protocol["month_hours"],"overhead",month)
        for hour in protocol["tax"]["assessment_hours"]:
            schedule(hour,"tax")
        for index in range(count):
            first = protocol["finite_market"]["first_contact_hour"]+index*protocol["finite_market"]["contact_spacing_hours"]
            schedule(first,"contact",{"index":index,"stage":"k1","kind":"initial"})
            collection_delay = max(2,scenario.get("collection_delay_hours",protocol["obligations"]["central_collection_delay_hours"]))
            schedule(first+collection_delay+protocol["finite_market"]["one_renewal_after_hours"]+1,"contact",{"index":index,"stage":"k1","kind":"renewal"})
            schedule(protocol["finite_market"]["k2_first_contact_hour"]+index*protocol["finite_market"]["contact_spacing_hours"],"contact",{"index":index,"stage":"k2","kind":"successor"})
        schedule(protocol["finite_market"]["k2_development_hour"],"k2-investment")
        for month in range(1,protocol["months"]+1):
            schedule(month*protocol["month_hours"]-1,"observe",month)
        while events:
            hour,_,kind,data = heapq.heappop(events)
            account.advance(hour)
            if kind=="overhead":
                if active:
                    account.cost("monthly-fixed-maintenance-"+str(data),profile["monthly_fixed_overhead"],hour)
            elif kind=="tax":
                summary = account.snapshot()["summary"]
                pre_tax = summary["profit"]+tax_assessed
                required = max(0,pre_tax)*protocol["tax"]["rate_numerator"]//protocol["tax"]["rate_denominator"]
                due = max(0,required-tax_assessed)
                account.cost("tax-assessment-"+str(hour),due,hour)
                tax_assessed += due
            elif kind=="k2-investment":
                if not active or not scenario.get("rights",True) or "k2" not in stages:
                    state["k2_investment"]={"funded":False,"reason":"SCIENTIFIC_ACCEPTANCE_UNMET" if "k2" not in stages else "NO_ACTIVE_RIGHTS_QUALIFIED_BUSINESS"}
                    continue
                available = account.snapshot()["summary"]["available"]
                forecast = 0
                for index,buyer in buyers.items():
                    remaining = _buyer_remaining(account,buyer["id"],buyer["budget"],buyer["adoption_spent"])
                    quote = _quote(protocol,profile,scenario,index,hour,remaining,available)
                    forecast += quote["selected"]["contribution_microUSD"]
                development = profile["k2_development"]
                if forecast <= development:
                    state["k2_investment"]={"funded":False,"reason":"REGISTERED_FINITE_FORECAST_DOES_NOT_COVER_DEVELOPMENT","forecast_microUSD":forecast,"cost_microUSD":development}
                    continue
                before = account.snapshot()["summary"]
                receipt = account.spend("k2-development","successor_package_qualification",development,hour,{"product_id":stages["k2"]["id"],"product_sha256":stages["k2"]["product_sha256"],"inheritance":scenario.get("inheritance","retained"),"physical_production":False,"all_inheritance_arms_same_content_cost_assumption":True},expected_net=forecast-development,allow_seed=not scenario.get("earned_only_k2",False))
                k2_available = receipt is not None
                state["k2_investment"]={"funded":k2_available,"receipt":receipt,"funding":receipt["funding"] if receipt else None,"cost_microUSD":development,"forecast_microUSD":forecast,"before_unrestricted_earned_microUSD":before["unrestrictedEarned"],"earned_only_control":scenario.get("earned_only_k2",False),"reason":None if receipt else "NATIVE_EARNED_OR_AVAILABLE_FUNDS_REFUSAL"}
            elif kind=="contact":
                index,stage,contact_kind = data["index"],data["stage"],data["kind"]
                buyer = buyers[index]
                decision = {"hour":hour,"buyer":buyer["id"],"stage":stage,"kind":contact_kind,"accepted":False}
                state["decisions"].append(decision)
                if not active:
                    decision["reason"]="NON_ENTRY_OR_STARTUP_FINANCING_REFUSAL"
                    continue
                if not scenario.get("rights",True):
                    decision["reason"]="COMMERCIAL_RIGHTS_UNRESOLVED_REFUSE"
                    continue
                if stage not in stages:
                    decision["reason"]="SCIENTIFIC_ACCEPTANCE_UNMET"
                    continue
                if stage=="k2" and not k2_available:
                    decision["reason"]="SUCCESSOR_NOT_FUNDED"
                    continue
                if buyer["failed"]:
                    decision["reason"]="PRIOR_QUALIFICATION_OR_PROVIDER_FAILURE_NO_FREE_REACTIVATION"
                    continue
                if contact_kind=="renewal" and (not buyer["k1_collected"] or buyer["last_k1"] is None or hour-buyer["last_k1"]<protocol["finite_market"]["renewal_cooldown_hours"]):
                    decision["reason"]="RENEWAL_BOUNDARY_OR_SUCCESSFUL_PRIOR_CONTRACT_REQUIRED"
                    continue
                summary = account.snapshot()["summary"]
                if summary["investmentStopped"]:
                    decision["reason"]="NATIVE_INVESTMENT_STOP_RETAINS_EXISTING_OBLIGATIONS"
                    continue
                remaining = _buyer_remaining(account,buyer["id"],buyer["budget"],buyer["adoption_spent"])
                quote = _quote(protocol,profile,scenario,index,hour,remaining,summary["available"])
                decision["buyer_remaining_budget_microUSD"] = remaining
                decision["choice"] = quote
                selected = quote["selected"]
                if selected["price_microUSD"] is None:
                    acquisition = account.spend("contact-"+contact_kind+"-"+stage+"-"+str(index),"eligible_acquisition",profile["acquisition"],hour,{"buyer":buyer["id"],"stage":stage,"cold_lead_counted_once":True,"no_compulsory_purchase":True},expected_net=1,allow_seed=True)
                    decision["acquisition_receipt"] = acquisition
                    decision["reason"]="VOLUNTARY_REFUSAL_OR_NEGATIVE_COMPLETE_CONTRIBUTION_OR_CASH_CONSTRAINT" if acquisition else "ELIGIBLE_CONTACT_UNAFFORDABLE"
                    continue
                price = selected["price_microUSD"]
                identity = stage+"-"+contact_kind+"-"+str(index)
                prepaid = account.spend("fulfillment-"+identity,"complete_package_checking_support_prepaid",_fulfillment(profile),hour,{"buyer":buyer["id"],"product_id":stages[stage]["id"],"product_sha256":stages[stage]["product_sha256"],"scope":"COPY_OF_APPROVED_COMPUTATIONAL_PACKAGE_WITH_CHECKING_AND_SUPPORT","prepaid_cost_categories_microUSD":{key:profile[key] for key in ("onboarding","compute","verification","correction","delivery_storage_isolation","support_term","compatibility_maintenance_term")},"support_term_hours":protocol["obligations"]["support_and_warranty_hours"],"no_new_physical_or_scientific_output_claim":True},expected_net=selected["contribution_microUSD"],allow_seed=True)
                decision["prepaid_fulfillment_receipt"] = prepaid
                if prepaid is None:
                    decision["reason"]="NATIVE_FULFILLMENT_RESERVATION_REFUSED"
                    continue
                acquisition = account.spend("contact-"+identity,"eligible_acquisition",profile["acquisition"],hour,{"buyer":buyer["id"],"stage":stage,"fulfillment_prepaid_first":True},expected_net=selected["contribution_microUSD"],allow_seed=True)
                decision["acquisition_receipt"] = acquisition
                if acquisition is None:
                    decision["reason"]="ACQUISITION_REFUSED_AFTER_PREPAYMENT_COST_RETAINED"
                    continue
                order = case_id+"-"+identity
                collection = hour+max(2,scenario.get("collection_delay_hours",protocol["obligations"]["central_collection_delay_hours"]))
                warranty = collection+protocol["obligations"]["support_and_warranty_hours"]
                residual = price*protocol["obligations"]["residual_principal_basis_points"]//10000
                account.begin(stages[stage]["id"],order,buyer["id"],price,buyer["budget"],hour,collection,warranty,residual)
                buyer["adoption_spent"] += profile["adoption"]
                if stage=="k1" and contact_kind=="initial":
                    buyer["last_k1"] = collection
                record = {"id":order,"buyer":buyer["id"],"index":index,"stage":stage,"kind":contact_kind,"price_microUSD":price,"budget_origin_microUSD":buyer["budget"],"begin_hour":hour,"delivery_hour":hour+1,"collection_hour":collection,"warranty_through_hour_inclusive":warranty,"residual_microUSD":residual,"state":"funded","decision_index":len(state["decisions"])-1,"prepaid_support_covers_entire_term":True}
                orders[order]=record
                state["orders"].append(record)
                decision["accepted"]=True
                decision["reason"]="VOLUNTARY_FUNDED_ORDER_COMPANY_CASH_UNCHANGED_BY_ESCROW"
                schedule(hour+1,"deliver",order)
                schedule(collection,"collect",order)
                schedule(warranty+1,"mature-observe",order)
            elif kind=="deliver":
                record=orders[data]
                product=stages[record["stage"]]
                artifact=json.loads((root/product["product_path"]).read_text())
                if scenario.get("qualification_failure"):
                    artifact=copy.deepcopy(artifact)
                    artifact["scope"]="UNQUALIFIED_MUTATED_PACKAGE"
                receipt=account.deliver(record["id"],product["id"],artifact,hour)
                record["acceptance"]=receipt
                record["state"]="verified" if receipt["accepted"] else "rejected"
                if not receipt["accepted"]:
                    account.event(record["id"],"refund",hour)
                    record["state"]="refunded"
                    buyers[record["index"]]["failed"]=True
            elif kind=="collect":
                record=orders[data]
                if record["state"]!="verified":
                    continue
                if scenario.get("provider_default") and record["kind"]=="initial" and record["index"]==0:
                    account.event(record["id"],"release",hour)
                    account.event(record["id"],"late_reversal",hour)
                    native_order = next(row for row in account.export()["ledger"]["orders"] if row["id"]==record["id"])
                    if int(native_order.get("refund_due",0))>0:
                        account.event(record["id"],"refund",hour)
                    record["state"]="provider-default-reversed"
                    buyers[record["index"]]["failed"]=True
                else:
                    account.event(record["id"],"release",hour)
                    record["state"]="released"
                    if record["stage"]=="k1":
                        buyers[record["index"]]["k1_collected"]=True
            elif kind=="observe":
                snapshot=account.snapshot()["summary"]
                state["monthly"].append({"month":data,"hour":hour,"calendar_utc":_calendar(protocol["epoch_utc"],hour),"state_microUSD":snapshot})
            elif kind!="mature-observe":
                raise ValueError("UNREGISTERED_EVENT_KIND")
        account.advance(max(end,max((row["warranty_through_hour_inclusive"]+1 for row in orders.values()),default=end)))
        exported=account.export()
        audit=audit_journal(exported,root=root,manifest=manifest)
        tape=exported["ledger"]
        aggregation=aggregate_native(tape)
        observer=trailing_profit(tape,operating_end_hour=end,operating_complete=True,aggregation=aggregation)
        for point in state["monthly"]:
            month_observer=trailing_profit(tape,operating_end_hour=point["hour"]+1,operating_complete=True,aggregation=aggregation)
            point["trailing_365_profit_microUSD"]=month_observer["trailing_365_day_profit_microUSD"]
            point["observed_short_window_profit_microUSD"]=month_observer["observed_window_profit_microUSD"]
        state["audit"]=audit
        state["observer"]=observer
        state["window_calendar_utc"]={"start_inclusive":_calendar(protocol["epoch_utc"],observer["interval"]["start_hour_inclusive"]),"end_exclusive":_calendar(protocol["epoch_utc"],observer["interval"]["end_hour_exclusive"])}
        state["final_native_summary_microUSD"]=tape["summary"]
        state["tax_assessed_microUSD"]=tax_assessed
        state["accepted_and_collected_orders"]=sum(r["state"]=="released" for r in orders.values())
        state["actual_package_deliveries"]=sum(r.get("acceptance",{}).get("accepted",False) for r in orders.values())
        state["distinct_synthetic_customers_collected"]=len({r["buyer"] for r in orders.values() if r["state"]=="released"})
        state["one_step_regret_max_microUSD"]=max((d["choice"]["one_step_regret_microUSD"] for d in state["decisions"] if "choice" in d),default=0)
        state["target_1b"]=observer["trailing_365_day_profit_microUSD"]>=micro(1_000_000_000)
        state["target_3b"]=observer["trailing_365_day_profit_microUSD"]>=micro(3_000_000_000)
        state["no_debt_no_followon_financing"]=True
        state["company_profit_is_not_investor_return"]=True
        state["cash_less_opening_microUSD"]=tape["summary"]["cash"]-opening
        state["account_summary_covered"]=tape["summary"]["payables"]==0 and tape["summary"]["cash"]>=sum(tape["summary"][key] for key in ("tailReserve","custodyReserve","workingCapital"))
        state["native_source_sha256"]=exported["connected_journal"]["source"]["sha256"]
        _save(folder/"account.public.json",exported)
        _save(folder/"aggregation.json",aggregation)
        _save(folder/"RESULT.json",state)
    return state


def _compact(state):
    summary=state["final_native_summary_microUSD"]
    return {"case_id":state["case_id"],"route":state["route"],"scenario":state["scenario"]["id"],"opening_microUSD":state["opening_microUSD"],"profit_microUSD":summary["profit"],"cash_microUSD":summary["cash"],"available_microUSD":summary["available"],"payables_microUSD":summary["payables"],"tail_reserve_microUSD":summary["tailReserve"],"revenue_microUSD":summary["revenue"],"expenses_microUSD":summary["expenses"],"trailing_365_profit_microUSD":state["observer"]["trailing_365_day_profit_microUSD"],"window_calendar_utc":state["window_calendar_utc"],"accepted_and_collected_orders":state["accepted_and_collected_orders"],"distinct_synthetic_customers_collected":state["distinct_synthetic_customers_collected"],"k2_investment":state["k2_investment"],"one_step_regret_max_microUSD":state["one_step_regret_max_microUSD"],"target_1b":state["target_1b"],"target_3b":state["target_3b"],"obligations_covered":state["account_summary_covered"],"matched_world_sha256":state["matched_world_sha256"],"native_source_sha256":state["native_source_sha256"],"result_path":"public/"+state["case_id"]+"/RESULT.json","account_path":"public/"+state["case_id"]+"/account.public.json"}


def _write_report(output,protocol,summary):
    text=["# Conditional computational-package economics", "", "These are finite authored business scenarios using canonical native accounts. No customer demand, commercial rights, physical deployment, financing commitment or actual revenue was validated. The primary unresolved-rights cases refuse licensing. The other cases explicitly assume hypothetical rights clearance.", "", "Each route has a separate account per scenario. Initial equity is not income; accounts are never pooled or topped up. Full-lifecycle computational costs, native fees, prepaid support, maintenance and declared taxes are included. Physical equipment and physical output are not offered. Unknown model/host bills remain unknown. A native financial audit verifies arithmetic and source binding, not market assumptions.", "", "| Route/scenario | Initial capital USD | Collected orders | Cumulative profit USD | Final365-day profit USD | Cash USD |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary["cases"]:
        if row["scenario"] in {"rights-unresolved","central-100k","central-1m","central-1b","non-entry","working-capital-aware","working-capital-greedy","earned-only-k2"}:
            text.append("| "+row["case_id"]+" | "+f"{row['opening_microUSD']/MICRO:,.2f}"+" | "+str(row["accepted_and_collected_orders"])+" | "+f"{row['profit_microUSD']/MICRO:,.2f}"+" | "+f"{row['trailing_365_profit_microUSD']/MICRO:,.2f}"+" | "+f"{row['cash_microUSD']/MICRO:,.2f}"+" |")
    text += ["", "The full registered denominator is "+str(len(summary["cases"]))+" separate businesses. All negative arms and refusal reasons are retained in per-case results. Additional capital cannot manufacture buyers, rights or an accepted scientific product. The one-step regret certificate applies only to the finite current price grid and cash state, not to a globally optimal enterprise.", "", "Operating epoch: "+protocol["epoch_utc"]+". Fixed endpoint: "+_calendar(protocol["epoch_utc"],protocol["operating_end_hour_exclusive"])+" exclusive. The final completed365-day window is computed from exact native event differences, not annualized month revenue. Later settlement drain is excluded from that operating window; its obligations remain visible.", "", "No USD1b or USD3b profit attainment is implied by capital, synthetic orders, computational checking or a scenario forecast. All claimed milestones must satisfy the exact source-bound trailing-year observer."]
    (output/"public"/"REPORT.md").write_text("\n".join(text)+"\n")


def run(root, output, products_path=None):
    root,output=Path(root).resolve(),Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((root/PROTOCOL).read_text())
    product_file=Path(products_path) if products_path else root/PREFIX/"PRODUCTS.json"
    if not product_file.is_absolute():
        product_file=root/product_file
    products=json.loads(product_file.read_text())
    if isinstance(products,dict):
        products=products["products"]
    if not isinstance(products,list) or len({p["id"] for p in products})!=len(products):
        raise ValueError("UNIQUE_PRODUCT_METADATA_LIST_REQUIRED")
    _save(output/"public"/"protocol.json",protocol)
    summary={"schema":"public-portfolio-native-economics-results/v1","protocol_sha256":hashlib.sha256((root/PROTOCOL).read_bytes()).hexdigest(),"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"products_file_sha256":hashlib.sha256(product_file.read_bytes()).hexdigest(),"scope":"SEPARATE_CONDITIONAL_COMPUTATIONAL_BUSINESSES_NOT_ACTUAL_COMMERCE","registered_businesses":len(ROUTES)*len(protocol["registered_scenarios"]),"cases":[],"actual_revenue_usd":0,"calibrated_demand":False,"actual_host_model_billing":None,"capital_secured":False}
    for route in ROUTES:
        for scenario in protocol["registered_scenarios"]:
            case_id=route+"-"+scenario["id"]
            print("START "+case_id,flush=True)
            try:
                result=_run_case(root,output,products,protocol,route,scenario)
            except Exception as error:
                _save(output/"public"/"CHECKPOINT.json",{"schema":"public-portfolio-economic-checkpoint/v1","failed_case":case_id,"error_type":type(error).__name__,"error":str(error),"completed_case_ids":[r["case_id"] for r in summary["cases"]],"registered_cases":summary["registered_businesses"],"failed_case_not_reseeded_or_retried":True})
                _save(output/"public"/"PARTIAL_RESULTS.json",summary)
                raise
            summary["cases"].append(_compact(result))
            print("DONE "+case_id+" collected="+str(result["accepted_and_collected_orders"])+" profit_microUSD="+str(result["final_native_summary_microUSD"]["profit"]),flush=True)
    summary["completed_businesses"]=len(summary["cases"])
    summary["target_1b_count"]=sum(row["target_1b"] for row in summary["cases"])
    summary["target_3b_count"]=sum(row["target_3b"] for row in summary["cases"])
    summary["working_capital_pairs"]=[]
    for route in ROUTES:
        pair={row["scenario"]:row for row in summary["cases"] if row["route"]==route and row["scenario"].startswith("working-capital-")}
        aware,greedy=pair["working-capital-aware"],pair["working-capital-greedy"]
        if aware["matched_world_sha256"]!=greedy["matched_world_sha256"]:
            raise ValueError("MATCHED_WORKING_CAPITAL_WORLD_CHANGED")
        summary["working_capital_pairs"].append({"route":route,"matched_world_sha256":aware["matched_world_sha256"],"aware_minus_greedy_profit_microUSD":aware["profit_microUSD"]-greedy["profit_microUSD"],"aware_minus_greedy_collected_orders":aware["accepted_and_collected_orders"]-greedy["accepted_and_collected_orders"]})
    _save(output/"public"/"RESULTS.json",summary)
    _write_report(output,protocol,summary)
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output",required=True)
    parser.add_argument("--products")
    args=parser.parse_args()
    result=run(args.root,args.output,args.products)
    print(json.dumps({"completed":result["completed_businesses"],"target_3b_count":result["target_3b_count"]}))
