"""A second, different productive task: synthetic shared-storage feasibility.

This is a decision-support computation, NOT a safety certification, electrical
installation plan, physical measurement, or demonstrated buyer market.
"""
from __future__ import annotations
from hashlib import sha256
from itertools import product
import json


def digest(data):
    return sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def scenario():
    return {
        'scope': 'synthetic-bench-tested-illustration-not-real-EV-batteries',
        'modules': [
            {'id':'SPARKY-A','usable_wh':4100,'cost_cents':1400,'research_only_qualified':True},
            {'id':'SPARKY-B','usable_wh':3300,'cost_cents':1200,'research_only_qualified':True},
            {'id':'SPARKY-C','usable_wh':3200,'cost_cents':1100,'research_only_qualified':True},
            {'id':'SPARKY-D','usable_wh':5100,'cost_cents':2000,'research_only_qualified':True},
            {'id':'SPARKY-UNVERIFIED','usable_wh':10000,'cost_cents':1,'research_only_qualified':False},
        ],
        'loads': [{'id':'CLINIC','required_wh':7000}, {'id':'LIBRARY','required_wh':3000}],
        'common_window':'illustrative-concurrent-4-hour-window',
    }


def solve(data):
    """Enumerate each eligible pack's unique assignment: idle / load0 / load1.

    Ordinary exhaustive discrete optimization, NOT a novel algorithm.
    """
    modules=data['modules']; loads=data['loads']
    if not (1<=len(loads)<=5 and 1<=len(modules)<=12):
        raise ValueError('BOUNDED_STUDY_REQUIRED')
    ids=[p['id'] for p in modules]; lid=[l['id'] for l in loads]
    if len(ids)!=len(set(ids)) or len(lid)!=len(set(lid)):
        raise ValueError('DISTINCT_IDENTITIES_REQUIRED')
    if any(type(p['usable_wh']) is not int or p['usable_wh']<=0 or type(p['cost_cents']) is not int or p['cost_cents']<0 or type(p['research_only_qualified']) is not bool for p in modules):
        raise ValueError('MODULE_INTEGRITY_REQUIRED')
    if any(type(l['required_wh']) is not int or l['required_wh']<=0 for l in loads):
        raise ValueError('LOAD_INTEGRITY_REQUIRED')
    eligible=sorted((p for p in modules if p['research_only_qualified']),key=lambda p:p['id'])
    best=None
    for choices in product(range(len(loads)+1),repeat=len(eligible)):
        totals={l['id']:0 for l in loads}; assignments=[]; cost=0
        for pack,assigned in zip(eligible,choices):
            if assigned:
                name=loads[assigned-1]['id']
                totals[name]+=pack['usable_wh']; cost+=pack['cost_cents']
                assignments.append({'module':pack['id'],'load':name})
        if any(totals[l['id']]<l['required_wh'] for l in loads):continue
        tie_key=(cost,len(assignments),tuple((x['module'],x['load']) for x in assignments))
        if best is None or tie_key<best[0]:best=tie_key,assignments,totals
    if best is None:
        return {'kind':'energy-plan/v1','source_sha256':digest(data),'status':'NOT_FEASIBLE_IN_MODEL',
                'assignments':[],'totals_wh':{},'cost_cents':0,'physical_status':'UNVALIDATED'}
    key,assignments,totals=best
    return {'kind':'energy-plan/v1','source_sha256':digest(data),'status':'FEASIBLE_IN_MODEL',
            'assignments':assignments,'totals_wh':totals,'cost_cents':key[0],
            'physical_status':'UNVALIDATED'}
