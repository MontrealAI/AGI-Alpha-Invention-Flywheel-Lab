"""Conditional compatibility-service economics using the existing protected exchange."""
import argparse
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).absolute().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.commerce006 import canonical, engine, hash_string, read_bytes, read_json, sha

SCOPE = 'pinned FastAPI documentation create/read, WebSocket, startup compatibility only; no production or security qualification'
CATEGORIES = ['discovery_failed_search', 'construction_integration', 'agent_inference', 'data_network_storage',
              'execution', 'verification_repair', 'deployment', 'maintenance_support', 'payment_fees',
              'refund_dispute_terminal_obligations', 'financing_capital_recovery']
FIXTURE_PRICE = 1_000_000
FIXTURE_OPENING = 20_000_000
FIXTURE_WORKING = 1_000_000


def _interval(value):
    if type(value) is not dict or set(value) != {'lower_microUSD', 'upper_microUSD', 'basis'}:
        raise ValueError('COST_INTERVAL_SCHEMA')
    lower, upper = value['lower_microUSD'], value['upper_microUSD']
    if type(lower) is not int or lower < 0 or (upper is not None and (type(upper) is not int or upper < lower)):
        raise ValueError('COST_INTERVAL_BOUNDS')
    if type(value['basis']) is not str or not value['basis']:
        raise ValueError('COST_BASIS_REQUIRED')
    return lower, upper


def frontier(contract):
    costs = contract['cost_intervals']
    if type(costs) is not dict or set(costs) != set(CATEGORIES):
        raise ValueError('ALL_LIFECYCLE_COST_CATEGORIES_REQUIRED')
    bounds = [_interval(costs[key]) for key in CATEGORIES]
    lower = sum(value[0] for value in bounds)
    upper = None if any(value[1] is None for value in bounds) else sum(value[1] for value in bounds)
    cohort = contract['cohort']
    if type(cohort) is not list or not cohort or any(type(x) is not str or not x for x in cohort) or len(set(cohort)) != len(cohort):
        raise ValueError('PROSPECTIVE_UNIQUE_COHORT_REQUIRED')
    prices = contract['illustrative_price_grid_microUSD']
    if type(prices) is not list or not prices or any(type(p) is not int or p < 0 for p in prices):
        raise ValueError('PRICE_GRID_SCHEMA')
    cases = []
    for price in prices:
        for paid in range(len(cohort) + 1):
            for reversals in sorted(set([0, paid])):
                collections = (paid - reversals) * price
                cases.append({'price_microUSD': price, 'paying_count': paid, 'refunded_count': reversals,
                              'admitted_count_including_unsold': len(cohort), 'net_collections_microUSD': collections,
                              'complete_profit_lower_microUSD': None if upper is None else collections - upper,
                              'complete_profit_upper_microUSD': collections - lower,
                              'unknown_cost_K_positive_profit_threshold_microUSD': collections - lower})
    return {'schema': 'agi-alpha/remediation-economic-frontier007/v1',
            'units': 'simulated microUSD; illustrative grid is not a market price or a participation forecast',
            'cohort': cohort, 'horizon': contract['horizon'],
            'known_cost_lower_bound_microUSD': lower, 'complete_cost_upper_bound_microUSD': upper,
            'unknown_categories': [key for key in CATEGORIES if costs[key]['upper_microUSD'] is None],
            'K_definition': 'All complete lifecycle cost above the recorded lower bound, including unknown inference and acquisition; no finite bound inferred from missing bills.',
            'profit_formula': 'paid_count * (1 - refund_fraction) * price - known_cost_lower_bound - K',
            'participation_condition': 'trust * expected_useful_value - (1-refund_probability) * price - switching - procurement - expected_dispute_cost >= best_alternative_utility',
            'competitive_price_ceiling': '(trust * expected_useful_value - switching - procurement - expected_dispute_cost - best_alternative_utility) / (1-refund_probability), if refund_probability < 1; at full refund test non-price obligations directly',
            'rational_operator_condition': 'expected complete profit >= best incremental outside option; available earned cash sufficient after all obligations and reserves',
            'buyer_parameters': contract['buyer_parameters'],
            'joint_stress': 'Lower trust and useful value jointly with higher switching, procurement, support and dispute costs; zero participation and full refund are retained.',
            'outside_options': contract['outside_options'], 'scenarios': cases,
            'baseline_same_cohort_complete_profit': None,
            'negative_to_positive_crossing': 'UNKNOWN_NO_ESTABLISHED_LOSS_MAKING_BASELINE',
            'conditional_commercial_viability': 'UNKNOWN_WITH_UNBOUNDED_K_OR_UNMEASURED_PARTICIPATION',
            'AGI_ALPHA_value_capture': 'UNKNOWN_NO_COMMITTED_PRICE_OR_PARTICIPATION',
            'investment_attractiveness': 'UNKNOWN; non-entry has zero incremental new commitment by definition, separate from service-threshold eligibility',
            'source_manifest': contract['market_source_manifest']}


