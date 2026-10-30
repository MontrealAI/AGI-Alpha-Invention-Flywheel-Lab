"""Adversarial, post-confirmation channel sensitivity; not calibrated evidence."""
from __future__ import annotations
import argparse
import json
import statistics
from pathlib import Path
from .growth_frontier import arm_policy,config_for
from .scale import simulate_scale

PRICES_USD=(500,5000,50000)
REALIZATION_BPS=(10000,5000,1000,100)
SEEDS=(8101,8102,8103,8104)


def analyze():
    rows=[]
    for price in PRICES_USD:
        for realization in REALIZATION_BPS:
            results=[]
            for seed in SEEDS:
                conf=config_for('base',2_500_000,'paid_distribution')
                policy=arm_policy('paid_distribution')
                policy.update(channel_tranche_cost_cents=price*100,channel_realization_bps=realization)
                results.append(simulate_scale(conf,seed,intervention=policy))
            rows.append({
                'tranche_cost_usd':price,'realization_bps':realization,'seed_count':len(SEEDS),
                'mean_trailing_12_collected_usd':round(statistics.mean(
                    x['monthly'][-1]['trailing_12_collected_revenue_cents'] for x in results)/100),
                'billion_trailing_reached':sum(x['milestones']['100000000000'] is not None for x in results),
                'cash_survival_count':sum(x['cash_survival'] for x in results),
                'mean_channel_spend_usd':round(statistics.mean(sum(r['channel_investment_cents']
                    for r in x['monthly']) for x in results)/100)
            })
    return {'schema':'agi-alpha/channel-inverse-stress/v1',
        'scope':'POST_CONFIRMATION_EXPLORATORY_UNVALIDATED',
        'source':'Original conditional enterprise scale with opt-in channel costs and deterministic seeds',
        'seeds':list(SEEDS),'tranche_is_500_contact_slots_per_month_for_12_months':True,
        'rows':rows,'observed_customers':0,'observed_collected_usd':0,'market_calibration':'NONE',
        'limits':['The model assigns buyer conversion probabilities without empirical channel measurements.',
            'These cases were examined after the earlier scenario results and are not a new independent confirmation.',
            'No market competition equilibrium or provider delivery agreement is established.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    a=parser.parse_args()
    if a.output.exists() or a.output.is_symlink() or any(p.is_symlink() for p in a.output.parents):
        parser.error('NEW_UNSYMLINKED_OUTPUT_REQUIRED')
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(analyze(),f,indent=2,sort_keys=True);f.write('\n')
    print('Post-confirmation channel sensitivity; no observed market results')

if __name__=='__main__':main()
