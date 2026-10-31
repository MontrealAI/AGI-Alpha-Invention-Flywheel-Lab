"""Read-only preflight: retain all already-authoritative financial source paths."""
import argparse
import ast
import json
from pathlib import Path


def source_paths(source):
    tree = ast.parse(source)
    assignments = [n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SOURCE_PATHS' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('EXACT_SOURCE_PATHS_ASSIGNMENT_REQUIRED')
    value = ast.literal_eval(assignments[0])
    if not isinstance(value, (tuple, list)) or not value or any(not isinstance(p, str) or not p.endswith('.py') or p.startswith('/') or '..' in Path(p).parts for p in value) or len(set(value)) != len(value):
        raise ValueError('REGULAR_UNIQUE_SOURCE_PATHS_REQUIRED')
    return set(value)


def check(reference, proposed):
    baseline = source_paths(reference)
    candidate = source_paths(proposed)
    missing = sorted(baseline - candidate)
    return {'accepted': not missing, 'required_paths': len(baseline), 'candidate_paths': len(candidate), 'union_paths': len(baseline | candidate), 'missing_required_paths': missing, 'scope': 'STATIC_SOURCE_PATH_MEMBERSHIP_ONLY; NOT_AUTHENTICATED_ACCOUNT_OR_GIT_MERGE_QUALIFICATION'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--required', type=Path, required=True)
    parser.add_argument('--proposed', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.required.read_text(), args.proposed.read_text())
    print(json.dumps(result, sort_keys=True))
    if not result['accepted']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
