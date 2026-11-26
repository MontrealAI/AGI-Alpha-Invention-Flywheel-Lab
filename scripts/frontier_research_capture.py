"""Retain authorized, externally observed scout results in the local research store."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import re

import frontier_public_watch as watch


SCHEMA = 'frontier/research-scout-capture-v1'
SCOUT_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', re.ASCII)
URL = re.compile(r"""(?<![\w./@-])https://[^\s<>()\[\]"'\x00-\x1f]{1,2048}(?![^\s<>()\[\]"'])""")
LAST = {'run_id', 'scheduled_for', 'started_at', 'completed_at', 'recorded_status'}
RESULT = {'run_id', 'scheduled_for', 'completed_at', 'content_text', 'content_truncated',
          'is_failure_message', 'requires_user_action'}
IDENTITY_FIELDS = ('run_id', 'scheduled_for', 'completed_at')
RUN_STATES = {'scheduled': 'SCHEDULED', 'pending': 'PENDING', 'in_progress': 'PENDING',
              'completed': 'COMPLETED', 'failed': 'FAILED', 'no_update': 'NO_UPDATE'}
RETRY = ('MISSING_BODY', 'STALE', 'UNALIGNED', 'TRUNCATED', 'PENDING')
RETRY_DELAYS = (60, 120, 240, 480, 900)

SQL = '''
    CREATE TABLE IF NOT EXISTS scout_scopes (
        scout_id TEXT PRIMARY KEY, stream TEXT, revoked_at TEXT
    );
    CREATE TABLE IF NOT EXISTS scout_observations (
        sha TEXT PRIMARY KEY, scout_id TEXT REFERENCES scout_scopes NOT NULL,
        observed_at TEXT NOT NULL, imported_at TEXT NOT NULL, slot TEXT,
        expected_key TEXT, run_state TEXT NOT NULL, result_state TEXT NOT NULL,
        retry_count INTEGER NOT NULL, retry_after TEXT, metadata TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS scout_observations_time
        ON scout_observations (scout_id, observed_at DESC);
    CREATE TABLE IF NOT EXISTS scout_revisions (
        id INTEGER PRIMARY KEY, scout_id TEXT REFERENCES scout_scopes NOT NULL,
        run_key TEXT NOT NULL, body_sha TEXT REFERENCES packets NOT NULL,
        observation_sha TEXT REFERENCES scout_observations NOT NULL DEFERRABLE INITIALLY DEFERRED,
        scheduled_for TEXT, completed_at TEXT, UNIQUE (scout_id, run_key, body_sha)
    );
    CREATE INDEX IF NOT EXISTS scout_revisions_slot ON scout_revisions (scout_id, scheduled_for);
    CREATE INDEX IF NOT EXISTS scout_revisions_completion ON scout_revisions (scout_id, completed_at);
    CREATE TABLE IF NOT EXISTS scout_links (
        revision INTEGER REFERENCES scout_revisions NOT NULL, url TEXT NOT NULL,
        PRIMARY KEY (revision, url)
    );
    CREATE VIEW IF NOT EXISTS active_research_observations AS
        SELECT o.* FROM observations o
        WHERE o.provenance NOT LIKE 'scout:%' OR EXISTS (
            SELECT 1 FROM scout_revisions r JOIN scout_scopes s ON s.scout_id = r.scout_id
            WHERE o.provenance = 'scout:' || r.id AND s.revoked_at IS NULL AND r.id = (
                SELECT MAX(newer.id) FROM scout_revisions newer
                WHERE newer.scout_id = r.scout_id AND newer.run_key = r.run_key
            )
        );
'''


class CaptureError(ValueError):
    """Describe invalid scope or input without rendering account data."""


def digest(raw):
    return sha256(raw).hexdigest()


def clock():
    return datetime.now(UTC).isoformat(timespec='microseconds')


def date(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise CaptureError('Invalid scout timestamp.')
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).isoformat(timespec='microseconds')
    except (OverflowError, ValueError):
        raise CaptureError('Invalid scout timestamp.') from None
    raise CaptureError('Scout timestamps require an explicit timezone.')


def identifier(value):
    if not isinstance(value, str) or not SCOUT_ID.fullmatch(value):
        raise CaptureError('Invalid scout or run identity.')
    return value


