"""P0-257 key-free dependency feasibility, not a native signer launcher."""
import base64
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time

PACKAGES = ('cryptography', 'cffi', 'pycparser')
EXPECTED = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
CODE = '''import sys, importlib.util, json
sys.path.extend(sys.argv[1:])
from cryptography.hazmat.primitives import hashes
h=hashes.Hash(hashes.SHA256()); h.update(b'abc')
print(json.dumps({'digest':h.finalize().hex(),'unrelated':importlib.util.find_spec('p0257_unrelated') is not None,'isolated':bool(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode)}))
'''

def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def regular(path):
    return not any(p.is_symlink() for p in (path, *path.parents)) and stat.S_ISREG(path.stat().st_mode)


def installed_manifest():
    files, versions, origins = {}, {}, {}
    for name in PACKAGES:
        d = metadata.distribution(name)
        versions[name] = d.version
        for item in d.files or ():
            rel = Path(str(item))
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('UNSAFE_RECORD_PATH')
            if '__pycache__' in rel.parts or rel.suffix in ('.pyc', '.pyo') or any(p.endswith('.dist-info') for p in rel.parts):
                continue
            path = Path(d.locate_file(item)).absolute()
            if not regular(path) or not item.hash or item.hash.mode != 'sha256':
                raise ValueError('REGULAR_HASHED_RECORD_REQUIRED')
            raw = path.read_bytes()
            if base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=') != item.hash.value:
                raise ValueError('RECORD_HASH_MISMATCH')
            key = rel.as_posix()
            if key in files:
                raise ValueError('DUPLICATE_RECORD_MEMBER')
            files[key], origins[key] = sha(raw), path
    return files, versions, origins


def verify(root, files):
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('SYMLINK_MEMBER')
        if path.is_dir():
            continue
        if not regular(path):
            raise ValueError('NONREGULAR_MEMBER')
        name = path.relative_to(root).as_posix()
        actual.add(name)
        if name not in files or sha(path.read_bytes()) != files[name]:
            raise ValueError('MEMBER_HASH_OR_IDENTITY_CHANGED')
    if actual != set(files):
        raise ValueError('CLOSURE_MEMBERSHIP_CHANGED')


def stage(root, files, origins):
    root.mkdir(mode=0o700)
    for name, expected in files.items():
        raw = origins[name].read_bytes()
        if sha(raw) != expected:
            raise ValueError('SOURCE_CHANGED_AFTER_FREEZE')
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    verify(root, files)


def child(paths):
    return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', CODE, *map(str, paths)],
                          capture_output=True, text=True, env={'LANG':'C', 'LC_ALL':'C'}, timeout=30)


def main():
    start, cpu = time.monotonic(), resource.getrusage(resource.RUSAGE_CHILDREN)
    files, versions, origins = installed_manifest()
    frozen = {'files': files, 'versions': versions, 'python': sys.version, 'interpreter_sha256': sha(Path(sys.executable).resolve().read_bytes())}
    out = {'protocol_commit':'476ab64f63bc013b65db2faa82b4da4038ac0ff3', 'manifest_sha256':sha(encoded(frozen)),
           'source_sha256':sha(Path(__file__).read_bytes()), 'versions':versions, 'python':sys.version,
           'interpreter_sha256':frozen['interpreter_sha256'], 'file_count':len(files), 'cases':[]}
    with tempfile.TemporaryDirectory(prefix='p0257-') as tmp:
        base = Path(tmp)
        (base/'manifest.json').write_bytes(encoded(frozen))
        root = base/'deps'
        stage(root, files, origins)
        result = child([])
        out['cases'].append({'id':1,'pass':result.returncode!=0 and 'ModuleNotFoundError' in result.stderr and 'cryptography' in result.stderr,'exit':result.returncode})
        verify(root, files)
        result = child([root])
        parsed = json.loads(result.stdout) if result.returncode == 0 else {}
        out['cases'].append({'id':2,'pass':parsed=={'digest':EXPECTED,'unrelated':False,'isolated':True},'exit':result.returncode,'result':parsed})
        member = root / 'cryptography/__init__.py'
        original = member.read_bytes()
        def rejected(case):
            try:
                verify(root, files)
            except ValueError as e:
                out['cases'].append({'id':case,'pass':True,'rejection':str(e),'child_launched':False})
            else:
                out['cases'].append({'id':case,'pass':False,'child_launched':False})
        member.write_bytes(original+b'\n# fixture change\n')
        rejected(3)
        member.write_bytes(original)
        extra = root/'p0257_unrelated.py'
        extra.write_text('MARKER = 257\n')
        rejected(4)
        extra.unlink()
        member.unlink()
        member.symlink_to(origins['cryptography/__init__.py'])
        rejected(5)
        member.unlink()
        member.write_bytes(original)
        verify(root, files)
        ambient = base/'ambient'
        ambient.mkdir()
        (ambient/'p0257_unrelated.py').write_text('MARKER = 257\n')
        result = child([metadata.distribution('cryptography').locate_file(''),ambient])
        parsed = json.loads(result.stdout) if result.returncode == 0 else {}
        out['cases'].append({'id':6,'pass':parsed=={'digest':EXPECTED,'unrelated':True,'isolated':True} and out['cases'][1]['pass'],'exit':result.returncode,'result':parsed})
        out['staged_bytes'] = sum((root/name).stat().st_size for name in files)
        out['manifest'] = frozen
    end = resource.getrusage(resource.RUSAGE_CHILDREN)
    out['waited_child_cpu_seconds'] = (end.ru_utime+end.ru_stime)-(cpu.ru_utime+cpu.ru_stime)
    out['wall_seconds'] = time.monotonic()-start
    out['passed'] = sum(x['pass'] for x in out['cases'])
    out['native_finance_qualified'] = False
    out['actual_billing_usd'] = None
    print(json.dumps(out,sort_keys=True,indent=2))
    return 0 if out['passed']==6 else 1

if __name__ == '__main__':
    raise SystemExit(main())
