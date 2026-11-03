"""Narrow, explicit cache repair for the preserved 50b primary crash.

The defective frozen operator confused its derived SQLite cache with recovery
authority. This compatibility command does not change its source, registration,
signed checkpoint, account identity, actions, costs, or original failed verdict.
It opens the existing account through that exact frozen native implementation,
audits it, and closes it to serialize the optional cache from the durable tape.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes

KNOWN_FROZEN_PRIMARY_SHA = '89fd55c2a26af87dbd7bedd3a540fac87ae191f5ff86271f860e7a5ad09116fe'
KNOWN_REGISTRATION_SHA = 'c74cf91b8390c9a1bdf676cf31a941000f5491e0dc9494c2d582eba6d0c7a7b5'
KNOWN_SOURCE_CLOSURE_SHA = 'd69cfaf470e995f3ea428f8bb56460d94872e24b931dbd44fa520f418e22fed5'
KEY = 'account.sqlite.adaptive-simulation-key'
REQUIRED = ('registration.json', 'manifest.json', 'jobs.json', 'STATE.json', KEY,
            'account.sqlite.actions.jsonl', 'account.sqlite.adaptive-account.json',
            'account.sqlite.connected-journal.json')
OPTIONAL = ('account.sqlite.adaptive-proofs.json', 'account.sqlite.adaptive-resolutions.json')

WORKER = r'''
import json, sys
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.finance import JournalAccount
from omega.primary_operator import registration, read, validate_manifest, game_for
p = Path(sys.argv[1]).resolve()
reg = read(p/'registration.json'); manifest = read(p/'manifest.json')
if canonical(reg) != canonical(registration(p/'source', reg['selection'])):
    raise ValueError('EXACT_FROZEN_REPAIR_REGISTRATION_REQUIRED')
validate_manifest(p/'source', game_for(reg['selection']), manifest, read(p/'jobs.json'))
rows = [strict_json(line) for line in (p/'account.sqlite.actions.jsonl').read_bytes().splitlines()]
before = digest(rows[1:])
with JournalAccount(p/'source', manifest, p/'account.sqlite', opening=reg['selection']['opening_microUSD'],
                    working=0, contract='omega-primary-counterpart:'+digest(reg)) as account:
    account.verify_checkpoint(read(p/'STATE.json'))
    if account.audit()['accepted'] is not True:
        raise ValueError('NATIVE_REPAIR_AUDIT_REJECTED')
    record = account.export()
    if record['ledger']['actions_sha256'] != before or canonical(record['ledger']['actions']) != canonical(rows[1:]):
        raise ValueError('RECOVERY_MUST_NOT_EXECUTE_FINANCIAL_ACTIONS')
    result = {'native_audit_accepted':True, 'native_actions_sha256':before,
              'native_action_count':len(rows)-1, 'checkpoint_verified':True}
print(json.dumps(result,sort_keys=True))
'''


def _bytes(path, *, allow_empty=False):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('EXISTING_REGULAR_RECOVERY_AUTHORITY_REQUIRED')
    raw = path.read_bytes()
    if (not raw and not allow_empty) or len(raw) > 64_000_000:
        raise ValueError('NONEMPTY_BOUNDED_RECOVERY_AUTHORITY_REQUIRED')
    return raw


def rebuild_checkpoint(output):
    output = Path(output).absolute()
    reg = strict_json(_bytes(output / 'registration.json'))
    if (digest(reg) != KNOWN_REGISTRATION_SHA or digest(reg['source_hashes']) != KNOWN_SOURCE_CLOSURE_SHA
            or reg['source_hashes'].get('omega/primary_operator.py') != KNOWN_FROZEN_PRIMARY_SHA):
        raise ValueError('ONLY_KNOWN_50B_FROZEN_REGISTRATION_REPAIR_ALLOWED')
    for name, expected in reg['source_hashes'].items():
        if hashlib.sha256(_bytes(output / 'source' / name, allow_empty=True)).hexdigest() != expected:
            raise ValueError('FROZEN_RECOVERY_SOURCE_CHANGED')
    # Refuse before Account construction, so unavailable authority cannot create
    # a replacement key, action tape, namespace, journal, or seed balance.
    before = {name: _bytes(output / name) for name in REQUIRED}
    before.update({name: _bytes(output / name) for name in OPTIONAL if (output / name).exists()})
    namespace = strict_json(before['account.sqlite.adaptive-account.json'])
    if namespace != {'account_path': str(output / 'account.sqlite'), 'namespace': 'adaptive012',
                     'schema': 'agi-alpha/adaptive012-account-namespace/v1'}:
        raise ValueError('SAME_REGISTERED_ACCOUNT_NAMESPACE_REQUIRED')
    tape = before['account.sqlite.actions.jsonl']
    rows = [strict_json(line) for line in tape.splitlines()]
    if (not tape.endswith(b'\n') or len(rows) < 43
            or rows[0].get('schema') != 'agi-alpha/commercial010-durable-actions/v1'
            or digest(rows[1:43]) != reg['selection']['historical_actions_sha256']):
        raise ValueError('EXISTING_EXACT_HISTORICAL_ACTION_PREFIX_REQUIRED')
    journal = strict_json(before['account.sqlite.connected-journal.json'])
    if any(entry['status'] != 'COMPLETE' for entry in journal['body']['entries']):
        raise ValueError('PENDING_FINANCIAL_ACTION_REPAIR_NOT_AUTHORIZED')
    cache = output / 'account.sqlite'
    if cache.exists():
        if not cache.is_file() or cache.is_symlink():
            raise ValueError('REGULAR_DERIVED_CHECKPOINT_REQUIRED')
        return {'needed': False, 'repaired': False, 'account_opened': False,
                'scope': 'Cache already exists; no repair or financial action attempted'}
    process = subprocess.run([sys.executable, '-c', WORKER, str(output)], cwd=output / 'source',
                             capture_output=True, text=True)
    if process.returncode:
        raise ValueError('EXACT_NATIVE_CHECKPOINT_REPAIR_FAILED:' + process.stderr[-3000:])
    after = {name: _bytes(output / name) for name in before}
    if before != after or {name for name in OPTIONAL if (output / name).exists()} != set(before).intersection(OPTIONAL):
        raise ValueError('RECOVERY_AUTHORITY_BYTES_CHANGED')
    result = strict_json(process.stdout)
    if not cache.is_file() or result['native_actions_sha256'] != digest(rows[1:]):
        raise ValueError('DERIVED_CACHE_REBUILD_NOT_VERIFIED')
    receipt = {'schema': 'omega/known-primary-derived-cache-recovery/v1', 'needed': True, 'repaired': True,
               **result, 'registration_sha256': KNOWN_REGISTRATION_SHA,
               'frozen_primary_source_sha256': KNOWN_FROZEN_PRIMARY_SHA,
               'frozen_source_closure_sha256': KNOWN_SOURCE_CLOSURE_SHA,
               'recovery_operator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'worker_sha256': hashlib.sha256(WORKER.encode()).hexdigest(),
               'authority_bytes_unchanged': True, 'private_authority_exported': False,
               'financial_actions_added': 0, 'frozen_source_or_registration_changed': False,
               'cache_created': True, 'explicit_engineering_intervention': True,
               'scope': 'Compatibility repair outside the frozen business operator; original direct-resume failure retained'}
    atomic_bytes(output / ('cache-recovery-' + result['native_actions_sha256'] + '.json'), canonical(receipt) + b'\n')
    return receipt


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    print(json.dumps(rebuild_checkpoint(parser.parse_args().output), sort_keys=True))
