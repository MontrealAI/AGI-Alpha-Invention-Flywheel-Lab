import argparse
import copy
import hashlib
import json
import resource
import sys
import time
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from experiments.commerce006 import engine, PINS

D = Decimal


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def amount(value):
    return format(D(value).quantize(D('.01'), rounding=ROUND_HALF_UP), '.2f')


def bounded_decimal(value, name, maximum='1000000000'):
    if type(value) not in {str, int}:
        raise ValueError('DECIMAL_STRING_OR_INTEGER_REQUIRED ' + name)
    result = D(value)
    if not result.is_finite() or not 0 <= result <= D(maximum):
        raise ValueError('DECIMAL_RANGE ' + name)
    return result


def raw_file(path, cap=2_000_000):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents):
        raise ValueError('REGULAR_UNSYMLINKED_FILE_REQUIRED')
    with path.open('rb') as handle:
        raw = handle.read(cap + 1)
    if len(raw) > cap:
        raise ValueError('INPUT_BYTE_CAP')
    return raw


def json_file(path, cap=1_000_000):
    def pairs(items):
        value = {}
        for k, v in items:
            if k in value:
                raise ValueError('DUPLICATE_JSON_KEY')
            value[k] = v
        return value
    raw = raw_file(path, cap)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    if type(value) is not dict:
        raise ValueError('JSON_OBJECT_REQUIRED')
    canonical(value)
    return value, raw


