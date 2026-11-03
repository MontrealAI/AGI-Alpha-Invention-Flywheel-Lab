import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile

FOLDER = 'experiments/outlearning_20261102_906c4f4d'
REPOSITORY = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
SOURCE_COMMIT = '85c8a3e98f31bac9d3867a022aaa758623335083'
ROOT_FILES = ('INPUT.json', 'SCIENCE.json', 'ECONOMICS.json', 'EXECUTION.json',
              'FAILURE.json', 'INDEPENDENT_REPLAY_FAILURE.json',
              'INDEPENDENT_REPLAY.json', 'RESOURCE_SCOPE.json', 'ADOPTION.json')
CHECKERS = ('postfreeze_replay.py', 'package_public_evidence.py')
SECRET_PATTERNS = (
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b'),
    re.compile(rb'\bAKIA[0-9A-Z]{16}\b'))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or str(rel) != name:
        raise ValueError('EXACT_RELATIVE_PUBLIC_PATH_REQUIRED')
    path = root.joinpath(*rel.parts)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('REGULAR_PUBLIC_FILE_REQUIRED:' + name)
    return path


def scan(name, raw):
    if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
        raise ValueError('POSSIBLE_SECRET_IN_ALLOWLIST_FILE:' + name)
    if name.endswith('.json'):
        def inspect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.lower() in {'api_key', 'openai_api_key', 'private_key', 'signing_key', 'simulation_key'} and isinstance(item, str) and item:
                        raise ValueError('PRIVATE_AUTHORITY_FIELD_IN_PUBLIC_FILE:' + name)
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
        inspect(strict(raw))


SETUP = '''import argparse, hashlib, json, shutil, subprocess
from pathlib import Path, PurePosixPath

def checked_path(root, name):
    rel=PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or str(rel)!=name: raise ValueError('RELATIVE_PATH_REQUIRED')
    p=root.joinpath(*rel.parts)
    if any(q.is_symlink() for q in (p,*p.parents)): raise ValueError('SYMLINK_REFUSED')
    return p

def main():
    p=argparse.ArgumentParser(); p.add_argument('--checkout',required=True,type=Path); p.add_argument('--evidence-root',default=Path(__file__).resolve().parent,type=Path); a=p.parse_args()
    root=a.evidence_root.resolve(); checkout=a.checkout.resolve()
    manifest=json.loads((root/'BUNDLE_MANIFEST.json').read_text())
    if manifest.get('schema')!='outlearning-public-bundle/v1' or manifest.get('private_authority_included') is not False: raise ValueError('EXTRACTED_PUBLIC_BUNDLE_REQUIRED')
    for name,entry in manifest['files'].items():
        f=checked_path(root,name)
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=entry['sha256']: raise ValueError('PUBLIC_PAYLOAD_CHANGED:'+name)
    inv=json.loads((root/'SOURCE_INVENTORY.json').read_text())
    commit=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
    if commit!=inv['source_commit']: raise ValueError('EXACT_FROZEN_COMMIT_REQUIRED')
    jobs=[]
    for name,entry in inv['files'].items():
        src=checked_path(checkout,name); dst=checked_path(root/'native/source',name)
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest()!=entry['sha256']: raise ValueError('FROZEN_SOURCE_BYTES_CHANGED:'+name)
        if dst.exists() and (not dst.is_file() or hashlib.sha256(dst.read_bytes()).hexdigest()!=entry['sha256']): raise ValueError('EXISTING_SOURCE_WOULD_CHANGE:'+name)
        jobs.append((src,dst))
    for name in ('postfreeze_replay.py','package_public_evidence.py'):
        src=checked_path(root,'checks/'+name); dst=checked_path(root/'native/source',inv['campaign_folder']+'/'+name)
        if dst.exists() and dst.read_bytes()!=src.read_bytes(): raise ValueError('EXISTING_ADDITIVE_CHECKER_WOULD_CHANGE')
        jobs.append((src,dst))
    for src,dst in jobs:
        if not dst.exists():
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst)
    print(json.dumps({'source_commit':commit,'source_files_verified':len(inv['files']),'copied_or_already_identical':len(jobs),'native_account_authority_required':False}))

if __name__=='__main__': main()
'''


