"""Matched adaptive-growth experiment on the existing conditional scale simulator.

No live market data, customer contact, provider spend, or financial execution.
Costed channel capacity is a hypothesis; it cannot be interpreted as proven reach.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from .scale import default_config, simulate_scale

SCHEMA='agi-alpha/transformational-growth-frontier/v1'
ARMS=('keyed_legacy','cash_contract','paid_distribution','adaptive_allocation','distribution_and_allocation','joint')
REGIMES=('base','weak_demand','price_and_cost_shock','supply_constraint','channel_failure')
CAPITAL=(2_500_000,25_000_000)
DEVELOPMENT_SEEDS=(31,37,41)
CONFIRMATION_SEEDS=(10001,10002,10003,10004,10005,10006,10007,10008)
TARGETS=(100_000_000,1_000_000_000,10_000_000_000,100_000_000_000,
         1_000_000_000_000,10_000_000_000_000,100_000_000_000_000)


def hash_data(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def arm_policy(name, regime='base'):
    if name not in ARMS: raise ValueError('UNREGISTERED_ARM')
    distribution=name in ('paid_distribution','distribution_and_allocation','joint')
    fast=name in ('cash_contract','joint')
    adaptive=name in ('adaptive_allocation','distribution_and_allocation','joint')
    return {
        'settlement':'same_period' if fast else 'legacy',
        'clearing_fee_bps':300 if fast else 0,
        'price_discount_bps':500 if fast else 0,
        'allocation':'demand_matched' if adaptive else 'legacy',
        'acquisition_max_share_bps':5500 if adaptive else 1600,
        'capacity_max_share_bps':6000 if adaptive else 2500,
        'distribution':'paid_channel_capacity' if distribution else 'none',
        'channel_tranche_contacts':500 if distribution else 0,
        'channel_tranche_cost_cents':(5_000_000 if regime=='channel_failure' else 50_000) if distribution else 0,
        'channel_duration_months':12 if distribution else 0,
        'channel_max_share_bps':500 if distribution else 0,
        'channel_realization_bps':(50 if regime=='channel_failure' else 10000) if distribution else 0,
        'common_draws':True
    }


def config_for(regime,capital,arm):
    if regime not in REGIMES or arm not in ARMS or type(capital) is not int or capital not in CAPITAL:
        raise ValueError('UNREGISTERED_FACTOR')
    c=default_config()
    c['months']=60
    c['opening_cash_cents']=capital
    c['targets_annual_collected_cents']=list(TARGETS)
    c['settlement_months']=0 if arm_policy(arm)['settlement']=='same_period' else 1
    if regime=='weak_demand':
        c.update(qualification_probability=.4,choice_probability=.045,
                 activation_probability=.6,monthly_churn_probability=.10,
                 collection_probability=.90)
    elif regime=='price_and_cost_shock':
        c.update(choice_probability=.10,monthly_churn_probability=.06,
                 annual_price_compression=.10,supplier_cost_multiplier=1.8,
                 collection_probability=.86,refund_probability=.08)
    elif regime=='supply_constraint':
        c.update(supplier_capacity_jobs=7500,supplier_outage_probability=.15,
                 supplier_cost_multiplier=1.5,technical_acceptance_probability=.94)
    if regime=='channel_failure':
        c.update(choice_probability=.10,collection_probability=.92,monthly_churn_probability=.08)
    c['assumptions'] += (' Exploratory matched-growth fixture: channel tranches represent paid, '
         'expiring solicitation capacity and do not produce buyers. Model response, capacity '
         'fees and new contract uptake are unmeasured. Instant collection has an explicit '
         '3% incremental clearing fee and 5% price discount; buyer choice response to terms '
         'is not calibrated. Common keyed draws provide partial event matching, not '
         'full matched counterfactual customer identities.')
    return c


def compact(run):
    m=run['monthly'][-1] if run['monthly'] else {}
    return {'cash_survival':run['cash_survival'],'terminal_reason':run['terminal_reason'],
        'months_completed':run['months_completed'],
        'trailing_12_collected_cents':m.get('trailing_12_collected_revenue_cents',0),
        'cumulative_collected_cents':run['cumulative_collected_revenue_cents'],
        'cumulative_complete_cost_profit_cents':run['cumulative_profit_cents'],
        'end_unrestricted_cash_cents':run['ending_unrestricted_cash_cents'],
        'milestones':run['milestones'],
        'channel_spend_cents':sum(x.get('channel_investment_cents',0) for x in run['monthly']),
        'fast_clearing_fee_cents':sum(x.get('fast_clearing_fee_cents',0) for x in run['monthly']),
        'binding_constraints':run['binding_constraints']}


def phase_results(seeds):
    if not seeds or len(seeds)!=len(set(seeds)) or set(seeds) not in (set(DEVELOPMENT_SEEDS),set(CONFIRMATION_SEEDS)):
        raise ValueError('UNREGISTERED_OR_OVERLAPPING_SEEDS')
    data={}
    for capital in CAPITAL:
        for regime in REGIMES:
            runs={}
            for arm in ARMS:
                conf=config_for(regime,capital,arm)
                pol=arm_policy(arm,regime)
                trajectories=[compact(simulate_scale(conf,seed,intervention=pol)) for seed in seeds]
                runs[arm]=trajectories
            data[f'{capital}:{regime}']=runs
    return data


def aggregate_phase(data):
    out={}
    for key,arms in data.items():
        out[key]={}
        for arm,runs in arms.items():
            count=len(runs)
            target_stats={str(target):{'reached':sum(t['milestones'][str(target)] is not None for t in runs),
                         'total':count,
                         'first_passage_months_including_unreached':[t['milestones'][str(target)] for t in runs]}
                         for target in TARGETS}
            out[key][arm]={
                'runs':count,'cash_survival_count':sum(x['cash_survival'] for x in runs),
                'mean_trailing_12_collected_cents':round(sum(x['trailing_12_collected_cents'] for x in runs)/count),
                'mean_complete_cost_profit_cents':round(sum(x['cumulative_complete_cost_profit_cents'] for x in runs)/count),
                'median_complete_cost_profit_cents':sorted(x['cumulative_complete_cost_profit_cents'] for x in runs)[count//2],
                'mean_channel_spend_cents':round(sum(x['channel_spend_cents'] for x in runs)/count),
                'mean_clearing_fee_cents':round(sum(x['fast_clearing_fee_cents'] for x in runs)/count),
                'binding_constraints':sorted(set().union(*(set(x['binding_constraints']) for x in runs))),
                'milestones':target_stats}
    return out


def evaluate():
    dev=aggregate_phase(phase_results(DEVELOPMENT_SEEDS))
    # This is a deterministic DEVELOPMENT-only selection. The prescribed
    # confirmation set is executed once with every arm, including the winner.
    scores={arm:0 for arm in ARMS}
    for data in dev.values():
        for arm,record in data.items():
            scores[arm]+=record['mean_complete_cost_profit_cents'] if record['cash_survival_count']==len(DEVELOPMENT_SEEDS) else -10**17
    selected=max(ARMS,key=lambda arm:(scores[arm],-ARMS.index(arm)))
    confirmation=aggregate_phase(phase_results(CONFIRMATION_SEEDS))
    return {'schema':SCHEMA,'scope':'UNVALIDATED_STRATEGIC_MARKET_PROJECTION',
        'protocol_sha256':hash_data({'arms':ARMS,'regimes':REGIMES,'capital':CAPITAL,
                  'dev':DEVELOPMENT_SEEDS,'confirm':CONFIRMATION_SEEDS,'targets':TARGETS}),
        'baseline_inherited':'enterprise.scale.simulate_scale exact legacy policy unchanged for intervention=None',
        'controlled_baseline':'keyed_legacy, same conditional economics but keyed per-stage random draws',
        'candidate_selected_on_development_only':selected,'development_scores_cents':scores,
        'development':dev,'confirmation':confirmation,
        'actual_customers':0,'actual_collected_usd':0,
        'financial_verdict':'NOT_EVALUATED_BY_NATIVE_LEDGER',
        'commercial_success':'NOT_ESTABLISHED_BY_THIS_PROJECTION',
        'beyond_human_foresight':'NOT_ESTABLISHED',
        'important_limits':[
            'Customer volumes, channel program costs, buyer choices and price sensitivity are authored hypotheses.',
            'Fixed price in conditional scale model is not a responsive strategic pricing equilibrium.',
            'Multiple policies share seeded stage draws but customer identity matching is incomplete.',
            'Same-period settlement is an explicitly priced hypothetical contract; physical clearing is untested.',
            'No real service, provider billing, customer payment or native authenticated reservation occurs.',
            'Unreached revenue targets remain censored within the declared 60-month qualification horizon; insolvency is a competing failure.',
            'Initial cash includes a declared bootstrap allocation; retained cash does not prove earned funding.'
        ]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink() or any(p.is_symlink() for p in args.output.parents):
        parser.error('NEW_UNSYMLINKED_OUTPUT_REQUIRED')
    result=evaluate()
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write('\n')
    print('Conditional held-out frontier executed; development winner:',result['candidate_selected_on_development_only'])
    print('Actual customer revenue: zero. No calibrated market-optimality claim.')

if __name__=='__main__':main()
