import argparse,hashlib,json
from decimal import Decimal as D,ROUND_HALF_UP
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def amount(value):return format(value.quantize(D('0.01'),rounding=ROUND_HALF_UP),'.2f')

def audit(root,output):
    output.mkdir(parents=True,exist_ok=False)
    policy_path=root/'research/next009/commerce/policy.json'
    report_path=root/'evidence/next009/commerce/net1-primary-final-v1/artifacts/COMMERCIAL.json'
    p=json.loads(policy_path.read_text());r=json.loads(report_path.read_text());n=p['cohort_size'];price=D(p['price_cad'])
    noninfer=sum(D(v) for v in p['non_inference_costs_per_attempt_cad'].values())
    inferred_usd=(D(p['input_tokens_per_attempt'])*D(p['inference_input_usd_per_million'])+D(p['output_tokens_per_attempt'])*D(p['inference_output_usd_per_million']))/1000000
    base_inference=inferred_usd*D(p['cad_per_usd']);fixed=sum(D(v) for v in p['fixed_costs_cad'].values());rows=[]
    by_name={row['name']:row for row in r['card_analytical_scenarios']}
    for scenario in p['scenarios']:
        sold,refunds,disputes,pending=[int(D(n)*D(scenario[k])) for k in ['sold_fraction','refund_fraction_of_cohort','dispute_fraction_of_cohort','pending_payout_fraction_of_cohort']]
        production=D(n)*(noninfer+base_inference*D(scenario['inference_multiplier']));extra=D(scenario['extra_lifecycle_cost_cad']);revenue=D(sold-refunds-disputes)*price
        processing=D(sold)*(D(p['card_route']['percentage'])*price+D(p['card_route']['fixed_cad']));dispute_fees=D(disputes)*D(p['card_route']['dispute_received_cad']);expenses=production+fixed+extra+processing+dispute_fees;profit=revenue-expenses
        delayed=D(pending)*price;working=D(p['working_capital_reserve_cad']);equity=production+fixed+extra+working if scenario.get('equity_policy')=='prefund_all_production_plus_working_only' else D(p['seller_initial_simulated_equity_cad']);bank=equity+revenue-delayed-expenses
        reserve=D(sold-refunds-disputes)*(price+D(p['card_route']['dispute_received_cad']));free=max(D(0),bank-reserve-working);net_earned=revenue-delayed-expenses;remaining_equity=max(D(0),equity+min(D(0),net_earned));earned_reserve=max(D(0),reserve+working-remaining_equity);conditional=max(D(0),min(free,net_earned-earned_reserve))
        expected={'earned_revenue':revenue,'production_all_attempts':production,'fixed_research_setup_overhead':fixed,'processing_fees_retained_on_refunds':processing,'dispute_fees':dispute_fees,'accounting_profit_within_authored_scenario':profit,'delayed_processor_receivable':delayed,'available_bank_cash':bank,'retained_principal_plus_dispute_reserve':reserve,'available_after_reserves':free,'conditional_earned_cash_after_equity_backing':conditional}
        observed=by_name[scenario['name']];checks=[{'field':k,'expected_exact':str(v),'expected_cents':amount(v),'reported':observed['cashflow_cad'][k],'passed':amount(v)==observed['cashflow_cad'][k]} for k,v in expected.items()]
        checks.extend([{'field':'cash_profit_bridge','passed':bank+delayed==equity+profit},{'field':'zero_qualified_reinvestment','passed':observed['reinvestment']['qualified_budget_cad']=='0.00' and observed['reinvestment']['investment_made'] is False},{'field':'human_claims_remain_unknown','passed':observed['frontiers']['human_time_observed'] is None and observed['frontiers']['human_full_cost_profit'] is None and observed['frontiers']['human_to_AI_profit_crossing']=='NOT_ESTABLISHED'}])
        rows.append({'scenario':scenario['name'],'checks':checks,'passed':all(c['passed'] for c in checks)})
    bindings={'artifact':root/'evidence/next009/construction/networks-v2/artifacts/Net1/generated_plan.json','receipt':root/'evidence/next009/verification/primary-confirmation/artifacts/ACCEPTANCE.json','verifier':root/'verification/next009/verify.py','protocol':root/'verification/next009/protocol.json'}
    identity_checks={k:sha(path)==r['binding'][k] for k,path in bindings.items()}
    source_check=sha(root/'research/next009/commerce/run.py')==r['adapter_sha256'];policy_check=sha(policy_path)==r['policy_template_sha256']
    claims=r['claims'];qualified=(claims['qualified_unrestricted_simulated_earnings_cad']=='0.00' and claims['actual_revenue_cad']=='0.00' and claims['earned_funded_successor']=='DEFERRED')
    result={'schema':'agi-alpha/next009-independent-commercial-arithmetic-audit/v1','passed':all(row['passed'] for row in rows) and all(identity_checks.values()) and source_check and policy_check and qualified,'policy_sha256':sha(policy_path),'commercial_report_sha256':sha(report_path),'auditor_sha256':sha(Path(__file__)),'identity_checks':identity_checks,'source_check':source_check,'policy_check':policy_check,'qualification_labels_correct':qualified,'scenario_count':len(rows),'scenarios':rows,'scope':'Independent Decimal arithmetic and source/claim audit. Does not import candidate commercial arithmetic or establish empirical model usage, cost completeness, demand, human duration, investment attractiveness or real revenue.','interpretation_notes':['CAD2057.8102 base profit and CAD1557.8102 conditional earned cash are authored-scenario results; qualified earned funds remain zero.','The 23.4456-minute human wage threshold compares wage-only labor with variable autonomous production cost, excluding fixed research/setup and processing expenses; it must not be described as a complete-cost advantage.','The 194.0885-minute wage-only threshold is a sufficient modeled human-loss condition under the declared revenue and fee basis, not an observed matched-task duration or demonstrated crossing.']}
    (output/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['passed','scenario_count','identity_checks','qualification_labels_correct']}))
    return result['passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if audit(a.root.resolve(),a.output.resolve()) else 1)
