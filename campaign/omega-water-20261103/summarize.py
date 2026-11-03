"""Derive compact public evidence from a fully replayed private simulation run."""
import argparse
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from commercial.ledger import digest
from omega import operate, strategy

def compact(native, source_commit, measurement=None):
    audit=operate.replay_audit(native)
    raw=json.loads((Path(native)/'result.json').read_text())
    registration=json.loads((Path(native)/'registration.json').read_text())
    game=strategy.make_game()
    if registration['game'] != json.loads(json.dumps(strategy.model_disclosure(game))):
        raise ValueError('CENTRAL_REFERENCE_GAME_REQUIRED')
    comparisons=[]
    for mode in operate.MODES:
        policy=strategy.solve(game,mode)
        rows=[r for r in raw['accounts'] if r['policy_mode']==mode]
        if len(rows)!=len(game.worlds):raise ValueError('COMPLETE_WORLD_COMPARISON_REQUIRED')
        priors={w.id:w.prior for w in game.worlds}
        expected=sum(priors[r['world_id']]*r['economic_profit_cents'] for r in rows)
        if expected!=policy.expected_profit_cents:raise ValueError('NATIVE_EXPECTATION_DIFFERS_FROM_POLICY')
        comparisons.append({**strategy.summary(game,policy),'expected_economic_profit_cents_exact':str(expected),
            'best_economic_profit_cents':max(r['economic_profit_cents'] for r in rows),
            'worlds':[{'id':r['world_id'],'prior':str(priors[r['world_id']]),
                'accepted_orders':r['accepted_orders'],'refunded_orders':r['refunded_orders'],
                'cash_profit_microUSD':r['native_summary_microUSD']['profit'],
                'economic_profit_cents':r['economic_profit_cents'],
                'ending_cash_microUSD':r['native_summary_microUSD']['cash'],
                'available_microUSD':r['native_summary_microUSD']['available'],
                'residual_reserve_microUSD':r['native_summary_microUSD']['tailReserve'],
                'trailing_year_profit_microUSD':r['trailing_profit']['trailing_365_day_profit_microUSD'],
                'native_audit_accepted':r['native_audit_accepted'],
                'native_actions_sha256':r['native_actions_sha256'],
                'public_record_sha256':r['public_record_sha256'],'trace_sha256':digest(r['trace'])} for r in rows]})
    variants={
        **{f'autonomous_ai{bill//100}_founder{slots}':strategy.make_game(costs=replace(strategy.Costs(),packaging_hours=0,research_cents=100,outreach_cents=100,webinar_facilitation_cents=0,ai_build_bill_cents=bill,founder_total_minutes=30,founder_slots_per_quarter=slots)) for bill in (10000,100000) for slots in (0,1)},
        'packaging_20h':strategy.make_game(cost_scenario='low'),
        'packaging_160h':strategy.make_game(cost_scenario='high'),
        'capital_1000usd':strategy.make_game(capital_cents=100000),
        'founder_value_20000usd':strategy.make_game(founder_value_cents=2000000),
        'lower_workload_30founder_60webinar_minutes':strategy.make_game(costs=replace(strategy.Costs(),founder_total_minutes=30,webinar_facilitation_cents=9340)),
        'exception12_dispute20_minutes':strategy.make_game(costs=replace(strategy.Costs(),exception_minutes_per_order=12,dispute_minutes_per_refund=20)),
        'ai100_base30usd':strategy.make_game(costs=replace(strategy.Costs(),ai_build_bill_cents=10000,webinar_unknown_base_cents=3000)),
        'ai1000_base90usd':strategy.make_game(costs=replace(strategy.Costs(),ai_build_bill_cents=100000,webinar_unknown_base_cents=9000)),
        'founder_opportunity_2000usd_per_hour':strategy.make_game(costs=replace(strategy.Costs(),founder_opportunity_cents_per_hour=200000)),
    }
    sensitivities={name:{**strategy.summary(g,strategy.solve(g)), 'scope':'PURE_FINITE_POLICY_SENSITIVITY_NOT_NATIVE_POSTED'} for name,g in variants.items()}
    return {'schema':'omega/corrected-compact-evidence/v2','executed_source_commit':source_commit,
        'source_hashes':registration['source_hashes'],'native_replay':audit,
        'native_result_sha256':digest(raw),'registration_sha256':digest(registration),
        'model':strategy.model_disclosure(game),'policy_comparisons':comparisons,'sensitivities':sensitivities,
        'value_of_research_cents_exact':str(Fraction(comparisons[0]['expected_economic_profit_cents_exact'])-Fraction(comparisons[1]['expected_economic_profit_cents_exact'])),
        'counterfactual_accounts_must_not_be_pooled':True,'all_accounts_independent_seed_microUSD':100000000000,
        'modeled_currency':'USD','endpoint_hour_exclusive':8760,
        'actual_complete_cost_profit_microUSD':None,'actual_tax_microUSD':None,'actual_model_host_bill_microUSD':None,
        'measured_execution_resources':measurement,'three_billion_target_achieved':False,'super_alpha':'NOT_ESTABLISHED',
        'buyer_evidence':'HISTORICAL_RESULT.json buyer, source a0884eab7cf6c8f271fef3553857bfc6e2024033; unchanged scientific result',
        'limits':['Authored demand/prior/reach and delivery outcomes, not customer evidence',
                  'Finite-model exactness is not real-world or global strategic optimality',
                  'Unvalidated founder-access premium drives central positive expected value',
                  'Costs are conditional model inputs; complete actual costs and taxes remain unknown',
                  'Simulated distribution rights do not grant a real open-source license',
                  'No actual payment, outreach, deployment, account migration or release']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',required=True);p.add_argument('--source-commit',required=True);p.add_argument('--measurement');p.add_argument('--autonomous');p.add_argument('--output',required=True);a=p.parse_args()
    result=compact(a.native,a.source_commit,json.loads(Path(a.measurement).read_text()) if a.measurement else None)
    if a.autonomous:
        ar=operate.replay(a.autonomous);reg=json.loads((Path(a.autonomous)/'registration.json').read_text());priors={w.id:w.prior for w in strategy.make_game().worlds}
        result['autonomous_native_sensitivity']={'scope':'NO_MANDATORY_HUMAN_PAYROLL_OR_FOUNDER; AUTHORED_MACHINE_AND_ACQUISITION_COSTS_NOT_ACTUAL_BILLS','registration_sha256':digest(reg),'native_result_sha256':digest(ar),'account_count':ar['account_count'],'model':reg['game'],'actual_complete_cost_profit_microUSD':None,'expected_economic_profit_cents_exact':str(sum(priors[r['world_id']]*r['economic_profit_cents'] for r in ar['accounts'])),'worlds':[{'id':r['world_id'],'accepted_orders':r['accepted_orders'],'refunded_orders':r['refunded_orders'],'economic_profit_cents':r['economic_profit_cents'],'cash_profit_microUSD':r['native_summary_microUSD']['profit'],'residual_reserve_microUSD':r['native_summary_microUSD']['tailReserve'],'native_audit_accepted':r['native_audit_accepted'],'native_actions_sha256':r['native_actions_sha256']} for r in ar['accounts']]}
    Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'bytes':Path(a.output).stat().st_size,'accounts':result['native_replay']['account_count'],'replay_accepted':result['native_replay']['accepted']}))
