#!/usr/bin/env python3
"""Separate exact arithmetic checker for the browser's two new constructions.
It solves measurement weights by Gaussian elimination, not the JS barycentric rule.
Source semantics: Surf the Exponential §6; Out-Learn §§2–8. No network/model calls.
"""
from __future__ import annotations
from fractions import Fraction as F
from itertools import combinations, product
from pathlib import Path
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parent

def linear_solve(matrix: list[list[F]], rhs: list[F]) -> list[F] | None:
    a=[list(row)+[v] for row,v in zip(matrix,rhs)]
    n=len(rhs)
    for col in range(n):
        pivot=next((r for r in range(col,n) if a[r][col]),None)
        if pivot is None: return None
        a[col],a[pivot]=a[pivot],a[col]
        divisor=a[col][col];a[col]=[v/divisor for v in a[col]]
        for r in range(n):
            if r!=col:
                v=a[r][col];a[r]=[x-v*y for x,y in zip(a[r],a[col])]
    return [a[i][-1] for i in range(n)]

def bank() -> list[dict]:
    out=[]
    for tail in combinations(range(1,9),3):
        times=(0,)+tail
        for suffix in product((1,-1),repeat=3):
            signs=(1,)+suffix
            a=[[F(t)**k for t in times] for k in range(3)]+[[F(s) for s in signs]]
            weights=linear_solve(a,[F(0),F(0),F(0),F(1)])
            if weights is None: continue
            amp=sum(map(abs,weights),F(0))
            cost10=40+20*sum(x!=y for x,y in zip(signs,signs[1:]))+times[-1]
            out.append(dict(times=times,signs=signs,weights=weights,A=amp,cost10=cost10))
    return out

def primary_check() -> dict:
    plans=bank(); assert len(plans)==380
    feasible=[]; compared=0
    for c in plans:
        for o in plans:
            compared+=1
            ec=c['A']/1000;eo=o['A']/1000
            radius=max((ec+eo)/(1+2*ec),eo)
            if radius<=F(3,1000):feasible.append((c['cost10'],o['cost10'],radius))
    assert compared==144400 and len(feasible)==31590
    observed={}
    for n in range(1,101):
        total,error=min((c+n*o,r) for c,o,r in feasible)
        observed[str(n)]={'total_cost':str(F(total,10)),'worst_error':str(error)}
    assert observed['1']=={'total_cost':'13','worst_error':'3/1003'}
    assert observed['19']=={'total_cost':'130','worst_error':'117/40090'}
    assert observed['20']=={'total_cost':'1363/10','worst_error':'1/334'}
    script="const C=require('./construction-core.js');let o={};for(let n=1;n<=100;n++){let r=C.selectPair(n).best;o[n]={total_cost:new C.Q(r.total10,10).toString(),worst_error:r.radius.toString()}}console.log(JSON.stringify(o));"
    js=json.loads(subprocess.check_output(['node','-e',script],cwd=ROOT,text=True))
    assert js==observed, 'Cross-language comparison failed'
    js_plans=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./construction-core.js').plans().valid));"],cwd=ROOT,text=True))
    lookup={(p['times'],p['signs']):p for p in plans}
    for p in js_plans:
        own=lookup[tuple(p['times']),tuple(p['signs'])]
        assert list(map(F,p['weights']))==own['weights']
        assert F(p['A'])==own['A'] and p['cost10']==own['cost10']
    t=(0,2,3,5);s=(1,1,-1,-1);w=[F(-1,8),F(5,8),F(-5,8),F(1,8)]
    cal=[F(7,5)*si+11+ti+2*ti*ti for ti,si in zip(t,s)]
    raw=[F(7,5)*si*F(2,7)+3-2*ti+ti*ti for ti,si in zip(t,s)]
    assert sum(a*b for a,b in zip(w,cal))==F(7,5)
    assert sum(a*b for a,b in zip(w,raw))==F(2,5)
    cubic_shift=sum(wi*F(1,100)*ti**3 for wi,ti in zip(w,t));assert cubic_shift==F(3,80)
    return {'candidate_schedules':448,'informative_schedules':380,'rejected_aliases':68,'full_pairs':compared,'qualifying_pairs':len(feasible),'cross_language_horizons':100,'exact_weight_matches':len(js_plans),'selected_horizons':{k:observed[k] for k in ['1','18','19','20','100']},'cubic_product_shift':str(cubic_shift),'scope':'Supplied quadratic-drift catalogue; abstract acquisition costs only.'}

def missing_check() -> dict:
    exported=json.loads(subprocess.check_output(['node','-e',"console.log(JSON.stringify(require('./construction-core.js').missingRun()));"],cwd=ROOT,text=True))
    counts={}
    for key in ('parent','child'):
        a=exported[key];outcomes={}
        n=0
        for entry in a['encoder']:
            x,y=entry['input'];label=entry['label'];answers=[]
            for i,query in enumerate(a['queries']):
                expected=max(x,y)<=query['hi']
                if query['kind']=='interval':expected=expected and min(x,y)>=query['lo']
                assert a['decoders'][label][i]==int(expected)
                answers.append(expected);n+=1
            outcomes.setdefault(tuple(answers),set()).add(label)
        assert all(len(v)==1 for v in outcomes.values())
        assert len(outcomes)==len(a['decoders'])
        counts[key]={'labels':len(outcomes),'checks':n}
    assert counts=={'parent':{'labels':3,'checks':36},'child':{'labels':6,'checks':54}}
    return {**counts,'strong_conventional_control':'Maximum and minimum/maximum tie the same finite outputs and label counts.','source_migration':'Fresh source values are required; old maximum labels cannot recover discarded minima.'}

if __name__=='__main__':
    record={'schema':'frontier/research-edition-evidence-v1','date':'2026-11-17','missing_move':missing_check(),'out_learn':primary_check(),'model_calls':0,'physical_deployment':False,'commercial_results':False,'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['index.html','construction-core.js','studio-ui.js']},'independence':'Separate Python algorithms under the same authoring process; not independent institutional review.'}
    (ROOT/'evidence').mkdir(exist_ok=True)
    (ROOT/'evidence'/'independent-replay.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))
