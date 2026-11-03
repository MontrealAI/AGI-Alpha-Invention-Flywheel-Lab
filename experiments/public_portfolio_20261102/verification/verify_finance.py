from __future__ import annotations
import argparse, copy, hashlib, json, sys, time
from pathlib import Path
import verify_science as base

ROOT=base.ROOT
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))


def read(path):
    return json.loads(Path(path).read_text())


def signed_profit_window(tape,end):
    start=max(0,end-8760);total=0
    for action in tape['actions']:
        if start<=action['day']<end:
            total+=(action['after']['revenue']-action['before']['revenue'])+(action['after']['recoveryIncome']-action['before']['recoveryIncome'])-(action['after']['expenses']-action['before']['expenses'])
    return total


def check_quotes(state,checks):
    profile=state['cost_profile_microUSD'];bad=[]
    for decision in state['decisions']:
        if 'choice' not in decision:
            continue
        quote=decision['choice'];value=None
        outside=quote['outside_costs_microUSD']
        for a in quote['actions'][1:]:
            inferred=a['buyer_utility_microUSD']+a['price_microUSD']+profile['adoption']
            value=inferred if value is None else value
            if inferred!=value:
                bad.append('inconsistent_value')
        if value is None:
            bad.append('empty_price_grid');continue
        best_outside=max([0,*[max(0,value-c) for c in outside.values()]])
        fulfillment=sum(profile[k] for k in ('onboarding','compute','verification','correction','delivery_storage_isolation','support_term','compatibility_maintenance_term'))
        eligible=[]
        for a in quote['actions'][1:]:
            price=a['price_microUSD'];buyer=price>=200000 and price+profile['adoption']<=decision['buyer_remaining_budget_microUSD'] and value-price-profile['adoption']>best_outside
            contribution=price-fulfillment-profile['acquisition']-200000
            if buyer!=a['chosen_by_buyer'] or contribution!=a['contribution_microUSD']:
                bad.append('buyer_or_contribution')
            if buyer and a['funding_feasible'] and contribution>0:
                eligible.append(contribution)
        optimum=max([0,*eligible]);achieved=quote['selected']['contribution_microUSD']
        if achieved!=optimum or quote['enumerated_one_step_optimum_microUSD']!=optimum or quote['one_step_regret_microUSD']!=optimum-achieved:
            bad.append('finite_optimum')
    checks.add('independent_current_price_game_arithmetic',not bad,failures=bad)


