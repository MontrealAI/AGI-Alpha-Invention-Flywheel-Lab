"""Execute the publicly registered finite observation cases without external IO."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from mechanism_harness.core import digest
from omega.observation import execute, retained_recipes, select_panel
from omega.observation_verify import conventional_execute, conventional_panel, verify_receipt

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'campaign/omega-continuation-bdd6/OBSERVATION_CASES.json'
REGISTERED_FIXTURE_SHA256 = '397019f7fd2a34cd17baf8936f7b52c080ba1de512de6da92db6d26dd74925b8'
REGISTRATION_COMMIT = 'de303edf37550caef668a9d926dbe79292ece567'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _device(request, evaluation):
    """Evaluator-owned deterministic device double; not a physical measurement."""
    sensors = {s['id']: s for s in request['sensors']}
    calls = []
    def read(ident):
        if ident not in sensors or not sensors[ident]['authorized'] or ident in calls:
            raise ValueError('UNAUTHORIZED_OR_REPEATED_DEVICE_CALL')
        calls.append(ident)
        return evaluation['readings'].get(ident)
    return read, calls


def _truth_acceptance(request, evaluation, receipt):
    truth_id = evaluation['true_world_id']
    truth = next((w for w in request['hypotheses'] if w['id'] == truth_id), None)
    accepted = receipt['status'] == 'MODEL_DECISION' and truth is not None and receipt['action'] in truth['accepted_actions']
    if receipt['status'] == 'MODEL_DECISION' and not accepted:
        raise AssertionError('EVALUATOR_REJECTED_ACTION')
    return accepted


def run():
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    if _sha(FIXTURE) != REGISTERED_FIXTURE_SHA256:
        raise ValueError('PUBLICLY_REGISTERED_FIXTURES_CHANGED')
    spec = json.loads(FIXTURE.read_text())
    results, retained = [], None
    for case in spec['cases']:
        request = copy.deepcopy(case['request'])
        if case['id'] in {'successor_inherited_recipe', 'successor_ordinary_equal_content'}:
            if retained is None or retained != request['inherited_recipes']:
                raise AssertionError('ACTUAL_PREDECESSOR_CONTENT_DIFFERS_FROM_REGISTRATION')
            request['inherited_recipes'] = copy.deepcopy(retained)
        evaluation = case['evaluation_only']
        record = {'case_id': case['id'], 'request_sha256': digest(request), 'role': case['role']}
        candidate_read, candidate_calls = _device(request, evaluation)
        conventional_read, conventional_calls = _device(request, evaluation)
        if evaluation['expected_input_error'] is not None:
            errors = {}
            for label, runner, reader in [('candidate', execute, candidate_read), ('conventional', conventional_execute, conventional_read)]:
                try:
                    runner(request, reader)
                except ValueError as exc:
                    errors[label] = str(exc)
                else:
                    raise AssertionError('INVALID_INPUT_WAS_ACCEPTED')
            if any(message != evaluation['expected_input_error'] for message in errors.values()) or candidate_calls or conventional_calls:
                raise AssertionError('STALE_INPUT_FAILURE_MISMATCH')
            record.update(status='INPUT_REJECTED', input_errors=errors, candidate_device_calls=[], conventional_device_calls=[])
            results.append(record)
            continue
        candidate_plan = select_panel(request)
        conventional_plan = conventional_panel(request)
        candidate = execute(request, candidate_read)
        conventional = conventional_execute(request, conventional_read)
        candidate_check = verify_receipt(request, candidate)
        conventional_check = verify_receipt(request, conventional)
        candidate_accepted = _truth_acceptance(request, evaluation, candidate)
        conventional_accepted = _truth_acceptance(request, evaluation, conventional)
        if case['id'] == 'separating_assay':
            retained = retained_recipes(request, candidate)
        record.update(candidate_plan=candidate_plan, conventional_plan=conventional_plan,
                      candidate_receipt=candidate, conventional_receipt=conventional,
                      candidate_device_calls=candidate_calls, conventional_device_calls=conventional_calls,
                      candidate_independent_check=candidate_check, conventional_independent_check=conventional_check,
                      candidate_useful_action_accepted=candidate_accepted, conventional_useful_action_accepted=conventional_accepted,
                      exact_plan_tie=candidate_plan == conventional_plan,
                      exact_transcript_tie=candidate == conventional)
        results.append(record)
    executed = [r for r in results if 'candidate_receipt' in r]
    by_id = {r['case_id']: r for r in executed}
    successor = {}
    predecessor_cost = by_id['separating_assay']['candidate_receipt']['incurred_cost_cents']
    for arm in ('no_predecessor', 'inherited_recipe', 'ordinary_equal_content', 'cash_only', 'no_sensing'):
        row = by_id['successor_' + arm]
        receipt = row['candidate_receipt']
        successor[arm] = {'status': receipt['status'], 'action': receipt['action'],
                          'successor_cost_cents': receipt['incurred_cost_cents'],
                          'initial_spending_capacity_cents': case_request(spec, 'successor_' + arm)['budget_cents'],
                          'causal_asset': 'identical_recipe_content' if arm in ('inherited_recipe', 'ordinary_equal_content') else None,
                          'prior_acquisition_cost_cents': predecessor_cost if arm in ('inherited_recipe', 'ordinary_equal_content') else 0,
                          'lifecycle_cost_cents': receipt['incurred_cost_cents'] + (predecessor_cost if arm in ('inherited_recipe', 'ordinary_equal_content') else 0)}
    try:
        git_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        git_head, dirty = None, None
    dependencies = ['omega/observation.py', 'omega/observation_verify.py', 'omega/observation_run.py',
                    'mechanism_harness/core.py', 'campaign/omega-continuation-bdd6/OBSERVATION_CASES.json']
    all_ties = all(r['exact_plan_tie'] and r['exact_transcript_tie'] for r in executed)
    return {'schema': 'omega-observation-result/v1', 'registration_commit': REGISTRATION_COMMIT,
            'fixture_sha256': REGISTERED_FIXTURE_SHA256, 'git_head': git_head, 'worktree_dirty': dirty,
            'source_sha256': {name: _sha(ROOT / name) for name in dependencies},
            'python': platform.python_version(), 'evidence_role': 'REGISTERED_FINITE_AUTHORED_COMPARISON',
            'summary': {'registered_cases': len(results), 'executed_valid_cases': len(executed),
                        'invalid_input_cases_rejected': len(results)-len(executed),
                        'candidate_useful_actions': sum(r['candidate_useful_action_accepted'] for r in executed),
                        'conventional_useful_actions': sum(r['conventional_useful_action_accepted'] for r in executed),
                        'exact_complete_outcome_ties': sum(r['exact_plan_tie'] and r['exact_transcript_tie'] for r in executed),
                        'extraordinary_advantage': 'NOT_ESTABLISHED_COMPLETE_CONVENTIONAL_TIE' if all_ties else 'UNRESOLVED_REQUIRES_REVIEW',
                        'retained_method_advantage': 'NOT_ESTABLISHED_EQUAL_CONTENT_CONTROL',
                        'observation_dependency': 'FINITE_MODEL_ONLY', 'physical_capability': 'NOT_ESTABLISHED',
                        'autonomous_discovery': 'NOT_ESTABLISHED_DEVELOPER_SUPPLIED_RECIPE_MENU'},
            'successor_controls': successor, 'cases': results,
            'cost_scope': {'currency': 'USD', 'money_unit': 'cents', 'numbers': 'AUTHORED_BUYER_RECIPE_AND_SAMPLE_COSTS',
                           'actual_host_model_development_hardware_energy_costs': 'UNKNOWN',
                           'not_native_seller_revenue_or_profit': True, 'buyer_value_and_demand': 'UNKNOWN',
                           'prior_observation_acquisition_cost': 'UNKNOWN_NOT_INCLUDED_IN_INCREMENTAL_PANEL_COST',
                           'savings_attribution': 'Declared recipe reconstruction cost; ordinary equivalent content receives the same benefit.'},
            'limitations': spec['uncertainties'] + ['Evaluator and candidate are separate code paths in one authored process, not organizationally independent field certification.',
                                                  'An omitted world can imitate an in-class observation; out-of-model detection is incomplete.',
                                                  'Developer-produced recipes and costs do not demonstrate autonomous discovery or observed willingness to pay.'],
            'telemetry': {'wall_seconds': time.perf_counter()-start_wall, 'cpu_seconds': time.process_time()-start_cpu}}


def case_request(spec, ident):
    return next(row['request'] for row in spec['cases'] if row['id'] == ident)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('NEW_RESULT_PATH_REQUIRED')
    result = run()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