def run_metadata(value, result=False):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - (RESULT if result else LAST):
        raise CaptureError('Unexpected scout run metadata.')
    run_id = value.get('run_id')
    output = {'run_id': identifier(run_id) if run_id is not None else None,
              'scheduled_for': date(value.get('scheduled_for')),
              'completed_at': date(value.get('completed_at'))}
    if result:
        for key in ('content_truncated', 'is_failure_message', 'requires_user_action'):
            flag = value.get(key, False)
            if flag is not None and type(flag) is not bool:
                raise CaptureError('Unexpected scout report flag.')
            output[key] = flag
    else:
        status = value.get('recorded_status')
        if status is not None and (not isinstance(status, str) or status not in RUN_STATES):
            raise CaptureError('Unexpected scout run state.')
        output.update(started_at=date(value.get('started_at')), recorded_status=status)
    return output


def identity(run):
    for field in IDENTITY_FIELDS:
        if run.get(field):
            return field + ':' + run[field]
    return None


def recorded_state(last, result, observed):
    if last is None:
        if result is None or result['completed_at'] is None:
            return 'UNKNOWN'
        return 'PENDING' if result['completed_at'] > observed else 'COMPLETED'
    if last['completed_at'] and last['completed_at'] > observed:
        return 'PENDING'
    if last['recorded_status'] is not None:
        return RUN_STATES[last['recorded_status']]
    if last['completed_at']:
        return 'COMPLETED'
    if last['started_at'] or (last['scheduled_for'] and last['scheduled_for'] <= observed):
        return 'PENDING'
    return 'SCHEDULED' if last['scheduled_for'] else 'UNKNOWN'


def alignment(last, result):
    if not last:
        return 'LATEST_RESULT_ONLY'
    overlap = [field for field in IDENTITY_FIELDS if last[field] and result[field]]
    if any(last[field] != result[field] for field in overlap):
        return 'STALE'
    if last['started_at'] and result['completed_at'] and result['completed_at'] < last['started_at']:
        return 'STALE'
    return overlap[0].upper() if overlap else 'UNALIGNED'


def behind_checkpoint(result, newest_slot, latest_event):
    if result['scheduled_for'] and newest_slot:
        return result['scheduled_for'] < newest_slot
    return bool(result['completed_at'] and latest_event and result['completed_at'] < latest_event)


def result_state(result, body, observed, state, stale, basis):
    if stale or basis == 'STALE':
        return 'STALE'
    if state in {'SCHEDULED', 'PENDING', 'FAILED', 'NO_UPDATE'}:
        return state
    if not result:
        return 'MISSING_BODY' if state == 'COMPLETED' else 'UNAVAILABLE'
    if basis == 'UNALIGNED' or not identity(result):
        return 'UNALIGNED'
    if not result['completed_at'] and state != 'COMPLETED':
        return 'PENDING'
    if result['completed_at'] and result['completed_at'] > observed:
        return 'PENDING'
    if result['is_failure_message']:
        return 'FAILED'
    if result['requires_user_action']:
        return 'NEEDS_USER_ACTION'
    if result['content_truncated']:
        return 'TRUNCATED'
    return 'AVAILABLE' if body and body.strip() else 'MISSING_BODY'


def logical_key(store, scout, run):
    """Resolve a run key and identify its prior key when identity is being enriched."""
    key = identity(run)
    slot, completed = run['scheduled_for'], run['completed_at']
    rows = store.execute(
        'SELECT DISTINCT run_key, scheduled_for, completed_at FROM scout_revisions '
        'WHERE scout_id = ? AND (run_key = ? OR scheduled_for = ? OR completed_at = ?)',
        (scout, key, slot, completed),
    ).fetchall()
    known_key = any(prior == key for prior, _, _ in rows)
    matches = {prior for prior, previous_slot, previous_completion in rows
               if (not slot or not previous_slot or slot == previous_slot)
               and (not completed or not previous_completion or completed == previous_completion)}
    if run['run_id']:
        if not known_key and len(matches) == 1:
            prior, = matches
            if not prior.startswith('run_id:'):
                return key, prior
        return key, key
    if len(matches) == 1:
        prior, = matches
        return prior, prior
    if matches or known_key:
        return None, None
    return key, key


