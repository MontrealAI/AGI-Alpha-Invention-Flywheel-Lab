"""Fail-closed public CSV disclosure-boundary receipt; not a governance verdict.

A blank cell is not evidence of inapplicability or noncompliance. A source
hash proves bytes were processed, never that an unauthenticated file is genuine.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

SCHEMA = 'gc-ai-register231/structural-receipt/v1'
UNKNOWN_TOKENS = frozenset({'unknown', 'n/a'})


class Rejected(ValueError):
    pass


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def scan(raw, *, source_url, expected_sha256=None, requested_fields=()):
    if not isinstance(raw, bytes):
        raise Rejected('BYTES_REQUIRED')
    digest = sha(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise Rejected('SOURCE_DIGEST_MISMATCH')
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise Rejected('UTF8_REQUIRED') from e
    try:
        stream = csv.reader(io.StringIO(content, newline=''), strict=True)
        header = next(stream)
        if not header or not any(header):
            raise Rejected('EMPTY_OR_INVALID_HEADER')
        if any(not name or not name.strip() for name in header):
            raise Rejected('EMPTY_HEADER_NAME')
        if len(header) != len(set(header)):
            raise Rejected('DUPLICATE_HEADER')
        width = len(header)
        columns = [{'name': name, 'nonblank': 0, 'empty': 0,
                    'whitespace_only': 0, 'literal_unknown': 0, 'literal_na': 0}
                   for name in header]
        seen = {}
        n = 0
        for record in stream:
            if len(record) != width:
                raise Rejected('ROW_WIDTH_MISMATCH:' + str(n + 1))
            n += 1
            t = tuple(record)
            seen[t] = seen.get(t, 0) + 1
            for i, cell in enumerate(record):
                c = columns[i]
                if cell == '':
                    c['empty'] += 1
                elif not cell.strip():
                    c['whitespace_only'] += 1
                else:
                    c['nonblank'] += 1
                    token = cell.strip().casefold()
                    if token == 'unknown':
                        c['literal_unknown'] += 1
                    elif token == 'n/a':
                        c['literal_na'] += 1
        if n == 0:
            raise Rejected('EMPTY_DATASET')
    except (csv.Error, StopIteration) as e:
        raise Rejected('INVALID_CSV') from e
    if not isinstance(source_url, str) or not source_url.startswith('https://'):
        raise Rejected('HTTPS_SOURCE_URL_REQUIRED')
    if len(set(requested_fields)) != len(requested_fields):
        raise Rejected('DUPLICATE_REQUESTED_FIELD')
    field_checks = [{'exact_field': f, 'status': ('PRESENT_IN_HEADER' if f in header else 'SCHEMA_FIELD_ABSENT')}
                    for f in requested_fields]
    duplicates = [count for count in seen.values() if count > 1]
    report = {
        'schema': SCHEMA,
        'source_url_claim': source_url,
        'provenance': 'CALLER_SUPPLIED_BYTES_NOT_AUTHENTICATED',
        'source_sha256': digest,
        'source_bytes': len(raw),
        'row_count': n,
        'column_count': width,
        'columns': columns,
        'requested_exact_fields': field_checks,
        'exact_duplicate_row_groups': len(duplicates),
        'extra_duplicate_row_instances': sum(x - 1 for x in duplicates),
        'declared_value_semantics': 'EMPTY_AND_LITERAL_TOKENS_ONLY_NO_CODEBOOK',
        'system_risk_impact_compliance_claim': 'NONE',
        'warnings': [
            'A blank or missing cell is not proof of not-applicable, compliant, low-risk or no use.',
            'An exact repeated row is not proof of a duplicated real AI system.',
            'Source hashes establish byte identity, not authenticity or governance meaning.',
        ],
    }
    report['report_sha256'] = sha(canon(report))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv_file', type=Path)
    p.add_argument('--source-url', required=True)
    p.add_argument('--expect-sha256')
    p.add_argument('--exact-field', action='append', default=[])
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = scan(args.csv_file.read_bytes(), source_url=args.source_url,
                      expected_sha256=args.expect_sha256,
                      requested_fields=args.exact_field)
        with args.output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write('\n')
        print(f"PROCESSED:{result['row_count']} rows / {result['column_count']} fields / {result['source_sha256']}")
        return 0
    except (Rejected, OSError, ValueError) as e:
        print('GC_REGISTER231_REJECTED:' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
