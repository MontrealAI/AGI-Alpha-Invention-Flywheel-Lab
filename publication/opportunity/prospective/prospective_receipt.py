"""Verify a local prospective receipt against the official bytes actually observed."""

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import sys


def sha(raw):
    return sha256(raw).hexdigest()


def receipt(root):
    registration_raw = (root / 'registration.json').read_bytes()
    registration = json.loads(registration_raw)
    trace_raw = (root / 'observations.jsonl').read_bytes()
    trace = [json.loads(line) for line in trace_raw.splitlines()]
    successful = []
    matching = []
    failed = []
    for index, row in enumerate(trace):
        assert row['sequence'] == index
        assert row['requested_at_utc'] >= registration['frozen_at_utc']
        if 'error' in row:
            failed.append({key: row[key] for key in ('sequence', 'requested_at_utc', 'error')})
            continue
        assert row['acquired_at_utc'] >= row['requested_at_utc']
        body = (root / f"{row['sha256']}.json").read_bytes()
        assert sha(body) == row['sha256'] and len(body) == row['bytes']
        source = json.loads(body)
        assert source['tag_name'] == registration['tag'] and source['prerelease'] is True
        assert row['total_assets'] == len(source['assets'])
        hits = [a for a in source['assets'] if a['name'] == registration['asset'] and a['state'] == 'uploaded'
                and type(a['size']) is int and a['size'] > 0 and isinstance(a.get('digest'), str)
                and a['digest'].startswith('sha256:') and len(a['digest']) == 71
                and all(c in '0123456789abcdef' for c in a['digest'][7:])]
        assert len(hits) <= 1
        assert row['competent_baseline_witnessed'] == bool(hits)
        assert (row['retained_result'] == 'DOCUMENTED_BY_CUTOFF') == bool(hits)
        if hits:
            assert row['witness'] == {key: hits[0][key] for key in row['witness']}
            matching.append(row)
        successful.append(row)
    assert trace and successful
    assert all(a['requested_at_utc'] < b['requested_at_utc'] for a, b in zip(trace, trace[1:]))
    seen = matching[0] if matching else None
    baseline = successful[0]
    last = successful[-1]
    absent_before_seen = [row for row in successful if seen and row['sequence'] < seen['sequence']]
    interval_censoring = (
        {'kind': 'INTERVAL_CENSORED',
         'last_observed_absence_utc': absent_before_seen[-1]['acquired_at_utc'],
         'first_observed_presence_utc': seen['acquired_at_utc']} if absent_before_seen else
        {'kind': 'LEFT_CENSORED', 'first_observed_presence_utc': seen['acquired_at_utc']} if seen else
        {'kind': 'RIGHT_CENSORED', 'last_observed_absence_utc': last['acquired_at_utc']}
    )
    def ms(k):
        return str(Decimal(median(row[k] for row in successful)) / 1_000_000)
    return {'registration': registration, 'registration_sha256': sha(registration_raw),
            'trace_sha256': sha(trace_raw), 'public_observations': len(trace), 'successful': len(successful),
            'failed': len(failed), 'failed_observations': failed,
            'total_response_bytes': sum(row['bytes'] for row in successful),
            'first_observed_at_utc': baseline['acquired_at_utc'], 'baseline_asset_witnessed': baseline['competent_baseline_witnessed'],
            'last_verified_at_utc': last['acquired_at_utc'], 'event': seen and seen['witness'],
            'verified_event_observed_at_utc': seen and seen['acquired_at_utc'],
            'artifact_registry_observability': interval_censoring,
            'tag_as_asset_rejections': sum(row['tag_only_as_artifact'] == 'INSUFFICIENT_EVIDENCE_ROLE'
                                           for row in successful),
            'observation_disposition': ('LATE_BASELINE_ALREADY_WITNESSED' if baseline['competent_baseline_witnessed']
                                        else 'SAME_SNAPSHOT_DETECTION' if seen else 'RIGHT_CENSORED_DURING_OBSERVATION'),
            'pipeline_lead_s': 0 if seen and not baseline['competent_baseline_witnessed'] else None,
            'median_request_ms': ms('fetch_ns'), 'median_ordinary_check_ms': ms('competent_baseline_ns'),
            'median_retained_adjudication_ms': ms('retained_stage_ns'),
            'limits': 'Both methods consume the same official public samples. This measures exact artifact attestation and scoped verification in one staged release, without proving global onset, independent acquisition lead, stable production operation or economics.'}


if __name__ == '__main__':
    print(json.dumps(receipt(Path(sys.argv[1])), indent=2, ensure_ascii=False, sort_keys=True))
