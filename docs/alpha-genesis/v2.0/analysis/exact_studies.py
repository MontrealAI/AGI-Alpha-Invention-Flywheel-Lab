"""Exact authored examples for ALPHA GENESIS FLYWHEEL OMEGA, edition 2.0.
No live models, invented measurements, payments, or claims of open-world optimality.
The reference solver below reimplements transitions, not the producer's methods.
"""
from dataclasses import replace
from fractions import Fraction as F
from functools import lru_cache
from itertools import product
from pathlib import Path
import argparse, json
from decision_model import Config, Planner


def oracle(config, allow_probe=True):
    """Independent finite recursion on tuple states and explicit transitions."""
    c=config
    @lru_cache(None)
    def solve(h, cash, probability, probed, built, done):
        if h == 0 or done == 3:
            return F(0)
        scores=[F(0)]
        for i in (0,1):
            if done & (1<<i):
                continue
            gains=[c.specialist_net_delivery[i]]
            if c.frontier_access:
                gains.append(c.frontier_net_delivery[i])
            if built == 1:
                gains.append(c.constructed_net_delivery[i]-c.maintenance_per_delivery)
            for gain in gains:
                scores.append(F(gain)+solve(h-1,cash+gain,probability,probed,built,done|(1<<i)))
        if built == 0 and cash-c.construction_cost >= c.protected_reserve:
            good=solve(h-1,cash-c.construction_cost,F(1),probed,1,done)
            bad=solve(h-1,cash-c.construction_cost,F(0),probed,-1,done)
            scores.append(-F(c.construction_cost)+probability*good+(1-probability)*bad)
        if allow_probe and not probed and built == 0 and cash-c.probe_cost >= c.protected_reserve:
            positive=probability*c.signal_sensitivity+(1-probability)*c.signal_false_positive
            total=-F(c.probe_cost)
            if positive:
                posterior=probability*c.signal_sensitivity/positive
                total+=positive*solve(h-1,cash-c.probe_cost,posterior,True,0,done)
            if positive < 1:
                posterior=probability*(1-c.signal_sensitivity)/(1-positive)
                total+=(1-positive)*solve(h-1,cash-c.probe_cost,posterior,True,0,done)
            scores.append(total)
        return max(scores)
    return solve(c.horizon,c.starting_cash,c.initial_p_good,False,0,0)


def encoded(x):
    return {'exact':str(x),'decimal':float(x)}


def calculations():
    configs={
        'diagnostic': Config(),
        'frontier_improves': replace(Config(),frontier_net_delivery=(28,30)),
        'upkeep_erases_gain': replace(Config(),maintenance_per_delivery=25),
        'no_market': replace(Config(),frontier_net_delivery=(-5,-5),specialist_net_delivery=(-6,-6),constructed_net_delivery=(-4,-4),maintenance_per_delivery=25),
    }
    rows=[]
    for label,c in configs.items():
        p=Planner(c); value,action=p.choose(); reference=oracle(c)
        if value!=reference: raise ArithmeticError('independent oracle mismatch')
        rows.append({'case':label,'first_action':action,'optimal_value':encoded(value),'no_probe_value':encoded(oracle(c,False)),'direct_delivery_value':encoded(p.greedy_no_experiment()[0]),'independent_oracle_equal':True})
    checked=0
    for prior,build,maintenance,tp in product((F(1,10),F(7,20),F(4,5)),(4,12,16),(0,10,25),(F(1,2),F(9,10))):
        c=replace(Config(),initial_p_good=prior,construction_cost=build,maintenance_per_delivery=maintenance,signal_sensitivity=tp)
        if Planner(c).choose()[0]!=oracle(c):raise ArithmeticError('sensitivity oracle mismatch')
        checked+=1
    c=Config(); p=Planner(c)
    branches=[{'probability':encoded(w),'posterior':encoded(s.p_good),'next_action':p.choose(s)[1]} for w,r,s in p.outcomes(p.initial(),'probe')]
    perfect=(c.initial_p_good*oracle(replace(c,initial_p_good=F(1)),False)+(1-c.initial_p_good)*oracle(replace(c,initial_p_good=F(0)),False))
    return {
        'scope':'EXACT_AUTHORED_FINITE_DECISION_EXAMPLES_NOT_EMPIRICAL_MARKETS',
        'cases':rows,'independently_reimplemented_sensitivity_cases':checked,'diagnostic_branches':branches,
        'information':{'no_probe':encoded(oracle(c,False)),'net_probe_advantage':encoded(p.choose()[0]-oracle(c,False)),'perfect_information_value_before_cost':encoded(perfect),'evpi':encoded(perfect-oracle(c,False))},
        'complementary_means':{'base':0,'instrument_only':-4,'interface_only':-3,'together':13,'joint_benefit':20,'scope':'Authored one-shot net values; no discovered tool.'},
        'competitive_diffusion':{'before':{'maximum_price':130,'cost':100,'margin':30},'after':{'maximum_price':60,'cost':40,'margin':20},'scope':'Illustrative buyer willingness-to-pay ceiling, no observed price.'},
        'retention':{'prospective_uses':12,'saving_per_use':8,'remaining_integration':15,'carrying_cost':20,'net_avoidance_value':61,'high_upkeep_value':-39},
    }


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    if args.out.exists(): raise SystemExit('Refusing to overwrite existing result')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(calculations(),indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