def readme(freeze):
    return f'''# Public evidence and key-free replay

This archive preserves the original 96 technical rows and 18 independent native
account exports. The unfavorable treatment comparison, initial execution failure,
and original replay-checker failure remain included. No account signing authority,
database, raw private action tape, or operating checkpoint is included.

## Source identity

- Repository: {REPOSITORY}
- Exact pre-confirmation commit: `{SOURCE_COMMIT}`
- Frozen protocol digest: `{freeze}`
- The 817-file canonical source selection is represented by `SOURCE_INVENTORY.json`,
  with its exact byte hashes; the public repository supplies the source bytes.
- `checks/postfreeze_replay.py` is an additive verification correction for serialized
  Python-versus-JSON representation. It does not replace frozen methods, evaluator,
  protocol, worlds, economics, or outcomes. Its bytes are in `BUNDLE_MANIFEST.json`.

## Restore source into a new extracted public bundle

Extract this archive into a new directory. Obtain a checkout of the exact commit;
an existing clone can be used. For a fresh clone:

```sh
git clone --filter=blob:none --no-checkout {REPOSITORY}.git frozen-checkout
git -C frozen-checkout checkout --detach {SOURCE_COMMIT}
python setup_source.py --checkout /absolute/path/to/frozen-checkout --evidence-root /absolute/path/to/extracted-evidence
```

The setup verifies every allowlisted payload and source byte before copying. It
requires the extracted bundle manifest and refuses conflicting existing files.
It does not modify the original operating directory, create accounts, reseed money,
open account authority, or rerun commerce. Runtime artifacts already present under
`native/source` remain unchanged. The source checkout must retain its Git commit
identity; the source copied into the bundle does not need `.git`.

Use Python 3.12 and the dependencies listed by the frozen source. Where they are
not already installed, the public dependency command is:

```sh
python -m pip install --only-binary=:all: -r /absolute/path/to/extracted-evidence/native/source/requirements-commercial010.txt
```

## Replay original evidence without signing keys

```sh
cd /absolute/path/to/extracted-evidence/native/source
python -m experiments.outlearning_20261102_906c4f4d.postfreeze_replay --output /absolute/path/to/extracted-evidence --expected-freeze {freeze} --receipt /absolute/path/to/new-public-replay.json
```

Use a new receipt filename. The checker regenerates and compares deterministic
technical constructions and independently replays the exported native journals;
it does not resume their private accounts. Successful replay establishes source
and result reproduction within the authored simulation, not actual provider
semantics, customers, or a discovery advantage.

## Contents and omissions

`BUNDLE_MANIFEST.json` hashes every payload file except itself. The adjacent archive
manifest records this manifest hash and the archive SHA-256. `FAILURE.json`,
`INDEPENDENT_REPLAY_FAILURE.json`, `RESOURCE_SCOPE.json`, and `ADOPTION.json` retain
failure/resource/decision context. Public native `RESULT.json` receipts supplement
the account exports. All actual request-bound delivered artifacts, including
failed attempts, are included at their original relative verification paths.

The archive deliberately omits raw private account files, checkpoints, authority,
duplicate resume stdout, and duplicate construction/delivery copies. The original
96 scientific rows retain their submitted programs and full probe transcripts.
Only a strict public-file allowlist was inspected for secret patterns; no broader
credential search or account-wide privacy audit was performed.
'''


