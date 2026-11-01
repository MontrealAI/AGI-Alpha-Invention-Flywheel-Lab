"""Declared finite complete-outcome buyer model shared by forecast and execution.

Values/budgets are independent public hypotheses, never multiples of our quote
or human wage anchor. Neither a forecast nor an outside option moves native cash.
"""
import copy
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

SCHEMA='connected-complete-offer-market/v1'

def _int(x,minimum=0):
    if type(x) is not int or not minimum<=x<=10**15:raise ValueError('BOUNDED_INTEGER_REQUIRED')
    return x

def validate_policy(p):
    if not isinstance(p,dict) or set(p) not in ({'schema','profiles','selection'},{'schema','profiles','selection','requested_jobs'}) or p['schema']!=SCHEMA or p['selection'] not in {'restricted','menu'}:raise ValueError('EXPLICIT_COMPLETE_OFFER_POLICY_REQUIRED')
    if not isinstance(p['profiles'],list) or not 1<=len(p['profiles'])<=16:raise ValueError('BOUNDED_REQUEST_PROFILES_REQUIRED')
    if 'requested_jobs' in p:
        requests=p['requested_jobs']
        if not isinstance(requests,dict) or not requests:raise ValueError('BOUNDED_PUBLIC_JOB_REQUESTS_REQUIRED')
        for buyer,ids in requests.items():
            if not isinstance(buyer,str) or not buyer or not isinstance(ids,list) or len(ids)!=len(set(ids)) or any(not isinstance(i,str) or not i for i in ids):raise ValueError('UNIQUE_REQUESTED_ADMITTED_IDS_REQUIRED')
    ids=[]
    for r in p['profiles']:
        if set(r)!={'id','services','price_grids','atoms','outside_options'}:raise ValueError('EXACT_REQUEST_PROFILE_REQUIRED')
        ids.append(r['id'])
        if not isinstance(r['id'],str) or not r['id'] or not 1<=len(r['services'])<=4 or len(set(r['services']))!=len(r['services']):raise ValueError('UNIQUE_APPLICABLE_SERVICES_REQUIRED')
        if set(r['price_grids'])!=set(r['services']):raise ValueError('COMPLETE_PRICE_GRID_REQUIRED')
        for grid in r['price_grids'].values():
            if not isinstance(grid,list) or not 1<=len(grid)<=8 or grid!=sorted(set(grid)):raise ValueError('BOUNDED_UNIQUE_PRICE_GRID_REQUIRED')
            for price in grid:_int(price,1)
        if not isinstance(r['atoms'],list) or not 1<=len(r['atoms'])<=32:raise ValueError('FINITE_VALUE_BUDGET_PRIOR_REQUIRED')
        for a in r['atoms']:
            if set(a)!={'weight_bps','budget_microUSD','values'} or set(a['values'])!=set(r['services']):raise ValueError('INDEPENDENT_VALUE_BUDGET_ATOM_REQUIRED')
            _int(a['weight_bps'],1);_int(a['budget_microUSD'])
            for v in a['values'].values():_int(v)
        if sum(a['weight_bps'] for a in r['atoms'])!=10000:raise ValueError('ATOM_WEIGHTS_SUM_10000_REQUIRED')
        names=[]
        if not isinstance(r['outside_options'],list) or len(r['outside_options'])>12:raise ValueError('FINITE_OUTSIDE_MENU_REQUIRED')
        for o in r['outside_options']:
            if set(o)!={'name','provider','service_id','price','quality_bps','delay_cost'} or o['provider'] not in {'human','rival','self_service'} or o['service_id'] not in r['services']:raise ValueError('APPLICABLE_OUTSIDE_OUTCOME_REQUIRED')
            names.append(o['name']);_int(o['price']);_int(o['delay_cost']);_int(o['quality_bps'])
            if o['quality_bps']>10000 or not isinstance(o['name'],str) or o['name'] in {'us','decline'}:raise ValueError('VALID_OUTSIDE_NAME_QUALITY_REQUIRED')
        if len(set(names))!=len(names):raise ValueError('UNIQUE_OUTSIDE_NAMES_REQUIRED')
    if len(ids)!=len(set(ids)):raise ValueError('UNIQUE_REQUEST_PROFILES_REQUIRED')
    return p

@dataclass(frozen=True, slots=True)
class MarketProfiles:
    """Validated, immutable public-profile snapshot for ONE operation or audit.

    No process-wide cache, account authority, buyer private draw or live balance
    is retained. A new operation must compile its own current policy. Encoded
    profiles prevent returned dictionaries from changing later answers.
    """
    encoded_profiles: tuple[str, ...]
    policy_sha256: str

    def profile(self, buyer_id):
        index=int(hashlib.sha256(('public-request:'+buyer_id).encode()).hexdigest(),16)%len(self.encoded_profiles)
        return json.loads(self.encoded_profiles[index])

    def context(self, buyer_id, observed_spend, rival_available=True):
        _int(observed_spend)
        if type(rival_available) is not bool:raise ValueError('PUBLIC_RIVAL_ELIGIBILITY_REQUIRED')
        return {'profile':self.profile(buyer_id),'observed_spend':observed_spend,'rival_available':rival_available}

    def atom(self, buyer_id, seed):
        return _atom_from_profile(self.profile(buyer_id),buyer_id,seed)


