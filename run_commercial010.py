"""Run the source-frozen commercial campaign with the existing bounded supervisor."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent
FREEZE = ROOT / 'campaign/commercial-010/SOURCE_FREEZE.json'


def checked_inputs(expected):
    if FREEZE.is_symlink() or hashlib.sha256(FREEZE.read_bytes()).hexdigest() != expected:
        raise ValueError('EXTERNAL_SOURCE_FREEZE_MISMATCH')
    freeze = json.loads(FREEZE.read_bytes())
    if freeze['scope'] != 'SIMULATED' or freeze['claim_mode'] != 'FINITE_ENGINEERING_COMPARISON':
        raise ValueError('FROZEN_EVIDENCE_SCOPE_REQUIRED')
    for name, digest in freeze['sources'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('RELATIVE_FROZEN_SOURCE_REQUIRED')
        source = ROOT / path
        if source.is_symlink() or any(p.is_symlink() for p in source.parents) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('FROZEN_SOURCE_CHANGED ' + name)
    from commercial.ledger import load_jobs
    from commercial.market import validate_policy
    manifest = ROOT / freeze['manifest']
    policy = ROOT / freeze['policy']
    load_jobs(ROOT, json.loads(manifest.read_bytes()))
    validate_policy(json.loads(policy.read_bytes()))
    return freeze, manifest, policy


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--freeze-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--resource-ledger', type=Path)
    p.add_argument('--check-inputs', action='store_true')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--smoke-world', default='qualified_differentiation')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    a = p.parse_args()
    freeze, manifest_path, policy_path = checked_inputs(a.freeze_sha256)
    if a.output.exists() or a.output.is_symlink():
        raise FileExistsError(a.output)
    if a.check_inputs:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('x') as f:
            json.dump({'scope': 'SIMULATED', 'source_freeze_sha256': a.freeze_sha256, 'inputs_accepted': True, 'commercial_verdict': 'NOT_EXECUTED_BY_INPUT_CHECK'}, f, indent=2)
        return
    if not a.worker:
        from experiments.resource006_v3 import run
        output = a.output.absolute()
        ledger = a.resource_ledger or output.with_name(output.name + '-resources.json')
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--freeze-sha256', a.freeze_sha256, '--output', str(output / 'artifacts')]
        if a.smoke:
            command.extend(['--smoke', '--smoke-world', a.smoke_world])
        limits = {'wall_seconds': 3600 if not a.smoke else 600, 'cpu_seconds': 3600 if not a.smoke else 600,
                  'memory_bytes': 2147483648, 'output_bytes': 64000000, 'storage_bytes': 800000000}
        result = run(command, output, ledger, 'commercial010-' + ('smoke-' if a.smoke else 'full-') + str(time.time_ns()), limits, cwd=ROOT)
        print(json.dumps({'state': result['receipt']['state'], 'receipt_path': str(output / 'RECEIPT.json'), 'scope': 'SIMULATED'}))
        if result['receipt']['state'] != 'complete':
            raise SystemExit(1)
        return
    from commercial.market import run_campaign, run_world
    if a.smoke:
        policy = json.loads(policy_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
        worlds = [w for w in policy['worlds'] if w['id'] == a.smoke_world]
        if len(worlds) != 1:
            raise ValueError('DECLARED_SMOKE_WORLD_REQUIRED')
        result = run_world(root=ROOT, manifest=manifest, policy=policy, world=worlds[0], seed=policy['exploration_seeds'][0], multiplier=9500, directory=a.output)
        print(json.dumps({'mode': 'ENGINEERING_REPLAY_ONLY', 'paid_jobs': result['paid_jobs'], 'scope': 'SIMULATED'}))
    else:
        result = run_campaign(root=ROOT, manifest_path=manifest_path, policy_path=policy_path, output=a.output,
                              expected_manifest_sha256=freeze['sources'][freeze['manifest']], expected_policy_sha256=freeze['sources'][freeze['policy']])
        print(json.dumps({'scope': result['scope'], 'verdicts': result['verdicts']}, indent=2))


if __name__ == '__main__':
    main()