def hash_value(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def bind_inputs(artifact, receipt, verifier_source, protocol, expected):
    if set(expected) != {'artifact', 'receipt', 'verifier', 'protocol'} or not all(hash_value(v) for v in expected.values()):
        raise ValueError('EXTERNAL_FROZEN_HASHES_REQUIRED')
    doc, doc_raw = json_file(artifact)
    accepted, accepted_raw = json_file(receipt)
    actual = {'artifact': sha(doc_raw), 'receipt': sha(accepted_raw), 'verifier': sha(raw_file(verifier_source)), 'protocol': sha(raw_file(protocol))}
    if actual != expected:
        raise ValueError('SOURCE_OR_FROZEN_RECEIPT_CHANGED')
    required = {'schema': 'agi-alpha/next009-delivery-acceptance/v1', 'accepted': True, 'artifact_sha256': actual['artifact'], 'verifier_source_sha256': actual['verifier'], 'protocol_sha256': actual['protocol'], 'scope': 'model-based-water-observation-plan'}
    if any(accepted.get(k) != v or type(accepted.get(k)) is not type(v) for k, v in required.items()):
        raise ValueError('INDEPENDENT_ACCEPTANCE_BINDING_OR_SCOPE')
    return doc, accepted, {**actual, 'artifact_canonical_sha256': sha(canonical(doc))}


def validate_policy(policy):
    if policy.get('schema') != 'agi-alpha/next009-commercial-policy/v1' or policy.get('currency') != 'CAD':
        raise ValueError('POLICY_SCHEMA_OR_CURRENCY')
    n = policy.get('cohort_size')
    if type(n) is not int or not 4 <= n <= 1000:
        raise ValueError('COHORT_SIZE_4_TO_1000_REQUIRED')
    for field in ('price_cad', 'cad_per_usd', 'seller_initial_simulated_equity_cad', 'working_capital_reserve_cad', 'inference_input_usd_per_million', 'inference_output_usd_per_million', 'human_wage_cad_per_hour'):
        bounded_decimal(policy[field], field)
    if D(policy['price_cad']) < 1 or D(policy['cad_per_usd']) <= 0:
        raise ValueError('NONPOSITIVE_PRICE_OR_FX')
    for field in ('input_tokens_per_attempt', 'output_tokens_per_attempt'):
        if type(policy[field]) is not int or not 0 <= policy[field] <= 100_000_000:
            raise ValueError('TOKEN_BUDGET_RANGE')
    for field in ('fixed_costs_cad', 'non_inference_costs_per_attempt_cad'):
        if type(policy[field]) is not dict or not policy[field]:
            raise ValueError('COST_CATEGORIES_REQUIRED')
        for k, v in policy[field].items():
            bounded_decimal(v, k)
    card = policy['card_route']
    for field in ('percentage', 'fixed_cad', 'dispute_received_cad'):
        bounded_decimal(card[field], field)
    if D(card['percentage']) >= 1 or card['refund_original_fee_returned'] is not False or card['reserve_release_assumed'] is not False:
        raise ValueError('UNSUPPORTED_CARD_OR_RESERVE_POLICY')
    if policy['qualified_unrestricted_simulated_earned_funds'] != '0.00':
        raise ValueError('UNSUPPORTED_COMMERCIAL_ADMISSION')
    for scenario in policy['scenarios']:
        for field in ('sold_fraction', 'refund_fraction_of_cohort', 'dispute_fraction_of_cohort', 'pending_payout_fraction_of_cohort'):
            bounded_decimal(scenario[field], field, '1')
        if D(scenario['refund_fraction_of_cohort']) + D(scenario['dispute_fraction_of_cohort']) + D(scenario['pending_payout_fraction_of_cohort']) > D(scenario['sold_fraction']):
            raise ValueError('INCONSISTENT_SCENARIO_COUNTS')
        bounded_decimal(scenario['inference_multiplier'], 'inference_multiplier', '1000')
        bounded_decimal(scenario['extra_lifecycle_cost_cad'], 'extra_lifecycle_cost_cad')
    return policy


def cost_inputs(policy, multiplier='1'):
    inference_usd = (D(policy['input_tokens_per_attempt']) * D(policy['inference_input_usd_per_million']) + D(policy['output_tokens_per_attempt']) * D(policy['inference_output_usd_per_million'])) / D(1_000_000)
    costs = {k: D(v) for k, v in policy['non_inference_costs_per_attempt_cad'].items()}
    costs['all_orchestration_inference_sensitivity'] = inference_usd * D(policy['cad_per_usd']) * D(multiplier)
    return costs


def card_projection(policy, scenario):
    n, p = policy['cohort_size'], D(policy['price_cad'])
    count = lambda k: int((D(n) * D(scenario[k])).to_integral_value(rounding=ROUND_FLOOR))
    sold, refunds, disputes, pending = [count(k) for k in ('sold_fraction', 'refund_fraction_of_cohort', 'dispute_fraction_of_cohort', 'pending_payout_fraction_of_cohort')]
    if refunds + disputes + pending > sold:
        raise ValueError('SCENARIO_INTEGER_COUNTS_OVERLAP')
    costs = cost_inputs(policy, scenario['inference_multiplier'])
    production = D(n) * sum(costs.values())
    fixed = sum(D(v) for v in policy['fixed_costs_cad'].values())
    extra = D(scenario['extra_lifecycle_cost_cad'])
    prep = production + fixed + extra
    card = policy['card_route']
    fees = D(sold) * (p * D(card['percentage']) + D(card['fixed_cad']))
    dispute_fees = D(disputes) * D(card['dispute_received_cad'])
    gross, reversed_revenue = D(sold) * p, D(refunds + disputes) * p
    revenue, delayed = gross - reversed_revenue, D(pending) * p
    expenses = prep + fees + dispute_fees
    profit = revenue - expenses
    work = D(policy['working_capital_reserve_cad'])
    equity = prep + work if scenario.get('equity_policy') == 'prefund_all_production_plus_working_only' else D(policy['seller_initial_simulated_equity_cad'])
    initial_feasible = equity >= prep + work
    cash = equity + revenue - delayed - expenses
    tail = D(sold - refunds - disputes) * (p + D(card['dispute_received_cad']))
    available = max(D(0), cash - tail - work)
    earned_cash_before_protection = max(D(0), revenue - delayed - expenses)
    equity_remaining = max(D(0), equity + min(D(0), revenue - delayed - expenses))
    earned_protection = max(D(0), tail + work - equity_remaining)
    conditional_earned = max(D(0), min(available, earned_cash_before_protection - earned_protection)) if initial_feasible else D(0)
    rate_refunds = D(refunds) / D(sold) if sold else D(0)
    rate_disputes = D(disputes) / D(sold) if sold else D(0)
    contribution = p * (1 - rate_refunds - rate_disputes - D(card['percentage'])) - D(card['fixed_cad']) - D(card['dispute_received_cad']) * rate_disputes
    q_break_even = prep / (D(n) * contribution) if contribution > 0 else None
    price_denominator = D(sold - refunds - disputes) - D(sold) * D(card['percentage'])
    price_break_even = (prep + D(sold) * D(card['fixed_cad']) + dispute_fees) / price_denominator if price_denominator > 0 else None
    base_inference = cost_inputs(policy)['all_orchestration_inference_sensitivity']
    non_inference = sum(D(v) for v in policy['non_inference_costs_per_attempt_cad'].values())
    inference_room = (revenue - fees - dispute_fees - fixed - extra) / D(n) - non_inference
    inference_multiplier_break_even = inference_room / base_inference if base_inference > 0 else None
    human_wage_floor = D(policy['human_wage_cad_per_hour'])
    h_cost_advantage = sum(costs.values()) / human_wage_floor if human_wage_floor > 0 else None
    h_profit_ceiling = (revenue - fees - dispute_fees) / (D(n) * human_wage_floor) if human_wage_floor > 0 else None
    counterfactual_reinvestment = conditional_earned * D(policy['reinvestment']['fraction_of_qualified_unrestricted_earnings'])
    cash_equal = cash + delayed == equity + profit
    if not cash_equal:
        raise AssertionError('CASH_PROFIT_BRIDGE_FAILED')
    return {'name': scenario['name'], 'scope': 'ANALYTICAL_SCENARIO_NOT_AN_OPERATIONAL_LEDGER_OR_OBSERVED_BUYER_COHORT',
            'counts': {'admitted_and_costed': n, 'modeled_paid': sold, 'unsold_or_nonpaying': n - sold, 'refunds': refunds, 'lost_disputes_disjoint_from_refunds': disputes, 'remaining_payouts_delayed': pending},
            'unit_cost_categories_cad': {k: str(v) for k, v in costs.items()},
            'cashflow_cad': {k: amount(v) for k, v in {'opening_declared_equity': equity, 'gross_captured': gross, 'refunds_and_chargebacks': reversed_revenue, 'earned_revenue': revenue, 'production_all_attempts': production, 'fixed_research_setup_overhead': fixed, 'additional_lifecycle_above_allowance': extra, 'processing_fees_retained_on_refunds': fees, 'dispute_fees': dispute_fees, 'complete_cost_within_authored_scenario': expenses, 'accounting_profit_within_authored_scenario': profit, 'net_collections_before_processing_expenses': revenue - delayed, 'delayed_processor_receivable': delayed, 'available_bank_cash': cash, 'retained_principal_plus_dispute_reserve': tail, 'working_capital': work, 'available_after_reserves': available, 'conditional_earned_cash_after_equity_backing': conditional_earned}.items()},
            'capital': {'new_real_spending': '0.00', 'new_simulated_capital_after_start': '0.00', 'prefunding_feasible': initial_feasible, 'cash_plus_receivable_equals_equity_plus_profit': cash_equal, 'reserves_are_restrictions_not_expenses': True},
            'frontiers': {'unpriced_additional_complete_cost_K_break_even_cad': amount(profit), 'paid_participation_break_even_fraction': None if q_break_even is None else str(q_break_even), 'price_break_even_cad_at_fixed_scenario_counts': None if price_break_even is None else amount(price_break_even), 'inference_cost_per_attempt_break_even_cad': amount(inference_room), 'inference_multiplier_break_even_against_policy_tokens': None if inference_multiplier_break_even is None else str(inference_multiplier_break_even), 'participation_support_interval': ['0', '1'], 'actual_participation_lower_bound': '0', 'human_minutes_for_wage_only_cost_to_exceed_scenario_unit_AI_cost': None if h_cost_advantage is None else str(h_cost_advantage * 60), 'human_minutes_per_admitted_attempt_above_which_wage_only_human_profit_is_negative': None if h_profit_ceiling is None else str(h_profit_ceiling * 60), 'human_time_observed': None, 'human_full_cost_profit': None, 'human_to_AI_profit_crossing': 'NOT_ESTABLISHED', 'human_tooling_and_review': 'Competent practitioners may use EPANET, optimization software and other normal tools; no manual arithmetic strawman or CPU-to-human-time conversion.', 'ordinary_AI_competitor_profit': None, 'incremental_nonentry_cashflow': '0.00', 'complete_enterprise_historical_research_cost': None},
            'investment_attractiveness': {'complete_NPV_cad': None, 'best_outside_option_NPV_cad': None, 'reason': 'Actual cash timing, tail duration, financing/opportunity cost and competing AI-native offer economics are unmeasured. Accounting profit is not NPV or an investment recommendation.', 'nonentry_incremental_new_commitment_NPV_cad': '0.00', 'historical_sunk_cost_not_reset': True},
            'reinvestment': {'policy_fraction': policy['reinvestment']['fraction_of_qualified_unrestricted_earnings'], 'counterfactual_all_evidence_qualified_budget_cad': amount(counterfactual_reinvestment), 'qualified_budget_cad': '0.00', 'decision': 'DEFER_NO_GROUNDED_PARTICIPATION_OR_COMPLETE_COST_BOUND', 'investment_made': False},
            'interpretation': 'Positive modeled profit is preserved. Unknown actual costs and participation prevent commercial validation; released reserves are never revenue. Full long-tail legal/physical losses and provider tax/FX spread are not bounded by this scenario.'}


def snapshot_rows(ex):
    return {'snapshot_microUSD': ex.snapshot(), 'trades': [dict(r) for r in ex.db.execute('SELECT id,buyer,price,rail,state,custody,refund_due,compensation_due,artifact_hash FROM trades ORDER BY id')], 'journal': [dict(r) for r in ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')], 'events': ex.db.execute('SELECT count(*) FROM events').fetchone()[0], 'provider_observations': ex.db.execute('SELECT count(*) FROM source_receipts').fetchone()[0]}


def native_mechanism(output, artifact, receipt, verifier_source, protocol, expected, policy):
    doc, accepted, binding = bind_inputs(artifact, receipt, verifier_source, protocol, expected)
    Exchange = engine()
    fx = D(policy['cad_per_usd'])
    micro = lambda cad: int((D(cad) / fx * D(1_000_000)).to_integral_value(rounding=ROUND_HALF_UP))
    price = micro(policy['price_cad'])
    base = {'schema': 'agi-alpha/next009-simulated-delivery/v1', 'binding': binding, 'commercial_admission': False}
    checks, snapshots = [], {}
    def validate(task):
        if type(task) is not dict or set(task) != set(base) | {'modeled_buyer_accepts'} or any(task[k] != v for k, v in base.items()) or type(task['modeled_buyer_accepts']) is not bool:
            raise ValueError('FROZEN_TASK_CHANGED')
    def check(task, value):
        validate(task)
        _, _, current = bind_inputs(artifact, receipt, verifier_source, protocol, expected)
        ok = current == binding and sha(canonical(value)) == binding['artifact_canonical_sha256'] and task['modeled_buyer_accepts']
        return {'accepted': bool(ok), 'decisive': True, 'scope': 'FUNCTIONAL_DELIVERY_UNDER_AUTHORED_BUYER_AND_LOCAL_PROVIDER_ONLY'}
    def opened(name, opening=None, working=None):
        return Exchange(output / (name + '.sqlite'), key=b'9' * 32, contract='next009/' + binding['receipt'], validate=validate, check=check, opening=micro(policy['seller_initial_simulated_equity_cad']) if opening is None else opening, working=micro(policy['working_capital_reserve_cad']) if working is None else working)
    def refuse(name, exceptions, action):
        try:
            action()
        except exceptions as e:
            checks.append({'name': name, 'passed': True, 'exception': type(e).__name__, 'detail': str(e)})
        else:
            raise AssertionError('EXPECTED_REFUSAL ' + name)
    def offer(ex, ident, rail='nonrecourse-simulated', buyer='modeled-funded', accepts=True):
        ex.offer(ident, buyer, price, rail, {**base, 'modeled_buyer_accepts': accepts}, 100)
        row = ex.order(ident)
        terms = {k: row[k] for k in ('id', 'buyer', 'price', 'rail', 'task_hash', 'contract', 'deadline')}
        ex.event(ident, 'consent-' + ident, 'consent', {'buyer': buyer, 'termsHash': sha(canonical(terms))}, 0)
    def fund(ex, ident, crash=False):
        return ex.event(ident, 'fund-' + ident, 'fund', ex.provider.issue(ex.order(ident), 'funded'), 1, crash=crash)
    def prepare(ex, ident):
        return ex.event(ident, 'prepare-' + ident, 'prepare', doc, 2)
    def release(ex, ident, crash=False):
        return ex.event(ident, 'release-' + ident, 'release', ex.provider.issue(ex.order(ident), 'cleared'), 3, crash=crash)
    ex = opened('native-main')
    try:
        ex.wallet('modeled-funded', micro('1000000'))
        ex.wallet('modeled-unfunded', 0)
        costs = cost_inputs(policy)
        for category, value in policy['fixed_costs_cad'].items():
            ex.cost('fixed-' + category, micro(value))
        for i in range(policy['cohort_size']):
            for category, value in costs.items():
                ex.cost('attempt-' + str(i) + '-' + category, micro(value))
        offer(ex, 'accepted')
        refuse('download-before-funding', PermissionError, lambda: ex.download('accepted', 'modeled-funded'))
        fund(ex, 'accepted')
        prepare(ex, 'accepted')
        refuse('download-before-clearing', PermissionError, lambda: ex.download('accepted', 'modeled-funded'))
        forged = ex.provider.issue(ex.order('accepted'), 'cleared')
        forged['signature'] = '0' * 64
        refuse('forged-clearing-observation', ValueError, lambda: ex.event('accepted', 'forged', 'release', forged, 3))
        release(ex, 'accepted')
        before = snapshot_rows(ex)
        release(ex, 'accepted')
        if before != snapshot_rows(ex):
            raise AssertionError('DUPLICATE_SETTLEMENT_CHANGED_STATE')
        checks.append({'name': 'duplicate-settlement-idempotent', 'passed': True})
        delivered = ex.download('accepted', 'modeled-funded')
        if delivered != canonical(doc):
            raise AssertionError('DELIVERED_BYTES_CHANGED')
        (output / 'DELIVERED.json').write_bytes(delivered)
        refuse('wrong-buyer-download', PermissionError, lambda: ex.download('accepted', 'other'))
        offer(ex, 'nonpayment', buyer='modeled-unfunded')
        refuse('nonpayment-refused', ValueError, lambda: fund(ex, 'nonpayment'))
        ex.event('nonpayment', 'cancel-nonpayment', 'cancel', {}, 2)
        offer(ex, 'buyer-rejection', accepts=False)
        fund(ex, 'buyer-rejection')
        refuse('modeled-buyer-rejection', ValueError, lambda: prepare(ex, 'buyer-rejection'))
        ex.event('buyer-rejection', 'refund-buyer-rejection', 'refund', {}, 3)
        before = snapshot_rows(ex)
        ex.event('buyer-rejection', 'refund-buyer-rejection', 'refund', {}, 3)
        if before != snapshot_rows(ex):
            raise AssertionError('DUPLICATE_REFUND_CHANGED_STATE')
        checks.append({'name': 'duplicate-refund-idempotent', 'passed': True})
        offer(ex, 'interrupted')
        before = snapshot_rows(ex)
        refuse('funding-before-commit-interrupted', InterruptedError, lambda: fund(ex, 'interrupted', True))
        if before != snapshot_rows(ex):
            raise AssertionError('FUNDING_CRASH_NOT_ATOMIC')
        ex.close()
        ex = opened('native-main')
        fund(ex, 'interrupted')
        prepare(ex, 'interrupted')
        before = snapshot_rows(ex)
        refuse('release-before-commit-interrupted', InterruptedError, lambda: release(ex, 'interrupted', True))
        if before != snapshot_rows(ex):
            raise AssertionError('RELEASE_CRASH_NOT_ATOMIC')
        ex.close()
        ex = opened('native-main')
        release(ex, 'interrupted')
        checks.append({'name': 'durable-reopen-recovery', 'passed': ex.download('interrupted', 'modeled-funded') == canonical(doc)})
        released = ['accepted', 'interrupted']
        for i in range(policy['cohort_size'] - 4):
            ident = 'additional-' + str(i)
            offer(ex, ident)
            fund(ex, ident)
            prepare(ex, ident)
            release(ex, ident)
            released.append(ident)
        snapshots['ideal_provider_before_clustered_reversal'] = snapshot_rows(ex)
        for ident in released:
            ex.event(ident, 'reversal-' + ident, 'late_reversal', {}, 4)
        snapshots['clustered_reversal'] = snapshot_rows(ex)
        if ex.snapshot()['revenue'] != 0 or ex.snapshot()['collections'] != 0 or ex.snapshot()['unrestrictedEarned'] != 0:
            raise AssertionError('REVERSED_REVENUE_OR_EARNINGS_REMAIN')
        refuse('breach-defers-native-investment', ValueError, lambda: ex.reserve_investment('successor', 1, 1, intent_hash=binding['artifact']))
    finally:
        ex.close()
    ex = opened('native-reversible-refusal')
    try:
        ex.wallet('modeled-funded', micro('1000'))
        offer(ex, 'card', rail='reversible')
        fund(ex, 'card')
        prepare(ex, 'card')
        refuse('reversible-card-not-nonrecourse', ValueError, lambda: release(ex, 'card'))
        refuse('reversible-card-delivery-gate', PermissionError, lambda: ex.download('card', 'modeled-funded'))
        ex.event('card', 'refund-card', 'refund', {}, 4)
        snapshots['reversible_route_refused'] = snapshot_rows(ex)
    finally:
        ex.close()
    ex = opened('native-custody-outage')
    try:
        ex.wallet('modeled-funded', micro('1000'))
        offer(ex, 'outage')
        fund(ex, 'outage')
        ex.event('outage', 'outage-loss', 'custody_loss', {}, 2)
        ex.event('outage', 'outage-refund', 'refund', {}, 3)
        snapshots['custody_outage_compensated'] = snapshot_rows(ex)
        if ex.order('outage')['state'] != 'refunded' or ex.snapshot()['revenue'] != 0:
            raise AssertionError('CUSTODY_LOSS_NOT_COMPENSATED')
        checks.append({'name': 'custody-loss-compensation-separate-from-revenue', 'passed': True})
    finally:
        ex.close()
    return {'schema': 'agi-alpha/next009-native-exchange-mechanism/v1', 'currency': 'simulated-microUSD', 'cad_quote_conversion': {'cad': policy['price_cad'], 'cad_per_usd': policy['cad_per_usd'], 'microUSD_rounded_half_up': price}, 'source_pins': PINS, 'binding': binding, 'checks': checks, 'all_checks_passed': all(c['passed'] for c in checks), 'snapshots': snapshots, 'native_provider_cost': None, 'native_provider_cost_status': 'UNKNOWN_IDEAL_NONRECOURSE_SIMULATION_HAS_NO_REAL_PROVIDER_QUOTE', 'card_fees_applied_to_native_provider': False, 'real_customer_or_provider_observations': False, 'native_scenario_earnings_are_not_qualified_commercial_earnings': True, 'successful_investment_reservations': 0, 'scope': 'Existing source-pinned Alpha exchange only. Native before-commit interruption tests are separate from the inherited SIGINT-startup defect and do not repair or qualify it.'}


def run(artifact, receipt, verifier_source, protocol, expected, output, price_cad=None, cohort_size=None):
    start, cpu = time.monotonic(), time.process_time()
    _, _, binding = bind_inputs(artifact, receipt, verifier_source, protocol, expected)
    policy, policy_raw = json_file(HERE / 'policy.json')
    if price_cad is not None:
        policy['price_cad'] = str(price_cad)
    if cohort_size is not None:
        policy['cohort_size'] = cohort_size
    validate_policy(policy)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen_policy = canonical(policy)
    (output / 'FROZEN_POLICY.json').write_bytes(frozen_policy)
    projections = [card_projection(policy, scenario) for scenario in policy['scenarios']]
    native = native_mechanism(output, artifact, receipt, verifier_source, protocol, expected, policy)
    result = {'schema': 'agi-alpha/next009-commerce/v1', 'decision': 'CONDITIONAL_SCENARIOS_EXECUTED_COMMERCIAL_VALIDATION_NOT_ESTABLISHED', 'binding': binding, 'policy_sha256': sha(frozen_policy), 'policy_template_sha256': sha(policy_raw), 'source_docket_sha256': sha(raw_file(HERE / 'source_docket.json')), 'adapter_sha256': sha(raw_file(__file__)), 'prospective_price_cad': policy['price_cad'], 'illustrative_opportunities': policy['cohort_size'], 'actual_technical_artifacts_bound': 1, 'card_analytical_scenarios': projections, 'native_exchange_mechanism': native, 'claims': {'technical_functional_acceptance': 'TRUSTED_FROZEN_RECEIPT_BOUND_TO_ACTUAL_BYTES', 'autonomous_complete_cost_advantage_over_humans': 'UNKNOWN_MATCHED_PERSON_TIME_AND_COMPLETE_COST', 'conditional_positive_operating_scenarios': any(D(s['cashflow_cad']['accounting_profit_within_authored_scenario']) > 0 for s in projections), 'negative_to_positive_human_profit_crossing': 'NOT_ESTABLISHED', 'competitive_commercial_viability': 'UNKNOWN_SUBSTITUTION_AND_UPTAKE', 'AGI_ALPHA_value_capture': 'UNKNOWN', 'qualified_unrestricted_simulated_earnings_cad': '0.00', 'earned_funded_successor': 'DEFERRED', 'actual_revenue_cad': '0.00', 'live_commerce': 'NOT_RUN'}, 'unknowns': ['matched competent-human task hours, loaded overhead, review and rework', 'AGI ALPHA-specific willingness to pay and repeated demand', 'actual session model revision, tokens, billed inference and tool usage', 'complete historical and current research/construction cost and recovery', 'provider eligibility, dispute frequency, taxes, FX spread, warranty tail and acquisition costs'], 'resources': {'wall_seconds': time.monotonic() - start, 'process_cpu_seconds': time.process_time() - cpu, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'new_paid_model_calls': 0, 'new_real_spending_cad': '0.00', 'complete_actual_monetary_cost': None}, 'assurance': 'Same shared model/host/libraries. Frozen external hashes establish artifact identity at the caller boundary, not independent external certification. No new financial ledger or production escrow implementation.'}
    for name, value in [('NATIVE_EXCHANGE.json', native), ('CARD_SCENARIOS.json', projections), ('COMMERCIAL.json', result)]:
        with (output / name).open('x') as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description='Bind actual accepted water-plan bytes to existing exchange checks and separate conditional CAD cashflow scenarios.')
    for name in ('artifact', 'receipt', 'verifier-source', 'protocol', 'expected-artifact-sha256', 'expected-receipt-sha256', 'expected-verifier-sha256', 'expected-protocol-sha256', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--price-cad')
    parser.add_argument('--cohort-size', type=int)
    args = parser.parse_args()
    expected = {'artifact': args.expected_artifact_sha256, 'receipt': args.expected_receipt_sha256, 'verifier': args.expected_verifier_sha256, 'protocol': args.expected_protocol_sha256}
    result = run(args.artifact, args.receipt, args.verifier_source, args.protocol, expected, args.output, args.price_cad, args.cohort_size)
    print(json.dumps({'output': args.output, 'native_checks_passed': result['native_exchange_mechanism']['all_checks_passed'], 'claims': result['claims']}))


if __name__ == '__main__':
    main()
