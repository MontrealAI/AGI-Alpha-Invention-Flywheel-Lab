"""Public-only replay of the four fixed interrupted R2 account continuations.

These are additional engineering replays, separate from the original 110/10.
No JournalAccount is opened and no original account authority is read.
"""
from __future__ import annotations
import argparse
from decimal import Decimal
import json
from pathlib import Path
import time

import verify_finance as frozen
import verify_science as base
from commercial.ledger import digest
from connected_enterprise.finance import audit_journal, source_identity
from r2_stream_audit import case_inputs, immutable_save, public_read

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / 'r2_recovery_actual_audit_protocol.json'
AMENDMENT = HERE / 'r2_recovery_actual_audit_execution_002.json'
SOURCE = 'bb74d40f7a84ca155189f908c091db32b27093e203e0d63696f327a9a2492901'
ORIGINAL_DRIVER = 'e067f29f2bea2815165ef914d7c887060f4003e42d0a059373e63f3f0fa73beb'
FAST_DRIVER = '7ad1153471a7091c7173fb936473d810c0a01e9e9ba1295ec4b03812974e937a'
MODEL = '35042231b532a843e3e849e5bd4448ff4967fe209b90c0fde48f63c4e66286f8'
TARGETS = ('interface-copy-30m', 'interface-stable-gap',
           'interface-earned-only-k2', 'interface-ordinary-reuse')
RECEIPTS = {ident: ('RECOVERY_001.json' if ident == 'interface-earned-only-k2'
                    else 'FAST_RECOVERY_002_001.json') for ident in TARGETS}


def require(condition, label):
    if not condition:
        raise ValueError(label)


def prefix_snapshot(record, count):
    actions = record['ledger']['actions']
    require(type(count) is int and 0 <= count <= len(actions), 'VALID_PREFIX_COUNT_REQUIRED')
    summary = actions[count - 1]['after'] if count else (actions[0]['before'] if actions else record['ledger']['summary'])
    checksum = digest(actions[:count])
    return {'summary': summary,
            'state_digest': digest({'config': record['ledger']['config'],
                                    'actions_sha256': checksum, 'summary': summary}),
            'actions_sha256': checksum, 'sequence': count, 'scope': 'SIMULATED',
            'ownership': 'MANDATORY_SINGLE_LOCAL_POSIX_WRITER',
            'filesystem': record['snapshot']['filesystem']}


def check_checkpoint(public_root):
    path = public_root / 'HOST_INTERRUPTION_CHECKPOINT.json'
    checkpoint, checksum = public_read(public_root, path)
    require(checksum == 'a5cf4299b448b5c8f063f205617abd8bbf717868815e00b92a39038838630665',
            'ORIGINAL_39_4_67_CHECKPOINT_REQUIRED')
    require(checkpoint['completed_businesses'] == 39 and checkpoint['interrupted_businesses'] == 4
            and checkpoint['not_started_businesses'] == 67, 'ORIGINAL_INTERRUPTION_DENOMINATORS_REQUIRED')
    commitments = checkpoint['public_prefix_commitments']
    require(len(commitments) == 43, 'ORIGINAL_43_CASE_PREFIX_COMMITMENTS_REQUIRED')
    # Field layout is inspected explicitly; no pathname from outside public is read.
    checked = 0
    for row in commitments:
        ident = row['case_id']
        require(ident in checkpoint['completed_case_ids'] + checkpoint['interrupted_case_ids'],
                'CHECKPOINT_REGISTERED_CASE_REQUIRED')
        for name, expected in row['public_prefix_files'].items():
            require(Path(name).name == name and name in {
                'manifest.json', 'account.public.json', 'RESULT.json', 'aggregation.json', 'RESOURCES.json'},
                'CHECKPOINT_PUBLIC_FILENAME_REQUIRED')
            _, actual = public_read(public_root, public_root / ident / name)
            require(actual == expected, 'ORIGINAL_CHECKPOINT_PUBLIC_BYTES_CHANGED:' + ident + '/' + name)
            checked += 1
    return {'checkpoint_sha256': checksum, 'case_commitments': 43,
            'public_files_rehashed': checked, 'passed': True}


