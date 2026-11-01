"""Reconstruct an audited *simulated* commerce revolution without editing accounts.

A native source-linked sequence is not causal uplift, observed external commerce,
recursive invention, a funding authorization, or a physical production result.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = 'agi-alpha/revolution-witness/v1'
NATIVE_RESULT_SCHEMA = 'agi-alpha/connected014-result/v1'
NATIVE_GROWTH_SCOPE = 'SIMULATED_EXACT_NATIVE_RECORDS'


class RevolutionError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise RevolutionError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def bounded_id(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}', value) is not None


def settled_orders(result, native_actions):
    """Do not count a simulated offer, preparation, acceptance, or receivable as collection."""
    released = {(a['args']['id'], a['day']) for a in native_actions
                if a.get('op') == 'event' and a.get('args', {}).get('action') == 'release'}
    out = {}
    seen = set()
    for row in result['orders']:
        require(type(row) is dict and bounded_id(row.get('id')), 'ORDER_ID_REQUIRED')
        require(row['id'] not in seen, 'DUPLICATE_ORDER')
        seen.add(row['id'])
        if row.get('outcome') != 'SETTLED':
            continue
        completed = row.get('service_receipt')
        first, second, third = row.get('qualified_time'), row.get('acceptance_time'), row.get('collection_time')
        require(type(completed) is dict and completed.get('accepted') is True, 'SETTLEMENT_WITHOUT_ACCEPTED_SERVICE')
        require(integer(first) and integer(second) and integer(third) and first <= second <= third,
                'SETTLEMENT_EVENT_ORDER_INVALID')
        require((row['id'], third) in released, 'SETTLEMENT_WITHOUT_NATIVE_RELEASE')
        require(integer(row.get('price'), 1) and integer(row.get('complete_cost')), 'NONINTEGER_ORDER_RESOURCES')
        out[row['id']] = row
    return out


def witness_from_rederived(result, growth, world):
    """Derive a source-linked sequence from *already independently audited* native records.

    Only ``live_witness`` obtains those records via the real frozen-source auditor.
    Calling this function with invented data is not an independent qualification.
    """
    require(bounded_id(world), 'BOUNDED_WORLD_ID_REQUIRED')
    require(type(result) is dict and result.get('schema') == NATIVE_RESULT_SCHEMA
            and result.get('scope') == 'CONDITIONAL_SIMULATION' and result.get('complete') is True,
            'COMPLETE_SIMULATED_NATIVE_RESULT_REQUIRED')
    require(type(growth) is dict and growth.get('scope') == NATIVE_GROWTH_SCOPE,
            'AUDITED_NATIVE_GROWTH_SCOPE_REQUIRED')
    ledger = result['owned_account']['ledger']
    actions = ledger['actions']
    require(type(actions) is list and actions and len(actions) <= 100_000,
            'BOUNDED_NATIVE_ACTION_HISTORY_REQUIRED')
    actions_sha = digest(actions)
    require(ledger.get('actions_sha256') == actions_sha == growth.get('native_actions_sha256'),
            'NATIVE_ACTION_BINDING_MISMATCH')
    require(result.get('summary') == ledger.get('summary'), 'NATIVE_FINAL_FINANCIAL_SUMMARY_MISMATCH')
    summary = ledger['summary']
    require(type(summary) is dict and all(integer(summary.get(k)) for k in ('collections', 'unrestrictedEarned'))
            and type(summary.get('profit')) is int, 'EXACT_NATIVE_FINANCIAL_SUMMARY_REQUIRED')
    require(type(result.get('orders')) is list and type(result.get('investments')) is list,
            'ORDER_AND_INVESTMENT_HISTORY_REQUIRED')
    collected = settled_orders(result, actions)
    attribution = growth['cohorts']['investment_attribution']
    require(type(attribution) is list, 'NATIVE_ATTRIBUTION_REQUIRED')
    indexed = {}
    for row in attribution:
        name = row.get('investment_id')
        require(bounded_id(name) and name not in indexed, 'UNIQUE_NATIVE_INVESTMENT_ATTRIBUTION_REQUIRED')
        indexed[name] = row
    earned = []
    seen = set()
    for investment in result['investments']:
        ident = investment.get('id')
        require(bounded_id(ident) and ident not in seen, 'UNIQUE_NATIVE_INVESTMENT_REQUIRED')
        seen.add(ident)
        require(ident in indexed, 'UNRECONCILED_NATIVE_INVESTMENT')
        attr = indexed[ident]
        require(investment.get('plan_id') == attr.get('plan_id')
                and investment.get('cost') == attr.get('cost_microUSD')
                and investment.get('kind') == attr.get('kind'),
                'INVESTMENT_ATTRIBUTION_DIFFERENCE')
        receipt = investment.get('funding_receipt') or {}
        if receipt.get('funding') != 'EARNED':
            continue
        require(integer(investment.get('purchased_time')) and integer(investment.get('cost'), 1),
                'POSITIVE_INVESTMENT_RESOURCE_REQUIRED')
        require(receipt.get('plan_id') == investment['plan_id']
                and receipt.get('amount') == investment['cost']
                and receipt.get('day') == investment['purchased_time'],
                'EARNED_NATIVE_RECEIPT_TERMS_CHANGED')
        seq = receipt.get('native_event_sequence')
        require(integer(seq) and seq < len(actions), 'EARNED_NATIVE_EVENT_SEQUENCE_INVALID')
        action = actions[seq]
        require(action.get('op') == 'finish' and action.get('seq') == seq
                and action.get('args', {}).get('id') == investment['plan_id']
                and action.get('day') == investment['purchased_time'],
                'EARNED_INVESTMENT_NOT_NATIVE_FINISH')
        require(receipt.get('native_actions_sha256') == digest(actions[:seq + 1]),
                'EARNED_NATIVE_PREFIX_CHANGED')
        prior = sorted((o for o in collected.values() if o['collection_time'] < investment['purchased_time']),
                       key=lambda o: (o['collection_time'], o['id']))
        key = 'capacity_source_plan_id' if investment['kind'] == 'capacity' else 'acquisition_source_plan_id'
        later = sorted((o for o in collected.values()
                        if o.get(key) == investment['plan_id']
                        and o['qualified_time'] >= investment['purchased_time']
                        and o['collection_time'] > investment['purchased_time']),
                       key=lambda o: (o['collection_time'], o['id']))
        require(sorted(attr.get('subsequent_collected_order_ids', [])) == sorted(o['id'] for o in later),
                'ATTRIBUTION_ORDER_LINKS_CHANGED')
        require(attr.get('attributed_collections_microUSD') == sum(o['price'] for o in later),
                'ATTRIBUTION_COLLECTIONS_CHANGED')
        trace = []
        if prior:
            o = prior[-1]
            trace.append({'stage': 'EARLIER_ACCEPTED_COLLECTION', 'order_id': o['id'],
                          'hour': o['collection_time'], 'simulated_microUSD': o['price']})
        trace.append({'stage': 'EARNED_FUNDED_NATIVE_RESOURCE_COMMITMENT',
                      'investment_id': ident, 'hour': investment['purchased_time'],
                      'simulated_microUSD': investment['cost'],
                      'native_prefix_sha256': receipt['native_actions_sha256']})
        if later:
            o = later[0]
            trace.append({'stage': 'SUBSEQUENT_ACCEPTED_AND_COLLECTED_WORK',
                          'order_id': o['id'], 'hour': o['collection_time'],
                          'simulated_microUSD': o['price']})
        earned.append({'investment_id': ident, 'kind': investment['kind'],
                       'prior_settlements': len(prior), 'source_linked_later_settlements': len(later),
                       'native_source_linked_revolution': bool(prior and later), 'trace': trace,
                       'qualified_counterfactual_uplift': None,
                       'attribution_is_nonadditive': True})
    require(len(indexed) == len(seen), 'UNEXPLAINED_NATIVE_ATTRIBUTION')
    closed = sum(x['native_source_linked_revolution'] for x in earned)
    status = ('SOURCE_LINKED_SIMULATED_REVOLUTION_WITNESSED' if closed
              else 'EARNED_INVESTMENT_WITHOUT_COMPLETE_LINK' if earned
              else 'NO_EARNED_FINANCED_INVESTMENT_IN_THIS_WORLD')
    return {
        'schema': SCHEMA, 'scope': 'SOURCE_LINKED_NATIVE_SIMULATION_ONLY',
        'world': world, 'result_sha256': digest(result), 'native_actions_sha256': actions_sha,
        'status': status, 'earned_investments': len(earned), 'closed_source_linked_revolutions': closed,
        'investments': earned, 'settled_orders': len(collected),
        'terminal_modeled_profit_microUSD': summary['profit'],
        'terminal_unrestricted_earned_microUSD': summary['unrestrictedEarned'],
        'actual_customers': 0, 'actual_collections_microUSD': 0, 'actual_profit_microUSD': None,
        'causal_extra_profit': 'NOT_ESTABLISHED_WITHOUT_MATCHED_COUNTERFACTUAL',
        'recursive_invention_improvement': 'NOT_ESTABLISHED_WITHOUT_FRESH_SUCCESSOR_COMPARISON',
        'physical_capacity': 'NOT_ESTABLISHED', 'current_successor_proof': None,
        'authority': [], 'funding_authority': False, 'execution_authority': False,
        'limitations': [
            'Source-linked utilization is not causal incremental profit, and channel/capacity attribution may overlap.',
            'The prior collected order demonstrates chronological history, not tracing particular monetary units to the investment.',
            'All buyers and money in this native world are simulated and complete host/model billing remains unmeasured.',
            'This pure function trusts its caller; only the CLI calls the canonical frozen-source audit first.',
        ],
    }


def _read_file(path, max_bytes):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and not any(x.is_symlink() for x in p.parents),
            'REGULAR_SOURCE_BOUND_FILE_REQUIRED')
    require(p.stat().st_size <= max_bytes, 'BOUNDED_FILE_REQUIRED')
    from flywheel_wheel.readout import strict_json
    return strict_json(p.read_bytes())


def live_witness(enterprise, world, timeout=600):
    """Use only an explicitly trusted, complete native output and its canonical auditor."""
    require(bounded_id(world), 'BOUNDED_WORLD_ID_REQUIRED')
    from flywheel_wheel.readout import _plain_directory, _invoke, snapshot_from_rederived, sha
    root = _plain_directory(enterprise)
    src = _plain_directory(root / 'source')
    require(integer(timeout, 1) and timeout <= 900, 'BOUNDED_AUDIT_TIMEOUT_REQUIRED')
    for name in ('FROZEN.json', 'REPORT.json', 'COMPLETE.json'):
        require((root / name).is_file() and not (root / name).is_symlink(), 'COMPLETE_ENTERPRISE_REQUIRED')
    command = [sys.executable, '-m', 'connected_enterprise']
    audit = _invoke(command + ['audit', '--output', str(root)], src, timeout)
    report = _read_file(root / 'REPORT.json', 4_000_000)
    scoreboard = _invoke(command + ['scoreboard', '--output', str(root)], src, timeout)
    snapshot_from_rederived(audit, report, scoreboard)
    indexes = [row for row in report['worlds_index'] if row['task']['id'] == world]
    require(len(indexes) == 1, 'REGISTERED_AUDITED_WORLD_REQUIRED')
    require(sum(b['business_reference'] == world for b in scoreboard['businesses']) == 1,
            'SCOREBOARD_WORLD_REQUIRED')
    result = _read_file(root / 'worlds' / world / 'RESULT.json', 64_000_000)
    growth = _read_file(root / 'worlds' / world / 'GROWTH.json', 32_000_000)
    require(sha(result) == indexes[0]['result_sha256'], 'REGISTERED_RESULT_CONTENT_CHANGED')
    require(result['source']['sha256'] == audit['source_sha256'], 'AUDITED_SOURCE_IDENTITY_CHANGED')
    require(all(result.get(k) == indexes[0]['task'][k] for k in ('seed', 'case', 'arm')),
            'REGISTERED_NATIVE_WORLD_IDENTITY_CHANGED')
    receipt = witness_from_rederived(result, growth, world)
    receipt['canonical_native_audit_sha256'] = sha(audit)
    receipt['report_sha256'] = sha(report)
    receipt['frozen_sha256'] = report['frozen_sha256']
    receipt['source_sha256'] = report['source_sha256']
    receipt['verification'] = 'CANONICAL_NATIVE_AUDIT_AND_STORED_GROWTH_REDERIVED'
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only source-linked simulated commercial revolution witness')
    parser.add_argument('--enterprise', required=True)
    parser.add_argument('--world', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--audit-timeout', type=int, default=600)
    parser.add_argument('--trust-frozen-source', action='store_true')
    args = parser.parse_args(argv)
    try:
        require(args.trust_frozen_source is True, 'EXPLICIT_FROZEN_SOURCE_TRUST_REQUIRED')
        from flywheel_wheel.preflight import fresh_output, write_new
        target = fresh_output(args.output, args.enterprise)
        receipt = live_witness(args.enterprise, args.world, timeout=args.audit_timeout)
        target.mkdir()
        write_new(target / 'REVOLUTION.json', canonical(receipt) + b'\n')
        print(json.dumps({'status': receipt['status'], 'witnesses': receipt['closed_source_linked_revolutions'],
                          'scope': receipt['scope'], 'funding_authority': False}, sort_keys=True))
        return 0
    except (RevolutionError, FileNotFoundError, OSError, ValueError, TypeError, KeyError, TimeoutError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
