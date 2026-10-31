"""Offline, source-bound candidate composition and independent checking."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from .core import ContractError, audit, capability_capsule, canonical, compose
from .evidence import reflect
from .experiment import experiment


def read(path):
    path = Path(path).absolute()
    if path.is_symlink() or any(q.is_symlink() for q in path.parents) or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ContractError('BOUNDED_REGULAR_INPUT_REQUIRED')
    def pairs(items):
        data = {}
        for k, v in items:
            if k in data:
                raise ContractError('DUPLICATE_JSON_KEY')
            data[k] = v
        return data
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)


def write_once(path, payload):
    path = Path(path).absolute()
    if path.exists() or path.is_symlink():
        raise FileExistsError('CREATE_ONLY_OUTPUT_REQUIRED')
    if not path.parent.is_dir() or any(q.is_symlink() for q in path.parents):
        raise ContractError('EXISTING_NORMAL_PARENT_REQUIRED')
    fd, temporary = tempfile.mkstemp(prefix='.mechanism-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(canonical(payload) + b'\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.chmod(path, 0o644)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline bounded mechanism synthesis; no runtime/financial authority')
    parser.add_argument('operation', choices=['compose', 'audit', 'capsule', 'reflect', 'experiment'])
    parser.add_argument('--spec', required=True)
    parser.add_argument('--plan')
    parser.add_argument('--check')
    parser.add_argument('--successor')
    parser.add_argument('--reference')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        spec = read(args.spec)
        if args.operation == 'experiment':
            if not args.successor or not args.reference:
                raise ContractError('SUCCESSOR_AND_REFERENCE_REQUIRED')
            value = experiment(spec, read(args.successor), read(args.reference))
        elif args.operation == 'reflect':
            value = reflect(spec)
        elif args.operation == 'compose':
            value = compose(spec)
        elif args.operation == 'audit':
            if not args.plan:
                raise ContractError('PLAN_REQUIRED')
            value = audit(spec, read(args.plan))
        else:
            if not args.plan or not args.check:
                raise ContractError('PLAN_AND_CHECK_REQUIRED')
            value = capability_capsule(spec, read(args.plan), read(args.check))
        write_once(args.output, value)
        print(json.dumps({'output': str(Path(args.output).absolute()), 'status': value.get('status', value.get('promotion_status', 'AUDITED')), 'claim_scope': value.get('scope', 'CANDIDATE_ONLY')}))
        return 0
    except (ContractError, FileExistsError, OSError, ValueError) as exc:
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