def load_case(public_root, ident):
    loaded = case_inputs(public_root, ident)
    receipt_path = public_root / ident / RECEIPTS[ident]
    if loaded is None or not receipt_path.is_file():
        return None
    parsed, hashes = loaded
    receipt, receipt_sha = public_read(public_root, receipt_path)
    hashes[RECEIPTS[ident]] = receipt_sha
    aggregation, aggregation_sha = public_read(public_root, public_root / ident / 'aggregation.json')
    hashes['aggregation.json'] = aggregation_sha
    return parsed, hashes, receipt, aggregation


def check_case(public_root, ident, parsed, receipt, operating):
    record, manifest, state = (parsed[name] for name in ('account.public.json', 'manifest.json', 'RESULT.json'))
    actual_source = source_identity(base.ROOT, manifest)
    require(actual_source['sha256'] == SOURCE and len(actual_source['files']) == 162
            and record['connected_journal']['source'] == actual_source, 'EXACT_BB74_162_FILE_SOURCE_REQUIRED')
    driver = ORIGINAL_DRIVER if ident == 'interface-earned-only-k2' else FAST_DRIVER
    require(base.digest(base.BASE / ('recovery_run.py' if driver == ORIGINAL_DRIVER else 'recovery_fast.py')) == driver,
            'EXACT_PUBLISHED_RECOVERY_DRIVER_REQUIRED')
    require(receipt['status'] == 'COMPLETE' and receipt['case_id'] == ident
            and receipt['source_sha256'] == SOURCE and receipt['recovery_driver_sha256'] == driver
            and receipt['financial_function_sha256'] == MODEL, 'COMPLETE_EXPECTED_RECOVERY_RECEIPT_REQUIRED')
    require(receipt['prefix_matched'] is True and receipt['original_authority_preserved'] is True
            and receipt['original_financial_source_unchanged'] is True
            and receipt['new_business_account_created'] is False
            and receipt['capital_copied_or_added_microUSD'] == 0
            and receipt['historical_requests_reexecuted_on_original'] == 0,
            'DECLARED_SAME_ACCOUNT_NO_RESEED_CONTRACT_REQUIRED')
    require(base.digest(base.BASE / 'economics.py') == MODEL, 'FROZEN_FINANCIAL_MODEL_REQUIRED')
    # Canonical audit derives all final native states and journal coverage afresh.
    native = audit_journal(record, root=base.ROOT, manifest=manifest)
    require(native['accepted'] is True, 'FULL_NATIVE_REPLAY_REQUIRED')
    arithmetic = frozen.check_case(public_root / ident, state, manifest, record,
                                   operating['operating_end_hour_exclusive'])
    require(arithmetic['passed'] is True, 'UNCHANGED_FULL_FINANCIAL_PREDICATES_REQUIRED')
    tape = record['ledger']; actions = tape['actions']; count = receipt['original_native_action_count']
    require(type(count) is int and 0 < count <= len(actions), 'VALID_NONEMPTY_ORIGINAL_NATIVE_PREFIX_REQUIRED')
    snapshot = prefix_snapshot(record, count)
    require(snapshot['actions_sha256'] == receipt['original_native_actions_sha256']
            == receipt['matched_native_actions_sha256'], 'EXACT_ORIGINAL_ACTION_PREFIX_REQUIRED')
    require(snapshot['summary'] == receipt['original_summary_microUSD']
            and digest(snapshot) == receipt['matched_controller_snapshot_sha256'],
            'ORIGINAL_PREFIX_FINANCIAL_SNAPSHOT_REQUIRED')
    require(type(receipt['original_journal_entry_count']) is int
            and 0 < receipt['original_journal_entry_count'] <= len(record['connected_journal']['entries']),
            'ORIGINAL_JOURNAL_PREFIX_COUNT_REQUIRED')
    if driver == FAST_DRIVER:
        require(receipt['native_actions_replayed_once'] == count
                and receipt['matched_exact_record_sha256'] == receipt['authenticated_original_record_sha256'],
                'FAST_ENTIRE_RECORD_EQUALITY_RECEIPT_REQUIRED')
    require(digest(actions) == tape['actions_sha256'] == receipt['final_native_actions_sha256'],
            'FINAL_NATIVE_ACTION_COMMITMENT_REQUIRED')
    require(base.digest(public_root / ident / 'RESULT.json') == receipt['result_sha256'],
            'RAW_FINAL_RESULT_COMMITMENT_REQUIRED')
    scenario = next(s for s in operating['registered_scenarios'] if ident == 'interface-' + s['id'])
    opening = int(Decimal(str(scenario['capital_usd'])) * 1_000_000)
    require(state['scenario'] == scenario and state['route'] == 'interface' and state['case_id'] == ident,
            'ORIGINAL_REGISTERED_SCENARIO_REQUIRED')
    config = tape['config']; summary = tape['summary']
    require(config['opening'] == opening == state['opening_microUSD'] == record['connected_journal']['opening']
            and config['working'] == 0 and config['contract'] == 'public-portfolio-' + ident,
            'UNCHANGED_SINGLE_ACCOUNT_OPENING_AND_LINEAGE_REQUIRED')
    require(state['native_source_sha256'] == SOURCE and state['final_native_summary_microUSD'] == summary,
            'FINAL_STATE_SOURCE_AND_SUMMARY_REQUIRED')
    require(summary['cash'] == opening + summary['collections'] + summary['recoveryIncome'] - summary['expensePaid']
            and summary['profit'] == summary['revenue'] + summary['recoveryIncome'] - summary['expenses'],
            'NO_ADDITIONAL_COMPANY_CAPITAL_CASH_PROFIT_IDENTITY_REQUIRED')
    expected_buyers = {'interface-p' + str(i).zfill(2) for i in range(operating['finite_market']['prospects_per_route'])}
    wallet_budget = int(Decimal(str(operating['profiles_usd']['interface']['buyer_base_value'])) * 3_000_000)
    wallets = [a for a in actions if a['op'] == 'wallet']
    buyers = [a['args']['buyer'] for a in wallets]
    require(len(buyers) == len(set(buyers)) and set(buyers) <= expected_buyers
            and all(a['args']['amount'] == wallet_budget for a in wallets),
            'ORIGINAL_FINITE_BUYER_WALLETS_NO_TOPUPS_REQUIRED')
    require(all(a['args']['buyer'] in expected_buyers for a in actions if a['op'] == 'offer'),
            'NO_UNREGISTERED_BUYER_FUNDING_REQUIRED')
    return {'passed': True, 'native_full_replay': native, 'financial_predicates': arithmetic,
            'original_native_action_count': count, 'final_native_action_count': len(actions),
            'new_suffix_action_count': len(actions) - count,
            'original_prefix_sha256_recomputed': snapshot['actions_sha256'],
            'original_snapshot_sha256_recomputed': digest(snapshot),
            'opening_microUSD': opening, 'buyer_wallets_once': len(wallets),
            'recovery_driver_sha256': driver,
            'whole_original_record_preimage_independently_reconstructed': False,
            'opaque_record_commitment_limit': 'The entire pre-recovery exported-record preimage is not separately exposed. This audit independently reconstructs the action prefix and financial snapshot; the original receipt whole-record equality and private custody remain qualified execution claims, not independently recovered opaque digests.'}


