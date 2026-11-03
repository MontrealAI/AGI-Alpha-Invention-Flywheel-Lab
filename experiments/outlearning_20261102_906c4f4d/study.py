from __future__ import annotations
import argparse
import copy
import hashlib
import importlib
import json
from pathlib import Path
import random
import resource
import statistics
import time
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from .world import ProbeSession, SCHEDULES, public_task, make_world
from .evaluate import evaluate, confirmation_specs, development_specs, summary

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
PACKAGE = 'experiments.outlearning_20261102_906c4f4d'
ARMS = ('treatment', 'ordinary')


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value) + b'\n')


def load_method(arm):
    if arm not in ARMS:
        raise ValueError('REGISTERED_ARM_REQUIRED')
    return importlib.import_module(PACKAGE + ('.treatment' if arm == 'treatment' else '.baseline')).construct


def construct_program(spec, arm, charge_probe=None, cost_multiplier=1):
    effective = copy.deepcopy(spec)
    for provider in effective['providers']:
        provider['probe_unit_microUSD'] *= cost_multiplier
        provider['call_microUSD'] *= cost_multiplier
    session = ProbeSession(effective)
    task = public_task(effective)
    prices = {p['id']: p['probe_unit_microUSD'] for p in task['providers']}
    financial_declines = []

    def probe(provider, sequence):
        cost = len(sequence) * prices[provider]
        if session.spent_microUSD + cost <= task['probe_budget_microUSD'] and charge_probe:
            if not charge_probe(len(session.transcript), provider, sequence, cost):
                financial_declines.append({'provider': provider, 'cost_microUSD': cost})
                return {'error': 'BUDGET_EXHAUSTED', 'remaining_microUSD': 0}
        return session(provider, sequence)

    started, before = time.monotonic(), time.process_time()
    output = load_method(arm)(copy.deepcopy(task), probe)
    if isinstance(output, dict) and 'program' in output:
        program = output['program']
        metadata = {key: value for key, value in output.items() if key != 'program'}
    else:
        program, metadata = output, {}
    return {'task': task, 'program': program, 'construction': metadata,
            'probe_cost_microUSD': session.spent_microUSD, 'probe_transcript': session.transcript,
            'financial_declines': financial_declines,
            'resources': {'cpu_seconds': time.process_time()-before, 'wall_seconds': time.monotonic()-started}}


def evaluate_program(spec, program):
    validate_case_spec(spec)
    if spec.get('operating_schedule') not in SCHEDULES:
        raise ValueError('PRECOMMITTED_OPERATING_SCHEDULE_REQUIRED')
    result = evaluate(spec, program)
    actual = next((row for row in result['outcomes'] if row['schedule'] == spec['operating_schedule']), None)
    return {**result, 'complete_delivery': bool(result['all_safe'] and actual and actual['delivered']),
            'actual_outcome': actual, 'operating_schedule': spec['operating_schedule']}


def validate_case_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError('REGISTERED_CASE_REQUIRED')
    stage, seed, stratum = spec.get('stage'), spec.get('seed'), spec.get('stratum')
    if stage == 'K1' and type(stratum) is int and 0 <= stratum < 8:
        expected_seed = 'economic-K1/v1/' + str(stratum)
        schedule = SCHEDULES[stratum % 4]
    elif stage == 'K2' and type(stratum) is int and 0 <= stratum < 6:
        allowed = [f'OUTLEARN-20261102-906c4f4d/confirmation/v1/{stratum}/{i}' for i in range(2)]
        if seed not in allowed:
            raise ValueError('REGISTERED_ECONOMIC_SEED_REQUIRED')
        replicate = allowed.index(seed)
        expected_seed = seed
        schedule = SCHEDULES[(stratum*2+replicate) % 4]
    else:
        raise ValueError('REGISTERED_ECONOMIC_FAMILY_REQUIRED')
    if seed != expected_seed:
        raise ValueError('REGISTERED_ECONOMIC_SEED_REQUIRED')
    expected = make_world(seed, stage, stratum)
    expected['operating_schedule'] = schedule
    if spec != expected:
        raise ValueError('REGISTERED_WORLD_OR_SCHEDULE_CHANGED')
    return True


def freeze_paths():
    names = {str(p.relative_to(ROOT)) for p in FOLDER.glob('*.py')}
    names.update(str(p.relative_to(ROOT)) for p in FOLDER.glob('*.json') if p.name not in {'FREEZE.json', 'CONFIRMATION_LOCK.json'})
    names.update(str(p.relative_to(ROOT)) for p in FOLDER.glob('*.md') if p.name not in {'README.md', 'RESULTS.md', 'INDEPENDENT_REVIEW.md', 'ECONOMIC_REVIEW.md'})
    names.update(('commercial/ledger.py', 'connected_enterprise/finance.py', 'connected_enterprise/runner.py',
                  '.github/workflows/outlearning-906c4f4d.yml'))
    return sorted(names)


