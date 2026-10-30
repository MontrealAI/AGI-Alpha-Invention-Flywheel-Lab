"""Build a compact, source-identified campaign package; replay needs no Git."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

PREFIXES = ('campaign/next-009/', 'inventions/measurement009/',
            'research/next009/', 'verification/next009/', 'docs/next009/',
            'flywheel/', 'experiments/', 'vendor/')
FILES = {'tests/test_next009.py', 'verification/__init__.py'}
PREFIX = 'AGI_ALPHA_Measurement_009/'

def package(root, commit, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('IMMUTABLE_COMMIT_REQUIRED')
    tree = subprocess.check_output(['git','ls-tree','-r','-z',commit],cwd=root)
    entries = {}
    for line in tree.split(b'\0'):
        if not line: continue
        info, name = line.split(b'\t',1); mode, kind, blob = info.decode().split()
        path=name.decode()
        included = (path.startswith(PREFIXES) or path in FILES or
            path.startswith('evidence/next009/archives/') or
            (path.startswith('evidence/next009/') and '/packages/' not in path and
             path.endswith('.json') and path.count('/')<=3))
        if not included: continue
        if kind!='blob' or mode not in {'100644','100755'}:
            raise ValueError('NONREGULAR_PACKAGE_MEMBER:'+path)
        if '__pycache__' in Path(path).parts or path.endswith('.pyc'):
            raise ValueError('GENERATED_SOURCE_MEMBER:'+path)
        raw=subprocess.check_output(['git','cat-file','blob',blob],cwd=root)
        entries[path]=(raw,{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob_sha1':blob})
    required={'research/next009/reproduce.py','research/next009/REPLAY_INPUTS.json',
              'inventions/measurement009/inputs/Net2.inp',
              'evidence/next009/archives/successor-r1.zip',
              'vendor/alpha_claim/protected_exchange.py'}
    if not required<=set(entries):raise ValueError('INCOMPLETE_CAMPAIGN_PACKAGE')
    manifest={'schema':'agi-alpha/next009-source-package/v1','source_commit':commit,
        'source_repository':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab',
        'entries':{p:meta for p,(_,meta) in sorted(entries.items())},
        'scope':'This campaign and pinned runnable dependencies, including lossless archives of all executed campaign evidence. Older campaigns remain at their immutable repository references; no claim to reproduce all historical campaigns.',
        'replay':'python -m research.next009.reproduce --require-clean --output NEW_DIRECTORY'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,(raw,_) in sorted(entries.items()):
            info=zipfile.ZipInfo(PREFIX+path,date_time=(2026,10,30,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        info=zipfile.ZipInfo(PREFIX+'PACKAGE_MANIFEST.json',date_time=(2026,10,30,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        z.writestr(info,json.dumps(manifest,indent=2)+'\n')
    report={'source_commit':commit,'package':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'bytes':output.stat().st_size,'files':len(entries),'uncompressed_bytes':sum(x['bytes'] for _,x in entries.values()),
        'qualification':'BUILD_ONLY; actual public download and clean execution required.'}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.')
    p.add_argument('--commit',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(package(a.root,a.commit,a.output)))