def compile_market(policy):
    """Validate ALL request identities/profiles once, before creating a snapshot.

    Deep copying first makes the validation and compilation concern exactly the
    same bytes. This is query preparation, not permission to use a stale policy.
    """
    frozen=copy.deepcopy(policy)
    validate_policy(frozen)
    encoded=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    return MarketProfiles(tuple(encoded(p) for p in frozen['profiles']),
                          hashlib.sha256(encoded(frozen).encode()).hexdigest())


def request_profile(policy,buyer_id):
    validate_policy(policy)
    index=int(hashlib.sha256(('public-request:'+buyer_id).encode()).hexdigest(),16)%len(policy['profiles'])
    return copy.deepcopy(policy['profiles'][index])

def market_context(policy,buyer_id,observed_spend,rival_available=True):
    _int(observed_spend)
    if type(rival_available) is not bool:raise ValueError('PUBLIC_RIVAL_ELIGIBILITY_REQUIRED')
    return {'profile':request_profile(policy,buyer_id),'observed_spend':observed_spend,'rival_available':rival_available}

def validate_context(ctx):
    if set(ctx)!={'profile','observed_spend','rival_available'}:raise ValueError('PUBLIC_CONTEXT_ONLY')
    validate_policy({'schema':SCHEMA,'selection':'menu','profiles':[ctx['profile']]})
    _int(ctx['observed_spend'])
    if type(ctx['rival_available']) is not bool:raise ValueError('PUBLIC_RIVAL_ELIGIBILITY_REQUIRED')

def private_atom(policy,buyer_id,seed):
    """Environment-only draw. Must not be supplied to the selling policy."""
    return _atom_from_profile(request_profile(policy,buyer_id),buyer_id,seed)


def _atom_from_profile(r,buyer_id,seed):
    n=int(hashlib.sha256(f'private-complete-offer:{seed}:{buyer_id}'.encode()).hexdigest(),16)%10000
    for i,a in enumerate(r['atoms']):
        n-=a['weight_bps']
        if n<0:return i
    raise AssertionError('WEIGHTS')

def _choices(ctx,atom,remaining,service_id,price):
    choices=[{'name':'decline','provider':'decline','service_id':None,'spend':0,'utility':0}]
    for o in ctx['profile']['outside_options']:
        if o['provider']=='rival' and not ctx['rival_available']:continue
        if o['price']<=remaining:choices.append({'name':o['name'],'provider':o['provider'],'service_id':o['service_id'],'spend':o['price'],'utility':atom['values'][o['service_id']]*o['quality_bps']//10000-o['price']-o['delay_cost']})
    if price is not None and service_id in ctx['profile']['services'] and price<=remaining:
        choices.append({'name':'us','provider':'us','service_id':service_id,'spend':price,'utility':atom['values'][service_id]-price})
    best=max(c['utility'] for c in choices)
    return sorted((c for c in choices if c['utility']==best),key=lambda c:c['name'])

def actual_choice(ctx,atom_index,remaining_budget,service_id,price,tie_draw):
    validate_context(ctx);_int(remaining_budget)
    if type(atom_index) is not int or not 0<=atom_index<len(ctx['profile']['atoms']):raise ValueError('ENVIRONMENT_ATOM_REQUIRED')
    if price is not None:_int(price,1)
    if not 0<=tie_draw<1:raise ValueError('UNIT_TIE_DRAW_REQUIRED')
    atom=ctx['profile']['atoms'][atom_index]
    if remaining_budget>atom['budget_microUSD']:raise ValueError('BUYER_BUDGET_CANNOT_INCREASE')
    choices=_choices(ctx,atom,remaining_budget,service_id,price)
    return copy.deepcopy(choices[min(len(choices)-1,int(tie_draw*len(choices)))])

def win_probability(ctx,service_id,price):
    validate_context(ctx);_int(price,1)
    if service_id not in ctx['profile']['services']:return 0.0
    atoms=[a for a in ctx['profile']['atoms'] if a['budget_microUSD']>=ctx['observed_spend']]
    weight=sum(a['weight_bps'] for a in atoms)
    if not weight:return 0.0
    probability=Fraction(0)
    for a in atoms:
        choices=_choices(ctx,a,a['budget_microUSD']-ctx['observed_spend'],service_id,price)
        if any(c['name']=='us' for c in choices):probability+=Fraction(a['weight_bps'],weight*len(choices))
    return float(probability)
