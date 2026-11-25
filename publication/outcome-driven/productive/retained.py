"""Scoped decision and first-failing prerequisite for frozen public observations."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


REQUIRED = ('build', 'deploy', 'verify-live')
WORKFLOW = '.github/workflows/research-pages.yml'
HEX256 = re.compile(r'[a-f0-9]{64}')


def gate(requirements):
    """Apply trusted, bounded checks in priority order and expose the first failure."""
    for code, allowed in requirements:
        if allowed is not True:
            return {'decision': 'HOLD', 'reason': code}
    return {'decision': 'GO', 'reason': None}


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return result if result.tzinfo == timezone.utc else None


def seconds(begin, end):
    if begin is None or end is None or end < begin:
        return None
    return int((end - begin).total_seconds())


def wait_seconds(job):
    eligible = [parse_time(step['started_at']) for step in job.get('steps', [])]
    first = min((stamp for stamp in eligible if stamp), default=None)
    return seconds(parse_time(job.get('created_at')), first) if seconds(first, parse_time(job.get('completed_at'))) is not None else None


def pages(case):
    run, witness = case['facts']['run'], case['facts']['witness']
    expected, commit = case['expected_run'], case['expected_commit']
    jobs = {name: [job for job in case['facts']['jobs'] if job['name'] == name] for name in REQUIRED}
    matched = {name: entries[0] for name, entries in jobs.items() if len(entries) == 1}
    scope = case['study_scope']
    origin = {'historical': 'observed_pinned_transcript', 'current_at_capture': 'observed_public'}.get(scope)
    result = gate((
        ('INELIGIBLE_OBSERVATION', origin is not None and case['origin'] == origin),
        ('WRONG_RUN', (run['id'], run['path'], run['head_branch'], run['event'], run['head_sha'])
         == (expected, WORKFLOW, 'main', case.get('expected_event', 'push'), commit)),
        ('RUN_NOT_SUCCESSFUL', (run['status'], run['conclusion']) == ('completed', 'success')),
        ('INCOMPLETE_JOB_LIST', len(matched) == len({job['id'] for job in matched.values()}) == len(REQUIRED)),
        ('JOB_SCOPE_MISMATCH', all((job['run_id'], job['run_attempt'], job['head_sha'])
                                  == (expected, run['run_attempt'], commit) for job in matched.values())),
        ('JOB_NOT_SUCCESSFUL', all((job['status'], job['conclusion']) == ('completed', 'success')
                                   for job in matched.values())),
        ('STALE_OR_MISSING_PUBLICATION', witness['source_commit'] == commit and str(witness['workflow_run']) == str(expected)),
    ))
    if result['decision'] == 'GO' or result['reason'] == 'STALE_OR_MISSING_PUBLICATION':
        waits = {name: wait_seconds(job) for name, job in matched.items()}
        total = seconds(parse_time(run['created_at']), parse_time(matched['verify-live']['completed_at']))
        largest = (sorted(waits, key=lambda name: (-waits[name], name))[0]
                   if all(value is not None for value in waits.values()) else None)
        result.update(wait_seconds=waits, wall_to_verified_seconds=total, longest_observed_wait=largest)
    return dict(result, case=case['id'], scope=scope, expected_commit=commit, expected_run=expected)


def upstream(case, withdrawn=False):
    release, archive = case['release'], case['archive']
    matching = [row for row in release['assets'] if row['name'] == case['expected_name']]
    asset = matching[0] if len(matching) == 1 else {}
    digest = asset.get('digest') or ''
    trusted = case['origin'] == 'observed_upstream_publisher' and not withdrawn
    result = gate((
        ('PUBLISHER_ORIGIN_UNBOUND', trusted),
        ('WRONG_UPSTREAM_RELEASE', release['tag'] == case['expected_tag'] and release['draft'] is False),
        ('RELEASE_DIGEST_UNAVAILABLE', len(matching) == 1 and asset['state'] == 'uploaded'
         and digest.startswith('sha256:') and HEX256.fullmatch(digest[7:]) is not None),
        ('ARCHIVE_UNAVAILABLE', archive is not None),
        ('ARCHIVE_IDENTITY_MISMATCH', bool(archive) and archive['sha256'] == archive['ordinary_sha256'] == digest[7:]
         and archive['size'] == asset.get('size')),
    ))
    if result['decision'] == 'GO':
        result.update(archive_bytes=archive['size'], sha256=archive['sha256'], asset_id=asset['id'],
                      publisher_prerelease=release['prerelease'],
                      server_members=archive['server_members'])
    return dict(result, scope='captured_linux_cpu_archive', expected_tag=case['expected_tag'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('method', choices=('pages', 'upstream', 'withdrawn'))
    parser.add_argument('case', type=Path)
    args = parser.parse_args()
    record = json.loads(args.case.read_bytes())
    if args.method == 'pages' and 'facts' not in record:
        result = {'decision': 'HOLD', 'reason': 'ORIGINAL_SCOPE_UNSUPPORTED'}
    else:
        result = pages(record) if args.method == 'pages' else upstream(record, withdrawn=args.method == 'withdrawn')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
