"""Keep source research local and run reviewed Opportunity Capture investigations."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
from time import monotonic

import frontier_public_watch as watch
import frontier_research_capture as scout_capture


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE = Path.home() / '.local/state/frontier-omega/research'
MAX_PACKET = 4_000_000
MAX_ATLAS = 20_000_000
ATLAS_RELEASE = watch.SITE + 'atlas-release.json'
ATLAS_LEDGER = watch.SITE + 'atlas-ledger.json'
PACKET_SCHEMA = 'frontier/research-updates-v1'
REPORT_ORIGINS = {'atlas': 'PUBLISHED_ATLAS', 'scout': 'SCOUT_RESULT', 'packet': 'REPORTED_PACKET'}
ARXIV_URL = re.compile(
    r'(?<![\w./@-])https://arxiv\.org/(?:abs|html|pdf)/'
    r'(\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}v[1-9]\d{0,2})(?:\.pdf)?'
    r'(?![\w/=%-]|\.\w)', re.ASCII,
)
STUDIES = {
    'routing-ceiling': {
        'ref': 'arxiv:2611.34825v1',
        'disposition': 'REACTIVATE',
        'bottleneck': 'DPP comparative tie and unknown value of conditional routing',
        'intervention': 'Measure case-level complementarity before investing in a learned router.',
        'registration': 'publication/prove-advantage/research-activation/ROUTING-REGISTRATION.md',
        'runner': 'publication/prove-advantage/research-activation/routing_mission.py',
        'inputs': ('publication/prove-advantage/research-activation/router_ceiling.py',),
        'schema': 'frontier/routeability-ceiling-v1',
    },
    'evaluation-sampling': {
        'ref': 'arxiv:2611.34617v1',
        'disposition': 'TEST',
        'bottleneck': 'Cost of repeated full evaluation',
        'intervention': 'Compare metadata-only sampling with stratified and complete evaluation.',
        'registration': 'publication/prove-advantage/research-activation/sampling-registration.md',
        'runner': 'publication/prove-advantage/research-activation/sampling_replay.py',
        'schema': 'frontier/evaluation-sampling-replay-v1',
    },
    'game-event-order': {
        'ref': 'arxiv:2611.34656v1',
        'disposition': 'REACTIVATE',
        'bottleneck': 'False-known claims about decision-time strategic information',
        'intervention': 'Validate reviewed decision-time event orders before compiling an exact game.',
        'registration': 'publication/prove-advantage/game-theory/research-reactivation/REGISTRATION.md',
        'runner': 'publication/prove-advantage/game-theory/research-reactivation/check.py',
        'inputs': tuple(f'publication/prove-advantage/game-theory/{part}.py' for part in ('curriculum', 'partition', 'replay')),
        'schema': 'frontier/game-theory-event-order-research-v1',
    },
}


class InputError(ValueError):
    """Report fixed operator-facing errors without echoing imported content."""


def now():
    return datetime.now(UTC).isoformat(timespec='seconds')


def fingerprint(raw):
    return sha256(raw).hexdigest()


def decode(raw):
    return json.loads(raw, object_pairs_hook=watch.unique_object)


def read(path, limit=MAX_PACKET):
    if path == '-':
        raw = sys.stdin.buffer.read(limit + 1)
    else:
        with Path(path).open('rb') as stream:
            raw = stream.read(limit + 1)
    if not 0 < len(raw) <= limit:
        raise InputError('Input is empty or exceeds the read limit.')
    return raw


def timestamp(value):
    if value == '':
        return ''
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise InputError('Observation time needs an explicit timezone.')
    return result.astimezone(UTC).isoformat()


def open_store(path):
    path = path.expanduser().resolve()
    if any((item / '.git').exists() for item in (path, *path.parents)):
        raise InputError('Choose a research state directory outside Git worktrees.')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.resolve() != path:
        raise InputError('The research state path changed during creation.')
    if os.name == 'posix':
        for parent in path.parents:
            info = parent.stat()
            if (info.st_uid not in {0, os.getuid()}
                    or info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                raise InputError('Choose a state directory under trusted, protected parents.')
    if os.name == 'posix' and (path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077):
        raise InputError('The research state directory must be owner-only.')
    db = path / 'research.sqlite3'
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(db, flags, 0o600), 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or db.is_symlink() or info.st_nlink != 1 or (os.name == 'posix' and
                (info.st_uid != os.getuid() or info.st_mode & 0o077)):
            raise InputError('The research database must be an owner-only regular file.')
    store = sqlite3.connect(db, timeout=20)
    store.executescript('''
        PRAGMA foreign_keys = ON;
        PRAGMA trusted_schema = OFF;
        PRAGMA synchronous = FULL;
        CREATE TABLE IF NOT EXISTS packets (
            sha TEXT PRIMARY KEY, body BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS arrivals (
            sha TEXT REFERENCES packets NOT NULL, stream TEXT NOT NULL, observed TEXT NOT NULL,
            imported TEXT NOT NULL, PRIMARY KEY (sha, stream, observed)
        );
        CREATE TABLE IF NOT EXISTS observations (
            ref TEXT NOT NULL, provenance TEXT NOT NULL, stream TEXT NOT NULL, observed TEXT NOT NULL,
            state TEXT NOT NULL, PRIMARY KEY (ref, provenance, stream, observed)
        );
        CREATE TABLE IF NOT EXISTS studies (
            name TEXT NOT NULL, ref TEXT NOT NULL, executable_sha TEXT NOT NULL,
            registration_sha TEXT NOT NULL, result TEXT NOT NULL,
            PRIMARY KEY (name, ref, executable_sha, registration_sha)
        );
    ''')
    store.executescript(scout_capture.SQL)
    return store


def record_report_references(store, text, origin, stream, observed):
    references = set(ARXIV_URL.findall(text))
    store.executemany('INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?)',
                      (('arxiv:' + ref, origin, stream, observed, 'DISCOVERED') for ref in references))


def capture_updates(store, raw):
    if not 0 < len(raw) <= MAX_PACKET:
        raise InputError('Input is empty or exceeds the read limit.')
    return scout_capture.capture(store, raw, record_report_references)


def import_updates(store, raw, *, structured, stream, observed):
    if structured:
        export = decode(raw)
        if not isinstance(export, dict) or set(export) != {'schema', 'updates'} or export['schema'] != PACKET_SCHEMA:
            raise InputError('Unexpected research update export.')
        updates = export['updates']
        if not isinstance(updates, list) or not updates:
            raise InputError('The research export needs at least one update.')
    else:
        updates = [{'stream': stream, 'observed_at': observed, 'text': raw.decode('utf-8-sig')}]
    recorded = now()
    with store:
        for update in updates:
            if (not isinstance(update, dict) or set(update) != {'stream', 'observed_at', 'text'}
                    or not all(isinstance(x, str) for x in update.values())):
                raise InputError('Each research update needs a stream, observation time and text.')
            body = update['text'].encode('utf-8')
            stream = update['stream']
            if not body.strip() or stream not in {*watch.STREAMS, 'manual'}:
                raise InputError('The update needs text and a known stream or manual origin.')
            observed = timestamp(update['observed_at'])
            digest = fingerprint(body)
            store.execute('INSERT OR IGNORE INTO packets VALUES (?, ?)', (digest, body))
            store.execute('INSERT OR IGNORE INTO arrivals VALUES (?, ?, ?, ?)', (digest, stream, observed, recorded))
            record_report_references(store, update['text'], 'packet:' + digest, stream, observed)


def import_atlas(store, request=watch.fetch):
    release = decode(request(ATLAS_RELEASE, MAX_PACKET))
    raw = request(ATLAS_LEDGER, MAX_ATLAS)
    if (release['schema'] != 'frontier-omega-alpha/atlas-release-v1'
            or fingerprint(raw) != release['ledger_sha256']):
        raise InputError('The Atlas ledger and live release manifest differ. Retry after publication settles.')
    ledger = decode(raw)
    if not isinstance(ledger.get('records'), list):
        raise InputError('The Atlas records have an unexpected format.')
    with store:
        for record in ledger['records']:
            if not isinstance(record.get('sources'), dict):
                raise InputError('The Atlas source history has an unexpected format.')
            for versions in record['sources'].values():
                for item in versions:
                    source, ref, stream = (item[k] for k in ('source', 'source_version', 'stream'))
                    valid = watch.ARXIV.fullmatch(ref) if source == 'arxiv' else source in watch.SOURCES and watch.TAG.fullmatch(ref)
                    commit = item['publisher_commit']
                    if (not valid or stream not in watch.STREAMS or not re.fullmatch(r'[0-9a-f]{40}', commit)
                            or item['decision'] not in {'test', 'watch'}):
                        raise InputError('Unexpected published reference provenance.')
                    state = 'DISCOVERED' if item['decision'] == 'test' else 'WATCH'
                    store.execute('INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?)',
                                  (source + ':' + ref, 'atlas:' + commit, stream, timestamp(item['observed_at']), state))


def status(store):
    observations = store.execute('SELECT ref, COUNT(*) FROM observations GROUP BY ref').fetchall()
    sources = dict(observations)
    active = {row[0] for row in store.execute('SELECT DISTINCT ref FROM active_research_observations')}
    studies = {}
    for name, study in STUDIES.items():
        runs = store.execute('SELECT COUNT(*) FROM studies WHERE name = ? AND ref = ?', (name, study['ref'])).fetchone()[0]
        studies[name] = {**study, 'observed': study['ref'] in active, 'recorded_executions': runs}
    return {
        'retained_packet_bodies': store.execute('SELECT COUNT(*) FROM packets').fetchone()[0],
        'recorded_packet_arrivals': store.execute('SELECT COUNT(*) FROM arrivals').fetchone()[0],
        'distinct_source_versions': len(sources),
        'active_source_versions': len(active),
        'reference_sightings': sum(sources.values()),
        'reference_sightings_by_origin': dict(Counter(row[0].split(':', 1)[0] for row in
                                                    store.execute('SELECT provenance FROM observations'))),
        'reference_sightings_by_intake_state': dict(store.execute('SELECT state, COUNT(*) FROM observations GROUP BY state')),
        'registered_studies': studies,
        'scout_capture': scout_capture.status(store),
    }


def cycle(store, name):
    """Run a named, reviewed local study. Research bytes never enter its arguments."""
    study = STUDIES[name]
    ref = study['ref']
    registration, runner = (ROOT / study[key] for key in ('registration', 'runner'))
    begin = monotonic()
    with store:
        store.execute('BEGIN IMMEDIATE')
        sightings = [{'stream': stream, 'observed_at': observed or None, 'provenance': origin,
                      'observation_basis': REPORT_ORIGINS[origin.split(':', 1)[0]]}
                     for stream, observed, origin in store.execute(
                         'SELECT stream, observed, provenance FROM active_research_observations WHERE ref = ? '
                         'ORDER BY observed, stream, provenance', (ref,))]
        if not sightings:
            raise InputError('Import an eligible report or Atlas release containing this exact source first.')
        registration_sha = fingerprint(registration.read_bytes())
        sources = {study['runner']: fingerprint(runner.read_bytes()),
                   **{path: fingerprint((ROOT / path).read_bytes()) for path in study.get('inputs', ())}}
        executable_sha = fingerprint(json.dumps(sources, sort_keys=True).encode())
        key = (name, ref, executable_sha, registration_sha)
        stored = store.execute('SELECT result FROM studies WHERE '
                               'name = ? AND ref = ? AND executable_sha = ? AND registration_sha = ?', key).fetchone()
        if stored:
            prior = decode(stored[0])
            return {**prior, 'execution': 'REUSED_RECEIPT', 'reuse_scope': 'HISTORICAL_RECEIPT_ONLY',
                    'new_sightings': [item for item in sightings if item not in prior['lineage']]}
        primary = {}

        def request(url, limit):
            raw = watch.fetch(url, limit)
            primary['sha256'] = fingerprint(raw)
            return raw

        title, url, date = watch.evidence({'source': 'arxiv', 'ref': ref.removeprefix('arxiv:')}, request)
        primary.update(title=title, url=url, date=date, checked_at=now(), scope='EXACT_VERSION_METADATA')
        started = now()
        operated = subprocess.run((sys.executable, '-E', '-B', str(runner)), cwd=ROOT, stdin=subprocess.DEVNULL,
                                  capture_output=True, check=False)
        if not operated.stdout:
            raise InputError('The registered runner returned no result. Run it directly to inspect the error.')
        result = decode(operated.stdout)
        if not isinstance(result, dict) or result.get('schema') != study['schema']:
            raise InputError('Study output schema differs from the registered runner.')
        receipt = {'study': name, 'source': primary,
                   'lineage': sightings,
                   'bottleneck': study['bottleneck'], 'registration_sha256': registration_sha,
                   'sources_sha256': sources, 'experiment_started_at': started,
                   'execution': 'LOCAL_REGISTERED_STUDY', 'runner_exit_code': operated.returncode,
                   'local_wall_seconds': round(monotonic() - begin, 6),
                   'result': result}
        store.execute('INSERT INTO studies VALUES (?, ?, ?, ?, ?)', (*key, json.dumps(receipt)))
        return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, default=DEFAULT_STORE)
    commands = parser.add_subparsers(dest='action', required=True)
    intake = commands.add_parser('import', help='Import Markdown, UTF-8 text or a structured research export.')
    intake.add_argument('file', nargs='?', default='-')
    intake.add_argument('--format', choices=('text', 'json'))
    intake.add_argument('--stream', choices=(*watch.STREAMS, 'manual'), default='manual')
    intake.add_argument('--observed-at', default='')
    capture = commands.add_parser('capture', help='Retain observed scout run metadata and available report text.')
    capture.add_argument('file', nargs='?', default='-')
    revoke = commands.add_parser('revoke-scout', help='Revoke one scout scope for local capture and subsequent processing.')
    revoke.add_argument('scout_id')
    commands.add_parser('atlas', help='Import the historical reference projection from the live public Atlas.')
    run = commands.add_parser('cycle', help='Activate one explicitly selected registered public study.')
    run.add_argument('study', choices=STUDIES)
    restore = commands.add_parser('restore-packet', help='Restore the exact evidence for a qualified public review.')
    restore.add_argument('case', choices=('ACT15', 'INV10'))
    restore.add_argument('output', type=Path, help='Write the verified files and receipt to a new directory.')
    restore.add_argument('--reads', type=int, choices=range(1, 9), default=2)
    commands.add_parser('status')
    args = parser.parse_args(argv)
    try:
        if args.action == 'restore-packet':
            from frontier_evidence_packets import restore_into
            print(json.dumps(restore_into(args.case, args.output, args.reads), indent=2))
            return
        with closing(open_store(args.store)) as store:
            if args.action == 'cycle':
                result = cycle(store, args.study)
            elif args.action == 'capture':
                changes = capture_updates(store, read(args.file))
                result = {'capture_outcomes': changes, 'scout_capture': scout_capture.status(store)}
            elif args.action == 'revoke-scout':
                scout_capture.revoke(store, args.scout_id)
                result = {'revocation': 'RECORDED', 'scout_capture': scout_capture.status(store)}
            else:
                if args.action == 'import':
                    structured = args.format == 'json' or (args.format is None and args.file.endswith('.json'))
                    import_updates(store, read(args.file), structured=structured, stream=args.stream, observed=args.observed_at)
                elif args.action == 'atlas':
                    import_atlas(store)
                result = status(store)
    except (InputError, scout_capture.CaptureError) as error:
        parser.exit(2, f'{error}\n')
    except sqlite3.OperationalError as error:
        if getattr(error, 'sqlite_errorcode', None) == sqlite3.SQLITE_BUSY:
            parser.exit(2, 'The local research store is busy. Retry after the current operation finishes.\n')
        parser.exit(2, 'The local research store could not be read or written. Check its path and permissions.\n')
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, sqlite3.Error) as error:
        parser.exit(2, f'Research intake or activation stopped ({type(error).__name__}). Check the input, store and study scope.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.action == 'cycle' and result['runner_exit_code']:
        raise SystemExit(1)