def check_case(folder,state,manifest,record,expected_end):
    checks=base.Checks();tape=record['ledger'];summary=tape['summary'];opening=tape['config']['opening']
    checks.add('capital_is_not_income',opening==state['opening_microUSD'] and summary['cash']==opening+summary['collections']+summary['recoveryIncome']-summary['expensePaid'])
    checks.add('complete_profit_identity',summary['profit']==summary['revenue']+summary['recoveryIncome']-summary['expenses'])
    prior=None;invalid=[];last=-1
    for a in tape['actions']:
        if a['day']<last or (prior is not None and a['before']!=prior):
            invalid.append(a['seq'])
        last=a['day'];prior=a['after']
        s=a['after']
        if s['cash']!=opening+s['collections']+s['recoveryIncome']-s['expensePaid'] or s['profit']!=s['revenue']+s['recoveryIncome']-s['expenses'] or not 0<=s['unrestrictedEarned']<=s['available']:
            invalid.append(a['seq'])
    checks.add('all_event_prefixes_conserve_cash_profit_and_earned_funds',not invalid,invalid_sequences=invalid)
    own=signed_profit_window(tape,expected_end);reported=state['observer']
    checks.add('independent_exact_completed_365_day_profit',reported['trailing_365_day_profit_microUSD']==own and reported['interval']['start_hour_inclusive']==expected_end-8760 and reported['interval']['end_hour_exclusive']==expected_end and reported['complete_365_day_operating_history'])
    monthly=[]
    for row in state['monthly']:
        actual=signed_profit_window(tape,row['hour']+1)
        expected=actual if row['hour']+1>=8760 else None
        if row['trailing_365_profit_microUSD']!=expected or row['observed_short_window_profit_microUSD']!=actual:
            monthly.append(row['month'])
    checks.add('all_monthly_windows_use_exact_native_event_boundaries',not monthly and len(state['monthly'])==36,failed_months=monthly)
    assessed=0;tax_failures=[]
    for a in tape['actions']:
        if a['op']=='cost' and a['args']['id'].startswith('tax-assessment-'):
            pretax=a['before']['profit']+assessed;due=max(0,max(0,pretax)//4-assessed)
            if a['args']['amount']!=due:
                tax_failures.append(a['seq'])
            assessed+=due
    checks.add('independent_cumulative_tax_assessments',not tax_failures and assessed==state['tax_assessed_microUSD'],failed_sequences=tax_failures)
    wallet_buyers=[a['args']['buyer'] for a in tape['actions'] if a['op']=='wallet']
    offers=[a for a in tape['actions'] if a['op']=='offer'];ids=[a['args']['id'] for a in offers]
    checks.add('buyer_wallet_never_topped_up_and_orders_not_duplicated',len(wallet_buyers)==len(set(wallet_buyers)) and len(ids)==len(set(ids)))
    product_ids={p['id'] for p in manifest['jobs']}
    checks.add('only_registered_route_products_offered',all(a['args']['job_id'] in product_ids and a['args']['job_id'].startswith(state['route']+'-') for a in offers))
    if state['route']=='arrangement':
        checks.add('original_rejected_arrangement_products_never_sold',not offers and not state['accepted_and_collected_orders'])
    if not state['scenario'].get('rights',True) or state['scenario']['id']=='no-demand':
        checks.add('rights_or_demand_failure_refuses_sales',not offers and not state['accepted_and_collected_orders'])
    k2=state.get('k2_investment') or {}
    if k2.get('funded') and state['scenario'].get('earned_only_k2'):
        checks.add('earned_only_successor_uses_actual_unrestricted_earnings',k2.get('funding')=='EARNED' and k2['before_unrestricted_earned_microUSD']>=k2['cost_microUSD'])
    coverage=summary['payables']==0 and summary['cash']>=sum(summary[k] for k in ('tailReserve','custodyReserve','workingCapital','reservedInvestment'))
    checks.add('reported_obligation_coverage_matches_native_state',bool(state['account_summary_covered'])==bool(coverage))
    released=sum(r['state']=='released' for r in tape['orders'])
    checks.add('collected_order_count_matches_native_orders',released==state['accepted_and_collected_orders'])
    check_quotes(state,checks)
    return {'case_id':state['case_id'],'checks':checks.rows,'passed':all(c['passed'] for c in checks.rows),
            'independent_trailing365_profit_microUSD':own,'native_full_replay':False,'obligations_covered':coverage}


def run(public_root):
    from connected_enterprise.finance import audit_journal
    from experiments.public_portfolio_20261102 import service
    protocol=read(HERE/'FINANCIAL_VERIFICATION_PROTOCOL.json')
    declared=read(ROOT/'experiments/public_portfolio_20261102/ECONOMICS_PROTOCOL.json')
    summary=read(public_root/'RESULTS.json');rows=[];all_ids=[]
    for compact in summary['cases']:
        ident=compact['case_id']
        if '/' in ident or '..' in ident:
            raise ValueError('invalid public case identity')
        folder=public_root/ident;state=read(folder/'RESULT.json');manifest=read(folder/'manifest.json');record=read(folder/'account.public.json')
        result=check_case(folder,state,manifest,record,declared['operating_end_hour_exclusive'])
        if ident in protocol['native_full_replay_subset']:
            try:
                audit=audit_journal(record,root=ROOT,manifest=manifest)
                result['native_full_replay']=True;result['native_audit']=audit
            except Exception as exc:
                result['passed']=False;result['native_replay_error']=type(exc).__name__+': '+str(exc)
        rows.append(result);all_ids.append(ident)
        print('AUDITED '+ident+' passed='+str(result['passed'])+' native='+str(result['native_full_replay']),flush=True)
    expected={r+'-'+s['id'] for r in ('purpose','interface','complementarity','arrangement','foundry') for s in declared['registered_scenarios']}
    negative_checks=base.Checks()
    candidate=copy.deepcopy(read(ROOT/'experiments/public_portfolio_20261102/PRODUCTS.json')[0])
    candidate['delivery_path']=service.PREFIX+'deliveries/independent-negative-test/'+candidate['id']+'.json'
    forged=copy.deepcopy(candidate);forged['approval_path']=service.PREFIX+'producer-chosen-approval.json'
    negative_checks.reject('producer_selected_approval_trust_anchor_refused',lambda:service._product(ROOT,forged))
    forged=copy.deepcopy(candidate);forged['product_path']=service.PREFIX+'producer-chosen-product.json'
    negative_checks.reject('noncanonical_product_path_refused',lambda:service._product(ROOT,forged))
    full_native=sum(r['native_full_replay'] for r in rows)
    denominator=set(all_ids)==expected and len(all_ids)==len(expected)==summary['registered_businesses']==summary['completed_businesses']
    subset_done=full_native==len(protocol['native_full_replay_subset'])
    return {'schema':'public-portfolio-independent-financial-replay/v1','checker_sha256':base.digest(__file__),
            'protocol_sha256':base.digest(HERE/'FINANCIAL_VERIFICATION_PROTOCOL.json'),'producer_summary_sha256':base.digest(public_root/'RESULTS.json'),
            'completed_accounts_checked':len(rows),'registered_denominator_complete':denominator,
            'independent_full_native_replays':full_native,'predeclared_native_subset_complete':subset_done,
            'authority_negative_checks':negative_checks.rows,'cases':rows,
            'passed':denominator and subset_done and all(r['passed'] for r in rows) and all(r['passed'] for r in negative_checks.rows),
            'scope':'Arithmetic on conditional authored businesses, not market validation or actual commerce; public exports only, no private account authority read',
            'target3b_independently_reached_accounts':sum(r['independent_trailing365_profit_microUSD']>=3_000_000_000_000_000 for r in rows)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public-root',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    public_root=Path(args.public_root).resolve();output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of independent financial audit')
    started=time.time();value=run(public_root);value['wall_seconds']=time.time()-started
    output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':value['passed'],'accounts_checked':value['completed_accounts_checked'],'full_native_replays':value['independent_full_native_replays']}))
    raise SystemExit(0 if value['passed'] else 1)
