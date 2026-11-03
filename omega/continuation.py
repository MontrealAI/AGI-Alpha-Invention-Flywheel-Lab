"""Execute the registered additive buyer/seller probe without reseeding accounts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import time

from commercial.persistence import atomic_bytes
from mechanism_harness.core import canonical, digest
from .commerce import run_fixture, inspect_continuation
from .economics import economics
from .process import ROOT, construct, fixture, run_simulated_buyer, source_binding
from .process_verify import conventional_policy, unfamiliar_cases, verify_policy


def source_files():
    names = set(source_binding())
    names.update(str(p.relative_to(ROOT)) for p in (ROOT/'omega').glob('*.py'))
    names.update(['omega/requirements.txt', 'omega/WORKFLOW.md', 'tests/test_omega_commerce.py',
                  'campaign/omega-continuation-20261103/PROTOCOL.md',
                  'campaign/omega-continuation-20261103/PRIOR_ART.md',
                  'campaign/omega-water-20261103/RESULT.json',
                  'connected_enterprise/finance.py', 'connected_enterprise/scale.py',
                  'adaptive_enterprise/account.py', 'commercial/persistence.py'])
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}


def run(output, *, account_directory=None):
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    identity = source_files()
    wall, cpu = time.perf_counter(), time.process_time()
    requests = [fixture(), fixture(True), *unfamiliar_cases()]
    rows = []
    for request in requests:
        started = time.process_time()
        candidate = construct(request)
        candidate_cpu = time.process_time() - started
        started = time.process_time()
        control = conventional_policy(request)
        control_cpu = time.process_time() - started
        accepted, control_accepted = verify_policy(request, candidate), verify_policy(request, control)
        same = (candidate['status'], candidate['worst_cost_cents']) == (control['status'], control['worst_cost_cents'])
        if not same:
            raise AssertionError('EXACT_CONVENTIONAL_DISAGREEMENT:' + request['name'])
        rows.append({'name': request['name'], 'request_sha256': digest(request),
                     'candidate_status': candidate['status'], 'control_status': control['status'],
                     'candidate_worst_cost_cents': candidate['worst_cost_cents'],
                     'control_worst_cost_cents': control['worst_cost_cents'], 'objective_tie': same,
                     'candidate_checked': accepted['accepted'] or accepted.get('refusal_verified'),
                     'control_checked': control_accepted['accepted'] or control_accepted.get('refusal_verified'),
                     'constructor_cpu_seconds': candidate_cpu, 'control_cpu_seconds': control_cpu})
    primary, successor = requests[:2]
    delivered = []
    for index, request in enumerate(requests[:2]):
        for model in request['models']:
            result = run_simulated_buyer(output/f'buyer-{index}-{model["id"]}.sqlite', request,
                                          model['responses'], model['yields'], interrupt=True)
            delivered.append({'request': request['name'], 'model': model['id'], **result})
    no_observation = copy.deepcopy(primary); no_observation['max_experiments'] = 0
    no_observation_result = construct(no_observation)
    robust_diagnostic = copy.deepcopy(no_observation); robust_diagnostic['max_total_cost_cents'] = 100
    alias = copy.deepcopy(primary['models'][0]); alias['yields']['a'] = 0
    omitted = run_simulated_buyer(output/'buyer-omitted-model.sqlite', primary, alias['responses'], alias['yields'])
    unpredictable = copy.deepcopy(primary['models'][0]); unpredictable['responses']['a'] = 99
    mismatch = run_simulated_buyer(output/'buyer-mismatch.sqlite', primary, unpredictable['responses'], unpredictable['yields'])
    if omitted['buyer']['state']['status'] != 'PRODUCTION_REJECTED' or mismatch['buyer']['state']['status'] != 'MODEL_MISMATCH':
        raise AssertionError('MODEL_COVERAGE_LIMIT_NOT_PRESERVED')
    predecessor = construct(primary)
    try:
        verify_policy(successor, predecessor)
    except ValueError as error:
        stale = str(error)
    else:
        raise AssertionError('STALE_PREDECESSOR_CERTIFICATE_ACCEPTED')
    artifact = output/'verified-finite-policy.json'
    atomic_bytes(artifact, canonical({'policy': predecessor, 'certificate': verify_policy(primary, predecessor),
                                    'scope': 'RESEARCH_FIXTURE_ARTIFACT_NOT_RELEASED_GENESIS_EDITION'}) + b'\n')
    seller = run_fixture(output/'seller-workflow-fixture', artifact)
    previous = json.loads((ROOT/'campaign/omega-water-20261103/RESULT.json').read_text())
    recorded = previous['seller']
    account = inspect_continuation(account_directory) if account_directory else {
        'status': 'BLOCKED_ORIGINAL_AUTHENTICATED_ACCOUNT_DIRECTORY_NOT_SUPPLIED',
        'native_account_modified': False, 'new_account_created': False,
        'product_posting_status': 'BLOCKED_PRODUCT_SPECIFIC_NATIVE_ACCEPTANCE_ADAPTER_NOT_IMPLEMENTED'}
    if source_files() != identity:
        raise ValueError('SOURCE_CHANGED_DURING_EXPERIMENT')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    result = {'schema': 'omega/continuation-result/v1', 'scope': 'EXECUTED_AUTHORED_COMPUTATIONAL_AND_WORKFLOW_RESEARCH',
              'preregistration_public_commit': '2f281eb2d0c6ca0a641a55eea4e0a9454c0ca0ad',
              'source_files_sha256': identity, 'source_sha256': digest(identity),
              'executed_git_commit': commit, 'working_tree_dirty': dirty,
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(),
                          'wall_seconds': time.perf_counter()-wall, 'cpu_seconds': time.process_time()-cpu,
                          'max_rss_kib_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          'actual_host_model_electricity_or_human_cost_usd': None},
              'comparison': {'requests': len(rows), 'qualified': sum(r['candidate_status']=='QUALIFIED_POLICY' for r in rows),
                             'unqualified': sum(r['candidate_status']=='NO_QUALIFIED_POLICY' for r in rows),
                             'ties': sum(r['objective_tie'] for r in rows), 'cases': rows,
                             'conventional_control': 'Independent exact contingent-policy constructor with identical inputs and permitted actions',
                             'human_or_frontier_model_labor_benchmark': 'NOT_RUN',
                             'physical_or_market_holdout': 'NOT_RUN'},
              'buyer_journeys': delivered,
              'missing_observation': {'at_original_budget': no_observation_result,
                                     'larger_budget_diagnostic_not_primary_arm': construct(robust_diagnostic)},
              'model_coverage_adversaries': {'omitted_alias': omitted, 'unpredicted_response': mismatch},
              'successor': {'stale_certificate_rejected': stale,
                            'no_predecessor_output': construct(successor),
                            'retained_generic_constructor': construct(successor),
                            'equal_content_ordinary_reuse': conventional_policy(successor),
                            'predecessor_observation_or_cash_used': False,
                            'retained_method_advantage': False, 'improved_discovery_method': 'NOT_IMPLEMENTED',
                            'scope': 'Recomputation and ordinary reuse tie; old observations/certificate do not transfer acceptance.'},
              'seller_workflow': seller, 'conditional_economics': economics(),
              'authoritative_account': {'status': account, 'record_kind': 'PRIOR_PUBLIC_REPORT_ONLY_NOT_REOPENED_ACCOUNT',
                        'source_commit': previous['executed_source_commit'],
                        'registration_sha256': recorded['registration_sha256'],
                        'actions_sha256': recorded['native_audit']['actions_sha256'],
                        'recorded_summary_microUSD': recorded['native_summary_microUSD'],
                        'recorded_trailing_365_day_microUSD': recorded['native_trailing_profit']['trailing_365_day_profit_microUSD'],
                        'recorded_window': recorded['native_trailing_profit']['interval'],
                        'new_primary_sales': 0, 'new_primary_postings': 0,
                        'this_continuation_costs_posted': False,
                        'complete_cost_profit_after_continuation': None},
              'verdict': {'super_alpha': 'NOT_ESTABLISHED', 'conventional_advantage': 'NONE_IN_TESTED_CONTRACT',
                          'buyer_capability': 'FINITE_MODEL_EXPERIMENT_POLICY_AND_INDEPENDENT_END_USE_REJECTION',
                          'seller_business': 'WORKFLOW_EXERCISED_DEMAND_AND_FULL_ECONOMICS_UNVALIDATED',
                          'usd3b_trailing_year_objective': 'NOT_ACHIEVED', 'merge_release_or_deployment': 'NONE'},
              'next_action': 'Preserve ordinary active-design route; require a real process/actuator/acceptance contract and original account custody before product-native financial operation.'}
    atomic_bytes(output/'RESULT.json', canonical(result) + b'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--account-directory')
    args = parser.parse_args()
    result = run(args.output, account_directory=args.account_directory)
    print(json.dumps({'result': str(Path(args.output)/'RESULT.json'), 'comparison': {k: result['comparison'][k] for k in ('requests','qualified','unqualified','ties')},
                      'native_primary_postings': 0, 'verdict': result['verdict']}, indent=2))


if __name__ == '__main__':
    main()
