from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess

MANIFEST_PATH = Path(__file__).with_name('SOURCE_MANIFEST.json')
WAVE_INPUT = 'tasks/19_wave/problem/input/testdata/08.json'
WAVE_PROGRAM = 'tasks/19_wave/problem/input/program'
GROCERY_PROGRAM = 'tasks/23_dynamic_grocery/problem/input/program'
GROCERY_PUBLIC = 'tasks/23_dynamic_grocery/public/rolling_input'
GROCERY_PRIVATE = 'tasks/23_dynamic_grocery/public/input/order_confirmations.csv'


def manifest():
    return json.loads(MANIFEST_PATH.read_text())


def source_path(root, name):
    base = Path(root).absolute()
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or str(rel) != name:
        raise ValueError('OPERATIONAL075_SAFE_SOURCE_PATH_REQUIRED')
    target = base / name
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError('OPERATIONAL075_REGULAR_SOURCE_REQUIRED')
    return target


def verify_source(root):
    root = Path(root).absolute()
    frozen = manifest()
    if frozen['repository'] != 'https://github.com/NineAbyss/OR-License' or frozen['commit'] != '2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47':
        raise ValueError('OPERATIONAL075_UPSTREAM_IDENTITY_CHANGED')
    checked = {}
    permitted = {'__future__', 'typing', 'argparse', 'json', 'collections', 'math', 'sys', 'pathlib', 'copy', 'csv', '_wave_engine', '_wave_objective', '_wave_verifier', '_grocery_judge', '_grocery_rolling'}
    for row in frozen['files']:
        name = row['path']; path = source_path(root, name)
        if not path.is_file():
            raise ValueError('OPERATIONAL075_SOURCE_FILE_MISSING:' + name)
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('OPERATIONAL075_SOURCE_BYTES_CHANGED:' + name)
        checked[name] = row['sha256']
        if name.endswith('.py'):
            imports = []
            tree = ast.parse(data.decode('utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import): imports.extend(v.name for v in node.names)
                elif isinstance(node, ast.ImportFrom): imports.append(node.module or '')
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'eval', 'exec', '__import__'}:
                    raise ValueError('OPERATIONAL075_DYNAMIC_UPSTREAM_EXECUTION_REFUSED')
            if set(imports) - permitted or sorted(set(imports)) != frozen['offline_client_imports'][name]:
                raise ValueError('OPERATIONAL075_OFFLINE_CLIENT_IMPORT_CHANGED:' + name)
    return {'accepted': True, 'upstream_commit': frozen['commit'], 'source_manifest_sha256': hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(), 'files_checked': len(checked), 'source_hashes': checked, 'scope': 'Exact public input and offline original client bytes; no model integration executed.'}


def fetch(output):
    destination = Path(output).absolute()
    if destination.exists():
        receipt = verify_source(destination)
        os.chmod(destination, 0o700)
        return receipt
    destination.mkdir(parents=True, mode=0o700)
    frozen = manifest()
    commands = [
        ['git', 'init', str(destination)],
        ['git', '-C', str(destination), 'remote', 'add', 'origin', frozen['repository'] + '.git'],
        ['git', '-C', str(destination), 'config', 'core.sparseCheckout', 'true'],
        ['git', '-C', str(destination), 'fetch', '--depth=1', '--filter=blob:none', 'origin', frozen['commit']],
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sparse = destination / '.git/info/sparse-checkout'
    sparse.parent.mkdir(parents=True, exist_ok=True)
    sparse.write_text(''.join('/' + row['path'] + '\n' for row in frozen['files']))
    subprocess.run(['git', '-C', str(destination), 'checkout', '--detach', 'FETCH_HEAD'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.chmod(destination, 0o700)
    return verify_source(destination)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=('fetch', 'verify')); parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    result = fetch(args.output) if args.command == 'fetch' else verify_source(args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
