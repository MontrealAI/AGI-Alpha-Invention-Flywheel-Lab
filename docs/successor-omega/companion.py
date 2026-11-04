"""Exact authored renewal model. Python standard library; no external effects."""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import NamedTuple
import argparse, hashlib, json

@dataclass(frozen=True)
class Spec:
    horizon: int = 16
    epoch_length: int = 4
    initial_cash: int = 100
    reserve: int = 20
    build_f: int = 40
    build_p: int = 60
    renew: int = 10
    maintenance: int = 1
    demand: bool = True
    def validate(self):
        ints = {k:v for k,v in asdict(self).items() if k != 'demand'}
        if any(type(v) is not int or v < 0 for v in ints.values()):
            raise ValueError('Nonnegative integer parameters required')
        if not 1 <= self.horizon <= 32 or self.epoch_length < 1:
            raise ValueError('Finite horizon 1..32 and positive epoch length required')
        if self.initial_cash < self.reserve or type(self.demand) is not bool:
            raise ValueError('Opening reserve or demand invalid')

class State(NamedTuple):
    t: int
    cash: int
    portable: bool
    p_epoch: int
    f_epoch: int

class Step(NamedTuple):
    action: str
    upfront: int
    collection: int
    after: State

SERVICES = {'legacy': (10,22), 'run_f': (12,42), 'run_p': (10,38)}

def transitions(s: State, p: Spec, portable_allowed=True, legacy_only=False):
    if s.t >= p.horizon: return ()
    epoch = s.t // p.epoch_length
    fee = p.maintenance if s.portable else 0
    actions = [('idle', fee, 0, s.portable, s.p_epoch, s.f_epoch)]
    if p.demand:
        actions.append(('legacy',fee+10,22,s.portable,s.p_epoch,s.f_epoch))
        if not legacy_only and s.f_epoch == epoch:
            actions.append(('run_f',fee+12,42,s.portable,s.p_epoch,s.f_epoch))
        if not legacy_only and s.portable and s.p_epoch == epoch:
            actions.append(('run_p',fee+10,38,True,s.p_epoch,s.f_epoch))
    if not legacy_only:
        if s.f_epoch != epoch:
            actions.append(('build_f',fee+p.build_f,0,s.portable,s.p_epoch,epoch))
        if portable_allowed and not s.portable:
            actions.append(('build_p',p.build_p+p.maintenance,0,True,epoch,s.f_epoch))
        if portable_allowed and s.portable and s.p_epoch != epoch:
            actions.append(('renew_p',fee+p.renew,0,True,epoch,s.f_epoch))
        if s.portable:
            actions.append(('retire',0,0,False,-1,s.f_epoch))
    return tuple(Step(a,u,r,State(s.t+1,s.cash-u+r,o,pe,fe))
                 for a,u,r,o,pe,fe in actions if s.cash-u >= p.reserve)

def solve(p: Spec, portable_allowed=True, legacy_only=False):
    p.validate()
    @lru_cache(None)
    def value(s):
        if s.t == p.horizon: return (s.cash,())
        candidates = [(value(x.after)[0], (x.action,)+value(x.after)[1])
                      for x in transitions(s,p,portable_allowed,legacy_only)]
        return min(candidates, key=lambda v:(-v[0],v[1]))
    start=State(0,p.initial_cash,False,-1,-1)
    terminal, policy = value(start)
    trace=[]; s=start
    for action in policy:
        step=next(x for x in transitions(s,p,portable_allowed,legacy_only) if x.action==action)
        trace.append({'t':s.t,'epoch':s.t//p.epoch_length,'action':action,
                      'opening':s.cash,'paid':step.upfront,'collected':step.collection,
                      'pre_collection':s.cash-step.upfront,'closing':step.after.cash})
        s=step.after
    return {'terminal_cash':terminal,'net_cash_surplus':terminal-p.initial_cash,
            'outflows':sum(x['paid'] for x in trace),
            'collections':sum(x['collected'] for x in trace),'trace':trace,
            'solver_states':value.cache_info().currsize}

def forward_oracle(p: Spec, portable_allowed=True, legacy_only=False):
    """Independent full reachability; does not reuse transitions()."""
    p.validate()
    layer={(p.initial_cash,False,-1,-1)}
    for t in range(p.horizon):
        nxt=set(); e=t//p.epoch_length
        for cash,owned,pe,fe in layer:
            fee=p.maintenance*owned
            options=[(fee,0,owned,pe,fe)]
            if p.demand:
                options.append((fee+10,22,owned,pe,fe))
                if not legacy_only:
                    if fe==e: options.append((fee+12,42,owned,pe,fe))
                    if owned and pe==e: options.append((fee+10,38,True,pe,fe))
            if not legacy_only:
                if fe!=e: options.append((fee+p.build_f,0,owned,pe,e))
                if portable_allowed:
                    if not owned: options.append((p.build_p+p.maintenance,0,True,e,fe))
                    elif pe!=e: options.append((fee+p.renew,0,True,e,fe))
                if owned: options.append((0,0,False,-1,fe))
            for cost,receipt,o,a,b in options:
                if cash-cost>=p.reserve:
                    nxt.add((cash-cost+receipt,o,a,b))
        layer=nxt
    return max(c for c,*_ in layer)

