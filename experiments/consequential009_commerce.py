"""Source-bound circuit-report exchange and explicit conditional economic worlds."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.commerce006 import engine

COST_CATEGORIES = (
    'discovery_failed_search', 'construction_integration', 'inference',
    'data_network_storage', 'execution', 'verification_rework',
    'customer_acquisition', 'maintenance_support', 'warranty_terminal',
    'capital_financing', 'tax_nonrecoverable',
)
SCOPE = ('Exact-model finite-cohort passive-circuit diagnostic report: certify the stated '
         'voltage scale ambiguity, provide a distinguishing calibrated measurement plan when '
         'supported, and abstain for unsupported or unknown-gain obligations. No physical '
         'inspection, empirical calibration, safety certification or production qualification.')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hash_ok(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def bounded(path, limit=2_000_000):
    path = Path(path).absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('SYMLINK_INPUT_REFUSED')
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('INPUT_MISSING_OR_OVERSIZED')
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError('INPUT_CHANGED_SIZE')
    return raw


def integer(value, lower=0, upper=10**12):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('NONNEGATIVE_BOUNDED_INTEGER_REQUIRED')
    return value


def load_authority(paths, expected):
    keys = {'artifact', 'receipt', 'protocol', 'candidate', 'verifier'}
    if set(paths) != keys or set(expected) != keys or not all(hash_ok(x) for x in expected.values()):
        raise ValueError('EXTERNAL_FROZEN_AUTHORITY_REQUIRED')
    raw = {key: bounded(paths[key]) for key in keys}
    if any(digest(raw[key]) != expected[key] for key in keys):
        raise ValueError('SOURCE_OR_ARTIFACT_CHANGED')
    artifact, receipt = json.loads(raw['artifact']), json.loads(raw['receipt'])
    required = {'artifact_sha256': expected['artifact'], 'protocol_sha256': expected['protocol'],
                'candidate_sha256': expected['candidate'], 'verifier_sha256': expected['verifier']}
    if not isinstance(artifact, dict) or not isinstance(receipt, dict):
        raise ValueError('JSON_OBJECT_REQUIRED')
    if any(receipt.get(key) != value for key, value in required.items()):
        raise ValueError('RECEIPT_SOURCE_FRAME_MISMATCH')
    if receipt.get('accepted') is not True:
        raise ValueError('ACTUAL_REPORT_NOT_INDEPENDENTLY_ACCEPTED')
    return artifact, receipt


def validate_policy(policy):
    expected = {'schema', 'scope', 'cohort', 'horizon', 'price_microUSD', 'opening_microUSD',
                'working_microUSD', 'modeled_costs_microUSD', 'cost_basis', 'human_comparator',
                'source_manifest', 'buyer_worlds', 'reinvestment', 'route'}
    if not isinstance(policy, dict) or set(policy) != expected or policy['schema'] != 'agi-alpha/consequential009-commerce-policy/v1':
        raise ValueError('POLICY_SCHEMA')
    if policy['scope'] != SCOPE or policy['horizon'] != '180 modeled days; unresolved reversal exposure remains reserved at terminal snapshot':
        raise ValueError('FROZEN_OBLIGATION_OR_HORIZON_MISMATCH')
    cohort = policy['cohort']
    if cohort != ['source-bound-report-001']:
        raise ValueError('ONE_UNIQUE_REPORT_PER_COUNTERFACTUAL_WORLD_REQUIRED')
    for key in ['price_microUSD', 'opening_microUSD', 'working_microUSD']:
        integer(policy[key])
    integer(policy['price_microUSD'], 200_000)
    costs = policy['modeled_costs_microUSD']
    if not isinstance(costs, dict) or set(costs) != set(COST_CATEGORIES):
        raise ValueError('ALL_COMPLETE_COST_CATEGORIES_REQUIRED')
    for amount in costs.values():
        integer(amount)
    if policy['cost_basis'] != 'AUTHORED_FINITE_COMPLETE_COST_CONDITIONS_NOT_OBSERVED_BILLS; all current and inherited costs above these amounts remain K':
        raise ValueError('COST_ASSUMPTIONS_MUST_REMAIN_EXPLICIT')
    route = policy['route']
    if route != {'engine_rail': 'nonrecourse-simulated', 'tariff_proxy': 'Stripe US domestic card; no live integration or merchant eligibility established',
                 'processing_basis_points': 290, 'processing_fixed_microUSD': 300_000,
                 'dispute_received_microUSD': 15_000_000, 'manual_counter_microUSD': 15_000_000,
                 'additional_dispute_reserve_microUSD': 29_800_000,
                 'assurance': 'Local provider scenario oracle only; captured cards remain reversible; full principal plus fee exposure retained. Additional assurance/integration costs remain K.'}:
        raise ValueError('FROZEN_ROUTE_AND_FEE_MISMATCH')
    human = policy['human_comparator']
    if set(human) != {'annual_wage_USD', 'annual_hours_assumption', 'compensation_to_wage_ratio', 'task_hours_grid', 'qualification'}:
        raise ValueError('HUMAN_COMPARATOR_SCHEMA')
    if human['annual_wage_USD'] != 120630 or human['annual_hours_assumption'] != 2080 or human['compensation_to_wage_ratio'] != [54, 36.97]:
        raise ValueError('HUMAN_RATE_SOURCE_MISMATCH')
    if human['qualification'] != 'BLS2025 electrical-engineer wage with broad June2026 full-time compensation loading; exact task hours and service overhead unmeasured. Grid is conditional, not observed human performance.':
        raise ValueError('HUMAN_TIME_QUALIFICATION_REQUIRED')
    if not isinstance(human['task_hours_grid'], list) or not human['task_hours_grid'] or any(type(x) not in {int, float} or not 0 <= x <= 1000 for x in human['task_hours_grid']):
        raise ValueError('HUMAN_HOUR_GRID')
    worlds = policy['buyer_worlds']
    required_worlds = {'conditional_participation', 'zero_demand', 'equal_ai_native_outside_option',
                       'strategic_nonpayment', 'rejected_delivery', 'outage_delay', 'interruption_recovery',
                       'correlated_benefit_warranty_reversals'}
    if not isinstance(worlds, list) or {w.get('id') for w in worlds} != required_worlds or len(worlds) != len(required_worlds):
        raise ValueError('ALL_FROZEN_STRESS_WORLDS_REQUIRED')
    fields = {'id', 'value_microUSD', 'realized_value_microUSD', 'trust_basis_points', 'switching_microUSD', 'outside_cost_microUSD',
              'funded', 'reversal', 'warranty_extra_microUSD', 'delivery', 'buyer_parameter_basis'}
    for world in worlds:
        if set(world) != fields or world['buyer_parameter_basis'] != 'AUTHORED_CONDITIONAL_WORLD_NOT_AGI_ALPHA_DEMAND_DATA':
            raise ValueError('BUYER_WORLD_SCHEMA_OR_EVIDENCE_SCOPE')
        for key in ['value_microUSD', 'realized_value_microUSD', 'switching_microUSD', 'outside_cost_microUSD', 'warranty_extra_microUSD']:
            integer(world[key])
        integer(world['trust_basis_points'], upper=10000)
        if type(world['funded']) is not bool or type(world['reversal']) is not bool or world['delivery'] not in {'accept', 'reject', 'delay', 'interrupt'}:
            raise ValueError('SCENARIO_EVENT_SCHEMA')
    reinvest = policy['reinvestment']
    if set(reinvest) != {'cap_microUSD', 'expected_net_value_microUSD', 'intent', 'intent_sha256'} or not hash_ok(reinvest['intent_sha256']) or digest(reinvest['intent'].encode()) != reinvest['intent_sha256']:
        raise ValueError('PRESPECIFIED_CONSTRUCTION_INTENT_REQUIRED')
    integer(reinvest['cap_microUSD'], 1)
    integer(reinvest['expected_net_value_microUSD'], 1)
    manifest = policy['source_manifest']
    if set(manifest) != {'path', 'sha256'} or not hash_ok(manifest['sha256']):
        raise ValueError('SOURCE_MANIFEST_SCHEMA')
    return policy


def conditional_frontier(policy, net_collections, payment_fees, extra_warranty=0, extra_disputes=0):
    total = sum(policy['modeled_costs_microUSD'].values()) + payment_fees + extra_warranty + extra_disputes
    human = policy['human_comparator']
    hourly = human['annual_wage_USD'] / human['annual_hours_assumption'] * human['compensation_to_wage_ratio'][0] / human['compensation_to_wage_ratio'][1]
    common = (policy['modeled_costs_microUSD']['customer_acquisition'] + policy['modeled_costs_microUSD']['warranty_terminal']
              + policy['modeled_costs_microUSD']['capital_financing'] + policy['modeled_costs_microUSD']['tax_nonrecoverable']
              + payment_fees + extra_warranty + extra_disputes)
    return {'AI_conditional_complete_cost_microUSD': total, 'AI_conditional_profit_microUSD': net_collections - total,
            'AI_actual_profit_interval_microUSD': [None, None],
            'unknown_K_definition': 'Additional current and inherited enterprise discovery/construction, inference, data, execution, verification, acquisition, support, financing, tax, assurance and liability costs above the authored scenario totals. Actual totals are unbounded and are not established to equal or exceed those authored amounts; the K frontier is conditional, not an actual profit interval.',
            'AI_positive_profit_requires_K_less_than_microUSD': net_collections - total,
            'human_loaded_compensation_USD_per_hour_sensitivity': hourly,
            'human_positive_profit_before_unmeasured_costs_requires_hours_less_than': (net_collections - common) / 1e6 / hourly,
            'AI_lower_cost_than_human_before_unknown_costs_requires_human_hours_greater_than': (total - common) / 1e6 / hourly,
            'human_conditional_grid': [{'hours_AUTHORED_NOT_OBSERVED': h,
                                        'profit_upper_microUSD_before_unknown_setup_tools_service_overhead': int(net_collections - common - h * hourly * 1e6)} for h in human['task_hours_grid']],
            'human_complete_cost_profit': 'UNKNOWN_EXACT_TASK_TIME_TOOLS_REVIEW_REWORK_AND_SERVICE_OVERHEAD',
            'human_to_AI_crossing': 'UNESTABLISHED; a negative grid value is not a measured human loss',
            'technical_parity_policy': 'A tie with ordinary impedance analysis or an AI-native control does not veto a human-service economic advantage; it does forbid claiming novel scientific superiority from the tie.',
            'investment_attractiveness': 'UNKNOWN versus non-entry and equally capable AI-native competitors; positive gross margin is insufficient.'}


def run(paths, expected, policy_path, expected_policy, output):
    wall, cpu = time.monotonic(), time.process_time()
    artifact, receipt = load_authority(paths, expected)
    policy_raw = bounded(policy_path, 256_000)
    if not hash_ok(expected_policy) or digest(policy_raw) != expected_policy:
        raise ValueError('EXTERNAL_FROZEN_POLICY_REQUIRED')
    policy = validate_policy(json.loads(policy_raw))
    manifest_path = ROOT / policy['source_manifest']['path']
    if not manifest_path.is_relative_to(ROOT) or '..' in Path(policy['source_manifest']['path']).parts or digest(bounded(manifest_path, 256_000)) != policy['source_manifest']['sha256']:
        raise ValueError('SOURCE_MANIFEST_CHANGED')
    source_manifest = json.loads(bounded(manifest_path, 256_000))
    artifact_object_hash = digest(canonical(artifact))
    frame = {'schema': 'agi-alpha/consequential009-report-task/v1', 'scope': SCOPE,
             'authority': expected, 'policy_sha256': expected_policy, 'report_object_sha256': artifact_object_hash}
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    output.mkdir(parents=True)
    Exchange = engine()
    checks, worlds = [], []

    def validate(task):
        if canonical(task) != canonical(frame):
            raise ValueError('FIXED_FUNCTIONAL_OBLIGATION_CHANGED')

    def check(task, value):
        validate(task)
        current_artifact, current_receipt = load_authority(paths, expected)
        accepted = (digest(canonical(value)) == artifact_object_hash
                    and digest(canonical(current_artifact)) == artifact_object_hash
                    and current_receipt.get('accepted') is True)
        return {'accepted': accepted, 'decisive': True, 'scope': SCOPE,
                'commercial_demand_established': False, 'physical_qualification': False}

    def refuse(label, exceptions, action):
        try:
            action()
        except exceptions as exc:
            checks.append({'check': label, 'passed': True, 'detail': str(exc)})
            return
        raise AssertionError('UNEXPECTED_SUCCESS ' + label)

    for world in policy['buyer_worlds']:
        directory = output / world['id']
        directory.mkdir()
        working = policy['working_microUSD'] + policy['route']['additional_dispute_reserve_microUSD']
        ex = Exchange(directory / 'exchange.sqlite', key=b'9' * 32,
                      contract='consequential009/' + expected_policy + '/' + world['id'],
                      validate=validate, check=check, opening=policy['opening_microUSD'], working=working)
        ident, buyer = 'source-bound-report-001', 'conditional-scenario-buyer'
        price = policy['price_microUSD']
        own_utility = world['value_microUSD'] * world['trust_basis_points'] // 10000 - price - world['switching_microUSD']
        outside_utility = max(0, world['value_microUSD'] - world['outside_cost_microUSD'])
        participates = own_utility >= outside_utility and own_utility >= 0
        payment_fee, dispute_fee, accepted, collected, investment = 0, 0, False, 0, None
        snapshots = {}
        try:
            for category, amount in policy['modeled_costs_microUSD'].items():
                ex.cost('conditional-complete-cost-' + category, amount)
            if world['warranty_extra_microUSD']:
                ex.cost('joint-adverse-warranty-extra', world['warranty_extra_microUSD'])
            snapshots['all_admitted_costs_including_unsold'] = ex.snapshot()
            ex.wallet(buyer, price if world['funded'] else 0)
            if participates:
                ex.offer(ident, buyer, price, policy['route']['engine_rail'], frame, 20)
                order = ex.order(ident)
                terms = {k: order[k] for k in ('id', 'buyer', 'price', 'rail', 'task_hash', 'contract', 'deadline')}
                ex.event(ident, 'consent', 'consent', {'buyer': buyer, 'termsHash': digest(canonical(terms))}, 0)
                funding = ex.provider.issue(ex.order(ident), 'funded')
                if not world['funded']:
                    refuse(world['id'] + '/nonpayment', ValueError, lambda: ex.event(ident, 'fund', 'fund', funding, 1))
                    ex.event(ident, 'cancel', 'cancel', {}, 2)
                else:
                    if world['delivery'] == 'interrupt':
                        refuse(world['id'] + '/interrupted-funding-atomicity', InterruptedError,
                               lambda: ex.event(ident, 'fund', 'fund', funding, 1, crash=True))
                        if ex.order(ident)['state'] != 'offered':
                            raise AssertionError('CRASH_CHANGED_STATE')
                        ex.close()
                        ex = Exchange(directory / 'exchange.sqlite', key=b'9' * 32,
                                      contract='consequential009/' + expected_policy + '/' + world['id'],
                                      validate=validate, check=check, opening=policy['opening_microUSD'], working=working)
                    ex.event(ident, 'fund', 'fund', funding, 1)
                    payment_fee = (price * policy['route']['processing_basis_points'] + 9999) // 10000 + policy['route']['processing_fixed_microUSD']
                    ex.cost('processing-fee-not-returned-on-refund', payment_fee)
                    if world['delivery'] == 'reject':
                        substituted = {**artifact, '__unverified_modification__': True}
                        refuse(world['id'] + '/rejected-report-cannot-settle', ValueError,
                               lambda: ex.event(ident, 'prepare', 'prepare', substituted, 2))
                        ex.event(ident, 'refund', 'refund', {}, 3)
                    else:
                        ex.event(ident, 'prepare', 'prepare', artifact, 2)
                        accepted = True
                        refuse(world['id'] + '/payment-gated-download', PermissionError, lambda: ex.download(ident, buyer))
                        if world['delivery'] == 'delay':
                            refuse(world['id'] + '/expired-release', ValueError,
                                   lambda: ex.event(ident, 'release', 'release', ex.provider.issue(ex.order(ident), 'cleared'), 21))
                            ex.event(ident, 'refund', 'refund', {}, 22)
                        else:
                            forged = ex.provider.issue(ex.order(ident), 'cleared')
                            forged['signature'] = '0' * 64
                            refuse(world['id'] + '/forged-clearing', ValueError,
                                   lambda: ex.event(ident, 'forged', 'release', forged, 3))
                            clearing = ex.provider.issue(ex.order(ident), 'cleared')
                            ex.event(ident, 'release', 'release', clearing, 3)
                            before = ex.snapshot()
                            ex.event(ident, 'release', 'release', clearing, 3)
                            if ex.snapshot() != before:
                                raise AssertionError('DUPLICATE_COLLECTION_CHANGED_ACCOUNTING')
                            if ex.download(ident, buyer) != canonical(artifact):
                                raise AssertionError('DELIVERED_REPORT_CHANGED')
                            collected = price
                            (directory / 'DELIVERED.json').write_bytes(canonical(artifact))
                            checks.append({'check': world['id'] + '/exact-delivery-and-duplicate-idempotence', 'passed': True})
                            if world['reversal']:
                                ex.event(ident, 'late-reversal', 'late_reversal', {}, 30)
                                dispute_fee = policy['route']['dispute_received_microUSD'] + policy['route']['manual_counter_microUSD']
                                ex.cost('received-and-lost-manual-dispute', dispute_fee)
                                collected = 0
            snapshots['terminal_180day_with_unresolved_exposure_retained'] = ex.snapshot()
            modeled = conditional_frontier(policy, collected, payment_fee, world['warranty_extra_microUSD'], dispute_fee)
            if ex.snapshot()['profit'] != modeled['AI_conditional_profit_microUSD']:
                raise AssertionError('MODEL_LEDGER_PROFIT_RECONCILIATION_FAILED')
            reinvest = policy['reinvestment']
            if ex.snapshot()['unrestrictedEarned'] >= reinvest['cap_microUSD'] and not ex.snapshot()['investmentStopped']:
                investment = ex.reserve_investment('conditional-measurement-extension', reinvest['cap_microUSD'],
                                                 reinvest['expected_net_value_microUSD'], intent_hash=reinvest['intent_sha256'])
            else:
                refuse(world['id'] + '/no-capital-or-negative-profit-funding', ValueError,
                       lambda: ex.reserve_investment('conditional-measurement-extension', reinvest['cap_microUSD'],
                                                    reinvest['expected_net_value_microUSD'], intent_hash=reinvest['intent_sha256']))
            snapshots['after_prespecified_conditional_reservation'] = ex.snapshot()
            rows = [dict(row) for row in ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')]
            orders = [dict(row) for row in ex.db.execute('SELECT id,buyer,price,state,custody,refund_due,compensation_due FROM trades ORDER BY id')]
            worlds.append({'id': world['id'], 'mode': 'CONDITIONALLY_ASSUMED_WORLD_NOT_OBSERVED_MARKET',
                           'one_admitted_report': policy['cohort'], 'fixed_obligation': SCOPE,
                           'buyer_inputs': world, 'own_utility_microUSD': own_utility,
                           'best_outside_utility_microUSD': outside_utility, 'participates_under_assumptions': participates,
                           'realized_utility_microUSD': world['realized_value_microUSD'] * world['trust_basis_points'] // 10000 - price - world['switching_microUSD'],
                           'source_bound_report_accepted': accepted, 'net_collections_microUSD': collected,
                           'snapshots': snapshots, 'economics': modeled, 'conditional_investment_reservation': investment,
                           'construction_spend': 0, 'journal': rows, 'orders': orders,
                           'terminal_reserve_rule': 'Full engine principal-plus0.20 tail plus additional29.80 fixed working reserve covers modeled30USD dispute fees. No reserve release is revenue; no empirical reversal-tail expiry is asserted.'})
        finally:
            ex.close()
    result = {'schema': 'agi-alpha/consequential009-commercial-execution/v1', 'scope': SCOPE,
              'commerce_adapter_sha256': digest(Path(__file__).read_bytes()),
              'authority': expected, 'policy_sha256': expected_policy, 'source_manifest': source_manifest,
              'actual_report_acceptance_receipt': receipt, 'worlds': worlds, 'checks': checks,
              'cohort_accounting': 'One source-bound report per counterfactual world. Worlds are alternative assumptions, not additive sales, independent customers, new scientific samples or measured delivery volume. All admitted preparation costs remain charged when unsold or rejected.',
              'evidence_grounded_decision': {'real_orders': 0, 'actual_commerce_receipts_microUSD': 0,
                  'AGI_ALPHA_demand': 'UNKNOWN', 'complete_actual_cost': 'UNKNOWN',
                  'commercial_human_to_AI_crossing': 'UNESTABLISHED',
                  'qualified_unrestricted_simulated_earned_funds_microUSD': 0,
                  'qualified_earned_funded_successor': 'DEFERRED_NO_QUALIFIED_EARNINGS',
                  'conditional_model_reservation': 'See each world; no successor construction or its benefit is invented by this adapter.',
                  'conditional_simulated_viability': 'Positive only under the explicit buyer, complete-cost and provider assumptions in profitable worlds; zero-demand, competitive and joint adverse worlds are retained.',
                  'live_commercial_success': 'UNRUN'},
              'route_limitations': ['No production escrow, Stripe merchant integration, paid provider call or real settlement.',
                  'The inherited engine calls its local release rail nonrecourse-simulated; a real captured card is reversible and is not thereby nonrecourse. Actual late reversals are executed in the adverse world.',
                  'The Stripe US tariff is an illustrative domesticUSD card proxy. Montreal merchant eligibility/Canada cross-border tariffs and any assurance provider cost are unmeasured; no silent currency conversion.',
                  'All complete costs above authored totals remain unbounded K, including inherited enterprise research. Positive assumed-world balances are not promoted to qualified funds.',
                  'The actual report is an exact-model engineering delivery; no physical metrology or safety qualification follows.'],
              'resources': {'wall_seconds': time.monotonic() - wall, 'cpu_seconds': time.process_time() - cpu,
                            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'external_paid_calls': 0, 'actual_inference_bill': None,
                            'complete_actual_monetary_cost': None}}
    (output / 'RESULT.json').write_bytes(json.dumps(result, indent=2, allow_nan=False).encode() + b'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ['artifact', 'receipt', 'protocol', 'candidate', 'verifier']:
        parser.add_argument('--' + key, type=Path, required=True)
        parser.add_argument('--expected-' + key + '-sha256', required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--expected-policy-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = {key: getattr(args, key) for key in ['artifact', 'receipt', 'protocol', 'candidate', 'verifier']}
    expected = {key: getattr(args, 'expected_' + key + '_sha256') for key in paths}
    result = run(paths, expected, args.policy, args.expected_policy_sha256, args.output)
    print(json.dumps({'worlds': len(result['worlds']), 'checks': len(result['checks']),
                      'qualified_funds': 0, 'resources': result['resources']}))


if __name__ == '__main__':
    main()
