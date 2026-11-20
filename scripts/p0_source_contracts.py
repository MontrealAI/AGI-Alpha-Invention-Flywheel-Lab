"""Read-only source/API composition preflight. Never accesses accounts or signing material.

This is a NEGATIVE integration instrument, not an authenticated source upgrade.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

TARGET = 'f0987aa48d5c9136b28540f54eabf5367e63bbe6'
OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
PATHS = {
    'adaptive_enterprise/account.py': ('bebc298d79e5b8928ab1070abc6943702f603c65', 'd8b3c159af21519c1bcc3c2cde0dc8c572ca1122'),
    'connected_enterprise/engine.py': ('a18c8c1bf9f8baf795e9c78d1a56ffe5b501afdd', '94550f078a6bb0ea8bda95682bdf3c6472c9749a'),
    'connected_enterprise/finance.py': ('02c81396ad90dbd31efbfeeb1a973fbbdb428bb4', 'c01e5cd97fb32b3e5fcd5cea190424d8f4f5d5ec'),
    'connected_enterprise/runner.py': ('02aebd24b9c1dc1e2d4bea40f387acbf1312829e', '020fcf81500c8e8843594d0bfd5d81dd815a151c'),
    'connected_enterprise/verify.py': ('08ff07f5d13ca4332edfa1785b49f142f071fc8a', '2975e645e7b8f8fee16576a339f2f09e221ebd41'),
}


def git(*arguments: str) -> str:
    return subprocess.run(['git', *arguments], check=True, text=True,
                          capture_output=True).stdout.strip()


def functions(source: str):
    tree = ast.parse(source)
    return tree, {n.name: n for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def mismatch_reason(call: ast.Call, definition) -> str | None:
    args = definition.args
    positional = [n.arg for n in args.posonlyargs + args.args]
    keyword_only = [n.arg for n in args.kwonlyargs]
    if any(isinstance(x, ast.Starred) for x in call.args) or any(k.arg is None for k in call.keywords):
        return None  # unpacking is statically indeterminate; do not invent incompatibility
    npos = len(call.args)
    if npos > len(positional) and args.vararg is None:
        return f'positional_{npos}_exceeds_{len(positional)}'
    names = [k.arg for k in call.keywords]
    if len(names) != len(set(names)):
        return 'duplicate_keyword'
    for name in names:
        if name not in positional[len(args.posonlyargs):] + keyword_only and args.kwarg is None:
            return 'unsupported_keyword_' + name
        if name in positional[:npos]:
            return 'repeated_positional_keyword_' + name
    required_pos = len(positional) - len(args.defaults)
    supplied = set(positional[:npos]) | set(names)
    for name in positional[:required_pos]:
        if name not in supplied:
            return 'missing_required_' + name
    for name, default in zip(keyword_only, args.kw_defaults):
        if default is None and name not in supplied:
            return 'missing_required_kwonly_' + name
    return None


def assess_pair(target_text: str, owner_text: str, path: str) -> dict:
    target_tree, target_defs = functions(target_text)
    _, owner_defs = functions(owner_text)
    removed = sorted(set(target_defs) - set(owner_defs))
    hazards = []
    for node in ast.walk(target_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in target_defs or name not in owner_defs:
            continue
        reason = mismatch_reason(node, owner_defs[name])
        if reason and mismatch_reason(node, target_defs[name]) is None:
            hazards.append({'callee': name, 'line': node.lineno, 'reason': reason})
    return {'path': path, 'target_only_functions': removed,
            'target_only_nonprivate': [x for x in removed if not x.startswith('_')],
            'retained_target_call_to_owner_function_hazards': hazards}


def prove(target: str, owner: str) -> dict:
    if (target, owner) != (TARGET, OWNER):
        raise ValueError('EXACT_PINNED_REVISIONS_REQUIRED')
    reports = []
    for path, expected in PATHS.items():
        actual = tuple(git('rev-parse', f'{ref}:{path}') for ref in (target, owner))
        if actual != expected:
            raise ValueError('PINNED_BLOB_MISMATCH:' + path)
        report = assess_pair(git('show', f'{target}:{path}'),
                             git('show', f'{owner}:{path}'), path)
        report['target_blob'], report['owner_blob'] = actual
        reports.append(report)
    return {
        'schema': 'agi-alpha/p0-source-api-negative195/v1',
        'scope': 'public_source_only_no_private_account_or_authority',
        'target_commit': target, 'owner_commit': owner,
        'status': 'BLOCKED_UNQUALIFIED_COMPOSITION', 'reports': reports,
        'limitations': [
            'Static AST hazards are not proof of all runtime semantic conflicts or safety',
            'Owner snapshot is historical, not proof of present private task state',
            'No signed state, signer, current writer, liability or queue was read',
            'No permission for merge, release or account transition follows from this test',
        ],
    }


def self_test() -> None:
    target = ('def source_identity(root,manifest=None):return root\n'
              'class A:\n def f(self):return source_identity(self.root,self.manifest)\n'
              'def fresh_account_config(x):return x\n')
    old = 'def source_identity(root):return root\n'
    r = assess_pair(target, old, 'fixture.py')
    assert r['target_only_nonprivate'] == ['fresh_account_config'], r
    assert any(x['callee'] == 'source_identity'
               and x['reason'] == 'positional_2_exceeds_1'
               for x in r['retained_target_call_to_owner_function_hazards']), r
    corrected = ('def source_identity(root,manifest=None):return root\n'
                 'def fresh_account_config(x):return x\n')
    rr = assess_pair(target, corrected, 'fixture.py')
    assert not rr['target_only_functions'] and not rr['retained_target_call_to_owner_function_hazards'], rr
    target_kw = ('def f(a,*,required=False):return a\n'
                 'def g():return f(1,required=True)\n')
    owner_kw = 'def f(a):return a\n'
    assert assess_pair(target_kw, owner_kw, 'fixture2.py')['retained_target_call_to_owner_function_hazards'][0]['reason'] == 'unsupported_keyword_required'
    print('SELF_TEST_PASS: positional, keyword, removed-function, repaired controls')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--target', default=TARGET)
    p.add_argument('--owner', default=OWNER)
    p.add_argument('--output', type=Path)
    p.add_argument('--expect-blocked', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    result = prove(args.target, args.owner)
    if args.output:
        if args.output.exists():
            raise FileExistsError('NEW_OUTPUT_PATH_REQUIRED')
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    if args.expect_blocked:
        reports = {r['path']: r for r in result['reports']}
        def hazard(path, name, reason):
            return any(x['callee'] == name and x['reason'] == reason
                       for x in reports[path]['retained_target_call_to_owner_function_hazards'])
        witnesses = [
            hazard('connected_enterprise/finance.py', 'source_identity', 'positional_2_exceeds_1'),
            hazard('connected_enterprise/verify.py', '_check_cost_semantics',
                   'unsupported_keyword_startup_evaluation_required'),
            'fresh_account_config' in reports['connected_enterprise/engine.py']['target_only_functions'],
            '_offer_menu' in reports['connected_enterprise/engine.py']['target_only_functions'],
            '_service_manifest' in reports['connected_enterprise/runner.py']['target_only_functions'],
        ]
        if not all(witnesses):
            raise ValueError('REGISTERED_NEGATIVE_WITNESSES_NOT_REPRODUCED:' + str(witnesses))
        print('PINNED_NEGATIVE_WITNESSES_REPRODUCED: P0 REMAINS BLOCKED')
        return 0
    return 2  # Fail closed: an unsafe composition must not be certified.


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, subprocess.CalledProcessError, OSError, SyntaxError) as exc:
        print('P0_SOURCE_PREFLIGHT_FAILED_CLOSED:' + str(exc), file=sys.stderr)
        sys.exit(1)
