"""Run the bounded ALPHA-1 technical or private commercial workflow."""

import argparse
import json
import os
import subprocess
import sys

from ..__main__ import dump, private_path
from .economics import bounded_file, review
from .eligibility import assess
from .observations import collect
from .process import screen
from .study import named, qualify, verify


def load_private(path):
    return json.loads(bounded_file(private_path(path)))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('select', help='Show the source-linked authorized selection')
    observe = actions.add_parser('observe', help='Read the named public primary sources')
    observe.add_argument('--allow-network', required=True, action='store_true')
    observe.add_argument('--output', required=True)
    run = actions.add_parser('qualify', help='Run before/after, independent and retained-successor comparisons')
    run.add_argument('--observation', required=True)
    run.add_argument('--output', required=True)
    audit = actions.add_parser('verify', help='Reproduce the technical receipt with direct SQL')
    audit.add_argument('--receipt', required=True)
    for name in ('fit', 'process'):
        op = actions.add_parser(name, help='Screen a private local request')
        op.add_argument('--request', required=True)
        op.add_argument('--output', required=True)
    ledger = actions.add_parser('reconcile', help='Verify an owner-trusted reviewer and reconcile a private pilot')
    for flag in ('packet', 'signature', 'reviewer-key', 'reviewer-key-sha256', 'evidence-dir', 'output'):
        ledger.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    try:
        protocol = named('protocol.json')
        if args.action == 'select':
            print(json.dumps(named('opportunities.json'), ensure_ascii=False, indent=2))
            return 0
        if args.action == 'verify':
            print(json.dumps(verify(load_private(args.receipt))))
            return 0
        if args.action == 'observe':
            result = collect(protocol)
        elif args.action == 'qualify':
            result = qualify(load_private(args.observation))
        elif args.action == 'fit':
            result = assess(load_private(args.request), protocol, protocol['after'])
        elif args.action == 'process':
            result = screen(load_private(args.request), protocol)
        else:
            result = review(private_path(args.packet), private_path(args.signature), private_path(args.reviewer_key),
                            args.reviewer_key_sha256, private_path(args.evidence_dir), protocol)
        dump(result, private_path(args.output))
        return 0
    except (ValueError, OSError, AttributeError, KeyError, TypeError, subprocess.SubprocessError):
        print('ALPHA-1 operation stopped on unqualified evidence or an I/O failure.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
