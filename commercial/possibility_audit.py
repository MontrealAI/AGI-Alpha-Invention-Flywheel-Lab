"""Separate reconstruction of finite exchange economics and actual service outputs."""
from __future__ import annotations

from itertools import combinations

from commercial import service, service_verifier
from commercial import possibility_exchange as exchange


def independent_normalization(raw):
    if raw['format']=='canonical':
        data=raw['order']
    elif raw['format']=='legacy':
        data={'scope':service.SCOPE,'currency':raw['currency'],'order_id':raw['id'],
              'require_complete':raw['require_complete'],
              'invoices':[{'id':r['key'],'customer':r['party'],'amount_cents':r['amount_minor']}
                          for r in raw['invoice_rows']],
              'payments':[{'id':r['key'],'customer':r['party'],'amount_cents':r['amount_minor'],
                           'invoice_refs':r['applies_to']} for r in raw['settlement_rows']]}
    else:
        raise ValueError('INDEPENDENT_CONNECTOR_UNKNOWN')
    service.validate(data)
    return data


def reprice(spec, method, party):
    n=len(party)
    if n<method['min_buyers'] or n>method['max_buyers']:
        return None
    groups={k:0 for k in ('shared_construction_cents','production_cents','verification_cents',
                        'failed_search_qualification_cents','partner_setup_cents',
                        'partner_resource_cents','partner_required_gain_cents')}
    groups['shared_construction_cents']=method['setup_cents']
    groups['production_cents']=n*method['unit_cents']
    groups['verification_cents']=n*method['verification_cents']
    groups['failed_search_qualification_cents']=method['qualification_cents']
    groups['partner_setup_cents']=method['partner_setup_cents']
    groups['partner_resource_cents']=n*method['partner_cost_cents']
    groups['partner_required_gain_cents']=n*method['partner_gain_cents']
    operating=sum(groups.values())
    residual=spec['capital_cents']-spec['protected_cents']-spec['risk_reserve_cents']
    if operating>residual:return None
    ceiling={b['id']:b['maximum_value_cents']-b['outside_utility_cents'] for b in party}
    minimum_gain={b['id']:max(b['minimum_gain_cents'],ceiling[b['id']]-b['budget_cents']) for b in party}
    if any(minimum_gain[x]>=ceiling[x] for x in ceiling):return None
    sum_gain=sum(ceiling.values())-operating
    if sum_gain<spec['provider_min_gain_cents']+sum(minimum_gain.values()):return None
    increment=(sum_gain-spec['provider_min_gain_cents']-sum(minimum_gain.values()))//(n+1)
    buyers={x:min(ceiling[x],minimum_gain[x]+increment) for x in ceiling}
    payments={x:ceiling[x]-buyers[x] for x in ceiling}
    provider=sum(payments.values())-operating
    if provider<spec['provider_min_gain_cents']:return None
    if any(payments[b['id']]>b['budget_cents'] for b in party):return None
    return {'method_id':method['id'],'method_kind':method['kind'],
            'buyer_ids':[b['id'] for b in party],
            'prices_cents':payments,'buyer_incremental_gains_cents':buyers,
            'partner_distributed_gain_cents':n*method['partner_gain_cents'],
            'costs_cents':groups,'complete_model_cost_cents':operating,
            'conditional_revenue_cents':sum(payments.values()),
            'conditional_provider_gain_cents':provider,
            'required_protected_cash_cents':operating+spec['protected_cents']+spec['risk_reserve_cents'],
            'total_declared_new_value_cents':sum(ceiling.values()),
            'created_surplus_cents':sum_gain}


def verify(spec, certificate):
    exchange.validate(spec)
    if not isinstance(certificate,dict) or certificate.get('schema')!=exchange.SCHEMA:
        raise ValueError('EXCHANGE_CERTIFICATE_SCHEMA_REQUIRED')
    if certificate.get('source_sha256')!=exchange.digest(spec) or certificate.get('source_hashes')!=exchange.hashes():
        raise ValueError('FROZEN_SOURCE_OR_GAME_CHANGED')
    if (certificate.get('conditional_mechanism_only') is not True or
            certificate.get('buyer_consent_observed') is not False or
            certificate.get('partner_consent_observed') is not False or
            certificate.get('native_cash_committed_cents') != 0 or
            certificate.get('actual_customer_collections_cents') != 0 or
            certificate.get('actual_profit_cents') is not None):
        raise ValueError('FABRICATED_CONSENT_COLLECTION_OR_PROFIT')
    eligible=[]
    buyers=sorted(spec['buyers'],key=lambda x:x['id'])
    for method in sorted(spec['methods'],key=lambda x:x['id']):
        for n in range(1,len(buyers)+1):
            for coalition in combinations(buyers,n):
                proposal=reprice(spec,method,coalition)
                if proposal is not None:eligible.append(proposal)
    rank=lambda r:(r['conditional_provider_gain_cents'],r['created_surplus_cents'],
                   -r['complete_model_cost_cents'],tuple(r['buyer_ids']),r['method_id'])
    ranked=sorted(eligible,key=rank,reverse=True)
    expected=ranked[0] if ranked else None
    if (certificate.get('ranked_options')!=ranked or certificate.get('chosen')!=expected or
            certificate.get('status')!=('CONDITIONALLY_FEASIBLE_NEW_BUSINESS' if expected else 'NO_BID_OR_RETAIN_CASH') or
            certificate.get('source_level')!='BOUNDED_AUTHORED_PUBLIC_SYNTHETIC_GAME_NOT_REAL_COMMERCIAL_INVENTION'):
        raise ValueError('UNTRUTHFUL_FEASIBLE_COALITION_OR_SELECTION')
    rows=certificate.get('produced_checked_outcomes')
    if not isinstance(rows,list):raise ValueError('ACTUAL_EXECUTED_WORK_RECEIPTS_REQUIRED')
    wanted=set(expected['buyer_ids']) if expected else set()
    if {x.get('buyer_id') for x in rows if isinstance(x,dict)}!=wanted or len(rows)!=len(wanted):
        raise ValueError('SELECTED_EXECUTABLE_WORK_MISSING_OR_DUPLICATED')
    byid={b['id']:b for b in buyers}
    for row in rows:
        buyer=byid[row['buyer_id']]
        target=independent_normalization(buyer['source'])
        if row.get('source_sha256')!=exchange.digest(buyer['source']) or row.get('normalized_order')!=target:
            raise ValueError('INDEPENDENT_SOURCE_CONNECTOR_CHANGED')
        fresh=service.reconcile(target)
        checked=service_verifier.audit_delivery(target,row.get('verified_report'))
        if row.get('verified_report')!=fresh or checked != row.get('independent_checker_receipt') or not checked['accepted'] or not fresh['accepted']:
            raise ValueError('FRESH_INDEPENDENT_SERVICE_CHECKER_REJECTED')
    return {'accepted':True,'source_sha256':exchange.digest(spec),'proposal_sha256':exchange.digest(certificate),
            'exhaustively_evaluated_candidate_count':sum(1 for method in spec['methods'] for n in range(1,len(buyers)+1)
                                                     for _ in combinations(buyers,n)
                                                     if method['min_buyers']<=n<=method['max_buyers']),
            'feasible_options':len(ranked), 'actual_verified_deliveries':len(rows),
            'maximum_possible_native_collections_cents':None,
            'actual_customer_collections_cents':0,
            'game_claim':'EXACT_FINITE_AUTHORED_PRICE_PARTICIPATION_OPTIMUM_NOT_TRUTHFUL_REVELATION_OR_REAL_DEMAND'}
