"""Inactive, append-only catalog preparation under the existing native signer.

No native job registry, manifest, balance, journal or history is modified. This
does not implement activation. Keep these signed proposals with private recovery
state; publish only key-free test summaries. An external expected-head receipt
is mandatory to detect a missing/truncated tail under local POSIX custody.
"""
import hashlib
import json
import os
import sys
from pathlib import Path
from .contract import accept, digest, TYPE

SCHEMA = 'enterprise078/inactive-catalog-proposal/v1'
FILES = ('catalog.py', 'contract.py')


def source_identity(root):
    root = Path(root)
    names = ['enterprise078/transactional_admission/'+n for n in FILES]
    names += ['enterprise078/transactional_data/'+n for n in ('acceptance.py','operator.py')]
    result = {}
    for name in names:
        p = root/name
        if not p.is_file() or p.is_symlink() or any(q.is_symlink() for q in p.parents):
            raise ValueError('REGULAR_CANDIDATE_SOURCE_REQUIRED')
        result[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def executing_identity(root):
    """Bind candidate files to loaded modules, not an arbitrary source tree.

    This is a local trusted-process/file identity check, not attestation against
    malicious process memory or an administrator changing files during execution.
    Native source/manifest identity remains independently checked by the account.
    """
    candidate = source_identity(root)
    for name, expected in candidate.items():
        module = sys.modules.get(name[:-3].replace('/', '.'))
        path = Path(module.__file__) if module is not None and getattr(module, '__file__', None) else None
        if (path is None or not path.is_file() or path.is_symlink()
                or any(p.is_symlink() for p in path.parents)
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ValueError('CATALOG_EXECUTING_SOURCE_MISMATCH')
    return candidate


def location(account):
    # Account snapshot checks canonical ownership before any preparation IO.
    account.snapshot()
    p = account.account.path
    directory = p.with_name(p.name+'.catalog-proposals')
    if directory.is_symlink() or any(q.is_symlink() for q in directory.parents):
        raise ValueError('PRIVATE_REGULAR_PROPOSAL_DIRECTORY_REQUIRED')
    return directory


def recover(account, root, expected_head):
    directory = location(account)
    files = sorted(directory.glob('*.json')) if directory.exists() else []
    previous = None
    states = []
    current_source = executing_identity(root)
    for i,p in enumerate(files):
        if p.name != f'{i:08d}.json' or p.is_symlink() or not p.is_file():
            raise ValueError('CONTIGUOUS_REGULAR_PROPOSALS_REQUIRED')
        if p.stat().st_size > 34_000_000:
            raise ValueError('BOUNDED_NATIVE_CHECKPOINT_PROPOSAL_REQUIRED')
        raw = p.read_text()
        envelope = json.loads(raw)
        if raw != json.dumps(envelope,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n':
            raise ValueError('CANONICAL_PROPOSAL_BYTES_REQUIRED')
        state = account.verify_checkpoint(envelope)
        if set(state) != {'schema','sequence','previous','status','candidate_source','request','delivery'}:
            raise ValueError('EXACT_CATALOG_PROPOSAL_REQUIRED')
        if (state['schema'] != SCHEMA or state['status'] != 'PREPARED_NOT_ACTIVE'
                or state['sequence'] != i or state['previous'] != previous
                or state['candidate_source'] != current_source
                or state['request'].get('type') != TYPE
                or state['delivery'].get('accepted') is not True
                or state['delivery'].get('native_catalog_admitted') is not False
                or state['delivery']['request_sha256'] != digest(state['request'])):
            raise ValueError('CATALOG_SOURCE_CHAIN_OR_TYPE_CHANGED')
        previous = digest(envelope)
        states.append(state)
    if previous != expected_head:
        raise ValueError('EXPECTED_CATALOG_HEAD_REQUIRED_NO_TRUNCATION')
    return states


def prepare(account, root, expected_head, contract, events, database, csv_path):
    states = recover(account, root, expected_head)
    receipt = accept(contract, events, database, csv_path)
    if not receipt['accepted']:
        raise ValueError('ACCEPTED_TYPED_DELIVERY_REQUIRED')
    state = {'schema':SCHEMA,'sequence':len(states),'previous':expected_head,
             'status':'PREPARED_NOT_ACTIVE','candidate_source':executing_identity(root),
             'request':contract,'delivery':receipt}
    before = digest(account.export())
    envelope = account.seal_checkpoint(state)
    directory = location(account); directory.mkdir(mode=0o700, exist_ok=True)
    p = directory/f'{len(states):08d}.json'
    # Exclusive creation never overwrites an old proposal. A torn write is a
    # refusal on reopen, not an invitation to re-sign/reset the chain.
    fd = os.open(p, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(envelope,f,sort_keys=True,separators=(',',':'));f.write('\n')
        f.flush();os.fsync(f.fileno())
    for parent in (directory,directory.parent):
        fd = os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    if digest(account.export()) != before:
        raise ValueError('FINANCIAL_HISTORY_CHANGED_DURING_PREPARATION')
    return {'head':digest(envelope),'status':'PREPARED_NOT_ACTIVE',
            'native_catalog_admitted':False,'financial_export_sha256':before,
            'request_sha256':digest(contract),'proposal_count':len(states)+1}
