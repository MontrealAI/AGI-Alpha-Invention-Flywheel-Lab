"""Consume only canonical completed native audit + recorded scoreboard as bounded evidence.

This module deliberately does not implement finance, operate an account or certify invention.
The canonical frozen-source audit rederives those claims. The scoreboard is a display.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SCHEMA = 'agi-alpha/flywheel-wheel-readout/v1'
SCOPE = 'RECORDED_CONDITIONAL_SIMULATION_AFTER_CANONICAL_AUDIT'
RINGS = {
    'commerce': ('Offer', 'Deliver', 'Collect', 'Reinvest'),
    'invention': ('Discovery', 'Synthesis', 'Reflection', 'Inheritance'),
    'production': ('Bottleneck', 'Instrument', 'Measurement', 'Replication'),
}
DECLARED_NATIVE_AUDIT = 'agi-alpha/connected014-package-audit/v1'
DECLARED_NATIVE_SCOPE = 'NATIVE_FINANCE_AND_OPERATING_SEMANTICS_WITH_ARTIFACT_REEXECUTION_AND_REPORT_REDERIVATION'

class EvidenceError(ValueError):
    pass

def _must(test, reason):
    if not test:
        raise EvidenceError(reason)

def strict_json(data):
    def pairs(rows):
        d = {}
        for k, v in rows:
            if k in d:
                raise EvidenceError('DUPLICATE_EVIDENCE_KEY')
            d[k] = v
        return d
    def invalid(_):
        raise EvidenceError('NONFINITE_EVIDENCE_NUMBER')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)

def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def empty_snapshot():
    return {
        'schema': SCHEMA, 'scope': 'ARCHITECTURE_ONLY_NO_ENTERPRISE_INPUT',
        'verification': 'NONE', 'source_sha256': None, 'frozen_sha256': None,
        'worlds': [], 'commercial_claim': 'NOT_EVIDENCED',
        'invention_claim': 'NOT_EVIDENCED', 'productive_claim': 'NOT_EVIDENCED',
        'real_customers': None, 'real_collections_microUSD': None,
        'actual_host_billing_microUSD': None,
        'rings': {key: {stage: 'NOT_EVIDENCED' for stage in stages} for key, stages in RINGS.items()},
        'funding_authority': False,
        'limits': ['Illustrative operating architecture, not a live enterprise dashboard.'],
    }

def snapshot_from_rederived(audit, report, scoreboard):
    """Bind receipt, report and scoreboard; caller must have run canonical independent audit.

    No user-controlled status flags are used to certify true invention, customers or physics.
    No balances from independent simulated businesses are aggregated into spendable cash.
    """
    _must(type(audit) is dict and audit.get('schema') == DECLARED_NATIVE_AUDIT, 'NATIVE_AUDIT_SCHEMA_REQUIRED')
    _must(audit.get('accepted') is True and audit.get('scope') == DECLARED_NATIVE_SCOPE, 'CANONICAL_ACCEPTED_NATIVE_AUDIT_REQUIRED')
    _must(type(report) is dict and report.get('schema') == 'agi-alpha/connected014-report/v1' and report.get('scope') == 'CONDITIONAL_SIMULATION', 'EXACT_SIMULATED_REPORT_REQUIRED')
    _must(type(scoreboard) is dict and scoreboard.get('schema') == 'agi-alpha/connected-scoreboard/v1' and scoreboard.get('scope') == 'RECORDED_CONDITIONAL_SIMULATION', 'EXACT_SCOREBOARD_SCOPE_REQUIRED')
    source = audit.get('source_sha256')
    _must(type(source) is str and len(source) == 64 and all(c in '0123456789abcdef' for c in source), 'SOURCE_DIGEST_REQUIRED')
    _must(source == report.get('source_sha256') == scoreboard.get('source_sha256'), 'MISMATCHED_SOURCE_IDENTITY')
    _must(report.get('frozen_sha256') == scoreboard.get('frozen_sha256'), 'MISMATCHED_FREEZE_IDENTITY')
    _must(type(report.get('frozen_sha256')) is str and len(report['frozen_sha256']) == 64, 'FROZEN_DIGEST_REQUIRED')
    _must(report.get('all_independent_audits_passed') is True, 'REPORT_AUDITS_NOT_PASSED')
    worlds = audit.get('worlds')
    _must(type(worlds) is int and worlds > 0 and worlds == report.get('worlds') == scoreboard.get('world_count'), 'WORLD_MEMBERSHIP_MISMATCH')
    businesses = scoreboard.get('businesses')
    _must(type(businesses) is list and len(businesses) == worlds, 'WORLD_BUSINESS_COUNT_MISMATCH')
    _must(type(scoreboard.get('report_sha256')) is str and len(scoreboard['report_sha256']) == 64, 'RECORDED_REPORT_DIGEST_REQUIRED')
    _must(scoreboard['report_sha256'] == sha(report), 'REPORT_CONTENT_BINDING_MISMATCH')
    _must(report.get('actual_commerce') == {'customers': 0, 'collections': 0, 'profit': None}, 'NON_SIMULATED_CLAIM_WITHOUT_EXTERNAL_EVIDENCE')
    claims = report.get('outcomes')
    _must(type(claims) is dict and claims.get('operating_implementation') == 'EXECUTED_WITH_INDEPENDENT_FINANCIAL_AND_OPERATING_SEMANTIC_AUDIT', 'OPERATING_CLAIM_MISMATCH')
    known_commercial = {'CONDITIONAL_SUCCESS', 'NOT_ESTABLISHED_IN_REGISTERED_REGION'}
    known_growth = {'CONDITIONAL_INCREASE_IN_PROFITABLE_DELIVERY', 'CAPABILITY_USE_WITHOUT_QUALIFIED_MATCHED_GROWTH', 'NOT_ESTABLISHED'}
    _must(claims.get('commercial_result') in known_commercial and claims.get('growth_result') in known_growth, 'UNKNOWN_SIMULATED_CLAIM_TYPE')
    _must(claims.get('billion_native_scale') == 'NOT_ESTABLISHED', 'SCALE_CLAIM_NOT_SUPPORTED')
    _must(scoreboard.get('target_status') == 'NOT_ESTABLISHED_BY_THIS_SCOREBOARD', 'UNSUPPORTED_TARGET_STATUS')
    unique = set()
    found = []
    for business in businesses:
        _must(type(business) is dict and type(business.get('business_reference')) is str, 'BUSINESS_REFERENCE_REQUIRED')
        _must(business['business_reference'] not in unique, 'DUPLICATED_BUSINESS')
        unique.add(business['business_reference'])
        _must(business.get('complete') is True and business.get('scope') == 'CONDITIONAL_SIMULATION', 'INCOMPLETE_BUSINESS_OR_SCOPE')
        _must(type(business.get('verification')) is dict and business['verification'].get('stored_audit_accepted') is True, 'STORED_BUSINESS_AUDIT_MISSING')
        actual = business.get('actual_external_commerce')
        _must(type(actual) is dict and actual.get('customers') == 0 and actual.get('collections_microUSD') == 0 and actual.get('profit_microUSD') is None, 'UNSUPPORTED_REAL_COMMERCE')
        sums = business.get('financial_state_microUSD')
        _must(type(sums) is dict and type(sums.get('profit')) is int and type(sums.get('cash')) is int, 'INTEGER_NATIVE_FINANCIAL_SUMMARY_REQUIRED')
        _must(business.get('trailing_twelve_month_profit_microUSD') is None, 'SHORT_HORIZON_ANNUALIZATION_REFUSED')
        found.append({'id': business['business_reference'], 'modeled_profit_microUSD': sums['profit'], 'modeled_cash_microUSD': sums['cash'], 'recorded_counts': business.get('recorded_counts', {})})
    ring = {key: {stage: 'NOT_ESTABLISHED_BY_NATIVE_COMMERCIAL_EVIDENCE' for stage in stages} for key, stages in RINGS.items()}
    def has_action(name):
        return any(type(w['recorded_counts']) is dict and type(w['recorded_counts'].get(name)) is int
                   and w['recorded_counts'][name] > 0 for w in found)
    ring['commerce']['Offer'] = ('AUDITED_CONDITIONAL_SIMULATION' if has_action('offers') else 'NO_VERIFIED_OFFERS_IN_WORLDS')
    ring['commerce']['Deliver'] = ('AUDITED_CONDITIONAL_SIMULATION' if has_action('accepted_orders') else 'NO_VERIFIED_ACCEPTED_DELIVERIES')
    ring['commerce']['Collect'] = ('AUDITED_CONDITIONAL_SIMULATION' if has_action('settled_orders') else 'NO_VERIFIED_SETTLED_ORDERS')
    ring['commerce']['Reinvest'] = ('AUDITED_CONDITIONAL_SIMULATION' if claims['growth_result'] == 'CONDITIONAL_INCREASE_IN_PROFITABLE_DELIVERY' and has_action('settled_orders') else 'NOT_ESTABLISHED_IN_THIS_COHORT')
    return {
        'schema': SCHEMA, 'scope': SCOPE, 'verification': 'CANONICAL_NATIVE_AUDIT_REDERIVED_IN_FROZEN_SOURCE',
        'source_sha256': source, 'frozen_sha256': report['frozen_sha256'],
        'worlds': found, 'commercial_claim': claims['commercial_result'],
        'invention_claim': 'NOT_ESTABLISHED_BY_NATIVE_COMMERCIAL_AUDIT',
        'productive_claim': 'NOT_ESTABLISHED_BY_NATIVE_COMMERCIAL_AUDIT',
        'real_customers': 0, 'real_collections_microUSD': 0,
        'actual_host_billing_microUSD': None, 'rings': ring,
        'funding_authority': False,
        'limits': [
            'Each simulated business retains its own account and cannot pool cash with another world.',
            'A read-only display neither opens nor authorizes a native financial account.',
            'Invention, discovery-policy improvement and physical production require separate qualified evidence.',
            'Actual host, frontier-model and complete engineering billing remain unavailable.',
            'Current authority and fresh mission proof do not transfer through this dashboard.',
        ],
    }

def _plain_directory(path):
    p = Path(path).expanduser().absolute()
    _must(p.is_dir() and not p.is_symlink(), 'EXISTING_NORMAL_ENTERPRISE_DIRECTORY_REQUIRED')
    _must(not any(part.is_symlink() for part in p.parents), 'PARENT_SYMLINK_REFUSED')
    return p

def _invoke(command, cwd, timeout):
    v = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    if v.returncode != 0:
        raise EvidenceError('CANONICAL_COMMAND_REJECTED:' + command[3])
    _must(len(v.stdout.encode('utf8')) <= 4_000_000, 'EXCESSIVE_CANONICAL_OUTPUT')
    return strict_json(v.stdout)

def live_readout(enterprise, *, timeout=600):
    """Invoke the canonical independent auditor and read-only scoreboard from frozen source.

    Requires an explicitly TRUSTED enterprise path: invoking frozen code is executable work.
    Does not schedule, start, resume or fund a business. The canonical auditor may write
    PACKAGE_AUDIT.json but does not mutate financial accounts.
    """
    root = _plain_directory(enterprise)
    src = _plain_directory(root / 'source')
    for name in ('FROZEN.json', 'REPORT.json', 'COMPLETE.json'):
        _must((root / name).is_file() and not (root / name).is_symlink(), 'COMPLETE_ENTERPRISE_INPUT_REQUIRED:' + name)
    _must((src / 'connected_enterprise' / 'runner.py').is_file(), 'FROZEN_RUNNER_REQUIRED')
    _must(type(timeout) is int and 1 <= timeout <= 900, 'FINITE_AUDIT_TIMEOUT_REQUIRED')
    runner = [sys.executable, '-m', 'connected_enterprise']
    audit = _invoke(runner + ['audit', '--output', str(root)], src, timeout)
    report = strict_json((root / 'REPORT.json').read_bytes())
    board = _invoke(runner + ['scoreboard', '--output', str(root)], src, timeout)
    return snapshot_from_rederived(audit, report, board)
