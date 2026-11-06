"""Independently implemented, source-replaying checker for CONTINUITY Ω synthetic drills.

Does not call the constructor. Same authorship is NOT third-party independence.
"""
from __future__ import annotations
import hashlib
import json


def _hash(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',', ':'),ensure_ascii=True).encode()).hexdigest()


def audit(case, handoff, passport):
    findings=[]
    def check(ok,label):
        if not ok:findings.append(label)
    check(isinstance(case,dict) and case.get('mode')=='SYNTHETIC' and case.get('real_authority') is False,'SYNTHETIC_ONLY_REQUIRED')
    events=case.get('source_events',[])
    check(isinstance(events,list) and len(events)>0 and _hash(events)==case.get('source_seal'),'SOURCE_SEAL_INVALID')
    if not isinstance(events,list):events=[]
    state={}; indices={}
    for i,event in enumerate(events,1):
        if not isinstance(event,dict):check(False,'EVENT_MALFORMED');continue
        oid=event.get('order_id');act=event.get('type')
        check(type(event.get('sequence')) is int and event['sequence']==i,'EVENT_PROVENANCE_MISSING')
        if act=='ACCEPT':
            if oid in state:check(False,'DUPLICATE_ACCEPTANCE');continue
            if type(event.get('quantity')) is not int or event['quantity']<=0:check(False,'INVALID_ACCEPT_QUANTITY');continue
            if not isinstance(event.get('spec_sha256'),str) or len(event['spec_sha256'])!=64:check(False,'SPEC_PROVENANCE_MISSING')
            if type(event.get('deadline_hours')) is not int or event['deadline_hours']<=0:check(False,'DEADLINE_INVALID')
            state[oid]={'order_id':oid,'product':event.get('product'),'quantity':event['quantity'],
                'fulfilled':0,'cancelled':False,'spec_sha256':event.get('spec_sha256'),
                'deadline_hours':event.get('deadline_hours'),'source_sequences':[i]}
            continue
        if oid not in state or state[oid]['cancelled']:
            check(False,'INVALID_EVENT_TARGET');continue
        row=state[oid];row['source_sequences'].append(i)
        if act=='AMEND':
            q=event.get('quantity')
            if type(q) is not int or q<row['fulfilled'] or q<=0:check(False,'BAD_AMENDMENT')
            else:row['quantity']=q
        elif act=='FULFILL':
            q=event.get('quantity')
            if type(q) is not int or q<=0 or row['fulfilled']+q>row['quantity']:check(False,'BAD_FULFILLMENT')
            else:row['fulfilled']+=q
        elif act=='CANCEL':row['cancelled']=True
        else:check(False,'UNRECOGNIZED_EVENT')
    objective=case.get('objective') or {}
    prod=objective.get('product')
    orders=[]
    for row in state.values():
        units=row['quantity']-row['fulfilled']
        if not row['cancelled'] and units>0 and row['product']==prod:
            orders.append({'order_id':row['order_id'],'units':units,'product':row['product'],
                'spec_sha256':row['spec_sha256'],'deadline_hours':row['deadline_hours'],
                'source_sequences':row['source_sequences']})
    orders.sort(key=lambda v:v['order_id'])
    check(len(orders)>0,'NO_OUTSTANDING_ORDERS')
    check(isinstance(handoff,dict) and handoff.get('schema')=='continuity-omega/handoff-v1','HANDOFF_SCHEMA')
    if not isinstance(handoff,dict):handoff={}
    if not isinstance(passport,dict):passport={}
    check(passport.get('schema')=='continuity-omega/passport-v1','PASSPORT_SCHEMA')
    check(handoff.get('exercise_id')==case.get('exercise_id')==passport.get('exercise_id'),'EXERCISE_IDENTITY')
    check(handoff.get('source_events_sha256')==_hash(events)==passport.get('source_events_sha256'),'SOURCE_BINDING')
    check(handoff.get('orders')==orders,'HANDOFF_DOES_NOT_MATCH_ORIGINAL_COMMITMENTS')
    total=sum(o['units'] for o in orders)
    check(handoff.get('required_units')==total,'REQUIRED_UNITS')
    check(handoff.get('scope')=='SYNTHETIC_ONLY_NOT_AN_AUTHORIZATION','SCOPE_MISREPRESENTED')
    if orders:
        check(handoff.get('latest_required_hours')==min(o['deadline_hours'] for o in orders),'DEADLINE_MISMATCH')
        check(all(o['deadline_hours']<=objective.get('deadline_hours',0) for o in orders),'OUTCOME_WINDOW_EXCEEDED')
    restored=case.get('restored_snapshot',[])
    observed={}; anomalies=[]
    if not isinstance(restored,list):check(False,'RESTORED_SNAPSHOT_MISSING');restored=[]
    for r in restored:
        if not isinstance(r,dict) or 'order_id' not in r or 'quantity' not in r:check(False,'BAD_RESTORED_RECORD');continue
        if r['order_id'] in observed:check(False,'DUPLICATE_RESTORED_RECORD')
        observed[r['order_id']]=r['quantity']
    for oid,row in sorted(state.items()):
        if oid not in observed:anomalies.append({'order_id':oid,'issue':'MISSING_FROM_RESTORED_SNAPSHOT'})
        elif observed[oid]!=row['quantity']:anomalies.append({'order_id':oid,'issue':'STALE_OR_CHANGED_RESTORED_QUANTITY'})
        elif row['cancelled']:anomalies.append({'order_id':oid,'issue':'CANCELLED_ORDER_REAPPEARED'})
    for oid in sorted(set(observed)-set(state)):
        anomalies.append({'order_id':oid,'issue':'UNSUPPORTED_RESTORED_ORDER'})
    check(passport.get('restoration_findings')==anomalies,'RESTORE_CHALLENGE_FINDINGS')
    # Challenge the full declared reservation book independently of the builder.
    # Negative, fractional and malformed claims must never manufacture headroom.
    all_suppliers=case.get('suppliers',[])
    for supplier in all_suppliers:
        if not isinstance(supplier,dict):
            check(False,'SUPPLIER_RECORD_INVALID');continue
        for field in ('capacity_units','quoted_cost','lead_hours'):
            value=supplier.get(field)
            check(type(value) is int and value >= (1 if field=='capacity_units' else 0),'SUPPLIER_RESOURCE_INVALID')
        reservations=supplier.get('existing_reservations')
        if not isinstance(reservations,list):
            check(False,'SUPPLIER_RESERVATION_INVALID');continue
        for reservation in reservations:
            if not isinstance(reservation,dict):
                check(False,'SUPPLIER_RESERVATION_INVALID');continue
            start=reservation.get('start_hour');end=reservation.get('end_hour');units=reservation.get('units')
            check(type(start) is int and start>=0 and type(end) is int and end>start
                  and type(units) is int and units>0,'SUPPLIER_RESERVATION_INVALID')
    supplier_id=handoff.get('supplier_id')
    selected=[s for s in case.get('suppliers',[]) if isinstance(s,dict) and s.get('supplier_id')==supplier_id]
    check(len(selected)==1,'SELECTED_SUPPLIER_IDENTITY')
    if len(selected)==1 and orders:
        s=selected[0]
        check(s.get('product')==prod and s.get('available') is True and
            s.get('simulated_qualification') is True and s.get('simulated_commitment') is True,
            'SUPPLIER_NOT_QUALIFIED_OR_SIMULATED_COMMITTED')
        check(s.get('failure_domain')==handoff.get('supplier_failure_domain'),'FAILURE_DOMAIN_IDENTITY')
        check(s.get('failure_domain') not in case.get('blocked_failure_domains',[]),'SUPPLIER_SHARED_OUTAGE')
        deadline=min(o['deadline_hours'] for o in orders)
        check(type(s.get('lead_hours')) is int and s['lead_hours']<=deadline and
            handoff.get('rehearsed_completion_hours')==s['lead_hours'],'SUPPLIER_LATE')
        used=0
        for r in s.get('existing_reservations',[]):
            if r.get('start_hour',0)<deadline and r.get('end_hour',0)>0:
                used+=r.get('units',0)
        free=s.get('capacity_units',0)-used
        check(free>=total and handoff.get('supplier_available_units_in_window')==free,'SUPPLIER_CAPACITY_OVERBOOKED')
        costs=case.get('economics',{}).get('costs',{})
        check(costs.get('supplier')==s.get('quoted_cost'),'QUOTED_COST_CHANGED')
        # A lower-cost eligible provider invalidates a selected minimum-cost promise.
        qualified=[]
        for alt in case.get('suppliers',[]):
            if alt.get('product')!=prod or alt.get('available') is not True or alt.get('simulated_qualification') is not True or alt.get('simulated_commitment') is not True:
                continue
            if alt.get('failure_domain') in case.get('blocked_failure_domains',[]) or alt.get('lead_hours',10**6)>deadline:
                continue
            enc=sum(r.get('units',0) for r in alt.get('existing_reservations',[]) if r.get('start_hour',0)<deadline and r.get('end_hour',0)>0)
            if alt.get('capacity_units',0)-enc>=total:qualified.append((alt['quoted_cost'],alt['lead_hours'],alt['supplier_id']))
        check(bool(qualified) and (s['quoted_cost'],s['lead_hours'],s['supplier_id'])==min(qualified),'BETTER_DECLARED_SUPPLIER_IGNORED')
    costset={'assessment','setup','reservation','supplier','transport','verification','support','rights','contingency'}
    econ=case.get('economics',{}); costs=econ.get('costs',{})
    check(set(costs)==costset and all(type(v) is int and v>=0 for v in costs.values()),'FULL_COST_CATEGORIES')
    if all(type(v) is int and v>=0 for v in costs.values()):
        total_cost=sum(costs.values())
        p=passport.get('economics',{})
        check(p.get('modeled_cost')==total_cost and p.get('offer')==econ.get('offer') and
              p.get('modeled_contribution')==econ.get('offer',0)-total_cost and
              p.get('currency')=='ILLUSTRATIVE_USD','ECONOMIC_ARITHMETIC')
        check(econ.get('offer',0)>=total_cost and econ.get('offer',10**9)<=case.get('buyer',{}).get('maximum_offer',0),'UNVIABLE_OR_UNAFFORDABLE_OFFER')
        check(p.get('customer_budget')==case.get('buyer',{}).get('maximum_offer'),'BUYER_BUDGET')
    check(case.get('scope_rights_declared') is True,'PERMITTED_DATA_SCOPE_ABSENT')
    check(case.get('buyer',{}).get('simulated_eligibility') is True,'BUYER_SYNTHETIC_ELIGIBILITY_MISSING')
    expected_key=_hash([case.get('exercise_id'),_hash(events),supplier_id,total])
    check(handoff.get('idempotency_key')==expected_key,'IDEMPOTENCY_BINDING')
    check(passport.get('handoff_sha256')==_hash(handoff),'PASSPORT_HANDOFF_BINDING')
    check(passport.get('technical_verdict')=='READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT','PRODUCER_VERDICT_SCOPE')
    controls=passport.get('evidence_boundary',{})
    for k in ['real_supplier_consent','real_customer_acceptance','real_recovery_proof','real_payment',
              'external_independent_certification','disaster_wide_continuity']:
        check(controls.get(k) is False,'IMPROPER_REAL_WORLD_CLAIM_'+k.upper())
    check(passport.get('comparison',{}).get('incremental_advantage')=='NOT_ESTABLISHED','UNSUPPORTED_SUPERIORITY')
    return {'schema':'continuity-omega/audit-v1','exercise_id':case.get('exercise_id'),
        'verdict':'PASS_SYNTHETIC_ONLY' if not findings else 'FAIL',
        'failure_count':len(findings),'failures':sorted(set(findings)),
        'replayed_orders':len(orders),'replayed_units':total,
        'restoration_gaps':anomalies,'scope':'SYNTHETIC_ONLY; independent code, same research authorship; no third-party certification',
        'source_digest_sha256':_hash(events),'handoff_sha256':_hash(handoff),
        'required_real_world_gates':['protect independent source evidence','obtain customer permission and confirmed supplier commitment',
            'execute scoped authorized drill','independent buyer acceptance','real invoice, collected payment and full cost reconciliation',
            'fresh different successor task; compare with competent conventional route']}
