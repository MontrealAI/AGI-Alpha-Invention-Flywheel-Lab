"""Append research to the existing primary account; never initialize a new one."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from connected_enterprise.scale import trailing_profit
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
COSTS = {'research': 300, 'construction': 300, 'verification': 150,
         'failures_corrections': 50, 'inference_tools_host_maintenance': 100}
CONTRACT = 'superalpha-coded-fabric-9ed2a315-primary'


def binding():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in HERE.iterdir() if p.suffix == '.py' or p.name == 'PROTOCOL.md'}


def check_prefix(record, previous):
    for section, key in (('ledger', 'actions'), ('connected_journal', 'entries')):
        prefix = previous[section][key]
        if record[section][key][:len(prefix)] != prefix:
            raise ValueError('ORIGINAL_HISTORY_CHANGED')
    if record['ledger']['config'] != previous['ledger']['config']:
        raise ValueError('ORIGINAL_ACCOUNT_IDENTITY_CHANGED')


def continue_account(private):
    # Refuse absent recovery authority; this function cannot seed a substitute.
    if not (private / 'account.sqlite').is_file():
        raise ValueError('ORIGINAL_ACCOUNT_REQUIRED')
    previous = json.loads((private / 'public/NATIVE_RECORD.json').read_text())
    manifest = json.loads((private / 'manifest.json').read_text())
    source = private / 'source'
    if len(previous['ledger']['actions']) != 5:
        raise ValueError('UNEXPECTED_PREDECESSOR')
    original = audit_journal(previous, root=source, manifest=manifest)
    if not original['accepted']:
        raise ValueError('ORIGINAL_AUDIT_FAILED')
    bound = binding()
    with JournalAccount(source, manifest, private / 'account.sqlite',
                        opening=100000 * 1000000, working=0, contract=CONTRACT) as account:
        check_prefix(account.export(), previous)
        for hour, (category, usd) in enumerate(COSTS.items(), 5):
            if not account.audit()['accepted']:
                raise ValueError('PRE_ACTION_AUDIT_FAILED')
            receipt = account.spend(ident='private-release-' + category,
                kind='registered_research', amount=usd * 1000000, day=hour,
                work={'category': category, 'research_source': bound,
                      'predecessor_record_sha256': digest(previous),
                      'scope': 'AUTHORED_PREPAID_ENVELOPE_NOT_MEASURED_BILLING'},
                expected_net=0, allow_seed=True)
            if receipt is None:
                raise ValueError('NOT_FUNDED')
        record = account.export()
        audit = account.audit()
    check_prefix(record, previous)
    independent = audit_journal(record, root=source, manifest=manifest)
    if not audit['accepted'] or not independent['accepted']:
        raise ValueError('CONTINUATION_AUDIT_FAILED')
    observer = trailing_profit(record['ledger'], operating_end_hour=10, operating_complete=True)
    report = {'scope': 'SAME_PRIMARY_ACCOUNT_CONTINUATION_AUTHORED_RESEARCH_COSTS',
        'contract': CONTRACT, 'opening_usd': 100000,
        'prior_expenses_usd': 2500, 'new_expense_envelopes_usd': COSTS,
        'summary_micro_usd': record['ledger']['summary'],
        'original_prefix_actions_sha256': previous['ledger']['actions_sha256'],
        'original_prefix_journal_entries_sha256': digest(previous['connected_journal']['entries']),
        'original_prefix_length': 5,
        'native_actions_sha256': audit['actions_sha256'],
        'native_source_sha256': record['connected_journal']['source']['sha256'],
        'research_source_sha256': bound,
        'original_manifest_resource_receipt': manifest['resource_receipt'],
        'manifest_sha256': digest(manifest),
        'audit_accepted': audit['accepted'], 'independent_replay_accepted': independent['accepted'],
        'original_history_unchanged': True, 'last_event_hour': 9, 'observer': observer,
        'actual_billing_usd': None, 'complete_actual_cost_profit_usd': None,
        'orders': 0, 'capital_injections_usd': 0, 'milestone_achieved': False,
        'offer_admitted': False, 'funding_decision': 'RETAIN_CASH_STOP_STRICT_OFFER',
        'cost_boundary': 'All $900 research envelopes prepaid. No sale/support/refund/supplier obligation opened. Actual inference/host billing unknown.',
        'tax_capital_financing': 'No positive taxable profit, tax credit, fixed asset, depreciation, debt or financing assumed.'}
    target = private / 'private-release-public'
    target.mkdir(exist_ok=True)
    for name, value in (('ACCOUNT.json', record), ('FINANCE.json', report)):
        path = target / name
        if path.exists():
            if json.loads(path.read_text()) != value:
                raise ValueError('RESTART_CHANGED_CONTINUATION')
        else:
            path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return report


def replay(evidence):
    record = json.loads((evidence / 'ACCOUNT.json').read_text())
    report = json.loads((evidence / 'FINANCE.json').read_text())
    if binding() != report['research_source_sha256']:
        raise ValueError('RESEARCH_SOURCE_CHANGED')
    with tempfile.TemporaryDirectory(prefix='private-release-replay-') as tmp:
        source = Path(tmp)
        for name in sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS)):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        manifest = prepare_services(source, 'fixture_services')
        # Reconstitute the ORIGINAL manifest, including historical timing metadata.
        # This is not a timing claim about this replay; hash must match the native history.
        manifest['resource_receipt'] = report['original_manifest_resource_receipt']
        if digest(manifest) != report['manifest_sha256']:
            raise ValueError('ORIGINAL_MANIFEST_NOT_REPRODUCED')
        audit = audit_journal(record, root=source, manifest=manifest)
    n = report['original_prefix_length']
    assert digest(record['ledger']['actions'][:n]) == report['original_prefix_actions_sha256']
    assert digest(record['connected_journal']['entries'][:n]) == report['original_prefix_journal_entries_sha256']
    assert audit['accepted'] and audit['summary'] == report['summary_micro_usd']
    assert audit['summary']['profit'] == -3400 * 1000000
    assert audit['summary']['available'] == 96600 * 1000000
    observer = trailing_profit(record['ledger'], operating_end_hour=10, operating_complete=True)
    assert observer == report['observer']
    assert not observer['complete_365_day_operating_history']
    assert observer['trailing_365_day_profit_microUSD'] is None
    return {'accepted': True, 'read_only': True, 'new_account_funded': False,
            'cash_usd': 96600, 'cumulative_modeled_profit_usd': -3400,
            'full_365_day_profit_usd': None, 'native_actions_sha256': audit['actions_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--continue-account', type=Path)
    parser.add_argument('--replay', type=Path)
    args = parser.parse_args()
    if bool(args.continue_account) == bool(args.replay):
        parser.error('choose exactly one action')
    result = continue_account(args.continue_account) if args.continue_account else replay(args.replay)
    print(json.dumps(result, sort_keys=True))
