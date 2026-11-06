"""Exact authored continuity-construction model; no commerce or LLM calls.

A strategy reserves whole four-unit blocks before the activation scenario is
observed. Recourse then allocates divisible integer units. Sources, capacities,
prices, permission and supplier menus are stipulated, not measured facts.
"""
from dataclasses import dataclass, asdict
from itertools import product
from collections import deque

SCENARIOS = ((), ('A',), ('B',), ('A', 'B'))

@dataclass(frozen=True)
class Case:
    adapter_cost: int = 2
    pooled_q_cost: int = 2
    cash: int = 13
    price_per_buyer: int = 8
    adapter_available: bool = True
    pooling_available: bool = True
    supplier_q_accepted: bool = True
    include_q_failure: bool = False

    def validate(self):
        for name in ('adapter_cost','pooled_q_cost','cash','price_per_buyer'):
            v=getattr(self,name)
            if type(v) is not int or v<0:
                raise ValueError('NONNEGATIVE_EXACT_INPUT_REQUIRED:'+name)
        for name in ('adapter_available','pooling_available','supplier_q_accepted','include_q_failure'):
            if type(getattr(self,name)) is not bool:
                raise ValueError('BOOLEAN_INPUT_REQUIRED:'+name)

@dataclass(frozen=True)
class Strategy:
    adapter: bool
    pooling: bool
    reserved: tuple

    def key(self):
        return (int(self.adapter), int(self.pooling), self.reserved)


def strategies(case):
    case.validate()
    for t, a, p, q, r in product((False,True),repeat=5):
        if t and not case.adapter_available: continue
        if a and not case.pooling_available: continue
        if q and not case.supplier_q_accepted: continue
        # An unqualified reserve is not an admitted technical operation.
        if q and not t: continue
        yield Strategy(t,a,tuple(k for k,on in zip(('P','Q','R'),(p,q,r)) if on))


def cost(case, strategy):
    # 2 fixed + 1 execution/verification allowance per covered buyer;
    # worst-case costs are charged whether a particular scenario activates or not.
    reservations=sum(4 if s=='P' else 9 if s=='R' else
                     (case.pooled_q_cost if strategy.pooling else 8)
                     for s in strategy.reserved)
    return 4 + case.adapter_cost*strategy.adapter + int(strategy.pooling) + reservations


def worlds(case):
    result=[{'active':s, 'failed':()} for s in SCENARIOS]
    if case.include_q_failure:
        result.append({'active':('A','B'),'failed':('Q',)})
    return result


def recourse(strategy, world):
    """Edmonds--Karp integer flow, including an explicit allocation witness."""
    active=tuple(world['active'])
    suppliers=[s for s in strategy.reserved if s not in world['failed']]
    cap={}
    def edge(u,v,c):
        cap[u,v]=c; cap.setdefault((v,u),0)
    for c in active: edge('S','client:'+c,4)
    for c in active:
        for s in suppliers:
            if s!='Q' or (strategy.adapter and c=='B'):
                edge('client:'+c,'supplier:'+s,4)
    for s in suppliers: edge('supplier:'+s,'T',4)
    residual=dict(cap); value=0
    while True:
        parent={'S':None}; todo=deque(['S'])
        while todo and 'T' not in parent:
            u=todo.popleft()
            for (a,b),v in sorted(residual.items()):
                if a==u and v>0 and b not in parent:
                    parent[b]=u;todo.append(b)
        if 'T' not in parent:break
        path=[];v='T'
        while parent[v] is not None:
            path.append((parent[v],v));v=parent[v]
        amount=min(residual[e] for e in path)
        for u,v in path:residual[u,v]-=amount;residual[v,u]+=amount
        value+=amount
    allocation=[]
    for (u,v),original in cap.items():
        if u.startswith('client:') and v.startswith('supplier:'):
            used=original-residual[u,v]
            if used: allocation.append({'client':u[7:],'supplier':v[9:],'units':used})
    return {'feasible':value==4*len(active),'delivered_units':value,
            'required_units':4*len(active),'allocation':allocation}


def _select(case, constraints):
    possible=[]
    for s in strategies(case):
        total=cost(case,s)
        if total>case.cash or total>=2*case.price_per_buyer:continue
        if all(recourse(s,w)['feasible'] for w in constraints):
            possible.append((total,s.key(),s))
    return min(possible,key=lambda x:x[:2])[2] if possible else None


def construct(case):
    """Finite counterexample-guided constraint generation, not open-world invention."""
    ws=worlds(case)
    constraints=[w for w in ws if len(w['active'])==1 and not w['failed']]
    history=[]
    while True:
        s=_select(case,constraints)
        if s is None:
            return {'decision':'DECLINE','strategy':None,'cost':None,'surplus':None,
                    'history':history,'witnesses':[]}
        failures=[w for w in ws if not recourse(s,w)['feasible']]
        history.append({'candidate':asdict(s),'cost':cost(case,s),
                        'counterexample':failures[0] if failures else None})
        if not failures:
            return {'decision':'ADMIT_MODEL','strategy':asdict(s),'cost':cost(case,s),
                    'surplus':2*case.price_per_buyer-cost(case,s),'history':history,
                    'witnesses':[{'world':w,**recourse(s,w)} for w in ws]}
        if failures[0] in constraints:raise RuntimeError('NONPROGRESSING_REFINEMENT')
        constraints.append(failures[0])


def financial_path(case, result):
    """Analytical cash path, NOT the repository's authoritative native account."""
    if result['decision']!='ADMIT_MODEL':return None
    c=result['cost']; receipts=2*case.price_per_buyer
    return {'opening':case.cash,'before_receipts':case.cash-c,
            'terminal':case.cash-c+receipts,'receipts_if_all_accepted':receipts,
            'complete_modeled_cost':c,'modeled_surplus':receipts-c,
            'actual_receipts':0, 'kind':'ANALYTICAL_CONDITIONAL_PATH'}
