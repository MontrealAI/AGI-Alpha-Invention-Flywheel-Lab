import argparse
import json
from pathlib import Path

from commercial.ledger import digest, strict_json
from connected_enterprise.finance import audit_journal
from .evaluate import confirmation_specs, evaluate
from .study import ARMS, analyze, construct_program, save, verify_freeze


def _read(path):
    return strict_json(Path(path).read_bytes())


def replay(output, expected_freeze):
    verify_freeze(expected_freeze)
    output = Path(output).resolve()
    run_input = _read(output/'INPUT.json')
    if run_input['freeze_sha256'] != expected_freeze:
        raise ValueError('RECORDED_RUN_FREEZE_MISMATCH')
    recorded_science = _read(output/'SCIENCE.json')
    expected_names = {f'{index:02d}-{arm}.json' for index in range(48) for arm in ARMS}
    actual_names = {path.name for path in (output/'science').glob('*.json')}
    if actual_names != expected_names:
        raise ValueError('EXACT_SCIENCE_FILES_REQUIRED')
    rows = []
    for index, spec in enumerate(confirmation_specs()):
        for arm in ARMS:
            row = _read(output/'science'/f'{index:02d}-{arm}.json')
            if row['arm'] != arm or row['stratum'] != spec['stratum']:
                raise ValueError('RECORDED_ARM_OR_FAMILY_MISMATCH')
            independent = construct_program(spec, arm)
            for key in ('task', 'program', 'construction', 'probe_cost_microUSD', 'probe_transcript', 'financial_declines'):
                if row[key] != independent[key]:
                    raise ValueError('CONSTRUCTION_REPLAY_MISMATCH:' + key)
            if evaluate(spec, row['program']) != row['evaluation']:
                raise ValueError('OUTCOME_REPLAY_MISMATCH')
            rows.append(row)
    analysis = analyze(rows)
    for key, value in analysis.items():
        if recorded_science.get(key) != value:
            raise ValueError('SCIENCE_AGGREGATION_MISMATCH:' + key)
    if recorded_science['freeze_sha256'] != expected_freeze:
        raise ValueError('SCIENCE_FREEZE_MISMATCH')
    native = []
    economic_path = output/'ECONOMICS.json'
    if type(run_input.get('economics')) is not bool:
        raise ValueError('EXPLICIT_ECONOMIC_RUN_SCOPE_REQUIRED')
    if run_input['economics'] and not economic_path.is_file():
        raise ValueError('REGISTERED_ECONOMICS_MISSING')
    if not run_input['economics'] and economic_path.exists():
        raise ValueError('UNREGISTERED_ECONOMIC_OUTPUT')
    if economic_path.exists():
        from .economics import protocol
        economics = _read(economic_path)
        if economics['freeze_sha256'] != expected_freeze or not economics['independent_accounts_not_pooled']:
            raise ValueError('ECONOMIC_IDENTITY_MISMATCH')
        if economics.get('development') is not False:
            raise ValueError('FULL_REGISTERED_ECONOMIC_COMPARISON_REQUIRED')
        cfg = protocol()
        expected_accounts = {
            f'{arm.replace("_", "-")}-{region}-{capital}': (arm, region, capital)
            for arm in (*ARMS, 'no_deploy')
            for region in cfg['regions']
            for capital in cfg['capital_usd']}
        identities = [row['identity'] for row in economics['accounts']]
        if len(expected_accounts) != 18 or len(identities) != 18 or set(identities) != set(expected_accounts):
            raise ValueError('EXACT_EIGHTEEN_NATIVE_ACCOUNTS_REQUIRED')
        source = output/'native'/'source'
        for declared in economics['accounts']:
            identity = declared['identity']
            if (declared['arm'], declared['region'], declared['capital_USD']) != expected_accounts[identity]:
                raise ValueError('NATIVE_ARM_REGION_OR_CAPITAL_CHANGED')
            if not identity.replace('-', '').isalnum():
                raise ValueError('BOUNDED_NATIVE_IDENTITY_REQUIRED')
            folder = output/'native'/identity
            record, manifest = _read(folder/'PUBLIC_ACCOUNT.json'), _read(folder/'MANIFEST.json')
            checked = audit_journal(record, root=source, manifest=manifest)
            if not checked['accepted']:
                raise ValueError('INDEPENDENT_NATIVE_AUDIT_REJECTED')
            if declared['native_export_sha256'] != digest(record):
                raise ValueError('NATIVE_EXPORT_BINDING_MISMATCH')
            summary = record['ledger']['summary']
            if summary != declared['financial_microUSD']:
                raise ValueError('NATIVE_SUMMARY_MISMATCH')
            if summary['profit'] != summary['revenue'] + summary['recoveryIncome'] - summary['expenses']:
                raise ValueError('RECOGNIZED_PROFIT_IDENTITY_FAILED')
            if not declared['complete'] or not declared['native_audit_accepted']:
                raise ValueError('INCOMPLETE_NATIVE_ACCOUNT')
            native.append({'identity': identity, 'accepted': True,
                           'public_export_sha256': digest(record), 'action_count': len(record['ledger']['actions'])})
    execution = _read(output/'EXECUTION.json')
    if execution['freeze_sha256'] != expected_freeze or execution['science_sha256'] != digest(recorded_science):
        raise ValueError('EXECUTION_RECEIPT_BINDING_MISMATCH')
    if economic_path.exists() and execution['economics_sha256'] != digest(_read(economic_path)):
        raise ValueError('ECONOMIC_EXECUTION_BINDING_MISMATCH')
    return {'schema': 'outlearning-independent-replay/v1', 'accepted': True,
            'freeze_sha256': expected_freeze, 'scientific_worlds': 48, 'scientific_rows': len(rows),
            'submitted_programs_replayed': len(rows), 'construction_and_probe_transcripts_replayed': len(rows),
            'scientific_summary_sha256': digest(recorded_science), 'native_accounts': native,
            'account_authority_opened': False, 'private_keys_required': False,
            'evidence_level': 'REPRODUCTION_OF_FROZEN_GENERATED_CONFIRMATION',
            'independence': 'Separate evaluator agent and checking path on shared host; not external experimentation.',
            'limits': 'Same authored simulator, frozen constructors and finite schedules. Replay does not establish real provider semantics, customer demand or general outlearning.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-freeze', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('NEW_REPLAY_RECEIPT_REQUIRED')
    result = replay(args.output, args.expected_freeze)
    save(args.receipt, result)
    print(json.dumps({key: result[key] for key in ('accepted', 'scientific_worlds', 'scientific_rows', 'freeze_sha256')}, sort_keys=True))


if __name__ == '__main__':
    main()
