from __future__ import annotations
import argparse
import json
from pathlib import Path
from .policy import loads, canonical


def main():
    parser = argparse.ArgumentParser(description='ALPHA GENESIS Ω: opt-in frontier discovery and native simulated operation')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('register', 'pilot'):
        p = sub.add_parser(name)
        p.add_argument('--output', required=True, type=Path)
        p.add_argument('--protocol', type=Path, default=Path(__file__).resolve().parents[1] / 'campaign/genesis-enterprise-002/PROTOCOL.json')
    for name in ('operate', 'resume', 'audit', 'export'):
        p = sub.add_parser(name)
        p.add_argument('--output', required=True, type=Path)
        if name in ('operate', 'resume'):
            p.add_argument('--max-steps', type=int)
        if name == 'export':
            p.add_argument('--destination', required=True, type=Path)
    p = sub.add_parser('observe')
    p.add_argument('--repo', required=True)
    p.add_argument('--output', required=True, type=Path)
    p = sub.add_parser('hypotheses')
    p.add_argument('--input', required=True, type=Path)
    p = sub.add_parser('propose')
    p.add_argument('--objective', required=True)
    p.add_argument('--observations', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--model', required=True)
    args = parser.parse_args()
    if args.command == 'observe':
        from .frontier import observe
        result = observe(args.repo)
        with args.output.open('xb') as f:
            f.write(canonical(result))
    elif args.command == 'hypotheses':
        from .frontier import validate_hypotheses
        result = validate_hypotheses(loads(args.input.read_bytes()))
    elif args.command == 'propose':
        from .codex import propose
        result = propose(args.objective, loads(args.observations.read_bytes()), args.output, args.model)
    else:
        from . import native
        if args.command in ('register', 'pilot'):
            result = native.register(Path(__file__).resolve().parents[1], args.output, args.protocol)
            if args.command == 'pilot':
                result = native.operate(args.output)
        elif args.command in ('operate', 'resume'):
            result = native.operate(args.output, max_steps=args.max_steps)
        elif args.command == 'audit':
            result = native.audit(args.output)
        else:
            result = native.export_public(args.output, args.destination)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
