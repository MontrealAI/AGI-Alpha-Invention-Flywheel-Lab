"""Independent source/cohort audit; money remains explicitly simulated."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from commercial.service_verifier import audit_delivery


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def _bound(root, relative, expected):
    path = Path(relative)
    if not isinstance(relative, str) or path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('RELATIVE_SOURCE_REQUIRED')
    full = Path(root) / path
    if full.is_symlink() or any(p.is_symlink() for p in full.parents):
        raise ValueError('SYMLINK_SOURCE_REFUSED')
    raw = full.read_bytes()
    if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('SOURCE_BYTE_IDENTITY_MISMATCH')
    return raw


def audit_service(root, manifest):
    if not isinstance(manifest, dict) or manifest.get('scope') != 'SYNTHETIC_PUBLIC_WORKLOAD':
        raise ValueError('SERVICE_SCOPE_REQUIRED')
    protocol = _json(_bound(root, manifest['source_freeze'], manifest['source_freeze_sha256']))
    if protocol.get('scope') != manifest['scope'] or protocol.get('frozen_before_execution') is not True:
        raise ValueError('FROZEN_PROTOCOL_REQUIRED')
    for path, expected in protocol['source_hashes'].items():
        _bound(root, path, expected)
    jobs, attempts = manifest['jobs'], manifest['attempts']
    if not isinstance(jobs, list) or not isinstance(attempts, list) or not jobs or not attempts:
        raise ValueError('WHOLE_COHORT_REQUIRED')
    observed, order_by_id, accepted = set(), {}, 0
    for job in jobs:
        if job['id'] in observed or job.get('scope') != manifest['scope'] or type(job.get('accepted')) is not bool:
            raise ValueError('UNIQUE_SCOPED_COHORT_REQUIRED')
        observed.add(job['id'])
        order = _json(_bound(root, job['input'], job['input_sha256']))
        artifact = _json(_bound(root, job['artifact'], job['artifact_sha256']))
        receipt = _json(_bound(root, job['receipt'], job['receipt_sha256']))
        fresh = audit_delivery(order, artifact)
        if order.get('order_id') != job['id'] or fresh['accepted'] is not job['accepted']:
            raise ValueError('FRESH_SERVICE_ACCEPTANCE_MISMATCH')
        if any(receipt.get(key) != value for key, value in fresh.items()):
            raise ValueError('STORED_ACCEPTANCE_RECEIPT_MISMATCH')
        if receipt.get('artifact_sha256') != job['artifact_sha256'] or receipt.get('input_file_sha256') != job['input_sha256']:
            raise ValueError('RECEIPT_FILE_IDENTITY_MISMATCH')
        if receipt.get('checker_source_sha256') != protocol['source_hashes']['commercial/service_verifier.py']:
            raise ValueError('CHECKER_SOURCE_MISMATCH')
        if type(job.get('human_intervention_seconds')) not in (int, float) or job['human_intervention_seconds'] != 0:
            raise ValueError('STRICT_AUTONOMY_SCOPE_REQUIRED')
        order_by_id[job['id']] = order
        accepted += int(fresh['accepted'])
    for key, expected in [('orders_count', len(jobs)), ('accepted_count', accepted), ('rejected_count', len(jobs) - accepted)]:
        if type(manifest.get(key)) is not int or manifest[key] != expected:
            raise ValueError('COHORT_' + key.upper() + '_MISMATCH')
    seen_attempts, covered, measured_cpu, unmetered = set(), set(), 0.0, []
    for attempt in attempts:
        if attempt['id'] in seen_attempts or attempt['job'] not in order_by_id or attempt['outcome'] not in {'ACCEPTED', 'REJECTED'}:
            raise ValueError('UNIQUE_BOUND_ATTEMPT_REQUIRED')
        seen_attempts.add(attempt['id'])
        covered.add(attempt['job'])
        artifact = _json(_bound(root, attempt['artifact'], attempt['artifact_sha256']))
        fresh = audit_delivery(order_by_id[attempt['job']], artifact)
        if fresh['accepted'] is not (attempt['outcome'] == 'ACCEPTED'):
            raise ValueError('ATTEMPT_OUTCOME_MISMATCH')
        for key in ['cpu_seconds', 'wall_seconds']:
            value = attempt.get(key)
            if value is None:
                unmetered.append(attempt['id'] + ':' + key)
            elif type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('INVALID_MEASURED_RESOURCE')
        measured_cpu += attempt.get('cpu_seconds', 0)
    if covered != observed:
        raise ValueError('MISSING_FAILED_OR_SUCCESSFUL_WORK_COST_OWNER')
    if manifest.get('actual_customers') != 0 or manifest.get('actual_collections_usd') != 0:
        raise ValueError('SYNTHETIC_TO_LIVE_TRANSITION_REFUSED')
    if manifest.get('host_token_billing') != 'UNKNOWN':
        raise ValueError('UNMETERED_HOST_BILLING_SCOPE_CHANGED')
    return {'accepted': True, 'scope': manifest['scope'], 'orders': len(jobs),
            'accepted_artifacts': accepted, 'rejected_jobs': len(jobs) - accepted,
            'attempts': len(attempts), 'measured_attempt_cpu_seconds': measured_cpu,
            'unmetered_attempt_resources': unmetered, 'actual_customers': 0,
            'actual_collections_usd': 0, 'host_token_billing': 'UNKNOWN',
            'independence': 'separate source audit; shared host/model family; no external certification'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = _json(args.manifest.read_bytes())
    result = audit_service(args.root, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