def validate_authority(artifact_path, acceptance_path, contract_path, *, expected_contract_sha256,
                       expected_acceptance_sha256, root=ROOT):
    if not hash_string(expected_contract_sha256) or not hash_string(expected_acceptance_sha256):
        raise ValueError('EXTERNAL_FROZEN_AUTHORITY_HASH_REQUIRED')
    contract, contract_raw = read_json(contract_path, 256_000)
    if sha(contract_raw) != expected_contract_sha256:
        raise ValueError('FROZEN_COMMERCE_CONTRACT_MISMATCH')
    fields = {'schema', 'scope', 'binding', 'cohort', 'horizon', 'offering', 'cost_intervals',
              'illustrative_price_grid_microUSD', 'buyer_parameters', 'outside_options', 'market_source_manifest',
              'commercial_admission', 'fixture_price_is_not_market_evidence'}
    if set(contract) != fields or contract['schema'] != 'agi-alpha/conditional-remediation-commercial007/v1':
        raise ValueError('COMMERCE_CONTRACT_SCHEMA')
    if contract['scope'] != SCOPE or contract['commercial_admission'] is not False or contract['fixture_price_is_not_market_evidence'] is not True:
        raise ValueError('UNQUALIFIED_COMMERCIAL_SCOPE')
    frontier(contract)
    market = contract['market_source_manifest']
    if type(market) is not dict or set(market) != {'path', 'sha256'} or not hash_string(market['sha256']):
        raise ValueError('MARKET_SOURCE_SCHEMA')
    market_path = Path(market['path']) if type(market['path']) is str else Path('/')
    if market_path.is_absolute() or '..' in market_path.parts or market_path.parts[:2] != ('campaign', 'cycle-007') or market_path.suffix != '.json':
        raise ValueError('MARKET_SOURCE_SCOPE')
    if sha(read_bytes(Path(root) / market_path, 1_000_000)) != market['sha256']:
        raise ValueError('MARKET_SOURCE_CHANGED')
    binding = contract['binding']
    required = {'artifact_sha256', 'candidate_sha256', 'technical_contract_sha256', 'verifier_sha256',
                'verifier_path', 'source_manifest_sha256'}
    if type(binding) is not dict or set(binding) != required or any(not hash_string(binding[k]) for k in required - {'verifier_path'}):
        raise ValueError('BINDING_SCHEMA')
    relative = Path(binding['verifier_path']) if type(binding['verifier_path']) is str else Path('/')
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'verification' or relative.suffix != '.py':
        raise ValueError('VERIFIER_SOURCE_SCOPE')
    if sha(read_bytes(Path(root) / relative, 2_000_000)) != binding['verifier_sha256']:
        raise ValueError('VERIFIER_SOURCE_CHANGED')
    artifact, raw = read_json(artifact_path, 2_000_000)
    if sha(raw) != binding['artifact_sha256']:
        raise ValueError('ARTIFACT_CHANGED')
    acceptance, acceptance_raw = read_json(acceptance_path, 256_000)
    if sha(acceptance_raw) != expected_acceptance_sha256:
        raise ValueError('FROZEN_ACCEPTANCE_CHANGED')
    wanted = {'schema': 'agi-alpha/compatibility-acceptance007/v1', 'scope': SCOPE,
              'artifact_sha256': binding['artifact_sha256'], 'candidate_sha256': binding['candidate_sha256'],
              'contract_sha256': binding['technical_contract_sha256'], 'verifier_sha256': binding['verifier_sha256'],
              'source_manifest_sha256': binding['source_manifest_sha256']}
    if any(acceptance.get(key) != value for key, value in wanted.items()):
        raise ValueError('TECHNICAL_ACCEPTANCE_BINDING')
    tests = acceptance.get('tests', {})
    counters = ['upstream_total', 'upstream_passed', 'upstream_skipped', 'protected_checks_total', 'protected_checks_passed']
    test_ok = (type(tests) is dict and all(type(tests.get(key)) is int for key in counters) and tests['upstream_total'] > 0
               and tests.get('upstream_passed') == tests['upstream_total'] and tests.get('upstream_skipped') == 0
               and tests.get('upstream_source_unchanged') is True
               and type(tests.get('protected_checks_total')) is int and tests['protected_checks_total'] > 0
               and tests.get('protected_checks_passed') == tests['protected_checks_total'])
    accepted = acceptance.get('accepted') is True and test_ok
    return artifact, contract, acceptance, accepted


