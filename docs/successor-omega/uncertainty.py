"""Exact no-foresight renewal study. Authored probabilities, not market data."""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache
from itertools import product
from pathlib import Path
import argparse,json

@dataclass(frozen=True)
class Risk:
    horizon:int=8
    initial_cash:int=100
    reserve:int=20
    change:F=F(1,4)
    failure:F=F(0)
    def validate(self):
        if any(type(x) is not int for x in (self.horizon,self.initial_cash,self.reserve)):
            raise ValueError('Integer horizon and cash required')
        if self.horizon<1 or not 0<=self.reserve<=self.initial_cash:
            raise ValueError('Invalid horizon or cash')
        if any(type(x) is not F or not 0<=x<=1 for x in (self.change,self.failure)):
            raise ValueError('Probabilities must be exact Fractions in [0,1]')

# State: cash, retained portable source, currently-qualified portable, qualified F.
def actions(s,r,allow=True):
    c,o,p,f=s; fee=int(o)
    raw=[('idle',fee,0,o,p,f),('legacy',fee+10,22,o,p,f)]
    if not f:raw.append(('build_f',fee+40,0,o,p,True))
    if f:raw.append(('run_f',fee+12,42,o,p,f))
    if allow and not o:raw.append(('build_p',61,0,True,True,f))
    if allow and o and not p:raw.append(('renew_p',11,0,True,True,f))
    if allow and o and p:raw.append(('run_p',11,38,True,True,f))
    if o:raw.append(('retire',0,0,False,False,f))
    return [(a,cost,(c-cost+receipt,owned,pq,fq))
            for a,cost,receipt,owned,pq,fq in raw if c-cost>=r.reserve]

def branches(action,after,r,terminal=False):
    c,o,p,f=after
    renew=[(F(1),after)]
    if action=='renew_p':renew=[(1-r.failure,after),(r.failure,(c,o,False,f))]
    result={}
    for w,s in renew:
        events=[(F(1),s)] if terminal else [(1-r.change,s),(r.change,(s[0],s[1],False,False))]
        for v,end in events:
            if w*v:result[end]=result.get(end,F(0))+w*v
    return tuple((v,s) for s,v in sorted(result.items()))

def optimize(r:Risk,allow=True):
    r.validate(); policy={}
    @lru_cache(None)
    def value(t,s):
        if t==r.horizon:return F(s[0])
        choices=[]
        for a,cost,end in actions(s,r,allow):
            score=sum((w*value(t+1,n) for w,n in branches(a,end,r,t+1==r.horizon)),F(0))
            choices.append((score,a))
        best=min(choices,key=lambda z:(-z[0],z[1]));policy[(t,s)]=best[1]
        return best[0]
    start=(r.initial_cash,False,False,False);answer=value(0,start)
    # Forward policy execution: independently inspect branchwise liquidity.
    law={start:F(1)};min_prefund=r.initial_cash
    for t in range(r.horizon):
        nxt={}
        for s,mass in law.items():
            a=policy[t,s]
            _,cost,end=next(x for x in actions(s,r,allow) if x[0]==a)
            min_prefund=min(min_prefund,s[0]-cost)
            for weight,n in branches(a,end,r,t+1==r.horizon):
                nxt[n]=nxt.get(n,F(0))+mass*weight
        law=nxt
    assert sum(law.values())==1 and min_prefund>=r.reserve
    expected=sum((mass*s[0] for s,mass in law.items()),F(0))
    assert expected==answer
    return {'expected':answer,'first_action':policy[0,start],
            'min_terminal':min(s[0] for s in law),'min_prefund':min_prefund,
            'states':value.cache_info().currsize}

def oracle_edges(s,r,allow,terminal):
    """Separate transition implementation; no calls to actions or branches."""
    cash,owned,pvalid,fvalid=s;upkeep=1 if owned else 0
    options={'idle':(upkeep,0,owned,pvalid,fvalid),
             'legacy':(10+upkeep,22,owned,pvalid,fvalid)}
    if fvalid:options['run_f']=(12+upkeep,42,owned,pvalid,True)
    else:options['build_f']=(40+upkeep,0,owned,pvalid,True)
    if owned:
        options['retire']=(0,0,False,False,fvalid)
        if allow:options['run_p' if pvalid else 'renew_p']=(11,38 if pvalid else 0,True,True,fvalid)
    elif allow:options['build_p']=(61,0,True,True,fvalid)
    out={}
    for action,(paid,received,o,p,f) in options.items():
        if cash-paid<r.reserve:continue
        endcash=cash-paid+received;dist={}
        for failed in (False,True):
            prob_fail=(r.failure if failed else 1-r.failure) if action=='renew_p' else F(not failed)
            for changed in (False,True):
                prob_change=F(not changed) if terminal else r.change if changed else 1-r.change
                w=prob_fail*prob_change
                if not w:continue
                end=(endcash,o,p and not failed and not changed,f and not changed)
                dist[end]=dist.get(end,F(0))+w
        assert sum(dist.values())==1
        out[action]=dist
    return out

def oracle(r:Risk,allow=True):
    r.validate();start=(r.initial_cash,False,False,False);layers=[{start}];graph=[]
    for t in range(r.horizon):
        layer={s:oracle_edges(s,r,allow,t+1==r.horizon) for s in layers[-1]};graph.append(layer)
        layers.append({end for options in layer.values() for dist in options.values() for end in dist})
    values={s:F(s[0]) for s in layers[-1]}
    for layer in reversed(graph):
        values={s:max(sum((w*values[n] for n,w in dist.items()),F(0)) for dist in opts.values())
                for s,opts in layer.items()}
    return values[start]

def history_tree(r:Risk,allow=True):
    """Unmemoized decision-history expansion, for small independent checks."""
    r.validate()
    def visit(t,s):
        if t==r.horizon:return F(s[0])
        return max(sum((prob*visit(t+1,n) for n,prob in dist.items()),F(0))
                   for dist in oracle_edges(s,r,allow,t+1==r.horizon).values())
    return visit(0,(r.initial_cash,False,False,False))

def serial(result):
    return {k:(str(v) if isinstance(v,F) else v) for k,v in result.items()}

def evaluate(horizon=8):
    rows=[]
    for q,f,c in product((F(0),F(1,8),F(1,4),F(1,2),F(3,4),F(1)),
                         (F(0),F(1,4),F(1,2),F(1)),(40,100)):
        r=Risk(horizon=horizon,initial_cash=c,change=q,failure=f)
        full=optimize(r);control=optimize(r,False)
        assert full['expected']==oracle(r) and control['expected']==oracle(r,False)
        gain=full['expected']-control['expected'];assert gain>=0
        rows.append({'q':str(q),'failure':str(f),'opening_cash':c,
                     'full':serial(full),'without_portable':serial(control),'gain':str(gain)})
    gains=[F(x['gain']) for x in rows]
    return {'schema':1,'scope':'Authored exact no-foresight model, not market or autonomous invention evidence',
            'horizon':horizon,'rows':rows,'summary':{'cases':len(rows),'oracle_comparisons':len(rows)*2,
            'positive':sum(x>0 for x in gains),'ties':sum(x==0 for x in gains),'max_gain':str(max(gains))}}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('uncertainty.json'))
    p.add_argument('--horizon',type=int,default=8)
    args=p.parse_args();result=evaluate(args.horizon);args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result['summary'],indent=2))
