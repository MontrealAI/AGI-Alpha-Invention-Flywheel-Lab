"""Direct conventional reference; no import of the retained decision mechanism."""

from datetime import datetime, timezone
import json
import sys
from pathlib import Path


def timestamp(value):
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def elapsed(first, last):
    t1, t2 = timestamp(first), timestamp(last)
    return int((t2 - t1).total_seconds()) if t1 and t2 and t2 >= t1 else None


def pages(row):
    main = {'case': row['id'], 'scope': row['study_scope'], 'expected_commit': row['expected_commit'],
            'expected_run': row['expected_run']}

    def hold(reason):
        return dict(main, decision='HOLD', reason=reason)

    run = row['facts']['run']
    official = row['origin'] == 'observed_public' and row['study_scope'] == 'current_at_capture'
    archived = row['origin'] == 'observed_pinned_transcript' and row['study_scope'] == 'historical'
    if not official and not archived:
        return hold('INELIGIBLE_OBSERVATION')
    if (run['id'] != main['expected_run'] or run['head_sha'] != main['expected_commit']
            or run['path'] != '.github/workflows/research-pages.yml'
            or run['head_branch'] != 'main' or run['event'] != row.get('expected_event', 'push')):
        return hold('WRONG_RUN')
    if run['status'] != 'completed' or run['conclusion'] != 'success':
        return hold('RUN_NOT_SUCCESSFUL')

    targets = {'build', 'deploy', 'verify-live'}
    jobs = [d for d in row['facts']['jobs'] if d['name'] in targets]
    if {d['name'] for d in jobs} != targets or len(jobs) != 3 or len({job['id'] for job in jobs}) != 3:
        return hold('INCOMPLETE_JOB_LIST')
    for job in jobs:
        if job['run_id'] != run['id'] or job['run_attempt'] != run['run_attempt'] or job['head_sha'] != run['head_sha']:
            return hold('JOB_SCOPE_MISMATCH')
    if any(job['status'] != 'completed' or job['conclusion'] != 'success' for job in jobs):
        return hold('JOB_NOT_SUCCESSFUL')

    witness = row['facts']['witness']
    if witness.get('source_commit') != run['head_sha'] or str(witness.get('workflow_run')) != str(run['id']):
        result = hold('STALE_OR_MISSING_PUBLICATION')
    else:
        result = dict(main, decision='GO', reason=None)
    waits = {}
    for job in jobs:
        starts = sorted(s['started_at'] for s in job['steps'] if timestamp(s.get('started_at')))
        stays = elapsed(job['created_at'], starts[0]) if starts and elapsed(starts[0], job['completed_at']) is not None else None
        waits[job['name']] = stays
    ending = next(d['completed_at'] for d in jobs if d['name'] == 'verify-live')
    largest = (max(sorted(waits), key=waits.get)
               if all(value is not None for value in waits.values()) else None)
    return dict(result, wait_seconds=waits, longest_observed_wait=largest,
                wall_to_verified_seconds=elapsed(run['created_at'], ending))


def upstream(row):
    result = {'decision': 'HOLD', 'reason': None, 'scope': 'captured_linux_cpu_archive',
              'expected_tag': row['expected_tag']}
    actual_release = row['release']
    if row['origin'] != 'observed_upstream_publisher':
        return dict(result, reason='PUBLISHER_ORIGIN_UNBOUND')
    if actual_release['tag'] != row['expected_tag'] or actual_release['draft'] is not False:
        return dict(result, reason='WRONG_UPSTREAM_RELEASE')
    assets = [item for item in actual_release['assets'] if item['name'] == row['expected_name']]
    if len(assets) != 1 or assets[0]['state'] != 'uploaded':
        return dict(result, reason='RELEASE_DIGEST_UNAVAILABLE')
    asset = assets[0]
    digest = asset['digest']
    if (not isinstance(digest, str) or len(digest) != 71 or not digest.startswith('sha256:')
            or set(digest[7:]) - set('0123456789abcdef')):
        return dict(result, reason='RELEASE_DIGEST_UNAVAILABLE')
    archive = row['archive']
    if archive is None:
        return dict(result, reason='ARCHIVE_UNAVAILABLE')
    if archive['size'] != asset['size'] or 'sha256:' + archive['ordinary_sha256'] != digest or archive['sha256'] != archive['ordinary_sha256']:
        return dict(result, reason='ARCHIVE_IDENTITY_MISMATCH')
    return dict(result, decision='GO', archive_bytes=archive['size'], sha256=archive['ordinary_sha256'],
                asset_id=asset['id'], publisher_prerelease=actual_release['prerelease'], server_members=archive['server_members'])


if __name__ == '__main__':
    method, path = sys.argv[1:]
    data = json.loads(Path(path).read_bytes())
    print(json.dumps(pages(data) if method == 'pages' else upstream(data), sort_keys=True))
