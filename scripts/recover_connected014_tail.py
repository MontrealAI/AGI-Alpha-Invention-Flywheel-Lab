"""Dry-run authenticated native-tail recovery; never writes the live account.

An owned shadow is an audit mirror of the same business, never another funded
enterprise. Only HMAC-authenticated original commands may be replayed. Live
application requires a separately authorized recovery phase and implementation.
"""
import argparse
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sys
import time

EXPECTED_SOURCE = '3d985299bf6cfaf546b712ebd9e878e875aaf730ffdb32023637aafc5504a38d'
EXPECTED_COMMIT = 'ffc1f2e14e88e11f75d5087ab0f7c4e60512431e'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def private_snapshot(directory):
    result = {}
    for p in sorted(directory.iterdir()):
        if p.is_symlink() or not p.is_file():
            raise ValueError('ONLY_REGULAR_ORIGINAL_FILES_SUPPORTED')
        result[p.name] = {'sha256': sha(p), 'bytes': p.stat().st_size, 'mode': p.stat().st_mode & 0o777}
    return result


def dry_run(study, world, output):
    start = time.monotonic()
    study, output = Path(study).resolve(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise ValueError('NEW_PRIVATE_DRY_RUN_OUTPUT_REQUIRED')
    if not world or Path(world).name != world:
        raise ValueError('EXACT_WORLD_IDENTIFIER_REQUIRED')
    source, live = study / 'source', study / 'worlds' / world
    frozen = json.loads((study / 'FROZEN.json').read_text())
    expected = frozen.pop('sha256')
    if digest(frozen) != expected or frozen['source']['sha256'] != EXPECTED_SOURCE or frozen['git_commit'] != EXPECTED_COMMIT:
        raise ValueError('REGISTERED_SOURCE002_FREEZE_REQUIRED')
    for name, value in frozen['source']['files'].items():
        if sha(source / name) != value:
            raise ValueError('FROZEN_BUSINESS_SOURCE_CHANGED:' + name)
    sys.path.insert(0, str(source))
    from adaptive_enterprise.account import Account
    from commercial.ledger import strict_json
    from connected_enterprise.finance import _seed_id, audit_journal, source_identity
    import adaptive_enterprise.account as account_module
    if Path(account_module.__file__).resolve() != source / 'adaptive_enterprise/account.py':
        raise ValueError('EXACT_CANONICAL_ACCOUNT_IMPORT_REQUIRED')
    before = private_snapshot(live)
    key = (live / 'account.sqlite.adaptive-simulation-key').read_bytes()
    if len(key) != 32:
        raise ValueError('EXISTING_PRIVATE_SIMULATION_KEY_REQUIRED')
    journal_envelope = strict_json((live / 'account.sqlite.connected-journal.json').read_bytes())
    journal = journal_envelope['body']
    signature = hmac.new(key, b'connected014-journal\n' + canonical(journal), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, journal_envelope['signature']):
        raise ValueError('ORIGINAL_COMMAND_WAL_HMAC_FAILED')
    if journal['source'] != source_identity(source):
        raise ValueError('ORIGINAL_COMMAND_WAL_SOURCE_CHANGED')
    state_envelope = strict_json((live / 'STATE.json').read_bytes())
    sealed = state_envelope['body']
    signature = hmac.new(key, b'connected014-operating-state\n' + canonical(sealed), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, state_envelope['signature']):
        raise ValueError('ORIGINAL_OPERATING_STATE_HMAC_FAILED')
    manifest = strict_json((study / 'SERVICES.json').read_bytes())
    tape_raw = (live / 'account.sqlite.actions.jsonl').read_bytes()
    if not tape_raw.endswith(b'\n'):
        raise ValueError('INCOMPLETE_NATIVE_LINE_NOT_SUPPORTED')
    rows = [strict_json(line) for line in tape_raw.splitlines()]
    config, actual = rows[0]['config'], rows[1:]
    if journal['contract'] != config['contract'] or sealed['contract'] != config['contract'] or journal['manifest_sha256'] != digest(manifest) or config['manifest_sha256'] != digest(manifest) or sealed['manifest_sha256'] != digest(manifest):
        raise ValueError('ORIGINAL_ACCOUNT_AUTHORITY_OR_COHORT_CHANGED')
    proofs = strict_json((live / 'account.sqlite.adaptive-proofs.json').read_bytes())
    resolutions = strict_json((live / 'account.sqlite.adaptive-resolutions.json').read_bytes())
    commands = []
    for entry in journal['entries']:
        if entry['status'] != 'COMPLETE':
            raise ValueError('THIS_RECOVERY_REQUIRES_COMPLETE_AUTHENTICATED_COMMANDS')
        req = entry['request']
        if req['operation'] == 'execute':
            commands.append({'op': req['op'], 'args': req['args'], 'day': req['day']})
        elif entry['funding'] == 'EARNED':
            plan = entry['plan']; proof = proofs[plan['plan_id']]
            signature = hmac.new(key, canonical(proof['body']), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, proof['signature']) or resolutions[plan['plan_id']] != entry['obligation_receipt']:
                raise ValueError('ORIGINAL_RESERVATION_OR_OBLIGATION_PROOF_CHANGED')
            commands.append({'op': 'reserve', 'args': {'id': plan['plan_id'], 'amount': req['amount'], 'expected_net_value': req['expected_net'], 'intent_sha256': digest(proof['body'])}, 'day': req['day']})
            bound = digest({'work_artifact_sha256': digest(req['work']), 'obligation_receipt_sha256': digest(entry['obligation_receipt'])})
            commands.append({'op': 'finish', 'args': {'id': plan['plan_id'], 'amount': req['amount'], 'artifact_sha256': bound}, 'day': req['day']})
        elif entry['funding'] == 'SEED' and req['allow_seed']:
            commands.append({'op': 'cost', 'args': {'id': _seed_id(req, journal['source']['sha256']), 'amount': req['amount']}, 'day': req['day']})
        else:
            raise ValueError('ORIGINAL_AUTHORIZED_FUNDING_REQUIRED')
    if len(actual) >= len(commands) or any({'op': row['op'], 'args': row['args'], 'day': row['day']} != cmd for row, cmd in zip(actual, commands)):
        raise ValueError('STRICT_ORIGINAL_NATIVE_PREFIX_REQUIRED')
    if sealed['native_sequence'] != len(commands):
        raise ValueError('SEALED_NATIVE_COVERAGE_MUST_EQUAL_AUTHORIZED_TAIL')
    output.mkdir(mode=0o700, parents=True)
    os.chmod(output, 0o700)
    backup = output / 'private-original'; backup.mkdir(mode=0o700)
    shadow = output / 'private-shadow'; shadow.mkdir(mode=0o700)
    for name in before:
        shutil.copy2(live / name, backup / name)
        if name.startswith('account.sqlite') and name not in {'account.sqlite.adaptive-account.json', 'account.sqlite.writer.lock'}:
            shutil.copy2(live / name, shadow / name)
    (backup / 'PRIVATE_BACKUP_MANIFEST.json').write_bytes(canonical(before) + b'\n')
    os.chmod(backup / 'PRIVATE_BACKUP_MANIFEST.json', 0o600)
    checks = []
    with Account(source, manifest, shadow / 'account.sqlite', opening=config['opening'], working=config['working'], contract=config['contract']) as account:
        for entry in journal['entries']:
            req = entry['request']
            if req['operation'] == 'execute':
                account.execute(req['op'], req['args'], req['day'])
            elif entry['funding'] == 'EARNED':
                plan = entry['plan']
                account.reserve(plan, expected_state_digest=plan['expected_state_digest'], authorized_digest=plan['authorized_digest'], amount=req['amount'], expected_net=req['expected_net'], day=req['day'])
                account.finish(plan['plan_id'], req['amount'], digest(req['work']), req['day'], obligation_receipt=entry['obligation_receipt'])
            else:
                account.cost(_seed_id(req, journal['source']['sha256']), req['amount'], req['day'])
            tape = account.export()['ledger']; receipt = entry['receipt']
            n = receipt['sequence'] if req['operation'] == 'execute' else receipt['native_event_sequence'] + 1
            prefix = tape['actions'][:n]
            if len(prefix) != n or digest(prefix) != receipt['actions_sha256' if req['operation'] == 'execute' else 'native_actions_sha256']:
                raise ValueError('ORIGINAL_SIGNED_NATIVE_PREFIX_RECEIPT_MISMATCH:' + entry['key'])
            if req['operation'] == 'execute':
                state_digest = digest({'config': tape['config'], 'actions_sha256': digest(prefix), 'summary': prefix[-1]['after']})
                if prefix[-1]['after'] != receipt['summary'] or state_digest != receipt['state_digest']:
                    raise ValueError('ORIGINAL_SIGNED_NATIVE_AFTER_STATE_MISMATCH:' + entry['key'])
            checks.append({'key': entry['key'], 'native_sequence': n, 'prefix_sha256': digest(prefix), 'matched': True})
        record = account.export()
        if len(record['ledger']['actions']) != len(commands) or record['ledger']['actions_sha256'] != sealed['native_actions_sha256']:
            raise ValueError('SEALED_COMPLETE_NATIVE_PREFIX_DIGEST_MISMATCH')
        record['connected_journal'] = copy.deepcopy(journal)
        record['connected_journal_sha256'] = digest(journal)
        checked = audit_journal(record, root=source, manifest=manifest)
        summary = record['ledger']['summary']
    unchanged = private_snapshot(live) == before
    if not unchanged:
        raise ValueError('ORIGINAL_ACCOUNT_CHANGED_DURING_DRY_RUN')
    result = {'schema': 'agi-alpha/connected014-authenticated-tail-dry-run/v1', 'accepted': True,
              'mode': 'DRY_RUN_ONLY_LIVE_ACCOUNT_NOT_WRITTEN', 'world': world,
              'business_source_commit': EXPECTED_COMMIT, 'business_source_sha256': EXPECTED_SOURCE,
              'recovery_tool_sha256': sha(__file__), 'original_native_actions': len(actual),
              'authenticated_reconstructed_native_actions': len(commands), 'missing_tail_actions': len(commands) - len(actual),
              'original_command_WAL_HMAC_verified': True, 'original_sealed_STATE_HMAC_verified': True,
              'all_reservation_proof_HMACs_verified': True, 'original_native_prefix_exact': True,
              'original_files_unchanged': unchanged, 'signed_receipt_prefixes_checked': len(checks),
              'receipt_checks': checks, 'sealed_native_sequence': sealed['native_sequence'],
              'sealed_native_actions_sha256': sealed['native_actions_sha256'], 'financial_audit': checked,
              'reconstructed_summary': summary, 'private_backup_retained': True,
              'backup_scope': 'Private simulation key retained only under0700dry-run directory; never publish backup/shadow.',
              'shadow_namespace': 'Canonical Account creates its path-local namespace; original marker is preserved unchanged in private backup.',
              'first_missing_command': commands[len(actual)], 'wall_seconds': time.monotonic() - start,
              'next_action': 'Await separate root-reviewed live application through canonical Account. No raw tape edit, reseeding or new financial receipt authorized by this dry-run result.'}
    (output / 'DRY_RUN.json').write_bytes(canonical(result) + b'\n')
    print(json.dumps({k: result[k] for k in ['accepted', 'world', 'original_native_actions', 'authenticated_reconstructed_native_actions', 'missing_tail_actions', 'original_files_unchanged', 'sealed_native_actions_sha256', 'wall_seconds']}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True); parser.add_argument('--world', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    dry_run(args.study, args.world, args.output)