def retain(store, scout, stream, observed, result, body, observation_sha, record_references):
    key, prior = logical_key(store, scout, result)
    if key is None:
        return 'UNALIGNED'
    content_sha = result['content_sha256']
    repeated = store.execute('SELECT 1 FROM scout_revisions WHERE scout_id = ? AND run_key = ? AND body_sha = ?',
                             (scout, prior, content_sha)).fetchone()
    head = store.execute(
        'SELECT o.observed_at FROM scout_revisions r JOIN scout_observations o '
        'ON o.sha = r.observation_sha WHERE r.scout_id = ? AND r.run_key = ? ORDER BY r.id DESC LIMIT 1',
        (scout, prior)).fetchone()
    if head and (head[0] > observed or (head[0] == observed and not repeated)):
        return 'REPEATED' if repeated else 'STALE'
    if head:
        store.execute(
            'UPDATE scout_revisions SET run_key = ?, scheduled_for = COALESCE(scheduled_for, ?), '
            'completed_at = COALESCE(completed_at, ?) WHERE scout_id = ? AND run_key = ?',
            (key, result['scheduled_for'], result['completed_at'], scout, prior),
        )
    if repeated:
        return 'REPEATED'
    store.execute('INSERT OR IGNORE INTO packets VALUES (?, ?)', (content_sha, body.encode('utf-8')))
    revision = store.execute(
        'INSERT INTO scout_revisions (scout_id,run_key,body_sha,observation_sha,scheduled_for,completed_at) '
        'VALUES (?,?,?,?,?,?)', (scout, key, content_sha, observation_sha,
                                result['scheduled_for'], result['completed_at'])).lastrowid
    links = {match.group().rstrip('.,;!?') for match in URL.finditer(body)}
    store.executemany('INSERT INTO scout_links VALUES (?,?)', ((revision, url) for url in sorted(links)))
    record_references(store, body, f'scout:{revision}', stream, observed)
    return 'REVISED' if head else 'CAPTURED'


def retry_after(store, scout, key, state, observed):
    if state not in RETRY:
        return 0, None
    previous = store.execute(
        'SELECT retry_count FROM scout_observations WHERE scout_id = ? AND expected_key IS ? '
        'AND observed_at <= ? ORDER BY observed_at DESC, rowid DESC LIMIT 1',
        (scout, key, observed)).fetchone()
    count = min((previous[0] if previous else 0) + 1, len(RETRY_DELAYS) + 1)
    if count > len(RETRY_DELAYS):
        return count, None
    try:
        next_try = datetime.fromisoformat(observed) + timedelta(seconds=RETRY_DELAYS[count - 1])
    except OverflowError:
        raise CaptureError('Observation time exceeds the retry range.') from None
    return count, next_try.isoformat(timespec='microseconds')


def check_observation_time(row):
    fields = {'scout_id', 'stream', 'observed_at', 'last_run', 'latest_result'}
    if not isinstance(row, dict) or set(row) != fields:
        raise CaptureError('Each observation needs scout, stream, time, run and result fields.')
    observed = date(row['observed_at'])
    if not observed:
        raise CaptureError('An exact observation time is required.')
    return observed


