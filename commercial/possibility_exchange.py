"""Finite search over conditional multi-buyer *business arrangements*.

The executor creates real public-synthetic service/checker artifacts. Every
quoted value, cost and budget is an authored hypothesis. No actual buyer agrees
or pays; this is not a second enterprise ledger or a live contract engine.
"""
from __future__ import annotations

from itertools import combinations
import hashlib
import json
from pathlib import Path

from commercial import service, service_verifier

SCHEMA = 'agi-alpha/possibility-exchange/v1'
LIMIT = 10**14
MAX_BUYERS = 8
MAX_METHODS = 8
FIELDS = ('setup_cents','unit_cents','verification_cents','qualification_cents',
          'partner_setup_cents','partner_cost_cents','partner_gain_cents')


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hashes():
    sources = (('producer', service), ('checker', service_verifier),
               ('constructor', __import__(__name__, fromlist=['_'])))
    return {name: hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest() for name, mod in sources}


def integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= LIMIT:
        raise ValueError('INTEGER_CENTS_REQUIRED:'+name)
    return value


def normalized(raw):
    if not isinstance(raw, dict) or raw.get('format') not in ('canonical','legacy'):
        raise ValueError('SOURCE_FORMAT_CONNECTOR_REQUIRED')
    if raw['format']=='canonical':
        if set(raw) != {'format','order'}:
            raise ValueError('CANONICAL_EXACT_SOURCE_REQUIRED')
        order = raw['order']
    else:
        if set(raw) != {'format','id','currency','require_complete','invoice_rows','settlement_rows'}:
            raise ValueError('LEGACY_EXACT_SOURCE_REQUIRED')
        if raw['currency']!='USD' or type(raw['require_complete']) is not bool:
            raise ValueError('LEGACY_CURRENCY_OR_COMPLETENESS_UNSUPPORTED')
        def convert(row, payment=False):
            expected={'key','party','amount_minor'} | ({'applies_to'} if payment else set())
            if not isinstance(row,dict) or set(row)!=expected:
                raise ValueError('EXACT_LEGACY_ROW_REQUIRED')
            result={'id':row['key'],'customer':row['party'],'amount_cents':row['amount_minor']}
            if payment:result['invoice_refs']=row['applies_to']
            return result
        order={'scope':service.SCOPE,'order_id':raw['id'],'currency':'USD',
               'require_complete':raw['require_complete'],
               'invoices':[convert(x) for x in raw['invoice_rows']],
               'payments':[convert(x,True) for x in raw['settlement_rows']]}
    service.validate(order)
    if order.get('require_complete') is not True:
        raise ValueError('COMPLETE_OUTCOME_REQUIRED')
    return order


def validate(spec):
    if not isinstance(spec,dict) or set(spec)!= {'schema','scope','capital_cents','protected_cents','risk_reserve_cents',
            'provider_min_gain_cents','buyers','methods'} or spec['schema']!=SCHEMA or spec['scope']!='SYNTHETIC_PUBLIC_HYPOTHESIS':
        raise ValueError('EXACT_EXCHANGE_SCHEMA_REQUIRED')
    for x in ('capital_cents','protected_cents','risk_reserve_cents','provider_min_gain_cents'):
        integer(spec[x],x)
    buyers=spec['buyers'];methods=spec['methods']
    if not isinstance(buyers,list) or not 1<=len(buyers)<=MAX_BUYERS or not isinstance(methods,list) or not 1<=len(methods)<=MAX_METHODS:
        raise ValueError('FINITE_BUYER_METHOD_SEARCH_BOUND_REQUIRED')
    ids=set();order_ids=set()
    for buyer in buyers:
        if not isinstance(buyer,dict) or set(buyer)!={'id','maximum_value_cents','outside_utility_cents','budget_cents','minimum_gain_cents','source'}:
            raise ValueError('EXACT_VOLUNTARY_BUYER_REQUIRED')
        ident=buyer['id']
        if type(ident) is not str or not ident or len(ident)>60 or ident in ids:
            raise ValueError('UNIQUE_BUYER_ID_REQUIRED')
        ids.add(ident)
        for name in ('maximum_value_cents','outside_utility_cents','budget_cents','minimum_gain_cents'):
            integer(buyer[name],name)
        if buyer['outside_utility_cents']>buyer['maximum_value_cents']:
            raise ValueError('OUTSIDE_OPTION_DOMINATES_AUTHORED_VALUE')
        order=normalized(buyer['source'])
        if order['order_id'] in order_ids:
            raise ValueError('DISTINCT_VERIFIABLE_DELIVERY_REQUIRED')
        order_ids.add(order['order_id'])
    methods_ids=set()
    for method in methods:
        if not isinstance(method,dict) or set(method)!=set(FIELDS)|{'id','kind','min_buyers','max_buyers'}:
            raise ValueError('EXACT_METHOD_CONTRACT_REQUIRED')
        ident=method['id']
        if type(ident) is not str or not ident or len(ident)>60 or ident in methods_ids:
            raise ValueError('UNIQUE_METHOD_ID_REQUIRED')
        methods_ids.add(ident)
        if method['kind'] not in ('direct_specialist','shared_proof'):
            raise ValueError('ADMITTED_METHOD_KIND_REQUIRED')
        for field in FIELDS:integer(method[field],field)
        for field in ('min_buyers','max_buyers'):
            if type(method[field]) is not int or not 1<=method[field]<=MAX_BUYERS:
                raise ValueError('METHOD_SCOPE_REQUIRED:'+field)
        if method['min_buyers']>method['max_buyers'] or (method['kind']=='direct_specialist' and (method['min_buyers']!=1 or method['max_buyers']!=1)) or (method['kind']=='shared_proof' and method['min_buyers']<2):
            raise ValueError('KNOWN_METHOD_SCOPE_CHANGED')
    return spec