@dataclass(frozen=True)
class Context:
    mission: str
    source: str
    supplier: str
    environment: str
    evaluator: str
    policy: str
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

class Institution:
    """Local state-machine witness, not a hardened authorization service."""
    def __init__(self, identity, knowledge=()):
        self.identity=identity; self.knowledge=tuple(knowledge)
        self.proof=None; self.authority=None; self.history=[]
    def qualify(self,ctx,passed,producer,verifier,expires,supported_actions=('deliver',)):
        if producer==verifier or passed is not True or expires<=0 or not supported_actions:
            raise ValueError('Distinct role identifiers, passing evidence and positive expiry required')
        self.proof=(ctx.digest(),expires,frozenset(supported_actions)); self.authority=None
        self.history.append(('qualified',ctx.digest()))
    def authorize(self,ctx,actions,owner_approval,now,expires):
        if owner_approval is not True or not actions or self.proof is None:
            raise ValueError('Explicit approval, action scope and proof required')
        digest,proof_end,supported=self.proof
        if digest!=ctx.digest() or not 0 <= now < expires <= proof_end or not set(actions)<=supported:
            raise ValueError('Context or validity mismatch')
        self.authority=(digest,frozenset(actions),expires)
        self.history.append(('authorized',digest))
    def permits(self,ctx,action,now):
        return bool(now>=0 and self.proof and self.authority and self.proof[0]==ctx.digest()
                    and self.authority[0]==ctx.digest() and now<self.proof[1]
                    and now<self.authority[2] and action in self.authority[1])
    def revoke(self):
        self.authority=None; self.history.append(('revoked',self.identity))
    def export(self):
        return {'schema':1,'identity':self.identity,'knowledge':list(self.knowledge),
                'history':[list(x) for x in self.history]}
    @classmethod
    def restore(cls,bundle):
        if bundle.get('schema')!=1 or 'proof' in bundle or 'authority' in bundle:
            raise ValueError('Invalid or privilege-bearing portable bundle')
        out=cls(bundle['identity'],bundle['knowledge'])
        out.history=[tuple(x) for x in bundle['history']]
        return out

def fixed_portable(p: Spec):
    """Supplied always-retain policy; None if it cannot be prefunded."""
    p.validate(); s=State(0,p.initial_cash,False,-1,-1)
    while s.t<p.horizon:
        epoch=s.t//p.epoch_length
        action=('build_p' if not s.portable else 'renew_p' if s.p_epoch!=epoch
                else 'run_p' if p.demand else 'idle')
        match=[x for x in transitions(s,p) if x.action==action]
        if not match:return None
        s=match[0].after
    return s.cash

def evaluate():
    base=Spec()
    main={name:solve(base,**kw) for name,kw in [
        ('portable',{}),('ordinary_equal_content',{}),
        ('no_portable',{'portable_allowed':False}),('legacy',{'legacy_only':True})]}
    if forward_oracle(base)!=main['ordinary_equal_content']['terminal_cash']:
        raise AssertionError('Equal-content conventional reachability disagrees')
    rows=[]
    for H,L,C,R,M in product((8,12,16),(4,8),(40,70,100),(5,10,25),(0,1,3)):
        p=Spec(H,L,C,20,40,60,R,M)
        full=solve(p); control=solve(p,False)
        for allow,r in [(True,full),(False,control)]:
            if r['terminal_cash']!=forward_oracle(p,allow):
                raise AssertionError('Independent enumeration disagrees')
        rows.append({'horizon':H,'epoch_length':L,'opening_cash':C,'renewal':R,
                     'maintenance':M,'portable':full['terminal_cash'],
                     'no_portable':control['terminal_cash'],
                     'gain':full['terminal_cash']-control['terminal_cash'],
                     'fixed_portable':fixed_portable(p)})
    diagnostic={}
    for name,p in [('no_turnover',replace(base,epoch_length=16)),
                   ('no_demand',replace(base,demand=False)),
                   ('high_maintenance',replace(base,maintenance=5)),
                   ('expensive_renewal',replace(base,renew=40)),
                   ('reserve_only',replace(base,initial_cash=20)),
                   ('low_opening_cash',replace(base,initial_cash=40)),
                   ('one_epoch',replace(base,horizon=4))]:
        diagnostic[name]={'spec':asdict(p),'full':solve(p),'no_portable':solve(p,False)}
    return {'schema':1,'interpretation':'Authored exact finite model; not market or ASI evidence',
            'spec':asdict(base),'main':main,'grid':rows,
            'grid_summary':{'cases':len(rows),'positive':sum(r['gain']>0 for r in rows),
                            'ties':sum(r['gain']==0 for r in rows),
                            'negative':sum(r['gain']<0 for r in rows),
                            'max_gain':max(r['gain'] for r in rows),
                            'fixed_infeasible':sum(r['fixed_portable'] is None for r in rows),
                            'fixed_loses':sum(r['fixed_portable'] is not None and r['fixed_portable']<r['no_portable'] for r in rows),
                            'fixed_wins':sum(r['fixed_portable'] is not None and r['fixed_portable']>r['no_portable'] for r in rows),
                            'fixed_ties':sum(r['fixed_portable']==r['no_portable'] for r in rows)},
            'diagnostics':diagnostic}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('results.json'))
    args=parser.parse_args()
    args.output.write_text(json.dumps(evaluate(),indent=2,sort_keys=True)+'\n')
