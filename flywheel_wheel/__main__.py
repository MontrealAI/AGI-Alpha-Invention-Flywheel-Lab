"""Render an actual round Flywheel Harness diagram, with optional canonical native proof."""
import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
from .readout import EvidenceError, empty_snapshot, live_readout, canonical
from .render import render_html, render_svg
from .coupling import live_context, assess, verify_proposal
from .preflight import fresh_output

def write_once(target, name, raw):
    path = target / name
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())

def publish(snapshot, target, *, detailed=False):
    target = Path(target).expanduser().absolute()
    if target.exists() or target.is_symlink() or not target.parent.is_dir() or any(p.is_symlink() for p in target.parents):
        raise EvidenceError('FRESH_NORMAL_OUTPUT_DIRECTORY_REQUIRED')
    if snapshot.get('funding_authority') is not False:
        raise EvidenceError('WHEEL_CANNOT_AUTHORIZE_FINANCE')
    if detailed:
        from .atlas import render_svg as draw, render_html as page
        svg = draw(snapshot)
        html = page(snapshot, svg)
    else:
        svg = render_svg(snapshot)
        html = render_html(snapshot, svg)
    target.mkdir(mode=0o755)
    write_once(target, 'snapshot.json', canonical(snapshot) + b'\n')
    write_once(target, 'wheel.svg', svg.encode('utf8'))
    write_once(target, 'index.html', html.encode('utf8'))
    return {'schema':'agi-alpha/flywheel-wheel-presentation/v1','output':str(target),'files':['snapshot.json','wheel.svg','index.html'],'scope':snapshot['scope'],'funding_authority':False}

def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only circular Flywheel Harness (no account or deployment authority)')
    parser.add_argument('mode', choices=['architecture', 'audit-render', 'atlas', 'precision', 'couple'])
    parser.add_argument('--output', required=True, help='fresh output directory; never an existing native enterprise')
    parser.add_argument('--enterprise', help='existing trusted completed native enterprise output for canonical re-audit')
    parser.add_argument('--trust-frozen-source', action='store_true', help='required for audit-render: acknowledge executing trusted frozen repository source')
    parser.add_argument('--audit-timeout', type=int, default=600)
    parser.add_argument('--request', help='couple: data-only economic contract')
    parser.add_argument('--universe', help='couple: existing portfolio universe')
    parser.add_argument('--world', help='couple: exactly one existing simulated business')
    args = parser.parse_args(argv)
    try:
        if args.mode in {'architecture', 'atlas', 'precision'}:
            if args.enterprise or args.trust_frozen_source:
                raise EvidenceError('ARCHITECTURE_REQUIRES_NO_ENTERPRISE')
            if args.mode == 'precision':
                from .precision import publish as publish_precision
                print(json.dumps(publish_precision(args.output),sort_keys=True))
                return 0
            snapshot = empty_snapshot()
        else:
            if not args.enterprise:
                raise EvidenceError('TRUSTED_EXISTING_ENTERPRISE_REQUIRED')
            if not args.trust_frozen_source:
                raise EvidenceError('EXPLICIT_TRUSTED_EXECUTABLE_SOURCE_ACKNOWLEDGEMENT_REQUIRED')
            fresh_output(args.output, args.enterprise)
            if args.mode == 'couple':
                if not args.request or not args.universe or not args.world:
                    raise EvidenceError('REQUEST_UNIVERSE_AND_SINGLE_WORLD_REQUIRED')
                from portfolio_scale.transformational import read_json
                request = read_json(Path(args.request))
                universe = read_json(Path(args.universe))
                context = live_context(args.enterprise, args.world, timeout=args.audit_timeout)
                proposal = assess(request, context, universe)
                verify_proposal(proposal, request, context, universe)
                target = Path(args.output).expanduser().absolute()
                if target.exists() or target.is_symlink() or not target.parent.is_dir() or any(p.is_symlink() for p in target.parents):
                    raise EvidenceError('FRESH_NORMAL_OUTPUT_DIRECTORY_REQUIRED')
                target.mkdir()
                write_once(target, 'context.json', canonical(context)+b'\n')
                write_once(target, 'proposal.json', canonical(proposal)+b'\n')
                print(json.dumps({'decision':proposal['decision'], 'scope':proposal['scope'], 'funding_authority':False}))
                return 0
            snapshot = live_readout(args.enterprise, timeout=args.audit_timeout)
        print(json.dumps(publish(snapshot,args.output,detailed=args.mode=='atlas'),sort_keys=True))
        return 0
    except (EvidenceError, FileExistsError, ValueError, OSError, TimeoutError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError, KeyError, RecursionError) as e:
        print(type(e).__name__ + ': ' + str(e),file=sys.stderr)
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