def evaluate(spec, method, party):
    """One fixed-price, budget-balanced finite coalition with declared buyer IR."""
    n=len(party)
    if not method['min_buyers']<=n<=method['max_buyers']:
        return None
    effective=[b['maximum_value_cents']-b['outside_utility_cents'] for b in party]
    floors=[max(b['minimum_gain_cents'],cap-b['budget_cents']) for b,cap in zip(party,effective)]
    if any(floor>=cap for floor,cap in zip(floors,effective)):
        return None
    costs={'shared_construction_cents':method['setup_cents'],
           'production_cents':n*method['unit_cents'],
           'verification_cents':n*method['verification_cents'],
           'failed_search_qualification_cents':method['qualification_cents'],
           'partner_setup_cents':method['partner_setup_cents'],
           'partner_resource_cents':n*method['partner_cost_cents'],
           'partner_required_gain_cents':n*method['partner_gain_cents']}
    total=sum(costs.values()); surplus=sum(effective)-total
    minimum=spec['provider_min_gain_cents']+sum(floors)
    if surplus<minimum or total+spec['protected_cents']+spec['risk_reserve_cents']>spec['capital_cents']:
        return None
    # Conditional equal-gain increment above outside-option and provider floors.
    # Cap each buyer at their total value; any remaining gains stay with provider.
    increment=(surplus-minimum)//(n+1)
    buyer_gains=[min(cap,minimum_gain+increment) for cap,minimum_gain in zip(effective,floors)]
    prices=[cap-gain for cap,gain in zip(effective,buyer_gains)]
    revenue=sum(prices);provider_gain=revenue-total
    if any(price<0 or price>buyer['budget_cents'] for price,buyer in zip(prices,party)) or provider_gain<spec['provider_min_gain_cents']:
        raise ValueError('INTERNAL_ALLOCATION_INVARIANT_FAILED')
    return {'method_id':method['id'],'method_kind':method['kind'],
            'buyer_ids':[b['id'] for b in party],
            'prices_cents':dict(zip((b['id'] for b in party),prices)),
            'buyer_incremental_gains_cents':dict(zip((b['id'] for b in party),buyer_gains)),
            'partner_distributed_gain_cents':n*method['partner_gain_cents'],
            'costs_cents':costs,'complete_model_cost_cents':total,
            'conditional_revenue_cents':revenue,'conditional_provider_gain_cents':provider_gain,
            'required_protected_cash_cents':total+spec['protected_cents']+spec['risk_reserve_cents'],
            'total_declared_new_value_cents':sum(effective),
            'created_surplus_cents':surplus}


def candidates(spec):
    validate(spec)
    buyers=sorted(spec['buyers'],key=lambda x:x['id'])
    for method in sorted(spec['methods'],key=lambda x:x['id']):
        for length in range(method['min_buyers'],min(method['max_buyers'],len(buyers))+1):
            for party in combinations(buyers,length):
                quote=evaluate(spec,method,party)
                if quote is not None:
                    yield quote


def ranking(row):
    return (row['conditional_provider_gain_cents'],row['created_surplus_cents'],
            -row['complete_model_cost_cents'],tuple(row['buyer_ids']),row['method_id'])


def build(spec):
    validate(spec)
    allowed=list(candidates(spec))
    best=max(allowed,key=ranking) if allowed else None
    deliveries=[]
    if best is not None:
        for buyer in sorted(spec['buyers'],key=lambda x:x['id']):
            if buyer['id'] not in best['buyer_ids']:continue
            order=normalized(buyer['source'])
            report=service.reconcile(order)
            checked=service_verifier.audit_delivery(order,report)
            if not checked['accepted'] or not report['accepted']:
                raise ValueError('UNQUALIFIED_COMPLETED_WORK_CANNOT_SUPPORT_COALITION')
            deliveries.append({'buyer_id':buyer['id'], 'source_sha256':digest(buyer['source']),
                'normalized_order':order,'verified_report':report,
                'independent_checker_receipt':checked})
    return {'schema':SCHEMA,'source_sha256':digest(spec),'source_hashes':hashes(),
            'ranked_options':sorted(allowed,key=ranking,reverse=True),
            'chosen':best,'produced_checked_outcomes':deliveries,
            'status':'CONDITIONALLY_FEASIBLE_NEW_BUSINESS' if best else 'NO_BID_OR_RETAIN_CASH',
            'conditional_mechanism_only':True, 'buyer_consent_observed':False,
            'partner_consent_observed':False, 'native_cash_committed_cents':0,
            'actual_customer_collections_cents':0, 'actual_profit_cents':None,
            'source_level':'BOUNDED_AUTHORED_PUBLIC_SYNTHETIC_GAME_NOT_REAL_COMMERCIAL_INVENTION'}
