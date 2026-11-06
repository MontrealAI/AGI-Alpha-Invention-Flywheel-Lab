"""Defensive verification boundary; never imports the constructor.

A caller pin binds the entire authored case, not just its event list. It is not a
signature, source-authentication service, capacity reservation, or live authority.
"""
from __future__ import annotations
import hashlib
import json
import re

_HEX = re.compile(r'^[a-f0-9]{64}$')
_COSTS = {'assessment', 'setup', 'reservation', 'supplier', 'transport',
          'verification', 'support', 'rights', 'contingency'}
_FLAGS = {'real_supplier_consent', 'real_customer_acceptance', 'real_recovery_proof',
          'real_payment', 'external_independent_certification', 'disaster_wide_continuity'}


def case_digest(case):
    """Canonical SHA-256 identity; external custody of the pin is caller-owned."""
    raw = json.dumps(case, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def input_findings(case, handoff, passport):
    """Reject unsupported shapes/types before any arithmetic or nested lookup."""
    errors = []
    def fail(code):
        errors.append(code)
    def record(value, keys, code):
        if type(value) is not dict or set(value) != set(keys):
            fail(code)
            return value if type(value) is dict else {}
        return value
    def array(value, code):
        if type(value) is not list:
            fail(code)
            return []
        return value
    def integer(value, code, minimum=0):
        if type(value) is not int or value < minimum:
            fail(code)
    def strings(obj, keys, code):
        if any(type(obj.get(k)) is not str for k in keys):
            fail(code)
    def flags(obj, keys, code):
        if any(type(obj.get(k)) is not bool for k in keys):
            fail(code)
    c = record(case, ['schema','mode','real_authority','exercise_id','source_events',
        'source_seal','objective','restored_snapshot','buyer','scope_rights_declared',
        'blocked_failure_domains','economics','suppliers'], 'CASE_SHAPE_INVALID')
    strings(c, ['schema','mode','exercise_id','source_seal'], 'CASE_TEXT_INVALID')
    flags(c, ['real_authority','scope_rights_declared'], 'CASE_FLAG_TYPE_INVALID')
    events = array(c.get('source_events'), 'SOURCE_EVENTS_INVALID')
    if not 0 < len(events) <= 20000:
        fail('SOURCE_EVENTS_INVALID')
    for event in events:
        base = ['sequence','type','order_id']
        if type(event) is not dict:
            fail('EVENT_MALFORMED')
            continue
        kind = event.get('type')
        if kind == 'ACCEPT':
            keys = base + ['quantity','product','spec_sha256','deadline_hours']
        elif kind in ('AMEND','FULFILL'):
            keys = base + ['quantity']
        elif kind == 'CANCEL':
            keys = base
        else:
            fail('UNRECOGNIZED_EVENT')
            continue
        e = record(event, keys, 'EVENT_FIELDS_INVALID')
        integer(e.get('sequence'), 'EVENT_PROVENANCE_MISSING', 1)
        strings(e, ['type','order_id'], 'INVALID_EVENT_ORDER_ID')
        if kind != 'CANCEL':
            integer(e.get('quantity'), 'INVALID_EVENT_QUANTITY', 1)
        if kind == 'ACCEPT':
            strings(e, ['product','spec_sha256'], 'EVENT_PRODUCT_OR_SPEC_INVALID')
            integer(e.get('deadline_hours'), 'DEADLINE_INVALID', 1)
    o = record(c.get('objective'), ['product','deadline_hours','no_lost_orders',
        'no_duplicates'], 'OBJECTIVE_SHAPE_INVALID')
    strings(o, ['product'], 'OBJECTIVE_PRODUCT_INVALID')
    integer(o.get('deadline_hours'), 'OBJECTIVE_HORIZON_INVALID', 1)
    flags(o, ['no_lost_orders','no_duplicates'], 'OBJECTIVE_FLAGS_INVALID')
    for row in array(c.get('restored_snapshot'), 'RESTORED_SNAPSHOT_MISSING'):
        r = record(row, ['order_id','quantity'], 'BAD_RESTORED_RECORD')
        strings(r, ['order_id'], 'BAD_RESTORED_RECORD')
        integer(r.get('quantity'), 'BAD_RESTORED_RECORD', 1)
    b = record(c.get('buyer'), ['maximum_offer','simulated_eligibility'], 'BUYER_SHAPE_INVALID')
    integer(b.get('maximum_offer'), 'BUYER_BUDGET_INVALID', 1)
    flags(b, ['simulated_eligibility'], 'BUYER_ELIGIBILITY_TYPE_INVALID')
    for domain in array(c.get('blocked_failure_domains'), 'BLOCKED_DOMAINS_INVALID'):
        if type(domain) is not str:
            fail('BLOCKED_DOMAINS_INVALID')
    for supplier in array(c.get('suppliers'), 'SUPPLIER_LIST_INVALID'):
        s = record(supplier, ['supplier_id','product','capacity_units','lead_hours',
            'failure_domain','available','simulated_qualification','simulated_commitment',
            'quoted_cost','existing_reservations'], 'SUPPLIER_RECORD_INVALID')
        strings(s, ['supplier_id','product','failure_domain'], 'SUPPLIER_ID_INVALID')
        flags(s, ['available','simulated_qualification','simulated_commitment'],
              'SUPPLIER_QUALIFICATION_FLAG_INVALID')
        for key in ['capacity_units','lead_hours','quoted_cost']:
            integer(s.get(key), 'SUPPLIER_RESOURCE_INVALID', 1 if key=='capacity_units' else 0)
        for reservation in array(s.get('existing_reservations'), 'SUPPLIER_RESERVATION_INVALID'):
            r = record(reservation, ['start_hour','end_hour','units'], 'SUPPLIER_RESERVATION_INVALID')
            for key in ['start_hour','end_hour','units']:
                integer(r.get(key), 'SUPPLIER_RESERVATION_INVALID', 0 if key=='start_hour' else 1)
            if type(r.get('start_hour')) is int and type(r.get('end_hour')) is int and r['start_hour'] >= r['end_hour']:
                fail('SUPPLIER_RESERVATION_INVALID')
    e = record(c.get('economics'), ['offer','costs'], 'ECONOMICS_SHAPE_INVALID')
    integer(e.get('offer'), 'OFFER_TYPE_INVALID', 1)
    costs = record(e.get('costs'), _COSTS, 'FULL_COST_CATEGORIES')
    for value in costs.values():
        integer(value, 'FULL_COST_CATEGORIES')
    h = record(handoff, ['schema','exercise_id','source_events_sha256','orders',
        'required_units','supplier_id','supplier_failure_domain','supplier_available_units_in_window',
        'rehearsed_completion_hours','latest_required_hours','idempotency_key','scope'], 'HANDOFF_SHAPE_INVALID')
    strings(h, ['schema','exercise_id','source_events_sha256','supplier_id',
        'supplier_failure_domain','idempotency_key','scope'], 'HANDOFF_TEXT_INVALID')
    for key in ['required_units','supplier_available_units_in_window','rehearsed_completion_hours','latest_required_hours']:
        integer(h.get(key), 'HANDOFF_NUMBER_TYPE_INVALID', 0 if key=='rehearsed_completion_hours' else 1)
    for order in array(h.get('orders'), 'HANDOFF_ORDER_LIST_INVALID'):
        r = record(order, ['order_id','units','product','spec_sha256','deadline_hours','source_sequences'], 'HANDOFF_ORDER_INVALID')
        strings(r, ['order_id','product','spec_sha256'], 'HANDOFF_ORDER_INVALID')
        integer(r.get('units'), 'HANDOFF_ORDER_INVALID', 1)
        integer(r.get('deadline_hours'), 'HANDOFF_ORDER_INVALID', 1)
        for seq in array(r.get('source_sequences'), 'HANDOFF_PROVENANCE_INVALID'):
            integer(seq, 'HANDOFF_PROVENANCE_INVALID', 1)
    p = record(passport, ['schema','exercise_id','technical_verdict','restoration_findings',
        'source_events_sha256','handoff_sha256','economics','comparison','evidence_boundary',
        'successor_hypothesis'], 'PASSPORT_SHAPE_INVALID')
    strings(p, ['schema','exercise_id','technical_verdict','source_events_sha256',
        'handoff_sha256','successor_hypothesis'], 'PASSPORT_TEXT_INVALID')
    for finding in array(p.get('restoration_findings'), 'RESTORE_CHALLENGE_FINDINGS'):
        r = record(finding, ['order_id','issue'], 'RESTORE_CHALLENGE_FINDINGS')
        strings(r, ['order_id','issue'], 'RESTORE_CHALLENGE_FINDINGS')
    pe = record(p.get('economics'), ['currency','offer','modeled_cost','modeled_contribution',
        'customer_budget'], 'PASSPORT_ECONOMICS_INVALID')
    strings(pe, ['currency'], 'PASSPORT_ECONOMICS_INVALID')
    for key in ['offer','modeled_cost','modeled_contribution','customer_budget']:
        integer(pe.get(key), 'PASSPORT_MONEY_TYPE_INVALID')
    comp = record(p.get('comparison'), ['conventional_route','incremental_advantage'], 'COMPARISON_SHAPE_INVALID')
    strings(comp, ['conventional_route','incremental_advantage'], 'COMPARISON_SHAPE_INVALID')
    boundary = record(p.get('evidence_boundary'), _FLAGS, 'EVIDENCE_BOUNDARY_INVALID')
    flags(boundary, _FLAGS, 'EVIDENCE_BOUNDARY_INVALID')
    return sorted(set(errors))


def checked_audit(case, handoff, passport, *, core, expected_case_sha256=None):
    """Fail closed on invalid structures; optionally bind a caller-held case pin."""
    failures = input_findings(case, handoff, passport)
    identity = None
    try:
        identity = case_digest(case)
    except (TypeError, ValueError, RecursionError):
        failures.append('INPUT_NOT_CANONICAL_JSON')
    if expected_case_sha256 is not None:
        if type(expected_case_sha256) is not str or not _HEX.fullmatch(expected_case_sha256):
            failures.append('CALLER_PIN_INVALID')
        elif identity != expected_case_sha256:
            failures.append('FROZEN_CASE_CHANGED')
    if failures:
        result = {'schema':'continuity-omega/audit-v1', 'verdict':'FAIL',
            'exercise_id':case.get('exercise_id') if type(case) is dict and type(case.get('exercise_id')) is str else None,
            'failures':sorted(set(failures)), 'failure_count':len(set(failures)),
            'scope':'SYNTHETIC_ONLY; rejected before unsafe evaluation; no authority'}
    else:
        result = core(case, handoff, passport)
    result.update({'case_sha256':identity,
        'case_binding':'CALLER_PIN_MATCHED' if expected_case_sha256 is not None and identity==expected_case_sha256 and not failures else 'UNPINNED' if expected_case_sha256 is None else 'PIN_REJECTED',
        'timing_evidence':'STIPULATED_NOT_MEASURED',
        'origin_authentication':'NOT_ESTABLISHED',
        'external_certification':False})
    return result
