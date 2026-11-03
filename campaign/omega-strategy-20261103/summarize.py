"""Compact audited results; never pool independent accounts into a business."""
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys

from commercial.ledger import digest, strict_json
from omega import market, market_native, process, process_verify, qualification_pool


def summarize(directory):
    directory = Path(directory)
    audit = market_native.audit(directory)
    result = strict_json((directory / 'result.json').read_bytes())
    registration = strict_json((directory / 'registration.json').read_bytes())
    policies = []
    for mode in registration['policies']:
        rows = [r for r in result['accounts'] if r['policy'] == mode]
        profits = [r['modeled_complete_economic_profit_cents'] for r in rows]
        policies.append({'policy': mode, 'cases': len(rows),
            'unweighted_mean_economic_profit_USD': statistics.mean(profits) / 100,
            'minimum_economic_profit_USD': min(profits) / 100,
            'maximum_economic_profit_USD': max(profits) / 100,
            'positive_cases': sum(p > 0 for p in profits),
            'accepted_bundles_per_case_range': [min(r['outcomes']['released'] for r in rows), max(r['outcomes']['released'] for r in rows)],
            'founder_minutes_per_case_range': [min(r['founder_minutes'] for r in rows), max(r['founder_minutes'] for r in rows)],
            'descriptive_mean_not_empirical_expectation_or_pooled_profit': True})
    same = []
    for i in range(len(registration['cases'])):
        joint = next(r for r in result['accounts'] if r['id'] == f'case{i}-joint')
        ordinary = next(r for r in result['accounts'] if r['id'] == f'case{i}-ordinary_reuse')
        same.append(joint['modeled_complete_economic_profit_cents'] == ordinary['modeled_complete_economic_profit_cents']
                    and joint['decisions'] == ordinary['decisions']
                    and joint['outcomes'] == ordinary['outcomes'])
    # Prospectively designated process-demand staged reference, not a selected winner.
    reference = next(r for r in result['accounts'] if r['id'] == 'case4-staged')
    package = [r for r in reference['funding_receipts'] if r['resource'] == 'package_process']
    old_request, successor = process.fixture(), process.fixture(True)
    old_policy = process.construct(old_request)
    stale_rejected = False
    try:
        process_verify.verify_policy(successor, old_policy)
    except ValueError:
        stale_rejected = True
    controls = []
    for name, constructor in (('retained_productive_code', process.construct),
                              ('ordinary_equal_content_reuse', process_verify.conventional_policy),
                              ('strong_conventional_construction', process_verify.conventional_policy)):
        policy = constructor(successor)
        checked = process_verify.verify_policy(successor, policy)
        executions = [process_verify.independent_execution(successor, policy, m['responses'], m['yields'])
                      for m in successor['models']]
        controls.append({'arm': name, 'accepted': checked['accepted'],
                         'worst_cost_cents': policy['worst_cost_cents'],
                         'independently_accepted_worlds': sum(e['production_accepted'] for e in executions),
                         'world_count': len(executions), 'same_input_and_resource_contract': True})
    causal = {'designated_reference_id': reference['id'], 'source_request_sha256': digest(old_request),
              'successor_request_sha256': digest(successor), 'stale_predecessor_policy_rejected': stale_rejected,
              'native_package_funding': package,
              'earned_funding_executed': any(r['funding'] == 'EARNED' for r in package),
              'without_productive_capability': {'process_output_available': False,
                  'interpretation': 'Water-only product has no process construction entry point; ordinary construction is separately allowed below.'},
              'controls': controls, 'equal_content_conventional_tie': len({r['worst_cost_cents'] for r in controls}) == 1,
              'cash_necessity_demonstrated': False,
              'cash_limit': 'The USD100,000 seed could also afford the small package task; earned funding is not exclusive enabling causation.',
              'better_discovery_method_demonstrated': False,
              'private_customer_information_reused': False}
    return {'schema': 'omega/compact-strategy-evidence/v1', 'audit': audit,
            'registration_sha256': digest(registration), 'source_commit': registration['git_commit'],
            'source_files_sha256': digest(registration['source_hashes']),
            'scope': 'Eight authored conditional worlds; six native policies each; no pooled enterprise or empirical forecast.',
            'policies': policies, 'joint_and_strong_ordinary_ties': sum(same),
            'matched_case_count': len(same), 'accounts': result['accounts'], 'causal_successor': causal,
            'cost_disclosure': registration['cost_disclosure'], 'primary_account': registration['primary_account'],
            'objective': {'USD': 3000000000, 'window_hours': 8760, 'achieved': False,
                          'original_primary_continued': False, 'actual_profit': None},
            'telemetry': result['telemetry']}


if __name__ == '__main__':
    print(json.dumps(summarize(sys.argv[1]), indent=2, sort_keys=True))
