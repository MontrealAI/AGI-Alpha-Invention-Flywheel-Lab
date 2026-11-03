"""Authored, reproducible finite market scenarios, never empirical demand."""
from __future__ import annotations
from itertools import product
import random
from .market_program import SCHEMA


def market(seed, family='complementary', *, width=3, services=('kpi_variance','reconciliation')):
    if family not in ('complementary','substitute','competitive','additive'):
        raise ValueError('DECLARED_MARKET_FAMILY_REQUIRED')
    rng=random.Random(seed)
    levels=[400+600*i for i in range(width)]
    outcomes=[{'id':'outside','services':[],'cost_cents':0}]
    outcomes += [{'id':'first','services':[services[0]],'cost_cents':120},
                 {'id':'second','services':[services[1]],'cost_cents':170},
                 {'id':'joint','services':sorted(services),'cost_cents':290}]
    types=[]
    for j,(a,b) in enumerate(product(levels,levels)):
        # Stable role IDs permit hypothesis transfer; actual values and weights vary.
        a+=rng.randrange(0,60);b+=rng.randrange(0,60)
        if family=='complementary':joint=a+b+rng.choice((0,200,500,800))
        elif family=='substitute':joint=max(a,b)+rng.choice((0,100,200))
        else:joint=a+b
        outside=0 if family!='competitive' else max(a,b)//2
        types.append({'id':f'type-{j:03d}','values':[0,a,b,joint],
                      'budget_cents':max(a,b,joint)+100,
                      'outside_utility':outside,'weight':rng.randrange(1,10)})
    return {'schema':SCHEMA,'id':f'{family}-{seed}','basis':'PUBLIC_SYNTHETIC_TYPE_DISTRIBUTION',
            'outcomes':outcomes,'types':types,'payment_bps':300,'participation_margin':1,
            'cost_basis':'AUTHORED_CENTS_RESOURCE_ENVELOPES_NOT_MEASURED_BILL',
            'limits':{'max_variables':20000,'max_rows':1000000,'max_nodes':100000,'max_rounds':40}}
