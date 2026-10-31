"""Fail-closed source-path preflight for nonconflicting multi-branch composition.

This checks literal source-authority membership, not source semantics, HMAC,
private account custody, or actual merge qualification.
"""
import argparse
import ast
import hashlib
import json
import stat
from pathlib import Path


def source_paths(raw):
    tree = ast.parse(raw.decode('utf-8'))
    assignments = [n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_PATHS' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('EXACT_SOURCE_PATHS_REQUIRED')
    value = ast.literal_eval(assignments[0])
    if not isinstance(value, (tuple, list)) or not value or len(value) > 1000:
        raise ValueError('BOUNDED_SOURCE_PATHS_REQUIRED')
    if any(type(p) is not str or not p.endswith('.py') or not p.isascii() or not p or p.startswith('/') or '\\' in p or any(x in ('', '.', '..') for x in p.split('/')) for p in value):
        raise ValueError('SAFE_SOURCE_PATHS_REQUIRED')
    if len(value) != len(set(value)):
        raise ValueError('DUPLICATE_SOURCE_PATHS_FORBIDDEN')
    return set(value)


def load(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
        raise ValueError('REGULAR_SOURCE_FILE_REQUIRED')
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > 8_000_000:
        raise ValueError('BOUNDED_SOURCE_FILE_REQUIRED')
    raw = path.read_bytes()
    return source_paths(raw), hashlib.sha256(raw).hexdigest()


def preflight(required, candidate=None):
    if not required or len(required) > 16 or len(set(label for label, _ in required)) != len(required):
        raise ValueError('DISTINCT_NONEMPTY_SOURCE_REFERENCES_REQUIRED')
    inventories = {}
    for label, path in required:
        if not label or len(label) > 80 or not label.isascii() or not all(c.isalnum() or c in '-_.' for c in label):
            raise ValueError('SAFE_SOURCE_LABEL_REQUIRED')
        paths, sha = load(path)
        inventories[label] = {'paths': sorted(paths), 'count': len(paths), 'file_sha256': sha}
    union = set().union(*(set(x['paths']) for x in inventories.values()))
    result = {'schema': 'agi-alpha/p0-multibranch-financial-source-preflight/v1',
              'references': inventories, 'required_union_paths': sorted(union), 'required_count': len(union),
              'required_missing_by_reference': {label: sorted(union - set(x['paths'])) for label, x in inventories.items()},
              'scope': 'STATIC_LITERAL_SOURCE_PATH_MEMBERSHIP_ONLY; NOT_RUNTIME_SOURCE_CLOSURE_OR_AUTHENTICATED_FINANCIAL_VALIDATION'}
    if candidate is not None:
        paths, sha = load(candidate)
        missing = sorted(union - paths)
        result['candidate'] = {'file_sha256': sha, 'path_count': len(paths), 'missing_required_paths': missing,
                               'extra_paths': sorted(paths - union), 'accepted': not missing}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--required', action='append', required=True, metavar='LABEL=PATH')
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args()
    inputs = []
    for entry in args.required:
        if '=' not in entry:
            parser.error('Each --required must be LABEL=PATH')
        label, path = entry.split('=', 1)
        inputs.append((label, path))
    result = preflight(inputs, args.candidate)
    print(json.dumps(result, sort_keys=True))
    if args.candidate is None or not result['candidate']['accepted']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
