"""Recheck only the four retained actual-recovery exports, without full campaign inputs.

The original 199-file interruption checkpoint is represented by its prior audit
receipt, not claimed rehashed by this selected-input reproduction command.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

import r2_recovery_actual_audit as original
import verify_finance as frozen
import verify_science as base
from r2_stream_audit import immutable_save


def run(public_root, previous_report):
    public_root, previous_report = Path(public_root).resolve(), Path(previous_report).resolve()
    original.require(base.digest(original.__file__) == '7485c2dfeefb5ec655e3b1b813b96844457a8a9eb9e5d416dc9b67333606a409',
                     'UNCHANGED_ORIGINAL_RECOVERY_AUDITOR_REQUIRED')
    prior = frozen.read(previous_report)
    original.require(prior['status'] == 'COMPLETE_FOUR_ENGINEERING_REPLAYS'
                     and prior['fixed_target_count'] == prior['completed_target_replays'] == 4
                     and prior['all_checked_predicates_passed'], 'ORIGINAL_SUCCESSFUL_FOUR_REPLAY_RECEIPT_REQUIRED')
    prior_cases = {row['case_id']: row for row in prior['cases']}
    original.require(set(prior_cases) == set(original.TARGETS), 'ORIGINAL_FIXED_FOUR_RECOVERY_TARGETS_REQUIRED')
    operating = frozen.read(base.BASE / 'ECONOMICS_PROTOCOL.json')
    original.require(frozen.read(public_root / 'protocol.json') == operating, 'ORIGINAL_ECONOMIC_PROTOCOL_REQUIRED')
    rows = []
    for ident in original.TARGETS:
        row = {'case_id': ident, 'passed': False}
        try:
            loaded = original.load_case(public_root, ident)
            original.require(loaded is not None, 'RETAINED_RECOVERY_PUBLIC_CASE_REQUIRED')
            parsed, hashes, receipt, _ = loaded
            metadata = prior_cases[ident]['receipt']['metadata']
            original.require(metadata['input_hashes'] == hashes and metadata['auditor_sha256'] == base.digest(original.__file__),
                             'EXACT_PREVIOUSLY_AUDITED_PUBLIC_RECOVERY_BYTES_REQUIRED')
            checked = original.check_case(public_root, ident, parsed, receipt, operating)
            original.require(original.load_case(public_root, ident)[1] == hashes, 'RETAINED_RECOVERY_INPUT_CHANGED')
            row.update({'passed': checked['passed'], 'input_hashes': hashes,
                        'native_replay_accepted': checked['native_full_replay']['accepted'],
                        'original_native_action_count': checked['original_native_action_count'],
                        'final_native_action_count': checked['final_native_action_count'],
                        'previous_independent_receipt_sha256': prior_cases[ident]['receipt_sha256']})
        except Exception as exc:
            row.update({'error_type': type(exc).__name__, 'error': str(exc)[:2000]})
        rows.append(row)
        print('RETAINED_RECOVERY_RECHECK ' + ident + ' passed=' + str(row['passed']), flush=True)
    return {'schema': 'public-portfolio/retained-four-recovery-native-recheck/v1',
            'checker_sha256': base.digest(__file__), 'original_checker_sha256': base.digest(original.__file__),
            'original_four_replay_report_sha256': base.digest(previous_report),
            'retained_recovery_cases_expected': 4, 'cases_rechecked': len(rows),
            'passed': len(rows) == 4 and all(row['passed'] for row in rows), 'cases': rows,
            'original_199_checkpoint_public_files_rehashed': False,
            'original_110_financial_checks_reperformed': False,
            'original_10_native_subset_reperformed': False,
            'scope': 'Rechecks exactly four retained key-free actual-recovery exports and prefix/no-reseed predicates through unchanged original auditor functions. Does not reperform omitted campaign inputs or original199-file checkpoint; all original110/10 denominators remain separate.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--public-root', required=True)
    p.add_argument('--original-four-report', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); original.require(not Path(args.output).exists(), 'REFUSE_EXISTING_RECHECK_OVERWRITE')
    started = time.time(); result = run(args.public_root, args.original_four_report)
    result['wall_seconds'] = time.time() - started; immutable_save(args.output, result)
    print(json.dumps({'passed': result['passed'], 'rechecked': result['cases_rechecked']}))
    raise SystemExit(0 if result['passed'] else 1)
