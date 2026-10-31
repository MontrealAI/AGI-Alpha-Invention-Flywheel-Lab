"""Optional execution of an admitted mechanism plan through the existing synthetic P0 service.

This module never writes native accounts, real clients, payment or allocation records.
It proves executable *composition* of existing functionality, not generated new APIs.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time

from .core import ContractError, audit, canonical, compose, digest

SCHEMA = 'agi-alpha/mechanism-operating027/v1'
OPERATORS = {
    'prepare_csv_order': (frozenset({'raw_public_exports'}), frozenset({'canonical_order'})),
    'produce_reconciliation': (frozenset({'canonical_order'}), frozenset({'reconciliation_files'})),
    'check_reconciliation': (frozenset({'canonical_order', 'reconciliation_files'}), frozenset({'independently_checked_delivery'})),
}
SOURCE_FILES = (
    'commercial/onboarding.py', 'commercial/service.py', 'commercial/service_verifier.py',
    'mechanism_harness/core.py', 'mechanism_harness/operating027.py',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _root():
    return Path(__file__).resolve().parents[1]


def _sources():
    root = _root()
    return {x: sha((root/x).read_bytes()) for x in SOURCE_FILES}


def _regular(path, max_bytes):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes or any(x.is_symlink() for x in path.parents):
        raise ContractError('BOUNDED_REGULAR_PUBLIC_INPUT_REQUIRED')
    return path


def _frozen_inputs(paths):
    if set(paths) != {'contract', 'invoices', 'payments'}:
        raise ContractError('THREE_DECLARED_INPUTS_REQUIRED')
    limits = {'contract': 10_000, 'invoices': 2_000_000, 'payments': 2_000_000}
    return {k: sha(_regular(paths[k], limits[k]).read_bytes()) for k in sorted(paths)}


def _validate_plan(spec, plan):
    result = audit(spec, plan)
    if not result['accepted'] or not result['goal_achieved_symbolically'] or result['candidate_bridges_require_separate_qualification']:
        raise ContractError('QUALIFIED_EXISTING_MECHANISMS_ONLY')
    if spec['candidate_bridges'] or set(spec['purpose']['initial']) != {'raw_public_exports'} or set(spec['purpose']['goal']) != {'independently_checked_delivery'}:
        raise ContractError('EXACT_PRODUCTION_GOAL_REQUIRED')
    if set(x['id'] for x in spec['mechanisms']) != set(OPERATORS) or len(spec['mechanisms']) != len(OPERATORS):
        raise ContractError('FIXED_EXISTING_ADAPTER_CATALOG_REQUIRED')
    for op in spec['mechanisms']:
        requirements, effects = OPERATORS[op['id']]
        if set(op['requires']) != requirements or set(op['provides']) != effects or op['effect'] != 'pure':
            raise ContractError('SYMBOLIC_SEMANTICS_NOT_BOUND_TO_REAL_ADAPTER')
        if op['origin'] not in {'developer_supplied', 'retrieved', 'externally_supplied'}:
            raise ContractError('PROPOSED_OR_UNTRUSTED_RUNTIME_OPERATOR')
    if set(plan['sequence']) != set(OPERATORS) or len(plan['sequence']) != 3:
        raise ContractError('ALL_THREE_OPERATING_STAGES_REQUIRED')
    if plan['status'] != 'SYMBOLIC_PLAN_FOUND':
        raise ContractError('NO_CANDIDATE_EXECUTION')
    return result


def _csv_expected(report):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['order_id', 'kind', 'row_id'])
    for row in report['exceptions']:
        writer.writerow([report['order_id'], row['kind'], row['id']])
    return out.getvalue().encode('utf-8')


def _load_json(path):
    def pairs(items):
        v = {}
        for key, value in items:
            if key in v:
                raise ContractError('DUPLICATE_JSON_KEY')
            v[key] = value
        return v
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractError('NONFINITE_JSON')))


def _audit_outputs(paths, output):
    """Recompute acceptance from real raw public inputs and the separate P0 service checker."""
    from commercial.onboarding import prepare_order
    from commercial.service_verifier import audit_delivery
    from commercial.service import canonical as service_canonical
    base = Path(output)
    raw_order = prepare_order(paths['contract'], paths['invoices'], paths['payments'])
    prepared = (base/'prepared-order.json').read_bytes()
    if prepared != service_canonical(raw_order):
        raise ContractError('PREPARED_ORDER_DOES_NOT_MATCH_CURRENT_SOURCE')
    report = _load_json(base/'production/reconciliation.json')
    checked = audit_delivery(raw_order, report)
    if (base/'production/exceptions.csv').read_bytes() != _csv_expected(report):
        raise ContractError('EXCEPTION_CSV_CHANGED_OR_INCOMPLETE')
    return checked


def execute(spec, plan, paths, output, *, execution_mode='composed'):
    """Execute only the existing public synthetic CSV -> producer -> checker boundary.

    Output is create-only; a failed or interrupted directory is never silently resumed.
    Complete receipt is descriptive and must be independently rederived via verify().
    """
    if execution_mode not in {'composed', 'ordinary_direct', 'inherited_existing_plan'}:
        raise ContractError('INVALID_EXECUTION_MODE')
    _validate_plan(spec, plan)
    input_before = _frozen_inputs(paths)
    source_before = _sources()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or any(x.is_symlink() for x in output.parents):
        raise ContractError('FRESH_NORMALIZED_OUTPUT_REQUIRED')
    output.mkdir()
    from commercial.onboarding import prepare_order
    from commercial.service import canonical as service_canonical, deliver
    from commercial.service_verifier import audit_delivery
    steps = []
    started = time.monotonic_ns()
    state = {}
    try:
        for ident in plan['sequence']:
            begin = time.process_time_ns()
            if ident == 'prepare_csv_order':
                state['order'] = prepare_order(paths['contract'], paths['invoices'], paths['payments'])
                (output/'prepared-order.json').write_bytes(service_canonical(state['order']))
            elif ident == 'produce_reconciliation':
                state['report'] = deliver(state['order'], output/'production')
            elif ident == 'check_reconciliation':
                state['checked'] = audit_delivery(state['order'], state['report'])
            else:
                raise ContractError('UNSUPPORTED_OPERATING_STEP')
            steps.append({'operator': ident, 'cpu_ns': time.process_time_ns()-begin})
        if _frozen_inputs(paths) != input_before or _sources() != source_before:
            raise ContractError('OPERATING_SOURCE_OR_INPUT_CHANGED_DURING_RUN')
        independently_checked = _audit_outputs(paths, output)
        if independently_checked != state['checked']:
            raise ContractError('PRODUCER_CHECKER_RESULT_DIVERGED')
        # Rejection is a legitimate terminal result, not a successful accepted delivery.
        receipt = {
            'schema': SCHEMA, 'status': 'ACCEPTED_IN_SYNTHETIC_SCOPE' if independently_checked['accepted'] else 'REJECTED_BY_INDEPENDENT_SERVICE_CHECKER',
            'scope': 'SYNTHETIC_PUBLIC_RECONCILIATION_ONLY', 'mode': execution_mode,
            'spec_sha256': digest(spec), 'plan_sha256': digest(plan), 'operating_source_sha256': digest(source_before),
            'source_files_sha256': source_before, 'source_inputs_sha256': input_before,
            'artifacts_sha256': {name: sha((output/name).read_bytes()) for name in ('prepared-order.json', 'production/reconciliation.json', 'production/exceptions.csv')},
            'checker': independently_checked, 'stage_cpu_ns': steps, 'elapsed_wall_ns': time.monotonic_ns()-started,
            'current_proof': None, 'authority': [], 'actual_customer_count': 0, 'actual_collected_usd': 0,
            'cost_scope': 'Measured local process CPU and wall for this invocation; no model provider, engineering cost, monetary cost, or buyer demand measured',
            'claim': 'EXECUTED_P0_SYNTHETIC_SERVICE_WITH_FRESH_INDEPENDENT_SERVICE_CHECKER',
        }
        (output/'RECEIPT.json').write_bytes(canonical(receipt)+b'\n')
        return receipt
    except BaseException:
        # Never convert an interrupted or failed run into a complete receipt.
        raise


def verify(spec, plan, paths, output):
    """Reconstruct the real service verdict; reject altered public files/source/receipt.

    Only asserts actual current synthetic service semantics; does not trust modelled resource
    savings or treat this receipt as a credential for financial or operational actions.
    """
    _validate_plan(spec, plan)
    output = Path(output).absolute()
    for name in ('prepared-order.json','production/reconciliation.json','production/exceptions.csv','RECEIPT.json'):
        _regular(output/name, 2_000_000)
    receipt = _load_json(output/'RECEIPT.json')
    expected_fields = {'schema', 'status', 'scope', 'mode', 'spec_sha256', 'plan_sha256',
                       'operating_source_sha256', 'source_files_sha256', 'source_inputs_sha256',
                       'artifacts_sha256', 'checker', 'stage_cpu_ns', 'elapsed_wall_ns',
                       'current_proof', 'authority', 'actual_customer_count', 'actual_collected_usd',
                       'cost_scope', 'claim'}
    if set(receipt) != expected_fields:
        raise ContractError('EXACT_SERVICE_RECEIPT_FIELDS_REQUIRED')
    if receipt.get('schema') != SCHEMA or receipt.get('scope') != 'SYNTHETIC_PUBLIC_RECONCILIATION_ONLY':
        raise ContractError('NOT_CURRENT_SYNTHETIC_SERVICE_RECEIPT')
    if receipt.get('mode') not in {'composed', 'ordinary_direct', 'inherited_existing_plan'}:
        raise ContractError('UNSUPPORTED_SERVICE_EXECUTION_MODE')
    if receipt.get('claim') != 'EXECUTED_P0_SYNTHETIC_SERVICE_WITH_FRESH_INDEPENDENT_SERVICE_CHECKER':
        raise ContractError('NO_EXTERNAL_SUCCESS_CLAIM_PERMITTED')
    if receipt.get('spec_sha256') != digest(spec) or receipt.get('plan_sha256') != digest(plan):
        raise ContractError('SOURCE_BOUND_PLAN_MISMATCH')
    if receipt.get('source_inputs_sha256') != _frozen_inputs(paths) or receipt.get('source_files_sha256') != _sources():
        raise ContractError('CURRENT_SOURCE_AND_INPUT_BINDING_REQUIRED')
    if receipt.get('operating_source_sha256') != digest(_sources()):
        raise ContractError('OPERATING_SOURCE_DIGEST_INVALID')
    actual = {name:sha((output/name).read_bytes()) for name in ('prepared-order.json','production/reconciliation.json','production/exceptions.csv')}
    if receipt.get('artifacts_sha256') != actual:
        raise ContractError('CHANGED_ARTIFACT')
    check = _audit_outputs(paths, output)
    expect = 'ACCEPTED_IN_SYNTHETIC_SCOPE' if check['accepted'] else 'REJECTED_BY_INDEPENDENT_SERVICE_CHECKER'
    if receipt.get('checker') != check or receipt.get('status') != expect:
        raise ContractError('STORED_VERDICT_DIFFERS_FROM_FRESH_CHECK')
    if receipt.get('current_proof') is not None or receipt.get('authority') != [] or receipt.get('actual_customer_count') != 0 or receipt.get('actual_collected_usd') != 0:
        raise ContractError('INHERITED_PROOF_AUTHORITY_OR_REAL_REVENUE_CLAIM')
    stages = receipt.get('stage_cpu_ns')
    if not isinstance(stages, list) or [row.get('operator') for row in stages] != plan['sequence'] or any(type(row.get('cpu_ns')) is not int or row['cpu_ns'] < 0 for row in stages):
        raise ContractError('INVALID_EXECUTION_METER_SHAPE')
    if type(receipt.get('elapsed_wall_ns')) is not int or receipt['elapsed_wall_ns'] < 0:
        raise ContractError('INVALID_WALL_METER_SHAPE')
    return {'accepted': check['accepted'], 'status': expect, 'scope': 'INDEPENDENT_P0_SYNTHETIC_SERVICE_REDERIVATION', 'receipt_sha256': sha((output/'RECEIPT.json').read_bytes()), 'input_sha256': digest(receipt['source_inputs_sha256']), 'current_proof': None, 'authority': [], 'cash_authority': False}


def main(argv=None):
    p=argparse.ArgumentParser(description='Actual synthetic P0 service composition; NO financial or customer authority')
    p.add_argument('operation',choices=['run','audit'])
    for field in ('spec','plan','contract','invoices','payments','output'):
        p.add_argument('--'+field,required=True)
    a=p.parse_args(argv)
    try:
        spec=_load_json(_regular(a.spec,2_000_000));plan=_load_json(_regular(a.plan,2_000_000))
        paths={x:getattr(a,x) for x in ('contract','invoices','payments')}
        result=execute(spec,plan,paths,a.output) if a.operation=='run' else verify(spec,plan,paths,a.output)
        print(json.dumps({'status':result['status'], 'scope':result['scope'], 'accepted':result.get('accepted',result['status']=='ACCEPTED_IN_SYNTHETIC_SCOPE')}))
        return 0
    except (ContractError,ValueError,OSError,KeyError,TypeError) as e:
        print(type(e).__name__+': '+str(e),file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