def package(source_output, destination):
    output, destination = Path(source_output).resolve(), Path(destination).absolute()
    repo = Path(__file__).resolve().parents[2]
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('SYMLINK_DESTINATION_REFUSED')
    if output == destination or output in destination.parents:
        raise ValueError('DESTINATION_MUST_BE_OUTSIDE_ORIGINAL_RUN')
    adjacent = destination.with_name(destination.name.removesuffix('.tar.gz')+'.manifest.json')
    if destination.exists() or adjacent.exists():
        raise ValueError('NEW_ARCHIVE_AND_MANIFEST_PATHS_REQUIRED')
    payload = {}

    def add(name, root=output, relative=None):
        if name in payload:
            raise ValueError('DUPLICATE_PUBLIC_PATH')
        raw = safe(root, relative or name).read_bytes()
        scan(name, raw)
        payload[name] = raw

    for name in ROOT_FILES:
        add(name)
    run_input, economics = strict(payload['INPUT.json']), strict(payload['ECONOMICS.json'])
    freeze = run_input['freeze_sha256']
    replay = strict(payload['INDEPENDENT_REPLAY.json'])
    if replay.get('accepted') is not True or replay.get('freeze_sha256') != freeze:
        raise ValueError('ACCEPTED_SOURCE_MATCHED_PUBLIC_REPLAY_REQUIRED')
    expected_science = {f'{i:02d}-{arm}.json' for i in range(48) for arm in ('treatment','ordinary')}
    if {p.name for p in (output/'science').glob('*.json')} != expected_science:
        raise ValueError('EXACT_NINETY_SIX_SCIENTIFIC_ROWS_REQUIRED')
    for name in sorted(expected_science):
        add('science/'+name)
    expected_accounts = {f'{a}-{r}-{c}' for a in ('treatment','ordinary','no-deploy')
                         for r in ('positive','weak','adverse') for c in (10000,100000)}
    rows = economics['accounts']
    if len(rows) != 18 or {r['identity'] for r in rows} != expected_accounts:
        raise ValueError('EXACT_EIGHTEEN_PUBLIC_ACCOUNTS_REQUIRED')
    artifact_count = 0
    for row in rows:
        identity = row['identity']
        for name in ('MANIFEST.json','PUBLIC_ACCOUNT.json','RESULT.json'):
            add(f'native/{identity}/{name}')
        manifest = strict(payload[f'native/{identity}/MANIFEST.json'])
        record = strict(payload[f'native/{identity}/PUBLIC_ACCOUNT.json'])
        if sha(canonical(record)) != row['native_export_sha256'] or record['ledger']['summary'] != row['financial_microUSD']:
            raise ValueError('PUBLIC_ACCOUNT_BINDING_CHANGED')
        for request in manifest['jobs']:
            path = request['delivery_path']
            if not re.fullmatch(re.escape(FOLDER+'/runtime/'+identity+'/')+r'order-[0-9]{2}\.json', path):
                raise ValueError('EXACT_DELIVERY_NAMESPACE_REQUIRED')
            if (output/'native/source'/path).is_file():
                add('native/source/'+path)
                artifact_count += 1
    original_source = output/'native/source'
    script = 'import json; from pathlib import Path; from connected_enterprise.runner import source_paths; print(json.dumps(source_paths(Path.cwd())))'
    selected = strict(subprocess.check_output([sys.executable,'-B','-c',script],cwd=original_source))
    tree_raw = subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','-z',SOURCE_COMMIT])
    tree = {}
    for entry in tree_raw.split(b'\0'):
        if entry:
            fields, name = entry.split(b'\t',1)
            mode, kind, ident = fields.decode().split()
            if kind == 'blob' and mode in ('100644','100755'):
                tree[name.decode()] = ident
    inventory = {}
    for name in sorted(set(selected)):
        if name not in tree:
            raise ValueError('CANONICAL_SOURCE_NOT_IN_FROZEN_PUBLIC_COMMIT:'+name)
        raw = safe(original_source,name).read_bytes()
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != tree[name]:
            raise ValueError('CANONICAL_SOURCE_BYTES_DIFFER_FROM_PUBLIC_COMMIT:'+name)
        inventory[name] = {'sha256':sha(raw),'size_bytes':len(raw)}
    frozen = strict(safe(original_source,FOLDER+'/FREEZE.json').read_bytes())
    if sha(canonical(frozen)) != freeze:
        raise ValueError('FROZEN_PROTOCOL_BINDING_CHANGED')
    for name, expected in frozen['files'].items():
        if inventory.get(name,{}).get('sha256') != expected:
            raise ValueError('FROZEN_FILE_OUTSIDE_CANONICAL_INVENTORY:'+name)
    for name in CHECKERS:
        add('checks/'+name, repo, FOLDER+'/'+name)
    payload['SOURCE_INVENTORY.json'] = canonical({'schema':'outlearning-pinned-source-inventory/v1',
        'source_commit':SOURCE_COMMIT,'repository':REPOSITORY,'campaign_folder':FOLDER,'files':inventory})+b'\n'
    payload['setup_source.py'] = SETUP.encode()
    payload['README_PUBLIC_REPLAY.md'] = readme(freeze).encode()
    for name, raw in payload.items():
        scan(name,raw)
    manifest = {'schema':'outlearning-public-bundle/v1','source_commit':SOURCE_COMMIT,
        'freeze_sha256':freeze,'private_authority_included':False,'scientific_rows':96,
        'native_accounts':18,'bound_delivery_artifacts':artifact_count,
        'canonical_source_files_referenced':len(inventory),
        'canonical_source_bytes_omitted':sum(x['size_bytes'] for x in inventory.values()),
        'scan_scope':'Strict allowlist only; no private authority files read and no account-wide credential search.',
        'files':{name:{'sha256':sha(raw),'size_bytes':len(raw)} for name,raw in sorted(payload.items())}}
    payload['BUNDLE_MANIFEST.json'] = canonical(manifest)+b'\n'
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.public-evidence-',delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with temporary.open('wb') as stream, gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as zipped:
            with tarfile.open(fileobj=zipped,mode='w',format=tarfile.PAX_FORMAT) as archive:
                for name,raw in sorted(payload.items()):
                    item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644;item.mtime=0
                    archive.addfile(item,io.BytesIO(raw))
        raw=temporary.read_bytes()
        receipt={'schema':'outlearning-public-archive-receipt/v1','archive_sha256':sha(raw),
            'archive_bytes':len(raw),'payload_bytes':sum(map(len,payload.values())),
            'archive_members':len(payload),'bundle_manifest_sha256':sha(payload['BUNDLE_MANIFEST.json']),
            'source_commit':SOURCE_COMMIT,'freeze_sha256':freeze,'secret_pattern_matches':0,
            'private_authority_included':False,'files':manifest['files']}
        os.link(temporary,destination)
        with adjacent.open('xb') as stream:
            stream.write(canonical(receipt)+b'\n')
    finally:
        temporary.unlink(missing_ok=True)
    return {key:value for key,value in receipt.items() if key!='files'} | {'destination':str(destination),'adjacent_manifest':str(adjacent)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-output',required=True,type=Path)
    parser.add_argument('--destination',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(package(args.source_output,args.destination),sort_keys=True))


if __name__=='__main__':
    main()
