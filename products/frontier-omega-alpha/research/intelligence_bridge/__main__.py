"""Review and receive a narrow finding using GitHub or a local inspection."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from ..__main__ import dump, private_path
from . import github_intake, intake, member

ROOT = Path(__file__).resolve().parent


def ledger_at(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 512 * 1024:
        raise ValueError('Invalid ledger path')
    return intake.history(path.read_bytes())


def render_run(result, old, output):
    output.mkdir(mode=0o700)
    record = result['record']
    summary = {'disposition': result['disposition'], 'record': record,
               'expected_prior_ledger_sha256': intake.digest(old), 'proposed_ledger_sha256': intake.digest(result['ledger'])}
    dump(summary, output / 'receipt.json')
    if result['ledger'] != old:
        dump(result['ledger'], output / 'ledger-next.json')


def receipt_at(path):
    path = private_path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 96 * 1024:
        raise ValueError('Invalid receipt path')
    return intake.load_json(path.read_bytes(), 96 * 1024)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    preview = subs.add_parser('prepare', help='Preflight one owner-reviewed projection before GitHub')
    preview.add_argument('--capsule', required=True)
    preview.add_argument('--disclosure-reviewed', required=True, action='store_true')
    receive = subs.add_parser('github', help='Receive one immutable PR blob using trusted GitHub metadata')
    receive.add_argument('--pr', required=True, type=int)
    receive.add_argument('--head', required=True, help='Full commit SHA explicitly approved for this intake')
    receive.add_argument('--allow-registered-experiment', action='store_true')
    for command in (preview, receive):
        command.add_argument('--ledger', default=str(ROOT / 'ledger.json'))
        command.add_argument('--output', required=True)
    review = subs.add_parser('review', help='Stage a reviewed hold, contradiction or invalidation')
    review.add_argument('--owner-reviewed', required=True, action='store_true')
    review.add_argument('--finding', required=True)
    review.add_argument('--phase', required=True, choices=sorted(intake.HOLDS - {'source-insufficient'}))
    review.add_argument('--ledger', required=True)
    review.add_argument('--output', required=True)
    export = subs.add_parser('member', help='Stage six encrypted-release inputs for owner review')
    export.add_argument('--owner-reviewed', required=True, action='store_true')
    export.add_argument('--receipt', required=True)
    export.add_argument('--ledger', required=True)
    export.add_argument('--output', required=True)
    promote = subs.add_parser('confirm-ledger', help='Bind one normalized append to the reviewed prior ledger')
    promote.add_argument('--owner-reviewed', required=True, action='store_true')
    for flag in ('receipt', 'ledger', 'proposal', 'output'):
        promote.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    try:
        now = datetime.now(timezone.utc)
        output = private_path(args.output)
        old = ledger_at(args.ledger)
        if args.command == 'review':
            dump(intake.observe_again(old, args.finding, args.phase, now), output)
            return 0
        if args.command == 'member':
            document = receipt_at(args.receipt)
            received = document.get('record', document)
            records = member.packet(received, old)
            output.mkdir(mode=0o700)
            for section, record in records.items():
                dump(record, output / (section + '.json'))
            return 0
        if args.command == 'confirm-ledger':
            report = receipt_at(args.receipt)
            proposed = ledger_at(private_path(args.proposal))
            record = report['record']
            if (not record or record.get('schema') != intake.RECORD or 'source_task_id' in record
                    or record['reception']['authenticated_by'] != 'github-rest'
                    or report['expected_prior_ledger_sha256'] != intake.digest(old)
                    or report['proposed_ledger_sha256'] != intake.digest(proposed)
                    or proposed != intake.append_record(old, record)):
                raise ValueError('Reviewer must reconcile the candidate against the current ledger')
            output.mkdir(mode=0o700)
            dump(proposed, output / 'ledger.json')
            dump(record, output / ('record-' + intake.digest(record) + '.json'))
            return 0
        if args.command == 'prepare':
            raw = intake.public_projection(private_path(args.capsule))
            prepared = intake.capsule(raw, now)
            reception = {'submitted_at': intake.utcstamp(now), 'submitter': None, 'github_pr': None,
                         'commit_sha': None, 'authenticated_by': 'local-only'}
            result = intake.receive(raw, old, reception, now)
            if prepared is None or result['disposition'] in ('duplicate', 'source-insufficient-repeat'):
                print(result['disposition'])
                return 0
            if result['disposition'] == 'source-insufficient':
                raise ValueError('Primary evidence is insufficient for public transfer')
            output.mkdir(mode=0o700)
            identifier = intake.event_id(prepared)
            dump(prepared, output / (identifier + '.json'))
            print(json.dumps({'id': identifier, 'branch': 'bridge-intake/' + identifier,
                              'path': intake.INBOX + identifier + '.json'}))
            return 0
        trusted = {name for name in os.environ.get('FRONTIER_BRIDGE_SUBMITTERS', '').split(',') if name}
        raw, reception = github_intake.intake_pr(args.pr, trusted, args.head)
        result = intake.receive(raw, old, reception, now, run_registered=args.allow_registered_experiment)
        render_run(result, old, output)
        return 0
    except (ValueError, KeyError, TypeError, OSError, AttributeError, subprocess.SubprocessError):
        print('Bridge intake stopped on a privacy, evidence, or authorization boundary.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
