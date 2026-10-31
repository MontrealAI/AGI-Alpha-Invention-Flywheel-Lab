"""Render an actual round Flywheel Harness diagram, with optional canonical native proof."""
import argparse
import json
import os
from pathlib import Path
import sys
from .readout import EvidenceError, empty_snapshot, live_readout, canonical
from .render import render_html, render_svg

def write_once(target, name, raw):
    path = target / name
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())

def publish(snapshot, target):
    target = Path(target).expanduser().absolute()
    if target.exists() or target.is_symlink() or not target.parent.is_dir() or any(p.is_symlink() for p in target.parents):
        raise EvidenceError('FRESH_NORMAL_OUTPUT_DIRECTORY_REQUIRED')
    if snapshot.get('funding_authority') is not False:
        raise EvidenceError('WHEEL_CANNOT_AUTHORIZE_FINANCE')
    svg = render_svg(snapshot)
    html = render_html(snapshot, svg)
    target.mkdir(mode=0o755)
    write_once(target, 'snapshot.json', canonical(snapshot) + b'\n')
    write_once(target, 'wheel.svg', svg.encode('utf8'))
    write_once(target, 'index.html', html.encode('utf8'))
    return {'schema':'agi-alpha/flywheel-wheel-presentation/v1','output':str(target),'files':['snapshot.json','wheel.svg','index.html'],'scope':snapshot['scope'],'funding_authority':False}

def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only circular Flywheel Harness (no account or deployment authority)')
    parser.add_argument('mode', choices=['architecture', 'audit-render'])
    parser.add_argument('--output', required=True, help='fresh output directory; never an existing native enterprise')
    parser.add_argument('--enterprise', help='existing trusted completed native enterprise output for canonical re-audit')
    parser.add_argument('--audit-timeout', type=int, default=600)
    args = parser.parse_args(argv)
    try:
        if args.mode == 'architecture':
            if args.enterprise:
                raise EvidenceError('ARCHITECTURE_REQUIRES_NO_ENTERPRISE')
            snapshot = empty_snapshot()
        else:
            if not args.enterprise:
                raise EvidenceError('TRUSTED_EXISTING_ENTERPRISE_REQUIRED')
            snapshot = live_readout(args.enterprise, timeout=args.audit_timeout)
        print(json.dumps(publish(snapshot,args.output),sort_keys=True))
        return 0
    except (EvidenceError, FileExistsError, ValueError, OSError, TimeoutError, json.JSONDecodeError) as e:
        print(type(e).__name__ + ': ' + str(e),file=sys.stderr)
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
