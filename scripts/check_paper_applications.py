#!/usr/bin/env python3
"""Check catalogue coverage and reviewed source identities, not scientific truth.

No candidate code is imported or executed. Correctness, applicability, optimality,
and deployment still require task-specific independent execution and review.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath

STATUSES = {'partial_runtime', 'standalone', 'guidance_only', 'historical', 'report'}
FIELDS = {'paper', 'pdf_sha256', 'title', 'status', 'pages', 'method',
          'applicability', 'observed_code', 'checks', 'gap', 'next_step'}


def read_json(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('DUPLICATE_JSON_KEY: ' + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def regular(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('RELATIVE_SOURCE_PATH_REQUIRED')
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts or '\\' in relative or str(name) != relative:
        raise ValueError('RELATIVE_SOURCE_PATH_REQUIRED')
    path = root.joinpath(*name.parts)
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('REGULAR_SOURCE_REQUIRED: ' + relative)
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('REGULAR_SOURCE_REQUIRED: ' + relative)
    return path


def check_reference(root, reference):
    if type(reference) is not dict or set(reference) != {'path', 'symbol', 'sha256'}:
        raise ValueError('EXACT_SOURCE_REFERENCE_REQUIRED')
    path = regular(root, reference['path'])
    if path.suffix != '.py':
        raise ValueError('EXECUTABLE_PYTHON_SOURCE_REQUIRED')
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError('REVIEWED_SOURCE_CHANGED: ' + reference['path'])
    symbol = reference['symbol']
    if type(symbol) is not str or not symbol or any(not p.isidentifier() for p in symbol.split('.')):
        raise ValueError('EXECUTABLE_SYMBOL_REQUIRED')
    nodes = ast.parse(path.read_text()).body
    for part in symbol.split('.'):
        matches = [n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part]
        if len(matches) != 1:
            raise ValueError('EXECUTABLE_SYMBOL_NOT_FOUND: ' + symbol)
        nodes = matches[0].body


def validate(root, audit=None):
    root = Path(root).resolve()
    publication = read_json(regular(root, 'docs/research/publication-manifest.json'))
    published = publication['papers']
    catalogue = {row['file']: row['sha256'] for row in published}
    if len(catalogue) != len(published):
        raise ValueError('DUPLICATE_PUBLICATION')
    if audit is None:
        audit = read_json(regular(root, 'docs/harness/PAPER_APPLICATIONS.json'))
    if set(audit) != {'schema', 'reviewed_base', 'scope', 'papers'} or audit['schema'] != 'paper-application-audit/v1':
        raise ValueError('APPLICATION_AUDIT_SCHEMA_REQUIRED')
    rows = audit['papers']
    if type(rows) is not list or len(rows) != len(catalogue):
        raise ValueError('COMPLETE_PUBLICATION_COVERAGE_REQUIRED')
    names = [row.get('paper') for row in rows if type(row) is dict]
    if len(names) != len(set(names)) or set(names) != set(catalogue):
        raise ValueError('COMPLETE_PUBLICATION_COVERAGE_REQUIRED')
    for row in rows:
        if set(row) != FIELDS:
            raise ValueError('EXACT_APPLICATION_FIELDS_REQUIRED')
        for field in FIELDS - {'observed_code', 'checks'}:
            if type(row[field]) is not str or not row[field].strip():
                raise ValueError('EXPLICIT_APPLICATION_SCOPE_REQUIRED: ' + field)
        if row['pdf_sha256'] != catalogue[row['paper']]:
            raise ValueError('PAPER_EDITION_CHANGED: ' + row['paper'])
        if row['status'] not in STATUSES:
            raise ValueError('QUALIFICATION_OR_OPTIMALITY_NOT_ESTABLISHED_BY_COVERAGE')
        for field in ('observed_code', 'checks'):
            if type(row[field]) is not list:
                raise ValueError('SOURCE_REFERENCE_LIST_REQUIRED')
            refs = row[field]
            if len({json.dumps(ref, sort_keys=True) for ref in refs}) != len(refs):
                raise ValueError('DUPLICATE_SOURCE_REFERENCE')
            for reference in refs:
                check_reference(root, reference)
        if row['status'] in {'partial_runtime', 'standalone'} and (not row['observed_code'] or not row['checks']):
            raise ValueError('CITATION_ONLY_IMPLEMENTATION_REFUSED')
        if row['status'] in {'guidance_only', 'historical', 'report'} and (row['observed_code'] or row['checks']):
            raise ValueError('EXPLICIT_PARTIAL_IMPLEMENTATION_STATUS_REQUIRED')
    return {'status': 'COVERAGE_AND_REVIEWED_IDENTITIES_VALID', 'paper_editions': len(rows),
            'scope': 'Traceability only. No execution, correctness, optimality, relevance, profit or deployment certification.',
            'statuses': {status: sum(row['status'] == status for row in rows) for status in sorted(STATUSES)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(validate(args.root), sort_keys=True))


if __name__ == '__main__':
    main()
