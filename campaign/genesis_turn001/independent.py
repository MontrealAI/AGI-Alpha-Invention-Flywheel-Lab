"""Separately implemented exhaustive acceptance oracle; never calls power.solve.

Recomputes all assignments and financial arithmetic from registered input values.
The native financial authority is audited separately using JournalAccount.audit().
"""
from __future__ import annotations
from itertools import product
from .power import digest


def accept_power(data, claim):
    assert claim['kind']=='energy-plan/v1' and claim['source_sha256']==digest(data)
    assert claim['physical_status']=='UNVALIDATED'
    parts={p['id']:p for p in data['modules']}
    loads={l['id']:l['required_wh'] for l in data['loads']}
    eligible=sorted((p for p in data['modules'] if p['research_only_qualified']),key=lambda p:p['id'])
    optimum=None
    for assignment in product([None,*sorted(loads)],repeat=len(eligible)):
        delivered={k:0 for k in loads}; fee=0; used=[]
        for part,dest in zip(eligible,assignment):
            if dest is None:continue
            delivered[dest]+=part['usable_wh']; fee+=part['cost_cents']; used.append((part['id'],dest))
        if all(delivered[k]>=loads[k] for k in loads):
            candidate=(fee,len(used),tuple(used))
            if optimum is None or candidate<optimum:optimum=candidate
    if optimum is None:
        assert claim['status']=='NOT_FEASIBLE_IN_MODEL' and claim['assignments']==[]
        assert claim['totals_wh']=={} and claim['cost_cents']==0
        return True
    assert claim['status']=='FEASIBLE_IN_MODEL'
    assert set(claim['totals_wh'])==set(loads)
    seen=set(); measured={k:0 for k in loads}; total=0; pairs=[]
    for a in claim['assignments']:
        p=a['module']; k=a['load']
        assert p in parts and parts[p]['research_only_qualified'] and k in loads and p not in seen
        seen.add(p);measured[k]+=parts[p]['usable_wh']; total+=parts[p]['cost_cents'];pairs.append((p,k))
    assert all(measured[k]>=loads[k] for k in loads)
    assert measured==claim['totals_wh'] and total==claim['cost_cents']
    assert (total,len(pairs),tuple(pairs))==optimum
    return True


def accept_cents(registered):
    """All fee and tax figures are authored simulator tariffs, not observed costs."""
    x=registered
    pre=x['price_cents']-sum(x['pre_successor_costs_cents'])
    assert pre>=0
    expected_tax=pre*x['tax_rate_basis_points']//10000
    assert x['tax_cents']==expected_tax
    assert x['earned_before_successor_cents']==pre-expected_tax
    assert x['successor_cost_cents']<=x['earned_before_successor_cents']
    assert x['net_after_successor_cents']==x['earned_before_successor_cents']-x['successor_cost_cents']
    assert x['actual_customer_receipts_cents']==0
    return True