def observe(store, row, observed, imported, record_references):
    scout = identifier(row['scout_id'])
    stream = row['stream']
    if not isinstance(stream, str) or stream not in watch.STREAMS:
        raise CaptureError('The observation needs a known scout stream.')
    scope = store.execute('SELECT stream, revoked_at FROM scout_scopes WHERE scout_id = ?', (scout,)).fetchone()
    if scope and scope[1]:
        return 'REVOKED'
    if scope and scope[0] != stream:
        raise CaptureError('Scout identity belongs to a different stream.')
    last = run_metadata(row['last_run'])
    result = run_metadata(row['latest_result'], result=True)
    body = row['latest_result'].get('content_text') if result is not None else None
    if body is not None and not isinstance(body, str):
        raise CaptureError('Scout result text must be a string or null.')
    if result is not None:
        result['content_sha256'] = digest(body.encode('utf-8')) if body is not None else None
    metadata = json.dumps({'last_run': last, 'latest_result': result}, sort_keys=True)
    observation_sha = digest(json.dumps([scout, stream, observed, metadata]).encode())
    if store.execute('SELECT 1 FROM scout_observations WHERE sha = ?', (observation_sha,)).fetchone():
        return 'DUPLICATE_OBSERVATION'

    store.execute('INSERT OR IGNORE INTO scout_scopes (scout_id,stream) VALUES (?,?)', (scout, stream))
    expected = last or result or {}
    slot = expected.get('scheduled_for')
    newest_slot, latest_event = store.execute('''
        SELECT MAX(slot), MAX(COALESCE(
            json_extract(metadata, '$.last_run.started_at'),
            json_extract(metadata, '$.last_run.completed_at'),
            CASE WHEN result_state NOT IN ('STALE','UNALIGNED','PENDING','SCHEDULED')
                THEN json_extract(metadata, '$.latest_result.completed_at') END))
        FROM scout_observations WHERE scout_id = ?
    ''', (scout,)).fetchone()
    state = recorded_state(last, result, observed)
    basis = alignment(last, result) if result else None
    stale = result and behind_checkpoint(result, newest_slot, latest_event)
    outcome = result_state(result, body, observed, state, stale, basis)
    if outcome == 'AVAILABLE':
        admitted = dict(result)
        if last:
            for field in IDENTITY_FIELDS:
                admitted[field] = admitted[field] or last[field]
        outcome = retain(store, scout, stream, observed, admitted, body, observation_sha, record_references)
    key = identity(expected)
    retries, next_try = ((0, None) if state in {'NO_UPDATE', 'FAILED'} else
                         retry_after(store, scout, key, outcome, observed))
    metadata = json.dumps({'last_run': last, 'latest_result': result, 'alignment': basis}, sort_keys=True)
    store.execute('INSERT INTO scout_observations VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                  (observation_sha, scout, observed, imported, slot, key, state, outcome, retries, next_try, metadata))
    return outcome


def capture(store, raw, record_references):
    export = json.loads(raw, object_pairs_hook=watch.unique_object)
    if not isinstance(export, dict) or set(export) != {'schema', 'observations'} or export['schema'] != SCHEMA:
        raise CaptureError('Unexpected scout observation export.')
    rows = export['observations']
    if not isinstance(rows, list) or not 0 < len(rows) <= 128:
        raise CaptureError('The scout export needs between 1 and 128 observations.')
    imported = clock()
    ordered = sorted(((check_observation_time(row), row) for row in rows), key=lambda item: item[0])
    with store:
        store.execute('BEGIN IMMEDIATE')
        return dict(Counter(observe(store, row, observed, imported, record_references) for observed, row in ordered))


def revoke(store, scout):
    scout = identifier(scout)
    with store:
        store.execute('BEGIN IMMEDIATE')
        store.execute('INSERT INTO scout_scopes (scout_id,revoked_at) VALUES (?,?) '
                      'ON CONFLICT (scout_id) DO UPDATE SET revoked_at = COALESCE(revoked_at, excluded.revoked_at)',
                      (scout, clock()))


def status(store):
    current = store.execute('''
        SELECT s.stream, o.observed_at, o.slot, o.run_state, o.result_state, o.retry_count, o.retry_after
        FROM scout_scopes s JOIN scout_observations o ON o.scout_id = s.scout_id
        WHERE s.revoked_at IS NULL AND o.rowid = (
            SELECT newer.rowid FROM scout_observations newer WHERE newer.scout_id = s.scout_id
            ORDER BY newer.observed_at DESC, newer.rowid DESC LIMIT 1
        ) ORDER BY s.stream, o.observed_at
    ''')
    gaps = store.execute('''
        SELECT COUNT(*) FROM (
            SELECT DISTINCT o.scout_id, o.slot FROM scout_observations o
            WHERE o.slot < (SELECT MAX(newer.slot) FROM scout_observations newer WHERE newer.scout_id = o.scout_id)
            AND NOT EXISTS (SELECT 1 FROM scout_revisions r
                            WHERE r.scout_id = o.scout_id AND r.scheduled_for = o.slot)
            AND NOT EXISTS (SELECT 1 FROM scout_observations terminal
                            WHERE terminal.scout_id = o.scout_id AND terminal.slot = o.slot
                            AND terminal.run_state IN ('NO_UPDATE','FAILED'))
        )
    ''').fetchone()[0]
    fields = ('stream', 'observed_at', 'scheduled_for', 'run_state', 'result_state', 'retry_count', 'retry_after')
    return {
        'latest_observed_scopes': [dict(zip(fields, row, strict=True)) for row in current],
        'revoked_scout_scopes': store.execute('SELECT COUNT(*) FROM scout_scopes WHERE revoked_at IS NOT NULL').fetchone()[0],
        'retained_report_revisions': store.execute('SELECT COUNT(*) FROM scout_revisions').fetchone()[0],
        'distinct_report_runs': store.execute(
            'SELECT COUNT(*) FROM (SELECT DISTINCT scout_id, run_key FROM scout_revisions)').fetchone()[0],
        'retained_source_links': store.execute('SELECT COUNT(*) FROM scout_links').fetchone()[0],
        'result_states': dict(store.execute('SELECT result_state, COUNT(*) FROM scout_observations GROUP BY result_state')),
        'known_unfilled_slots': gaps,
        'historical_report_denominator': None,
    }
