"""Select an edition and carry its public-feature sequence across Pages runs."""

from datetime import datetime
import json
import re

from frontier_public_watch import REPOSITORY

RUN = re.compile(r'[1-9][0-9]{0,15}\Z')
UTC = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z')
CHECK_STEP = 'Verify the actual public English and French pages and ledger bytes'
RUNS = f'https://github.com/{REPOSITORY}/actions/runs/'
API = f'https://api.github.com/repos/{REPOSITORY}/actions/runs/'


def witnessed_run(run, request):
    """Use the first successful deployed-page check, including after a retry."""
    if not RUN.fullmatch(run):
        return None
    try:
        data = json.loads(request(f'{API}{run}/jobs?filter=all&per_page=100', 800_000))
        matches = []
        for job in data['jobs']:
            if (job['run_id'], job['name']) != (int(run), 'verify-live'):
                continue
            for step in job.get('steps', []):
                value = step.get('completed_at')
                if (step['name'] == CHECK_STEP and step['conclusion'] == 'success'
                        and isinstance(value, str) and UTC.fullmatch(value)):
                    datetime.fromisoformat(value)
                    matches.append(value)
        return min(matches, default=None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def key(entry):
    return (entry['id'], entry['source_version'])


def feed(briefs, previous, run, witness):
    """Feature one qualified lead, then a shorter public recap in a later build."""
    by_version = {key(brief): brief for brief in briefs}

    def prior_slot(name, fields):
        saved = previous.get(name)
        if (isinstance(saved, dict) and saved.keys() == fields
                and all(isinstance(value, str) for value in saved.values()) and key(saved) in by_version
                and isinstance(saved['member_run'], str) and RUN.fullmatch(saved['member_run'])):
            return saved
        return None

    first_fields = {'id', 'source_version', 'member_run'}
    edition = prior_slot('edition', first_fields)
    public = prior_slot('public_feature', first_fields | {'public_run', 'member_checked_at'})
    if public and (not isinstance(public['public_run'], str) or not RUN.fullmatch(public['public_run'])
                   or not isinstance(public['member_checked_at'], str) or not UTC.fullmatch(public['member_checked_at'])):
        public = None

    # A WATCH item remains in the radar. Evidence-backed reviews and proposed
    # comparisons can change the featured edition even on a modest news day.
    actionable = [b for b in briefs if b['verdict'] != 'WATCH']
    lead = max(actionable or briefs, key=lambda b: (b['updated_at'],
               b['verdict'] in ('PREPARE', 'TEST NOW'), b['edition_kind'] == 'capability', b['id']))
    if edition and (public is None or key(public) != key(edition)) and edition['member_run'] != run:
        checked = witness(edition['member_run'])
        if checked:
            public = {**edition, 'member_checked_at': checked, 'public_run': run}
    if not edition or (public and key(public) == key(edition) and key(lead) != key(edition)):
        edition = {'id': lead['id'], 'source_version': lead['source_version'], 'member_run': run}
    return {'edition': edition, 'public_feature': public}
