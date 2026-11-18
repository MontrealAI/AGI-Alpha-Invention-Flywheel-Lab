"""Issue dated early-supernova candidate notices and independently verify their first later test."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from evolution_trials.verify import decide, from_utc, require_match, roster_for
from invention.early_survey.acquire import MAX_TARGETS, select_targets
from invention.evolution.alert import csv_bytes, evaluate_cohort, json_bytes, julian

SELECTION = '2026-10-18T00:00:00Z'
START = '2026-10-25T00:00:00Z'
END = '2026-11-01T00:00:00Z'
INDEX = '80829974c96cfae41ff587d5fad038229d05e50ae04ec99d80accd01c5b6fe7e'
REFERENCE_INDEX = 'e5740fff884ba87a3779b373e2ed09e58d37fcd177c467e2c0ae22037c057ddb'


def load_document(raw, digest):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('The public archive input differs from its recorded digest')
    return json.loads(raw, parse_float=Decimal)


def response(folder, receipt):
    raw = gzip.decompress((folder / receipt['file']).read_bytes())
    rows = load_document(raw, receipt['sha256'])
    if len(raw) != receipt['bytes'] or len(rows) != receipt['rows'] or receipt['status'] != 200:
        raise ValueError('Archive response does not reproduce its acquisition receipt')
    return rows


def load_objects(folder, requests, targets):
    rows, requested = [], []
    for receipt in requests:
        batch = parse_qs(urlparse(receipt['url']).query)['objectId'][0].split(',')
        requested.extend(batch)
        these = response(folder, receipt)
        if any(row['i:objectId'] not in batch for row in these):
            raise ValueError('An object response contains a target outside the requested batch')
        rows.extend(these)
    if sorted(requested) != targets or len({r['i:candid'] for r in rows}) != len(rows):
        raise ValueError('Archive requests must cover the selected roster exactly, with unique detections')
    return rows


def sources(folder):
    index = load_document((folder / 'index.json').read_bytes(), INDEX)
    ref_index = load_document((folder / 'reference-index.json').read_bytes(), REFERENCE_INDEX)
    classes = response(folder, index['requests'][0])
    targets = select_targets(classes)
    require_match(roster_for(classes, from_utc(SELECTION), from_utc(START), MAX_TARGETS), targets)
    require_match(index['selected_targets'], targets)
    objects = load_objects(folder, index['requests'][1:], targets)
    refs = {r['i:candid']: r for r in load_objects(folder, ref_index, targets)}
    return targets, objects, refs


def broker_and_reference(alert, by_id, refs):
    ids = [int(alert[k]['candid']) for k in ('baseline', 'trigger', 'followup') if alert[k]]
    ref_ids = []
    for cid in ids:
        measurement, ref = by_id[cid], refs.get(cid, {})
        if ref and any(measurement[k] != ref[k] for k in ('i:objectId', 'i:field', 'i:rcid')):
            raise ValueError('Separate reference lookup disagrees on the identity of a detection')
        rfid = ref.get('i:rfid')
        ref_ids.append(str(rfid) if type(rfid) is int and rfid > 0 else None)
    trigger = by_id[ids[1]]
    def number(field):
        value = trigger.get(field)
        return float(value) if type(value) in (Decimal, int) and Decimal(value).is_finite() else None
    status = 'unknown' if None in ref_ids else ('matched' if len(set(ref_ids)) == 1 else 'changed')
    alert['reference_image'] = {'status': status, 'rfids': ref_ids}
    # Preserve the broker's observed baseline and use of an upper limit alongside its rate.
    # Missing metadata stays null. No unknown rate enters the registered issue rule.
    alert['broker_at_trigger'] = {'rate_mag_per_day': number('d:mag_rate'),
                                  'sigma_mag_per_day': number('d:sigma_rate'),
                                  'gap_days': number('d:delta_time'), 'from_upper': trigger.get('d:from_upper')}


def calculate(as_of=None, *, folder=HERE / 'sources'):
    as_of = END if as_of is None else as_of
    cutoff = julian(as_of)
    result = {'scope': 'paired historical early-supernova candidate archive study', 'as_of_utc': as_of,
              'cohorts': [], 'summary': {}}
    if cutoff < julian(START):
        return result
    targets, rows, refs = sources(folder)
    public = [r for r in rows if type(r['i:programid']) is int and r['i:programid'] == 1]
    by_id = {r['i:candid']: r for r in public}
    for key, lookback in [('early_cold', 0), ('early_warm', 7)]:
        cohort = evaluate_cohort(key, targets, public, julian(START), julian(END), cutoff,
                                 baseline_lookback_days=lookback, require_same_detector=True)
        direct = decide(targets, public, from_utc(START), from_utc(as_of),
                        baseline_lookback_days=lookback, reference_fields=('i:field', 'i:rcid'))
        require_match(direct, {field: cohort[field] for field in direct})
        for alert in cohort['alerts']:
            broker_and_reference(alert, by_id, refs)
        cohort['source_sha256'] = {'archive_index': INDEX, 'reference_index': REFERENCE_INDEX}
        result['cohorts'].append(cohort)
        result['summary'][key] = dict(comparisons=sum(r['comparisons'] for r in cohort['coverage']),
                                      alerts=len(cohort['alerts']), **Counter(r['status'] for r in cohort['alerts']))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', help='UTC event-time cutoff, ending in Z')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--out', type=Path, help='Create a new dated JSON decision')
    group.add_argument('--csv', type=Path, help='Create a new action queue')
    group.add_argument('--check', action='store_true', help='Reconstruct and compare the two final delivered files')
    args = parser.parse_args()
    if args.check and args.as_of not in (None, END):
        parser.error('Frozen delivery is the November 1 UTC closing decision')
    result = calculate(args.as_of)
    if args.check:
        if json_bytes(result) != (HERE / 'RESULT.json').read_bytes() or csv_bytes(result) != (HERE / 'worklist.csv').read_bytes():
            raise ValueError('The registered public decision differs from the reconstructed queue')
        print(json.dumps(result['summary']))
    elif args.out or args.csv:
        with (args.out or args.csv).open('xb') as output:
            output.write(csv_bytes(result) if args.csv else json_bytes(result))
    else:
        sys.stdout.buffer.write(json_bytes(result))


if __name__ == '__main__':
    main()