def run(public_root, cache_root):
    public_root, cache_root = Path(public_root).resolve(), Path(cache_root).resolve()
    require(tuple(frozen.read(PROTOCOL)['targets']) == TARGETS, 'ORIGINAL_FIXED_FOUR_TARGETS_REQUIRED')
    amendment = frozen.read(AMENDMENT)
    require(amendment['original_protocol_sha256'] == base.digest(PROTOCOL)
            and amendment['fast_recovery_driver_sha256'] == FAST_DRIVER, 'EXPLICIT_EXECUTION_ADAPTER_AMENDMENT_REQUIRED')
    operating = frozen.read(base.BASE / 'ECONOMICS_PROTOCOL.json')
    require(frozen.read(public_root / 'protocol.json') == operating, 'UNCHANGED_ORIGINAL_ECONOMIC_PROTOCOL_REQUIRED')
    checkpoint = check_checkpoint(public_root)
    rows = []; missing = []
    for ident in TARGETS:
        loaded = load_case(public_root, ident)
        if loaded is None:
            missing.append(ident); continue
        parsed, hashes, receipt, aggregation = loaded
        metadata = {'case_id': ident, 'input_hashes': hashes, 'auditor_sha256': base.digest(__file__),
                    'protocol_sha256': base.digest(PROTOCOL), 'execution_amendment_sha256': base.digest(AMENDMENT),
                    'financial_source_sha256': SOURCE, 'frozen_primary_checker_sha256': base.digest(frozen.__file__)}
        path = cache_root / (ident + '.json')
        if path.exists():
            row = frozen.read(path)
            require(row['metadata'] == metadata, 'IMMUTABLE_RECOVERY_AUDIT_INPUT_CHANGED:' + ident)
        else:
            started = time.time()
            try:
                audit = check_case(public_root, ident, parsed, receipt, operating)
            except Exception as exc:
                audit = {'passed': False, 'native_full_replay': False,
                         'error_type': type(exc).__name__, 'error': str(exc)[:2000]}
            reread = load_case(public_root, ident)
            require(reread is not None and reread[1] == hashes, 'RECOVERY_PUBLIC_INPUT_CHANGED_DURING_AUDIT:' + ident)
            row = {'schema': 'public-portfolio/independent-actual-recovery-replay/v1',
                   'metadata': metadata, 'audit': audit, 'wall_seconds': time.time() - started,
                   'original_account_or_authority_opened': False, 'operating_accounts_mutated': False}
            immutable_save(path, row)
        rows.append({'case_id': ident, 'passed': row['audit']['passed'], 'receipt_sha256': base.digest(path),
                     'receipt': row})
        print('ACTUAL_RECOVERY_AUDIT ' + ident + ' passed=' + str(row['audit']['passed']), flush=True)
    return {'schema': 'public-portfolio/four-actual-recovery-audit/v1',
            'status': 'COMPLETE_FOUR_ENGINEERING_REPLAYS' if len(rows) == 4 and all(r['passed'] for r in rows)
                      else 'PARTIAL_OR_FAILED_ENGINEERING_AUDIT',
            'auditor_sha256': base.digest(__file__), 'protocol_sha256': base.digest(PROTOCOL),
            'execution_amendment_sha256': base.digest(AMENDMENT), 'financial_source_sha256': SOURCE,
            'fixed_target_count': 4, 'completed_target_replays': len(rows),
            'all_checked_predicates_passed': all(r['passed'] for r in rows), 'missing_targets': missing,
            'original_checkpoint_preservation': checkpoint, 'cases': rows,
            'original_110_10_denominators_unchanged': True,
            'scope': 'Four separate post-interruption engineering replays of known partial worlds. Public native action continuity and no duplicate seed/wallet evidence; no private key access, full opaque preimage attestation, actual commerce, new industry or profit milestone.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public-root', required=True); parser.add_argument('--cache-root', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    require(not Path(args.output).exists(), 'REFUSE_PRIOR_RECOVERY_AUDIT_OVERWRITE')
    started = time.time(); result = run(args.public_root, args.cache_root)
    result['wall_seconds'] = time.time() - started
    immutable_save(args.output, result)
    print(json.dumps({k: result[k] for k in ('status', 'completed_target_replays', 'all_checked_predicates_passed')}))
    raise SystemExit(0 if result['all_checked_predicates_passed'] else 1)