def run(artifact_path, acceptance_path, contract_path, output, *, expected_contract_sha256,
        expected_acceptance_sha256, root=ROOT):
    wall, cpu = time.monotonic(), time.process_time()
    artifact, contract, acceptance, technical_accepted = validate_authority(
        artifact_path, acceptance_path, contract_path, expected_contract_sha256=expected_contract_sha256,
        expected_acceptance_sha256=expected_acceptance_sha256, root=root)
    ProtectedExchange = engine()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    output.mkdir(parents=True)
    checks, admitted, semantic = [], [], []
    task_base = {'schema': 'agi-alpha/compatibility-fixture007/v1', 'artifact_sha256': sha(canonical(artifact)),
                 'contract_sha256': expected_contract_sha256, 'acceptance_sha256': expected_acceptance_sha256,
                 'scope': SCOPE, 'commercial_admission': False}

    def validate(task):
        if type(task) is not dict or set(task) != set(task_base) | {'model_accepts'} or any(task[k] != v for k, v in task_base.items()) or type(task['model_accepts']) is not bool:
            raise ValueError('FROZEN_TASK_MISMATCH')

    def check(task, value):
        validate(task)
        current = validate_authority(artifact_path, acceptance_path, contract_path,
                                     expected_contract_sha256=expected_contract_sha256,
                                     expected_acceptance_sha256=expected_acceptance_sha256, root=root)
        ok = current[3] and task['model_accepts'] and sha(canonical(value)) == task_base['artifact_sha256']
        result = {'accepted': bool(ok), 'decisive': True, 'commercial_acceptance': False,
                  'scope': 'SOURCE_BOUND_COMPATIBILITY_ARTIFACT_FIXTURE_ONLY'}
        semantic.append(result)
        return result

    def opened():
        return ProtectedExchange(output / 'exchange.sqlite', key=b'7' * 32, contract='conditional007/' + expected_contract_sha256,
                                 validate=validate, check=check, opening=FIXTURE_OPENING, working=FIXTURE_WORKING)

    def refuse(name, kinds, action):
        try:
            action()
        except kinds as exc:
            checks.append({'name': name, 'passed': True, 'detail': str(exc)})
        else:
            raise AssertionError('UNEXPECTED_SUCCESS ' + name)

    ex = opened()
    snapshots = {}
    try:
        ex.wallet('fixture-funded', 100_000_000)
        ex.wallet('fixture-unfunded', 0)

        def offer(ident, *, accepts=True, buyer='fixture-funded'):
            ex.offer(ident, buyer, FIXTURE_PRICE, 'nonrecourse-simulated', {**task_base, 'model_accepts': accepts}, 20)
            row = ex.order(ident)
            terms = {k: row[k] for k in ('id', 'buyer', 'price', 'rail', 'task_hash', 'contract', 'deadline')}
            ex.event(ident, 'consent-' + ident, 'consent', {'buyer': buyer, 'termsHash': sha(canonical(terms))}, 0)
            admitted.append({'id': ident, 'buyer': buyer, 'model_accepts': accepts, 'price_microUSD': FIXTURE_PRICE,
                             'real_buyer': False, 'commercially_admitted': False})

        def fund(ident, *, crash=False):
            return ex.event(ident, 'fund-' + ident, 'fund', ex.provider.issue(ex.order(ident), 'funded'), 1, crash=crash)

        def prepare(ident):
            return ex.event(ident, 'prepare-' + ident, 'prepare', artifact, 2)

        def release(ident):
            return ex.event(ident, 'release-' + ident, 'release', ex.provider.issue(ex.order(ident), 'cleared'), 3)

        offer('nonpayment', buyer='fixture-unfunded')
        refuse('nonpayment', ValueError, lambda: fund('nonpayment'))
        ex.event('nonpayment', 'cancel-nonpayment', 'cancel', {}, 2)
        offer('rejected', accepts=False)
        fund('rejected')
        refuse('rejected-delivery', ValueError, lambda: prepare('rejected'))
        refuse('rejected-download', PermissionError, lambda: ex.download('rejected', 'fixture-funded'))
        ex.event('rejected', 'refund-rejected', 'refund', {}, 3)
        before = ex.snapshot()
        ex.event('rejected', 'refund-rejected', 'refund', {}, 3)
        if ex.snapshot() != before:
            raise AssertionError('DUPLICATE_REFUND_CHANGED_BALANCE')
        checks.append({'name': 'duplicate-refund-idempotent', 'passed': True})
        offer('interrupted')
        refuse('funding-interruption-rollback', InterruptedError, lambda: fund('interrupted', crash=True))
        if ex.order('interrupted')['state'] != 'offered':
            raise AssertionError('INTERRUPTED_FUNDING_CHANGED_STATE')
        ex.close()
        ex = opened()
        fund('interrupted')
        if technical_accepted:
            for ident in ['interrupted', 'correlated-0', 'correlated-1', 'correlated-2']:
                if ident != 'interrupted':
                    offer(ident)
                    fund(ident)
                prepare(ident)
                refuse('download-before-clearing-' + ident, PermissionError, lambda ident=ident: ex.download(ident, 'fixture-funded'))
                forged = ex.provider.issue(ex.order(ident), 'cleared')
                forged['signature'] = '0' * 64
                refuse('forged-receipt-' + ident, ValueError, lambda ident=ident, forged=forged: ex.event(ident, 'forged-' + ident, 'release', forged, 3))
                release(ident)
                before = ex.snapshot()
                release(ident)
                if ex.snapshot() != before:
                    raise AssertionError('DUPLICATE_SETTLEMENT_CHANGED_LEDGER')
                if ex.download(ident, 'fixture-funded') != canonical(artifact):
                    raise AssertionError('DELIVERY_BYTES_CHANGED')
            checks.append({'name': 'accepted-exact-artifact-duplicate-settlement', 'passed': True})
            (output / 'DELIVERED.json').write_bytes(canonical(artifact))
            snapshots['positive_functional_fixture_before_stress'] = ex.snapshot()
            for ident in ['interrupted', 'correlated-0', 'correlated-1', 'correlated-2']:
                ex.event(ident, 'reverse-' + ident, 'late_reversal', {}, 4)
        else:
            refuse('unaccepted-delivery-cannot-settle', ValueError, lambda: prepare('interrupted'))
            ex.event('interrupted', 'refund-interrupted', 'refund', {}, 3)
        snapshots['final_full_reversal_or_rejection'] = ex.snapshot()
        if any(ex.snapshot()[key] != 0 for key in ['revenue', 'collections', 'unrestrictedEarned', 'custodyRestricted']):
            raise AssertionError('UNQUALIFIED_FUNDS_REMAIN')
        refuse('capital-and-refunds-cannot-fund-successor', ValueError,
               lambda: ex.reserve_investment('additional-capability', 1, 1, intent_hash=contract['binding']['artifact_sha256']))
        rows = [dict(row) for row in ex.db.execute('SELECT id,buyer,price,state,custody,refund_due,compensation_due FROM trades ORDER BY id')]
        journal = [dict(row) for row in ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
    finally:
        ex.close()
    result = {'schema': 'agi-alpha/conditional-commerce007/v1', 'mode': 'SIMULATED_FUNCTIONAL_ENGINEERING_QUALIFICATION_ONLY',
              'binding': contract['binding'], 'technical_acceptance': acceptance, 'technical_accepted': technical_accepted,
              'scope': SCOPE, 'offering': contract['offering'], 'economic_frontier': frontier(contract),
              'all_fixture_inputs': admitted, 'all_fixture_outcomes': rows, 'journal': journal,
              'checks': checks, 'semantic_checks': semantic, 'snapshots': snapshots,
              'fixture_pricing': 'USD 1 simulated engineering input per fixture; never claimed as market-supported demand or price',
              'fixture_accounting_scope': 'The reused engine has no unpriced cost posting; any displayed fixture profit excludes unknown complete costs. The parametric frontier retains them as K.',
              'commercial_decision': {'commercial_cohort_admitted': False, 'observed_orders': 0, 'real_receipts_microUSD': 0,
                                      'qualified_simulated_earned_funds_microUSD': 0, 'complete_cost_surplus': 'UNKNOWN',
                                      'earned_funded_successor': 'DEFERRED_NO_QUALIFIED_EARNINGS', 'live_commercial_success': 'UNRUN'},
              'resources': {'wall_seconds': time.monotonic() - wall, 'cpu_seconds': time.process_time() - cpu,
                            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'external_paid_calls': 0, 'complete_monetary_cost_microUSD': None},
              'limits': ['Procedural verifier separation on a shared host/model is not external certification.',
                         'Trusted external contract and receipt hashes establish identity, not actual buyer authority.',
                         'Free self-service and ordinary AI-native alternatives remain admissible; unexecuted routes are not assumed to fail.',
                         'This artifact is scoped compatibility evidence, not production support, complete security remediation or commercial acceptance.',
                         'No fixture balance, deposit, refund, reserve release or opening capital becomes commercially qualified earned funds.']}
    with (output / 'COMMERCIAL.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['artifact', 'acceptance', 'contract', 'output', 'expected-contract-sha256', 'expected-acceptance-sha256']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = run(Path(args.artifact), Path(args.acceptance), Path(args.contract), Path(args.output),
                 expected_contract_sha256=args.expected_contract_sha256,
                 expected_acceptance_sha256=args.expected_acceptance_sha256)
    print(json.dumps({'technical_accepted': result['technical_accepted'], 'commercial_decision': result['commercial_decision']}))


if __name__ == '__main__':
    main()