def freeze():
    path = FOLDER/'FREEZE.json'
    if path.exists():
        raise ValueError('FROZEN_PROTOCOL_CANNOT_BE_OVERWRITTEN')
    value = {'schema': 'outlearning-source-freeze/v1', 'files': {
        name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in freeze_paths()},
        'confirmation_rule': '48 K2 worlds, six strata by eight fixed seeds; four schedules each; no replacement',
        'evidence_boundary': 'Before confirmation; K1 development and ordinary engineering tests are exposed.'}
    save(path, value)
    return digest(value)


def verify_freeze(expected):
    value = strict_json((FOLDER/'FREEZE.json').read_bytes())
    if digest(value) != expected:
        raise ValueError('EXPECTED_FREEZE_DIGEST_MISMATCH')
    for name, sha in value['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise ValueError('FROZEN_SOURCE_CHANGED:' + name)
    return value


def normalize_spec(spec):
    providers = [{key: value for key, value in row.items() if key != 'id'} for row in spec['providers']]
    return {'stage': spec['stage'], 'providers': sorted(providers, key=canonical),
            'budget': spec['probe_budget_microUSD'], 'steps': spec['max_steps']}


def _net(row, price=600_000_000):
    evaluation = row['evaluation']
    delivered = evaluation['delivered_count'] if evaluation['all_safe'] else 0
    gross = delivered * price
    cost = 4*row['probe_cost_microUSD'] + evaluation['operation_cost_microUSD'] + evaluation['residual_exposure_microUSD']
    return (gross-cost)/4


def analyze(rows):
    if len(rows) != 96 or any(row.get('arm') not in ARMS for row in rows):
        raise ValueError('EXACT_REGISTERED_CONFIRMATION_DENOMINATOR_REQUIRED')
    expected = {spec['world_id']: (digest(spec), spec['stratum']) for spec in confirmation_specs()}
    seen = {arm: set() for arm in ARMS}
    for row in rows:
        evaluation, arm = row['evaluation'], row['arm']
        ident = evaluation['world_id']
        if (ident not in expected or ident in seen[arm]
                or (evaluation['world_sha256'], row['stratum']) != expected[ident]):
            raise ValueError('UNIQUE_REGISTERED_MATCHED_WORLD_REQUIRED')
        seen[arm].add(ident)
    if any(ids != set(expected) for ids in seen.values()):
        raise ValueError('ALL_REGISTERED_WORLDS_REQUIRED')
    by_arm = {arm: [row for row in rows if row['arm'] == arm] for arm in ARMS}
    pairs = []
    for left, right in zip(by_arm['treatment'], by_arm['ordinary']):
        if left['evaluation']['world_sha256'] != right['evaluation']['world_sha256']:
            raise ValueError('MATCHED_WORLD_REQUIRED')
        pairs.append({'world_id': left['evaluation']['world_id'], 'stratum': left['stratum'],
                      'delta_microUSD': _net(left)-_net(right),
                      'treatment_net_microUSD': _net(left), 'ordinary_net_microUSD': _net(right)})
    means = [statistics.mean(p['delta_microUSD'] for p in pairs if p['stratum'] == group) for group in range(6)]
    rng = random.Random('OUTLEARN-906c4f4d-cluster-bootstrap-v1')
    boots = sorted(statistics.mean(rng.choices(means, k=6)) for _ in range(4096))
    interval = [boots[102], boots[3993]]
    summaries = {arm: summary(by_arm[arm]) for arm in ARMS}
    extra_harm = summaries['treatment']['harm_schedules'] > summaries['ordinary']['harm_schedules']
    material = interval[0] > 3_000_000 and not extra_harm
    return {'schema': 'outlearning-method-comparison/v1', 'arms': summaries, 'paired_worlds': len(pairs),
            'primary': {'name': 'conditional_net_contribution_per_K2_request_at_600_USD',
                        'mean_delta_microUSD': statistics.mean(p['delta_microUSD'] for p in pairs),
                        'family_cluster_percentile95_microUSD': interval,
                        'family_mean_delta_microUSD': means,
                        'material_threshold_microUSD': 3_000_000,
                        'rationale': '300 USD authored incremental K2 method deployment burden divided by 100 non-guaranteed future qualified opportunities.',
                        'method_advantage_established': material,
                        'uncertainty_scope': 'Descriptive resampling of six authored mechanism families, not calibrated market probabilities or independent real-provider inference.'},
            'paired_effects': pairs,
            'ordinary_reuse_is_equal_content_ablation': True,
            'human_productivity_advantage': 'UNMEASURED',
            'general_model_self_improvement': 'NOT_ESTABLISHED'}


def run(output, expected, label, economics=True):
    frozen = verify_freeze(expected)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('NEW_RUN_OUTPUT_REQUIRED_USE_RESUME_FOR_ORIGINAL')
    if label not in {'confirmation', 'reproduction'}:
        raise ValueError('EXPLICIT_EXECUTION_LABEL_REQUIRED')
    if label == 'confirmation':
        with (FOLDER/'CONFIRMATION_LOCK.json').open('x') as stream:
            json.dump({'freeze_sha256': expected, 'output': str(output)}, stream)
    output.mkdir(parents=True)
    started, cpu = time.monotonic(), time.process_time()
    save(output/'INPUT.json', {'freeze_sha256': expected, 'label': label, 'economics': economics})
    try:
        specs = list(confirmation_specs())
        normalized = [digest(normalize_spec(spec)) for spec in specs]
        k1 = [digest(normalize_spec(spec)) for spec in development_specs()]
        exact_ids = [digest(spec) for spec in specs]
        freshness = {'exact_world_duplicates': len(exact_ids)-len(set(exact_ids)),
                     'permutation_normalized_mechanism_duplicates': len(normalized)-len(set(normalized)),
                     'K1_K2_normalized_overlap': len(set(k1) & set(normalized)),
                     'shared_provenance': 'One authored simulator. K1 singleton mechanisms are deliberately retained; fresh K2 composes them with changed costs, lags, holds and measurement gaps.',
                     'external_blinding': False, 'case_count': len(specs)}
        rows = []
        for i, spec in enumerate(specs):
            for arm in ARMS:
                row = construct_program(spec, arm)
                row.update(arm=arm, stratum=spec['stratum'], evaluation=evaluate(spec, row['program']))
                rows.append(row)
                save(output/'science'/f'{i:02d}-{arm}.json', row)
        science = analyze(rows)
        science.update(freeze_sha256=expected, execution_label=label, freshness=freshness)
        save(output/'SCIENCE.json', science)
        econ = None
        if economics:
            from .economics import run_portfolio
            econ = run_portfolio(output/'native', expected)
            save(output/'ECONOMICS.json', econ)
        result = {'freeze_sha256': expected, 'label': label,
                  'science_sha256': digest(science), 'economics_sha256': digest(econ) if econ else None,
                  'cpu_seconds': time.process_time()-cpu, 'wall_seconds': time.monotonic()-started,
                  'paid_model_API_calls': 0, 'new_external_spending_USD': 0,
                  'actual_model_tokens_and_billing': None, 'source_files': len(frozen['files'])}
        save(output/'EXECUTION.json', result)
        return result
    except BaseException as exc:
        save(output/'FAILURE.json', {'type': type(exc).__name__, 'message': str(exc),
                                  'freeze_sha256': expected, 'cpu_seconds': time.process_time()-cpu,
                                  'wall_seconds': time.monotonic()-started, 'outcomes_preserved': True})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['freeze', 'run', 'resume-economics'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-freeze')
    parser.add_argument('--label', choices=['confirmation', 'reproduction'], default='reproduction')
    parser.add_argument('--science-only', action='store_true')
    args = parser.parse_args()
    if args.command == 'freeze':
        result = {'freeze_sha256': freeze()}
    elif args.command == 'run':
        result = run(args.output, args.expected_freeze, args.label, not args.science_only)
    else:
        frozen = verify_freeze(args.expected_freeze)
        original = strict_json((args.output/'INPUT.json').read_bytes())
        if original['freeze_sha256'] != args.expected_freeze or not (args.output/'SCIENCE.json').is_file():
            raise ValueError('ORIGINAL_COMPLETED_SCIENCE_REQUIRED_FOR_ECONOMIC_RESUME')
        start, cpu = time.monotonic(), time.process_time()
        from .economics import run_portfolio
        result = run_portfolio(args.output/'native', args.expected_freeze)
        save(args.output/'ECONOMICS.json', result)
        science = strict_json((args.output/'SCIENCE.json').read_bytes())
        final = args.output/'EXECUTION.json'
        if final.exists():
            receipt = strict_json(final.read_bytes())
            if receipt['science_sha256'] != digest(science) or receipt['economics_sha256'] != digest(result):
                raise ValueError('COMPLETED_EXECUTION_CHANGED_ON_RESUME')
        else:
            save(final, {'freeze_sha256': args.expected_freeze, 'label': original['label'],
                         'science_sha256': digest(science), 'economics_sha256': digest(result),
                         'resumed_original_accounts': True, 'prior_failure_preserved': (args.output/'FAILURE.json').exists(),
                         'resume_cpu_seconds': time.process_time()-cpu, 'resume_wall_seconds': time.monotonic()-start,
                         'full_interrupted_resource_total': None,
                         'paid_model_API_calls': 0, 'new_external_spending_USD': 0,
                         'actual_model_tokens_and_billing': None, 'source_files': len(frozen['files'])})
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
