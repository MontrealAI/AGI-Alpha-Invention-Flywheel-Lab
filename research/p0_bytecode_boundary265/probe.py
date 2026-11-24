"""P0-265: key-free development probe, not a native audit."""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import resource
import subprocess
import sys
import tempfile
import time


def source_inventory(root):
    root = Path(root).absolute()
    files = {}
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root)
        if any(part in {'__pycache__', '.git', '.venv', 'historical-source-versions'} for part in relative.parts):
            continue
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('HISTORICAL_SOURCE_SYMLINK_REFUSED')
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files or len(files) > 4000:
        raise ValueError('BOUNDED_PINNED_HISTORICAL_SOURCE_REQUIRED')
    return files


def main():
    start = time.monotonic()
    cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    with tempfile.TemporaryDirectory(prefix='p0265-') as td:
        base = Path(td)
        root = base / 'source'
        root.mkdir()
        module = root / 'fixture265.py'
        module.write_text('VALUE = "OLD"\n')
        stamp = 1700000000
        os.utime(module, (stamp, stamp))
        py_compile.compile(str(module), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        module.write_text('VALUE = "NEW"\n')
        os.utime(module, (stamp, stamp))
        pinned = source_inventory(root)
        prefix = base / 'fresh-cache'
        prefix.mkdir()
        env = {'PATH': os.defpath, 'HOME': td, 'LANG': 'C.UTF-8',
               'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
        code = 'import sys;sys.path.insert(0,sys.argv[1]);import fixture265;print(fixture265.VALUE)'
        def run(flags, program=code):
            p = subprocess.run([sys.executable, *flags, '-c', program, str(root)],
                               cwd=root, env=env, capture_output=True, text=True, check=True)
            return p.stdout.strip()
        observed = {}
        observed['ordinary'] = run([])
        observed['no_write'] = run(['-B'])
        observed['isolated_no_write'] = run(['-I', '-S', '-B'])
        observed['fresh_cache_prefix'] = run(['-I', '-S', '-B', '-X', 'pycache_prefix='+str(prefix)])
        nested = ('import subprocess,sys;print(subprocess.check_output('
                  '[sys.executable,"-B","-c",'+repr(code)+',sys.argv[1]],text=True).strip())')
        observed['nested_prefix_not_inherited'] = run(['-I','-S','-B','-X','pycache_prefix='+str(prefix)], nested)
        for p in (root/'__pycache__').glob('*.pyc'):
            p.unlink()
        observed['clean_source'] = run(['-I','-S','-B'])
        expected = {'ordinary':'OLD','no_write':'OLD','isolated_no_write':'OLD',
                    'fresh_cache_prefix':'NEW','nested_prefix_not_inherited':'OLD','clean_source':'NEW'}
        checks = {k: observed[k] == v for k,v in expected.items()}
        checks['owner_inventory_equal'] = source_inventory(root) == pinned
        checks['fresh_prefix_stays_empty'] = not any(prefix.rglob('*'))
    end_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'scope':'synthetic CPython timestamp-cache development probe',
               'python':sys.version.split()[0], 'observed':observed,'checks':checks,
               'accepted':all(checks.values()),'actual_billing_usd':None,
               'wall_seconds':time.monotonic()-start,
               'waited_child_cpu_seconds':end_cpu.ru_utime+end_cpu.ru_stime-cpu.ru_utime-cpu.ru_stime}
    print(json.dumps(receipt,sort_keys=True))
    return 0 if receipt['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
