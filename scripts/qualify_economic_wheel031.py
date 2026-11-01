"""Bounded fresh synthetic integration, no imported private account and no real commerce."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flywheel_wheel.coupling import SCHEMA, live_context, assess, verify_proposal
from flywheel_wheel.readout import canonical, sha, live_readout
from flywheel_wheel.__main__ import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.absolute()
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise ValueError('FRESH_PROOF_OUTPUT_REQUIRED')
    output.mkdir()
    started = time.monotonic()
    usage0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    deadline = started + 420
    from connected_enterprise.engine import default_config
    config = default_config()
    config.update(horizon_days=7, customer_pool=4, initial_slots=1, maximum_slots=1)
    registration = {
        'schema': 'agi-alpha/connected014-registration/v1', 'label': 'economic-wheel031-wiring',
        'evidence_role': 'development', 'seeds': [2610311931], 'configs': {'central': config},
        'arms': ['baseline', 'growth'], 'control_arm': 'baseline', 'candidate_arm': 'growth',
        'service_cohort_seed': 2610311932, 'workers': 1,
    }
    registration_path = output / 'INPUT.json'
    registration_path.write_bytes(canonical(registration))
    enterprise = output / 'private-enterprise'
    commands = []

    def run(*parts):
        remaining = int(deadline - time.monotonic())
        if remaining <= 0: raise TimeoutError('CUMULATIVE_PROOF_WALL_LIMIT')
        result = subprocess.run([sys.executable, '-m', 'connected_enterprise', *parts],
                                cwd=ROOT, capture_output=True, timeout=min(180, remaining))
        commands.append({'operation': parts[0], 'returncode': result.returncode})
        if result.returncode:
            raise RuntimeError('NATIVE_COMMAND_FAILED:' + parts[0] + ':' + result.stderr.decode(errors='replace')[-3000:])

    run('register', '--config', str(registration_path), '--output', str(enterprise))
    run('operate', '--output', str(enterprise))
    frozen = json.loads((enterprise/'FROZEN.json').read_bytes())
    world = '2610311931-central-baseline'
    snapshot = live_readout(enterprise, timeout=max(1, min(120, int(deadline-time.monotonic()))))
    ctx = live_context(enterprise, world, timeout=max(1, min(120, int(deadline-time.monotonic()))))
    before = {p.relative_to(enterprise).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in enterprise.glob('worlds/*/account.sqlite*') if p.is_file()}
    if not before: raise RuntimeError('NATIVE_ACCOUNT_HISTORY_EXPECTED')
    request = {
        'schema': SCHEMA, 'expected_context_sha256': sha(ctx), 'planning_cap_microUSD': 1_000_000,
        'allocation': {'schema': 'alpha-transformational-allocation/v1', 'scope': 'SIMULATED',
            'currency': 'simulated-microUSD', 'scenarios': {'unknown-market': 10000},
            'actions': [{'id': 'next-delivery', 'lane': 'delivery', 'catalog_id': 'reconciliation',
                'cost': config['production_cost'], 'requires': [], 'exclusive_group': None,
                'cash_returns': None, 'evidence': 'no-new-market-forecast-supplied', 'authorized': True}],
            'synergies': [], 'max_states': 16, 'worst_loss_limit': 0, 'downside_penalty_bps': 10000},
        'assets': [], 'shared_costs': [],
        'incentives': [{'id': 'review-fee', 'role': 'verifier', 'payee': 'checker',
            'adjudicator': 'audit-owner', 'basis': 'completed_check', 'cap_microUSD': 100_000,
            'evidence_ref': 'declared-design-contract-not-payment'}],
        'attachments': {'next-delivery': {'scope': 'synthetic-reconciliation', 'asset_ids': [],
            'incentive_ids': ['review-fee'], 'shared_cost_ids': [], 'producer': 'producer',
            'checker': 'checker', 'fresh_mission_check': True, 'base_excludes_declared_extras': True}},
    }
    universe = {'jobs': [{'id': 'reconciliation'}]}
    proposal = assess(request, ctx, universe)
    checked = verify_proposal(proposal, request, ctx, universe)
    if proposal['decision'] != 'RETAIN_CASH' or proposal['selected_actions']:
        raise RuntimeError('UNKNOWN_RETURN_MUST_NOT_BECOME_CASH')
    after = {p.relative_to(enterprise).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in enterprise.glob('worlds/*/account.sqlite*') if p.is_file()}
    if before != after: raise RuntimeError('READ_ONLY_PLAN_CHANGED_NATIVE_HISTORY')
    public = output/'public'
    publish(snapshot, public, detailed=True)
    (public/'proposal.json').write_bytes(canonical(proposal)+b'\n')
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'schema': 'agi-alpha/economic-wheel-integration/v1',
        'scope': 'FRESH_SEVEN_DAY_SYNTHETIC_WIRING_NOT_ECONOMIC_ADVANTAGE',
        'source_sha256': frozen['source']['sha256'], 'frozen_sha256': frozen['sha256'],
        'world_count': len(snapshot['worlds']), 'selected_native_world': world,
        'native_audit_reexecuted': True, 'planner_reuses_existing_allocator': True,
        'proposal_rederived': checked['accepted'], 'native_history_unchanged': True,
        'decision': proposal['decision'], 'unknown_return_preserved': True,
        'funding_authority': False, 'actual_customers': 0, 'actual_collections_microUSD': 0,
        'actual_profit_microUSD': None, 'commands': commands,
        'wall_seconds': time.monotonic()-started,
        'child_cpu_seconds': usage.ru_utime + usage.ru_stime - usage0.ru_utime - usage0.ru_stime,
        'limits': ['No payment, operating reallocation, economic uplift, incentive equilibrium or recursive improvement is established.',
                   'CPU/wall are command resources, not complete engineering/model/host bills.',
                   'Only public sanitized files are uploaded; private native state remains in the disposable runner.']}
    (public/'INTEGRATION.json').write_bytes(canonical(receipt)+b'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__': main()
