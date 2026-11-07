"""Synthetic fallback handoff constructor: no recovery, network, or payment authority.

Input events are treated as a separately protected, trustworthy reference *only*
within the explicitly authored drill. The seal binds bytes, not real-world truth.
"""
from __future__ import annotations
import hashlib
import json
import re
from copy import deepcopy

SCHEMA = 'continuity-omega/synthetic-drill-v1'
PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9._-]{0,63}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')

class DrillRejected(ValueError):
    pass

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def exact_int(value, field, *, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise DrillRejected(f'{field}: expected {"positive" if positive else "nonnegative"} integer')
    return value

def clean_id(value, field):
    if not isinstance(value, str) or not PATTERN.fullmatch(value):
        raise DrillRejected(f'{field}: invalid identifier')
    return value

def guarded_case(case):
    if not isinstance(case, dict) or case.get('schema') != SCHEMA:
        raise DrillRejected('unsupported exercise schema')
    if case.get('mode') != 'SYNTHETIC' or case.get('real_authority') is not False:
        raise DrillRejected('real-world authority is never supplied by this exercise')
    clean_id(case.get('exercise_id'), 'exercise_id')
    events = case.get('source_events')
    if not isinstance(events, list) or not events or len(events) > 20000:
        raise DrillRejected('source event list missing or exceeds local drill bound')
    seal = case.get('source_seal')
    if not isinstance(seal, str) or not HEX64.fullmatch(seal) or seal != digest(events):
        raise DrillRejected('protected source-event seal mismatch')
    objective = case.get('objective')
    if not isinstance(objective, dict):
        raise DrillRejected('missing objective')
    clean_id(objective.get('product'), 'product')
    exact_int(objective.get('deadline_hours'), 'deadline_hours', positive=True)
    if objective['deadline_hours'] > 10000:
        raise DrillRejected('unsupported drill horizon')
    if objective.get('no_lost_orders') is not True or objective.get('no_duplicates') is not True:
        raise DrillRejected('cannot relax the signed-off functional promise')
    restored = case.get('restored_snapshot')
    if not isinstance(restored, list):
        raise DrillRejected('missing recovered snapshot')
    for r in restored:
        if not isinstance(r, dict):
            raise DrillRejected('invalid recovered snapshot')
        clean_id(r.get('order_id'), 'recovered order id')
        exact_int(r.get('quantity'), 'recovered quantity', positive=True)
    if len({r['order_id'] for r in restored}) != len(restored):
        raise DrillRejected('duplicate recovered order')
    buyer = case.get('buyer')
    if not isinstance(buyer, dict):
        raise DrillRejected('missing buyer')
    exact_int(buyer.get('maximum_offer'), 'maximum_offer', positive=True)
    if buyer.get('simulated_eligibility') is not True:
        raise DrillRejected('buyer has not met even the synthetic participation condition')
    economics = case.get('economics')
    if not isinstance(economics, dict) or not isinstance(economics.get('costs'), dict):
        raise DrillRejected('missing complete modeled cost categories')
    if set(economics['costs']) != {'assessment','setup','reservation','supplier','transport','verification','support','rights','contingency'}:
        raise DrillRejected('modeled cost categories incomplete')
    for k,v in economics['costs'].items():
        exact_int(v, f'cost:{k}')
    exact_int(economics.get('offer'), 'proposed offer', positive=True)
    if economics['offer'] > buyer['maximum_offer']:
        raise DrillRejected('proposed offer exceeds buyer hypothetical budget')
    suppliers = case.get('suppliers')
    if not isinstance(suppliers,list) or not suppliers:
        raise DrillRejected('no alternative providers declared')
    ids=set()
    for s in suppliers:
        if not isinstance(s, dict): raise DrillRejected('invalid supplier record')
        sid=clean_id(s.get('supplier_id'),'supplier_id')
        if sid in ids: raise DrillRejected('duplicate supplier identity')
        ids.add(sid)
        clean_id(s.get('product'), 'supplier product')
        clean_id(s.get('failure_domain'), 'supplier failure domain')
        for f in ('capacity_units','quoted_cost','lead_hours'):
            exact_int(s.get(f),f,positive=(f=='capacity_units'))
        reservations=s.get('existing_reservations')
        if not isinstance(reservations,list):raise DrillRejected('supplier reservation records missing')
        for r in reservations:
            if not isinstance(r,dict): raise DrillRejected('invalid capacity reservation')
            st=exact_int(r.get('start_hour'),'reservation start')
            en=exact_int(r.get('end_hour'),'reservation end',positive=True)
            un=exact_int(r.get('units'),'reservation units',positive=True)
            if st>=en: raise DrillRejected('empty/reversed reservation interval')
        for flag in ('available','simulated_qualification','simulated_commitment'):
            if type(s.get(flag)) is not bool:
                raise DrillRejected(f'undeclared {flag} is not consent')
    return True

def outstanding(events, product):
    orders={}
    for pos,e in enumerate(events,1):
        if not isinstance(e,dict) or e.get('sequence')!=pos:
            raise DrillRejected('noncontiguous event provenance')
        oid=clean_id(e.get('order_id'),'event order')
        act=e.get('type')
        if act=='ACCEPT':
            if oid in orders:raise DrillRejected('duplicate acceptance')
            qty=exact_int(e.get('quantity'),'accepted units',positive=True)
            clean_id(e.get('product'),'order product')
            spec=e.get('spec_sha256')
            if not isinstance(spec,str) or not HEX64.fullmatch(spec):
                raise DrillRejected('missing verifiable specification digest')
            deadline=exact_int(e.get('deadline_hours'),'order deadline',positive=True)
            orders[oid]={'order_id':oid,'quantity':qty,'fulfilled':0,'product':e['product'],
                         'spec_sha256':spec,'deadline_hours':deadline,'status':'ACTIVE',
                         'source_sequences':[pos]}
        elif act in ('AMEND','CANCEL','FULFILL'):
            if oid not in orders or orders[oid]['status']!='ACTIVE':
                raise DrillRejected('amendment, cancel or fulfillment without active order')
            obj=orders[oid];obj['source_sequences'].append(pos)
            if act=='AMEND':
                q=exact_int(e.get('quantity'),'amended units',positive=True)
                if q < obj['fulfilled']:raise DrillRejected('amendment erases delivered units')
                obj['quantity']=q
            elif act=='CANCEL':obj['status']='CANCELLED'
            else:
                q=exact_int(e.get('quantity'),'delivered units',positive=True)
                if obj['fulfilled']+q>obj['quantity']:raise DrillRejected('over-fulfillment')
                obj['fulfilled']+=q
        else:raise DrillRejected('unrecognized event type')
    active=[]
    for obj in orders.values():
        remaining=obj['quantity']-obj['fulfilled']
        if obj['status']=='ACTIVE' and remaining and obj['product']==product:
            active.append({'order_id':obj['order_id'],'units':remaining,
                'product':obj['product'],'spec_sha256':obj['spec_sha256'],
                'deadline_hours':obj['deadline_hours'], 'source_sequences':obj['source_sequences']})
    return sorted(active,key=lambda x:x['order_id']),orders

def restored_anomalies(orders, snapshot):
    """Compare the v1 *outstanding-work* snapshot, not the whole order history.

    v1 records only gross quantity. They cannot attest to already completed
    units; an active partially fulfilled order must fail closed until a
    separately versioned, independently witnessed snapshot exists.
    """
    got={r['order_id']:r['quantity'] for r in snapshot}
    anomalies=[]
    for oid,o in sorted(orders.items()):
        if o['status']=='CANCELLED':
            if oid in got:
                anomalies.append({'order_id':oid,'issue':'CANCELLED_ORDER_REAPPEARED'})
            continue
        if o['quantity']==o['fulfilled']:
            if oid in got:
                anomalies.append({'order_id':oid,'issue':'COMPLETED_ORDER_REAPPEARED'})
            continue
        if oid not in got:
            anomalies.append({'order_id':oid,'issue':'MISSING_FROM_RESTORED_SNAPSHOT'})
        elif got[oid]!=o['quantity']:
            anomalies.append({'order_id':oid,'issue':'STALE_OR_CHANGED_RESTORED_QUANTITY'})
        elif o['fulfilled']>0:
            anomalies.append({'order_id':oid,'issue':'FULFILLMENT_PROVENANCE_UNSUPPORTED_V1'})
    for oid in sorted(set(got)-set(orders)):
        anomalies.append({'order_id':oid,'issue':'UNSUPPORTED_RESTORED_ORDER'})
    return anomalies

def qualified_supplier(s, total_units, deadline, product, blocked_domains):
    if s['product']!=product or not all(s[f] for f in ('available','simulated_qualification','simulated_commitment')):
        return False,0
    if s['failure_domain'] in blocked_domains or s['lead_hours']>deadline:return False,0
    # Conservative, single common 0..deadline interval; never infer spare capacity from one instant.
    reserved=sum(r['units'] for r in s['existing_reservations'] if r['start_hour']<deadline and r['end_hour']>0)
    free=s['capacity_units']-reserved
    return free>=total_units,free

def construct(case):
    guarded_case(case)
    obj=case['objective'];events=case['source_events']
    active,orders=outstanding(events,obj['product'])
    # A v1 gross-only restored snapshot cannot distinguish already fulfilled
    # units from unshipped work. Do not issue an executable-looking handoff.
    # No v1 source, event, or financial history is reinterpreted or rewritten.
    if any(o['status']=='ACTIVE' and o['fulfilled']>0 for o in orders.values()):
        raise DrillRejected('restoration fulfillment provenance unsupported in v1 gross-only snapshot')
    if not active:raise DrillRejected('no outstanding eligible commitment')
    if any(o['deadline_hours'] > obj['deadline_hours'] for o in active):
        raise DrillRejected('order falls outside frozen deadline horizon')
    total=sum(o['units'] for o in active)
    deadline=min(o['deadline_hours'] for o in active)
    blocked=set(case.get('blocked_failure_domains', []))
    if not isinstance(case.get('blocked_failure_domains', []), list):raise DrillRejected('invalid blocked domains')
    for b in blocked:clean_id(b,'blocked failure domain')
    choices=[]
    for s in case['suppliers']:
        admissible,free=qualified_supplier(s,total,deadline,obj['product'],blocked)
        if admissible:choices.append((s['quoted_cost'],s['lead_hours'],s['supplier_id'],free,s))
    if not choices:raise DrillRejected('no simulated supplier can satisfy capacity and deadline')
    *_,selected=min(choices,key=lambda t:t[:3])
    if selected['quoted_cost']!=case['economics']['costs']['supplier']:
        raise DrillRejected('supplier quoted cost differs from modeled full-cost plan')
    costs=sum(case['economics']['costs'].values())
    offer=case['economics']['offer']
    if offer < costs:raise DrillRejected('no nonnegative modeled contribution after full costs')
    if case.get('scope_rights_declared') is not True:
        raise DrillRejected('information-sharing permission absent from scenario')
    matched=restored_anomalies(orders,case['restored_snapshot'])
    handoff={'schema':'continuity-omega/handoff-v1','exercise_id':case['exercise_id'],
        'source_events_sha256':digest(events),'orders':active,'required_units':total,
        'supplier_id':selected['supplier_id'],'supplier_failure_domain':selected['failure_domain'],
        'supplier_available_units_in_window':next(x[3] for x in choices if x[2]==selected['supplier_id']),
        'rehearsed_completion_hours':selected['lead_hours'],
        'latest_required_hours':deadline,'idempotency_key':digest([case['exercise_id'],digest(events),selected['supplier_id'],total]),
        'scope':'SYNTHETIC_ONLY_NOT_AN_AUTHORIZATION'}
    plan={'schema':'continuity-omega/passport-v1','exercise_id':case['exercise_id'],
        'technical_verdict':'READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT',
        'restoration_findings':matched,'source_events_sha256':digest(events),
        'handoff_sha256':digest(handoff),
        'economics':{'currency':'ILLUSTRATIVE_USD','offer':offer,'modeled_cost':costs,
                     'modeled_contribution':offer-costs,'customer_budget':case['buyer']['maximum_offer']},
        'comparison':{'conventional_route':'SAME_INPUTS_AND_SUPPLIER_ACCESS',
            'incremental_advantage':'NOT_ESTABLISHED'},
        'evidence_boundary':{'real_supplier_consent':False,'real_customer_acceptance':False,
            'real_recovery_proof':False,'real_payment':False,'external_independent_certification':False,
            'disaster_wide_continuity':False},
        'successor_hypothesis':'Test a new product family only after independent specifications, capacity, rights and costs are requalified.'}
    return handoff,plan
