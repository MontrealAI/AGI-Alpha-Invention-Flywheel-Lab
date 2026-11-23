"""Independently check an emitted query against the frozen signed ecCodes reference."""
import argparse
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent / 'products/frontier-omega-alpha/research'
sys.path.insert(0, str(root / 'archive_point'))
from replay import audit, verify

KEY = 'd16ea889e128693e68fe91802e3228849ee4a92f6984f51a12ba4da86ae34a9e'
RECEIPT = root / 'archive_point' / 'evidence' / 'confirmation.json'


def compare(path):
    audit(RECEIPT, KEY)
    with path.open('rb') as handle:
        raw = handle.read(64_001)
    if len(raw) > 64_000:
        raise ValueError('OVERSIZED_RESULT')
    query = json.loads(raw)
    if query.get('state') != 'AVAILABLE':
        return {'state': 'ABSTAIN', 'reason': 'QUERY_DID_NOT_RETURN_A_VALUE'}
    rows = verify(RECEIPT, KEY)['receipt']['cases']
    match = next((r for r in rows if all(query.get('case', {}).get(k) == r['case'].get(k)
                 for k in ('day', 'cycle', 'latitude', 'longitude'))), None)
    if match is None:
        return {'state': 'ABSTAIN', 'reason': 'NO_INDEPENDENT_REGISTERED_MATCH'}
    recorded = match['candidate']
    recovered = query['field']
    matched = (
        query['body_bytes'] <= 393216
        and query['body_bytes'] == query['index_source']['body_bytes'] + recovered['source']['body_bytes']
        and recovered['index'] == match['reference']['index']
        and abs(recovered['temperature_k'] - match['reference']['temperature_k']) <= 1e-10
        and recovered['source']['sha256'] == recorded['source']['sha256']
        and query['index_source']['sha256'] == match['index']['sha256']
    )
    return {'state': 'MATCHED_SIGNED_REFERENCE' if matched else 'REJECTED',
            'candidate_bytes': query['body_bytes'], 'registration': 'archived NOAA GFS 2 m f024',
            'reference': 'ecCodes on the full indexed field',
            'complete_operating_cost': None, 'member_productivity': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', nargs='?', type=Path)
    args = parser.parse_args()
    output = compare(args.result) if args.result else audit(RECEIPT, KEY)
    print(json.dumps(output, sort_keys=True, separators=(',', ':')))
    return 0 if output.get('state', 'MATCHED_SIGNED_REFERENCE') == 'MATCHED_SIGNED_REFERENCE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
