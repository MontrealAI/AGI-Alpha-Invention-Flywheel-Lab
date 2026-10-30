"""Apply a published, reviewed authenticated-tail recovery through Account only."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import recover_connected014_tail as recovery

REPOSITORY = Path(__file__).resolve().parents[1]
EXPECTED_DRY_RUN_TOOL_SHA256 = '43690533d651f123104d10772d3688e63d9e2be0ed96c1ffd7e27d1d791507b3'


def published_bytes(commit, name):
    return subprocess.check_output(['git', 'show', commit + ':' + name], cwd=REPOSITORY)


def apply(study, world, dry_run_path, output, phase_path, publication_commit):
    start = time.monotonic()
    if world != '2610301803-central-growth':
        raise ValueError('ONLY_ROOT_REVIEWED_RECOVERY_WORLD_AUTHORIZED')
    if len(publication_commit) != 40 or any(c not in '0123456789abcdef' for c in publication_commit):
        raise ValueError('PUBLISHED_RECOVERY_COMMIT_REQUIRED')
    phase_path, dry_run_path = Path(phase_path).resolve(), Path(dry_run_path).resolve()
    phase = json.loads(phase_path.read_text())
    if phase['schema'] != 'agi-alpha/connected014-authenticated-recovery-allocation/v1' or world not in phase['subject']:
        raise ValueError('EXPLICIT_ROOT_REVIEWED_RECOVERY_PHASE_REQUIRED')
    utc = datetime.timezone.utc
    registered = datetime.datetime.fromisoformat(phase['registered_utc'].replace('Z', '+00:00'))
    deadline = min(registered + datetime.timedelta(minutes=phase['bounds']['wall_minutes']),
                   datetime.datetime.fromisoformat(phase['absolute_closeout_utc'].replace('Z', '+00:00')),
                   datetime.datetime.fromisoformat(phase['remaining_global_cutoff_utc'].replace('Z', '+00:00')))
    if datetime.datetime.now(utc) >= deadline:
        raise TimeoutError('DECLARED_RECOVERY_PHASE_EXHAUSTED')
    published = {
        'scripts/recover_connected014_tail.py': Path(recovery.__file__).resolve(),
        'scripts/apply_connected014_tail.py': Path(__file__).resolve(),
        phase_path.relative_to(REPOSITORY).as_posix(): phase_path,
        'evidence/connected014/engineering/AUTHENTICATED_TAIL_DRY_RUN.json': dry_run_path}
    for name, local in published.items():
        if hashlib.sha256(published_bytes(publication_commit, name)).hexdigest() != recovery.sha(local):
            raise ValueError('PUBLISHED_ROOT_REVIEWED_RECOVERY_BYTES_REQUIRED:' + name)
    prior = json.loads(dry_run_path.read_text())
    if not prior['accepted'] or prior['world'] != world or prior['business_source_sha256'] != recovery.EXPECTED_SOURCE or prior['business_source_commit'] != recovery.EXPECTED_COMMIT or prior['recovery_tool_sha256'] != EXPECTED_DRY_RUN_TOOL_SHA256 or recovery.sha(recovery.__file__) != EXPECTED_DRY_RUN_TOOL_SHA256:
        raise ValueError('EXACT_ACCEPTED_ROOT_REVIEWED_DRY_RUN_REQUIRED')
    study, output = Path(study).resolve(), Path(output).absolute()
    live, source = study / 'worlds' / world, study / 'source'
    backup_manifest = json.loads((dry_run_path.parent / 'private-original' / 'PRIVATE_BACKUP_MANIFEST.json').read_text())
    if recovery.private_snapshot(live) != backup_manifest:
        raise ValueError('LIVE_AUTHENTIC_FILES_CHANGED_SINCE_REVIEWED_DRY_RUN')
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise ValueError('NEW_PRIVATE_LIVE_RECOVERY_OUTPUT_REQUIRED')
    output.mkdir(parents=True, mode=0o700); os.chmod(output, 0o700)
    preflight = recovery.dry_run(study, world, output / 'private-preflight')
    if preflight['sealed_native_actions_sha256'] != prior['sealed_native_actions_sha256'] or preflight['original_native_actions'] != 246 or preflight['authenticated_reconstructed_native_actions'] != 397:
        raise ValueError('FRESH_AUTHENTICATED_PREFLIGHT_CHANGED')
    if recovery.private_snapshot(live) != backup_manifest or datetime.datetime.now(utc) >= deadline:
        raise ValueError('UNCHANGED_LIVE_AUTHORITY_AND_REMAINING_PHASE_REQUIRED')
    from adaptive_enterprise.account import Account
    from commercial.ledger import strict_json
    from connected_enterprise.finance import JournalAccount, _seed_id, audit_journal
    journal = strict_json((live / 'account.sqlite.connected-journal.json').read_bytes())['body']
    manifest = strict_json((study / 'SERVICES.json').read_bytes())
    state_envelope = strict_json((live / 'STATE.json').read_bytes())
    rows = [strict_json(line) for line in (live / 'account.sqlite.actions.jsonl').read_bytes().splitlines()]
    config, original = rows[0]['config'], rows[1:]
    checks = []
    with Account(source, manifest, live / 'account.sqlite', opening=config['opening'], working=config['working'], contract=config['contract']) as account:
        if account.export()['ledger']['actions'] != original or len(original) != 246:
            raise ValueError('EXCLUSIVE_OWNER_ORIGINAL246_PREFIX_CHANGED')
        for entry in journal['entries']:
            if datetime.datetime.now(utc) >= deadline:
                raise TimeoutError('RECOVERY_PHASE_BOUNDARY_AUTHENTIC_PARTIAL_APPEND_PRESERVED')
            req = entry['request']
            if req['operation'] == 'execute':
                account.execute(req['op'], req['args'], req['day'])
            elif entry['funding'] == 'EARNED':
                plan = entry['plan']
                account.reserve(plan, expected_state_digest=plan['expected_state_digest'], authorized_digest=plan['authorized_digest'], amount=req['amount'], expected_net=req['expected_net'], day=req['day'])
                account.finish(plan['plan_id'], req['amount'], recovery.digest(req['work']), req['day'], obligation_receipt=entry['obligation_receipt'])
            else:
                account.cost(_seed_id(req, journal['source']['sha256']), req['amount'], req['day'])
            tape = account.export()['ledger']; receipt = entry['receipt']
            n = receipt['sequence'] if req['operation'] == 'execute' else receipt['native_event_sequence'] + 1
            prefix = tape['actions'][:n]
            if len(prefix) != n or recovery.digest(prefix) != receipt['actions_sha256' if req['operation'] == 'execute' else 'native_actions_sha256']:
                raise ValueError('ORIGINAL_SIGNED_NATIVE_PREFIX_RECEIPT_MISMATCH:' + entry['key'])
            if req['operation'] == 'execute':
                state_digest = recovery.digest({'config': tape['config'], 'actions_sha256': recovery.digest(prefix), 'summary': prefix[-1]['after']})
                if prefix[-1]['after'] != receipt['summary'] or state_digest != receipt['state_digest']:
                    raise ValueError('ORIGINAL_SIGNED_NATIVE_AFTER_STATE_MISMATCH:' + entry['key'])
            checks.append({'key': entry['key'], 'native_sequence': n, 'prefix_sha256': recovery.digest(prefix), 'matched': True})
        record = account.export()
        if record['ledger']['actions'][:246] != original or len(record['ledger']['actions']) != 397 or record['ledger']['actions_sha256'] != prior['sealed_native_actions_sha256']:
            raise ValueError('ORIGINAL_PREFIX_OR_SEALED397_NATIVE_DIGEST_MISMATCH')
        record['connected_journal'] = copy.deepcopy(journal); record['connected_journal_sha256'] = recovery.digest(journal)
        checked = audit_journal(record, root=source, manifest=manifest)
    after = recovery.private_snapshot(live)
    permitted = {'account.sqlite', 'account.sqlite.actions.jsonl', 'account.sqlite.persistence.json'}
    if set(after) != set(backup_manifest) or any(after[name] != value for name, value in backup_manifest.items() if name not in permitted):
        raise ValueError('NON_NATIVE_AUTHENTIC_RECOVERY_RECORD_CHANGED')
    with JournalAccount(source, manifest, live / 'account.sqlite', opening=config['opening'], working=config['working'], contract=config['contract']) as normal:
        if normal.verify_checkpoint(state_envelope) != state_envelope['body']['state'] or not normal.audit()['accepted']:
            raise ValueError('NORMAL_JOURNAL_OWNERSHIP_RECOVERY_REOPEN_FAILED')
    result = {'schema': 'agi-alpha/connected014-authenticated-live-tail-recovery/v1', 'accepted': True,
              'publication_commit': publication_commit, 'phase_sha256': recovery.sha(phase_path),
              'apply_tool_sha256': recovery.sha(__file__), 'dry_run_tool_sha256': EXPECTED_DRY_RUN_TOOL_SHA256,
              'reviewed_dry_run_sha256': recovery.sha(dry_run_path), 'business_source_commit': recovery.EXPECTED_COMMIT,
              'business_source_sha256': recovery.EXPECTED_SOURCE, 'world': world, 'original_native_actions': 246,
              'recovered_native_actions': 397, 'appended_original_authorized_actions': 151,
              'original246_prefix_unchanged': True, 'sealed397_digest_matched': True,
              'sealed397_digest': prior['sealed_native_actions_sha256'], 'all367_signed_receipt_prefixes_matched': len(checks) == 367,
              'original_keys_journal_state_proofs_resolutions_unchanged': True, 'normal_journal_reopen_accepted': True,
              'financial_audit': checked, 'receipt_checks': checks, 'raw_native_tape_edits': False,
              'shadow_database_or_marker_installed': False, 'new_seed_or_receipt': False,
              'registered_deadline_utc': deadline.isoformat(), 'wall_seconds': time.monotonic() - start,
              'mode': 'ORIGINAL_AUTHENTICATED_TAIL_ONLY_NO_NEW_BUSINESS_EVENT_EXECUTED'}
    (output / 'LIVE_RECOVERY.json').write_bytes(recovery.canonical(result) + b'\n')
    print(json.dumps({k: result[k] for k in ['accepted', 'world', 'original_native_actions', 'recovered_native_actions', 'appended_original_authorized_actions', 'normal_journal_reopen_accepted', 'wall_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['study', 'world', 'dry-run', 'output', 'phase', 'publication-commit']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    apply(args.study, args.world, args.dry_run, args.output, args.phase, args.publication_commit)
