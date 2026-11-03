"""Posthoc public replay of the two later complementarity continuations.

Reuses independently authored frozen financial and native checkers. The
integration owner runs this extra engineering check after all110 outcomes;
it changes neither the original110/10 nor the earlier fixed-four audit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time

import verify_finance as frozen
import verify_science as base
from commercial.ledger import digest
from connected_enterprise.finance import audit_journal, source_identity
from r2_recovery_actual_audit import prefix_snapshot, require, FAST_DRIVER, SOURCE, MODEL
from r2_stream_audit import immutable_save, public_read

TARGETS = ('complementarity-ordinary-reuse', 'complementarity-no-inheritance')


def run(public_root):
    public_root = Path(public_root).resolve()
    protocol = frozen.read(base.BASE / 'ECONOMICS_PROTOCOL.json')
    rows = []
    for ident in TARGETS:
        folder = public_root / ident
        values, hashes = {}, {}
        for name in ('manifest.json', 'account.public.json', 'RESULT.json', 'FAST_RECOVERY_002_002.json'):
            value, checksum = public_read(public_root, folder / name)
            values[name], hashes[name] = value, checksum
        manifest, record, state, receipt = (values[name] for name in
            ('manifest.json', 'account.public.json', 'RESULT.json', 'FAST_RECOVERY_002_002.json'))
        actual = source_identity(base.ROOT, manifest)
        require(actual['sha256'] == SOURCE and record['connected_journal']['source'] == actual,
                'UNCHANGED_FINANCIAL_SOURCE_REQUIRED')
        require(receipt['status'] == 'COMPLETE' and receipt['case_id'] == ident
                and receipt['recovery_driver_sha256'] == FAST_DRIVER
                and receipt['financial_function_sha256'] == MODEL
                and receipt['prefix_matched'] is True
                and receipt['new_business_account_created'] is False
                and receipt['capital_copied_or_added_microUSD'] == 0
                and receipt['historical_requests_reexecuted_on_original'] == 0,
                'SAME_ACCOUNT_RECOVERY_RECEIPT_REQUIRED')
        tape = record['ledger']; actions = tape['actions']
        count = receipt['original_native_action_count']
        snapshot = prefix_snapshot(record, count)
        require(digest(actions[:count]) == receipt['original_native_actions_sha256']
                == receipt['matched_native_actions_sha256']
                and snapshot['summary'] == receipt['original_summary_microUSD']
                and digest(snapshot) == receipt['matched_controller_snapshot_sha256'],
                'EXACT_NATIVE_PREFIX_AND_SNAPSHOT_REQUIRED')
        require(receipt['native_actions_replayed_once'] == count
                and receipt['matched_exact_record_sha256'] == receipt['authenticated_original_record_sha256']
                and receipt['final_native_actions_sha256'] == digest(actions) == tape['actions_sha256']
                and receipt['result_sha256'] == hashes['RESULT.json'],
                'RECOVERY_COMMITMENTS_REQUIRED')
        scenario = next(s for s in protocol['registered_scenarios'] if ident == 'complementarity-' + s['id'])
        opening = int(scenario['capital_usd']) * 1_000_000
        require(state['scenario'] == scenario and state['route'] == 'complementarity'
                and tape['config']['opening'] == state['opening_microUSD'] == opening
                and tape['config']['contract'] == 'public-portfolio-' + ident
                and state['final_native_summary_microUSD'] == tape['summary'],
                'ORIGINAL_SCENARIO_CAPITAL_AND_LINEAGE_REQUIRED')
        native = audit_journal(record, root=base.ROOT, manifest=manifest)
        arithmetic = frozen.check_case(folder, state, manifest, record, protocol['operating_end_hour_exclusive'])
        require(native['accepted'] and arithmetic['passed'], 'FULL_NATIVE_AND_FINANCIAL_REPLAY_REQUIRED')
        rows.append({'case_id': ident, 'passed': True, 'input_sha256': hashes,
            'original_native_actions': count, 'final_native_actions': len(actions),
            'native_replay': native, 'financial_checks': arithmetic,
            'whole_original_record_preimage_independently_reconstructed': False})
    return {'schema': 'public-portfolio/additional-two-recovery-replay/v1',
        'status': 'COMPLETE_TWO_ENGINEERING_REPLAYS', 'passed': True,
        'checker_sha256': base.digest(__file__), 'frozen_primary_checker_sha256': base.digest(frozen.__file__),
        'financial_source_sha256': SOURCE, 'targets': list(TARGETS), 'cases': rows,
        'registration': 'Posthoc additional integration check after all110 outcomes; no fresh blinding or change to financial predicates.',
        'execution_independence': 'Integration owner runs independently authored frozen arithmetic/native implementations; this wrapper is not an additional independent scientific constructor.',
        'original_110_10_and_fixed_four_unchanged': True,
        'scope': 'Public native prefix and snapshot continuity only. No private owner/key access, whole opaque original-record preimage attestation, market validation or profit attainment.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--public-root', required=True)
    parser.add_argument('--output', required=True); args = parser.parse_args()
    require(not Path(args.output).exists(), 'NO_REPLAY_REPORT_OVERWRITE')
    started = time.time(); result = run(args.public_root); result['wall_seconds'] = time.time() - started
    immutable_save(args.output, result)
    print(json.dumps({'passed': result['passed'], 'engineering_replays': len(result['cases'])}))
