"""Narrow, registered native capital operation; synthetic work and cash only."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import shutil
import time

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from commercial.terms import prospective_terms
from connected_enterprise.finance import JournalAccount, audit_journal

SCHEMA = 'agi-alpha/native-capital-registration/v1'
FREEZE = 'agi-alpha/native-capital-freeze/v1'
MICRO = 1_000_000


def default_config():
    return {'schema': 'agi-alpha/native-capital-config/v1', 'clock_unit': 'INTEGER_HOURS',
            'arrivals': 12, 'interval_hours': 4, 'settlement_hours': 1, 'protection_hours': 2,
            'opening_microUSD': 500 * MICRO, 'working_microUSD': 100 * MICRO,
            'price_microUSD': 200 * MICRO, 'production_cost_microUSD': 50 * MICRO,
            'premium_microUSD': MICRO, 'payment_bps': 290, 'payment_fixed_microUSD': 300_000,
            'tax_bps': 2000, 'setup_microUSD': 5 * MICRO, 'buyer_budget_microUSD': 300 * MICRO,
            'buyer_value_microUSD': 350 * MICRO, 'human_hours': 4,
            'human_loaded_microUSD_hour': 62_500_000, 'rival_price_microUSD': 220 * MICRO,
            'self_service_value_microUSD': 180 * MICRO, 'self_service_effort_microUSD': 60 * MICRO,
            'decline_every': 0, 'service_cohort_seed': 2610312001, 'recycling_enabled': True,
            'claims': [], 'horizon_hours': 48}


def validate_config(raw):
    if not isinstance(raw, dict) or set(raw) - set(default_config()):
        raise ValueError('DECLARED_NATIVE_CAPITAL_CONFIGURATION_REQUIRED')
    cfg = {**default_config(), **copy.deepcopy(raw)}
    if 'horizon_hours' not in raw:
        cfg['horizon_hours'] = (cfg['arrivals'] - 1) * cfg['interval_hours'] + cfg['settlement_hours'] + cfg['protection_hours'] + 1
    if cfg['schema'] != default_config()['schema'] or cfg['clock_unit'] != 'INTEGER_HOURS' or type(cfg['recycling_enabled']) is not bool:
        raise ValueError('NATIVE_CAPITAL_SCHEMA_CLOCK_OR_POLICY_INVALID')
    for key, value in cfg.items():
        if key in {'schema', 'clock_unit', 'recycling_enabled', 'claims'}:
            continue
        if type(value) is not int or not 0 <= value <= 10**12:
            raise ValueError('BOUNDED_NATIVE_CAPITAL_INTEGER_REQUIRED:' + key)
    if (not 1 <= cfg['arrivals'] <= 24 or cfg['interval_hours'] < 1 or cfg['settlement_hours'] < 1
            or cfg['protection_hours'] < 1 or cfg['price_microUSD'] < 200_000
            or cfg['production_cost_microUSD'] < 1 or cfg['payment_bps'] > 10_000 or cfg['tax_bps'] > 10_000
            or cfg['working_microUSD'] > cfg['opening_microUSD']):
        raise ValueError('BOUNDED_NATIVE_CAPITAL_OPERATING_LIMIT_REQUIRED')
    drain = (cfg['arrivals'] - 1) * cfg['interval_hours'] + cfg['settlement_hours'] + cfg['protection_hours'] + 1
    if cfg['horizon_hours'] < drain:
        raise ValueError('PREREGISTERED_HORIZON_MUST_INCLUDE_MATURITY_DRAIN')
    if not isinstance(cfg['claims'], list) or len(cfg['claims']) > 24:
        raise ValueError('BOUNDED_REGISTERED_CLAIMS_REQUIRED')
    for claim in cfg['claims']:
        if (not isinstance(claim, dict) or set(claim) != {'hour', 'order_index', 'amount', 'kind'}
                or any(type(claim[k]) is not int for k in ['hour', 'order_index', 'amount'])
                or not 0 <= claim['order_index'] < cfg['arrivals'] or not 0 < claim['amount'] <= 10**12
                or not claim['order_index'] * cfg['interval_hours'] + cfg['settlement_hours'] < claim['hour'] <= cfg['horizon_hours']
                or claim['kind'] not in {'ordinary', 'disputed', 'covered', 'provider_default'}):
            raise ValueError('EXACT_REGISTERED_NATIVE_CLAIM_REQUIRED')
    return cfg


def _read(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('REGULAR_CAPITAL_FILE_REQUIRED')
    return strict_json(path.read_bytes())


def _write(path, value):
    atomic_bytes(Path(path), canonical(value) + b'\n')


def is_capital(output):
    path = Path(output) / 'FROZEN.json'
    return path.is_file() and _read(path).get('schema') == FREEZE


def freeze(root, config, output, *, comparison=False):
    from .runner import identity
    root, output = Path(root).resolve(), Path(output).resolve()
    cfg = validate_config(config)
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise FileExistsError('NEW_NATIVE_CAPITAL_OUTPUT_REQUIRED')
    source = identity(root)
    output.mkdir(parents=True)
    for name in source['files']:
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    if identity(output / 'source') != source:
        raise ValueError('NATIVE_CAPITAL_FROZEN_SOURCE_CHANGED')
    frozen = {'schema': FREEZE, 'scope': 'CONDITIONAL_SYNTHETIC_ENGINEERING', 'source': source,
              'config': cfg, 'comparison': comparison,
              'registered_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'policy': 'Finite inbound opportunities, voluntary utility choice, native earned funding; no real commerce.',
              'stopping': 'Registered finite opportunities and horizon; retain every decline, failure and outstanding obligation.'}
    frozen['sha256'] = digest(frozen)
    _write(output / 'FROZEN.json', frozen)
    return frozen


def read_freeze(output):
    from .runner import identity
    output = Path(output).resolve()
    frozen = _read(output / 'FROZEN.json')
    body = {k: v for k, v in frozen.items() if k != 'sha256'}
    if (frozen.get('schema') != FREEZE or digest(body) != frozen.get('sha256')
            or validate_config(frozen['config']) != frozen['config'] or identity(output / 'source') != frozen['source']):
        raise ValueError('NATIVE_CAPITAL_REGISTRATION_OR_SOURCE_CHANGED')
    return frozen


def register(output):
    from adaptive_enterprise.instruments import prepare_services, load_jobs
    output = Path(output).resolve()
    frozen = read_freeze(output)
    if (output / 'REGISTRATION.json').exists() or (output / 'SERVICES.json').exists():
        raise FileExistsError('NATIVE_CAPITAL_ALREADY_REGISTERED')
    manifest = prepare_services(output / 'source', 'capital-service-inputs', cohort_seed=frozen['config']['service_cohort_seed'])
    accepted = sorted((j for j in manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted']), key=lambda j: j['id'])
    if len(accepted) < frozen['config']['arrivals']:
        raise ValueError('SUFFICIENT_DISTINCT_QUALIFIED_RECONCILIATION_JOBS_REQUIRED')
    load_jobs(output / 'source', manifest)
    opportunities = [{'index': i, 'id': 'capital-order-' + str(i).zfill(3), 'buyer_id': 'synthetic-buyer-' + str(i).zfill(3),
                      'hour': i * frozen['config']['interval_hours'], 'job_id': accepted[i]['id']}
                     for i in range(frozen['config']['arrivals'])]
    registration = {'schema': SCHEMA, 'frozen_sha256': frozen['sha256'], 'manifest_sha256': digest(manifest),
                    'opportunities': opportunities, 'service_scope': 'One deterministic synthetic reconciliation service; no frontier model call.',
                    'cost_policy': 'Declared prepaid complete-resource invoice includes production, verification, delivery and support; premiums, payment fees, setup and tax charged separately. Host/model billing unknown.',
                    'tax_policy': 'Incremental cumulative positive-profit provision at settlement, no modeled loss refund.',
                    'claim_precedence': 'Registered claims before maturity before settlement before arrival at the same hour.',
                    'comparison': 'Recycling enabled versus disabled holds prospective terms, opportunities, buyer policy, costs, source and opening cash fixed.'}
    registration['sha256'] = digest(registration)
    _write(output / 'SERVICES.json', manifest)
    _write(output / 'REGISTRATION.json', registration)
    return registration


def read_registration(output):
    frozen = read_freeze(output)
    registration = _read(Path(output) / 'REGISTRATION.json')
    manifest = _read(Path(output) / 'SERVICES.json')
    if (registration.get('schema') != SCHEMA or digest({k: v for k, v in registration.items() if k != 'sha256'}) != registration.get('sha256')
            or registration['frozen_sha256'] != frozen['sha256'] or registration['manifest_sha256'] != digest(manifest)):
        raise ValueError('NATIVE_CAPITAL_MANIFEST_OR_REGISTRATION_CHANGED')
    accepted = sorted((j for j in manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted']), key=lambda j: j['id'])
    expected = [{'index': i, 'id': 'capital-order-' + str(i).zfill(3), 'buyer_id': 'synthetic-buyer-' + str(i).zfill(3),
                 'hour': i * frozen['config']['interval_hours'], 'job_id': accepted[i]['id']} for i in range(frozen['config']['arrivals'])]
    if registration['opportunities'] != expected:
        raise ValueError('NATIVE_CAPITAL_OPPORTUNITIES_NOT_REDERIVED')
    return frozen, registration, manifest


def _choice(cfg, index):
    value = 0 if cfg['decline_every'] and (index + 1) % cfg['decline_every'] == 0 else cfg['buyer_value_microUSD']
    human = cfg['human_hours'] * cfg['human_loaded_microUSD_hour']
    options = [('decline', 0, 0)]
    for name, price in [('us', cfg['price_microUSD']), ('human', human), ('rival', cfg['rival_price_microUSD'])]:
        if price <= cfg['buyer_budget_microUSD']:
            options.append((name, value - price, price))
    options.append(('self_service', (min(value, cfg['self_service_value_microUSD']) - cfg['self_service_effort_microUSD']), 0))
    best = max(options, key=lambda item: item[1])
    return {'choice': best[0], 'utility_microUSD': best[1], 'cash_price_microUSD': best[2],
            'buyer_budget_microUSD': cfg['buyer_budget_microUSD'], 'buyer_value_microUSD': value,
            'options': [{'provider': n, 'utility_microUSD': u, 'cash_price_microUSD': p} for n, u, p in options],
            'assumption_scope': 'Authored voluntary deterministic choice, no demand calibration or real buyer.'}


def _queue(state, kind, hour, ident, **fields):
    priority = {'startup': 0, 'claim': 1, 'mature': 2, 'settle': 3, 'arrival': 4}[kind]
    state['queue'].append({'kind': kind, 'hour': hour, 'id': ident, 'priority': priority, **fields})
    state['queue'].sort(key=lambda e: (e['hour'], e['priority'], e['id']))


def _initial(frozen, registration, enabled):
    state = {'schema': 'agi-alpha/native-capital-state/v1', 'registration_sha256': registration['sha256'],
             'recycling_enabled': enabled, 'queue': [], 'current': None, 'events': [], 'orders': [],
             'decisions': [], 'processed_events': 0, 'tax_provisioned': 0, 'last_hour': 0}
    _queue(state, 'startup', 0, 'startup')
    for opportunity in registration['opportunities']:
        _queue(state, 'arrival', opportunity['hour'], 'arrival-' + opportunity['id'], opportunity=opportunity)
    for index, claim in enumerate(frozen['config']['claims']):
        _queue(state, 'claim', claim['hour'], 'registered-claim-' + str(index), claim=claim)
    return state


def operate(output, *, max_events=None, business=None, enabled=None):
    from adaptive_enterprise.instruments import execute_job
    from enterprise.runner import RunLock
    output = Path(output).resolve()
    frozen, registration, manifest = read_registration(output)
    cfg = frozen['config']
    enabled = cfg['recycling_enabled'] if enabled is None else enabled
    business = output / 'business' if business is None else Path(business)
    business.mkdir(parents=True, exist_ok=True)
    if max_events is not None and (type(max_events) is not int or max_events < 1):
        raise ValueError('POSITIVE_NATIVE_CAPITAL_EVENT_BOUND_REQUIRED')
    root = output / 'source'
    contract = 'native-capital-p0/' + digest({'registration': registration['sha256'], 'recycling_enabled': enabled})
    jobs = {j['id']: j for j in manifest['jobs']}
    with RunLock(business), JournalAccount(root, manifest, business / 'account.sqlite', opening=cfg['opening_microUSD'], working=cfg['working_microUSD'], contract=contract) as account:
        state_path = business / 'STATE.json'
        state = account.verify_checkpoint(_read(state_path)) if state_path.exists() else _initial(frozen, registration, enabled)
        if state['registration_sha256'] != registration['sha256'] or state['recycling_enabled'] is not enabled:
            raise ValueError('NATIVE_CAPITAL_CONTINUING_BUSINESS_IDENTITY_CHANGED')
        performed = 0
        while state['queue'] and (max_events is None or performed < max_events):
            if state['current'] is None:
                state['current'] = copy.deepcopy(state['queue'][0])
                account.save_checkpoint(state_path, state)
            event = state['current']; moment = event['hour']; kind = event['kind']
            if moment > cfg['horizon_hours']:
                raise ValueError('REGISTERED_NATIVE_CAPITAL_HORIZON_EXCEEDED')
            detail = {}
            if kind == 'startup':
                account.cost('capital-complete-setup', cfg['setup_microUSD'], moment)
            elif kind == 'arrival':
                opportunity = event['opportunity']; ident = opportunity['id']; choice = _choice(cfg, opportunity['index'])
                fee = (cfg['price_microUSD'] * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed_microUSD']
                price = cfg['price_microUSD']; production = cfg['production_cost_microUSD']; premium = cfg['premium_microUSD']
                expected_profit = price - production - premium - fee
                maximum_tax = max(0, expected_profit) * cfg['tax_bps'] // 10000
                if 'decision' not in event:
                    before = account.snapshot(); summary = before['summary']
                    seed_remaining = max(0, cfg['opening_microUSD'] - cfg['working_microUSD'] - summary['expensePaid'] - summary['payables'] - summary['reservedInvestment'])
                    affordable = summary['available'] >= production + premium + fee + price + maximum_tax
                    policy_funded = enabled or seed_remaining >= production + premium + fee + maximum_tax
                    admitted = choice['choice'] == 'us' and affordable and policy_funded and expected_profit > 0 and not summary['investmentStopped']
                    event['decision'] = {'index': opportunity['index'], 'hour': moment, 'order_id': ident, 'buyer': choice,
                                         'audited_before': before, 'remaining_original_seed_spend_cap': seed_remaining,
                                         'affordable': affordable, 'policy_funded': policy_funded, 'admitted': admitted,
                                         'reason': ('ADMITTED' if admitted else 'VOLUNTARY_OUTSIDE_CHOICE' if choice['choice'] != 'us'
                                                    else 'INSUFFICIENT_OR_COMMITTED_CASH' if not affordable else 'RECYCLING_DISABLED_SEED_CAP' if not policy_funded
                                                    else 'NONPOSITIVE_COMPLETE_COST_EXPECTATION_OR_STOPPED_ACCOUNT')}
                    account.save_checkpoint(state_path, state)
                decision = event['decision']
                if decision['admitted']:
                    settled_at = moment + cfg['settlement_hours']; boundary = settled_at + cfg['protection_hours']
                    terms = prospective_terms(ident, price, boundary, settled_at, premium=premium, fee=fee)
                    account.execute('register_terms', {'id': 'terms-' + ident, 'terms': terms}, moment)
                    funding = account.spend('production-' + ident, 'production_contract', production, moment,
                                            {'job_id': opportunity['job_id'], 'artifact_sha256': jobs[opportunity['job_id']]['artifact_sha256'],
                                             'terms_sha256': digest(terms),
                                             'resource_contract': 'Prepaid complete synthetic production, checking, delivery and support invoice'},
                                            expected_net=expected_profit, allow_seed=True, seed_only=not enabled)
                    if funding is None:
                        raise ValueError('REGISTERED_NATIVE_PRODUCTION_FUNDING_DISAPPEARED')
                    account.execute('wallet', {'buyer': opportunity['buyer_id'], 'amount': cfg['buyer_budget_microUSD']}, moment)
                    account.execute('offer', {'id': ident, 'buyer': opportunity['buyer_id'], 'price': price,
                                             'job_id': opportunity['job_id'], 'deadline': settled_at, 'terms_id': 'terms-' + ident}, moment)
                    for action in ['consent', 'fund']:
                        account.execute('event', {'id': ident, 'event_id': ident + '-' + action, 'action': action}, moment)
                    execution = execute_job(root, jobs[opportunity['job_id']])
                    if execution['accepted'] is not True:
                        raise ValueError('NATIVE_CAPITAL_USEFUL_EXECUTION_NOT_ACCEPTED')
                    account.execute('event', {'id': ident, 'event_id': ident + '-accept', 'action': 'prepare'}, moment)
                    state['orders'].append({**opportunity, 'accepted_hour': moment, 'settled_hour': None, 'matured_hour': None,
                                            'terms': terms, 'terms_sha256': digest(terms), 'funding_receipt': funding,
                                            'execution': execution, 'production_cost': production, 'premium': premium, 'payment_fee': fee,
                                            'price': price, 'tax': 0})
                    _queue(state, 'settle', settled_at, 'settle-' + ident, order_id=ident)
                state['decisions'].append(decision); detail = {'order_id': ident, 'decision': decision['reason']}
            elif kind == 'settle':
                order = next(o for o in state['orders'] if o['id'] == event['order_id'])
                release_receipt = account.execute('event', {'id': order['id'], 'event_id': order['id'] + '-collect', 'action': 'release'}, moment)
                if 'tax_intent' not in event:
                    summary = release_receipt['summary']
                    event['tax_intent'] = max(0, max(0, summary['profit'] + state['tax_provisioned']) * cfg['tax_bps'] // 10000 - state['tax_provisioned'])
                    account.save_checkpoint(state_path, state)
                tax = event['tax_intent']
                if tax:
                    account.cost('tax-' + order['id'], tax, moment)
                order['tax'] = tax; order['settled_hour'] = moment; state['tax_provisioned'] += tax
                _queue(state, 'mature', order['terms']['maturity_day'] + 1, 'maturity-' + order['id'], order_id=order['id'])
                detail = {'order_id': order['id'], 'tax': tax}
            elif kind == 'mature':
                order = next(o for o in state['orders'] if o['id'] == event['order_id'])
                account.execute('mature', {'id': order['id'], 'event_id': 'maturity:' + order['id'] + ':' + order['terms_sha256']}, moment)
                order['matured_hour'] = moment; detail = {'order_id': order['id']}
            elif kind == 'claim':
                claim = event['claim']; ident = 'capital-order-' + str(claim['order_index']).zfill(3)
                if any(o['id'] == ident and o['settled_hour'] is not None for o in state['orders']):
                    account.execute('claim', {'id': ident, 'claim_id': event['id'], 'amount': claim['amount'], 'kind': claim['kind']}, moment)
                    detail = {'order_id': ident, 'claim_recorded': True}
                else:
                    detail = {'order_id': ident, 'claim_recorded': False, 'reason': 'NO_ACTIVATED_COLLECTED_CONTRACT'}
            else:
                raise ValueError('REGISTERED_NATIVE_CAPITAL_EVENT_REQUIRED')
            state['events'].append({'id': event['id'], 'kind': kind, 'hour': moment, **detail})
            state['queue'].pop(0); state['current'] = None; state['processed_events'] += 1; state['last_hour'] = moment
            account.save_checkpoint(state_path, state); performed += 1
        record = account.export(); checked = account.audit()
        result = {'schema': 'agi-alpha/native-capital-result/v1', 'registration_sha256': registration['sha256'],
                  'source_sha256': frozen['source']['sha256'], 'recycling_enabled': enabled,
                  'complete': not state['queue'], 'state': state, 'owned_account': record, 'summary': checked['summary'],
                  'scope': 'CONDITIONAL_SYNTHETIC_ENGINEERING_NOT_EXTERNAL_COMMERCE'}
        _write(business / 'RESULT.json', result)
        return result


def _score(result, cfg):
    state, record, summary = result['state'], result['owned_account'], result['summary']
    actions = record['ledger']['actions']; releases = {e['args']['id']: e for e in actions if e['op'] == 'event' and e['args']['action'] == 'release'}
    maturities = {e['args']['id']: e for e in actions if e['op'] == 'mature'}
    per_order = {}
    for order in state['orders']:
        subtotal = {}
        for row in record['ledger']['journal']:
            if row['order_id'] == order['id']:
                subtotal[row['kind']] = subtotal.get(row['kind'], 0) + int(row['amount'])
        per_order[order['id']] = (subtotal.get('revenue', 0) - subtotal.get('contra_revenue', 0)
                                  + subtotal.get('recovery_income', 0) - subtotal.get('expense', 0)
                                  + subtotal.get('expense_reversal', 0) - order['production_cost'] - order['tax'])
    lineage = []
    for order in state['orders']:
        funding = order['funding_receipt']
        if funding['funding'] != 'EARNED':
            continue
        reservation = next(e for e in actions if e['op'] == 'reserve' and e['args']['id'] == funding['plan_id'])
        lineage.append({'later_order_id': order['id'], 'reservation_sequence': reservation['seq'], 'plan_id': funding['plan_id'],
                        'amount_microUSD': reservation['args']['amount'], 'audited_unrestricted_earned_before': reservation['before']['unrestrictedEarned'],
                        'earlier_collected_order_ids': [ident for ident, e in releases.items() if e['seq'] < reservation['seq']],
                        'earlier_matured_order_ids': [ident for ident, e in maturities.items() if e['seq'] < reservation['seq']],
                        'later_settled': order['settled_hour'] is not None,
                        'later_modeled_profit_microUSD': per_order[order['id']],
                        'basis': 'Audited fungible earned cash, not an exclusive physical cash-lot claim.'})
    settled = [o for o in state['orders'] if o['settled_hour'] is not None]
    earned = [row for row in lineage if row['later_settled'] and row['later_modeled_profit_microUSD'] > 0 and row['earlier_matured_order_ids']]
    return {'schema': 'agi-alpha/native-capital-scoreboard/v1', 'scope': result['scope'], 'complete': result['complete'],
            'recycling_enabled': result['recycling_enabled'], 'arrivals_observed': len(state['decisions']),
            'voluntary_choices_for_us': sum(d['buyer']['choice'] == 'us' for d in state['decisions']),
            'qualified_orders': len(state['orders']), 'accepted_orders': len(state['orders']), 'settled_orders': len(settled),
            'matured_orders': len(maturities), 'profitable_earned_continuations': len(earned),
            'repeated_earned_financed_expansion': result['complete'] and len(earned) >= 2 and summary['profit'] > 0 and summary['unrestrictedEarned'] > 0 and summary['payables'] == 0 and not summary['investmentStopped']
                                                 and summary['cash'] >= summary['custodyReserve'] + summary['tailReserve'] + summary['workingCapital'] + summary['reservedInvestment'],
            'native_summary': summary, 'funding_lineage': lineage, 'per_order_native_profit_microUSD': per_order,
            'shared_setup_cost_microUSD': cfg['setup_microUSD'], 'tax_provisioned_microUSD': sum(o['tax'] for o in state['orders']),
            'tax_cash_paid_microUSD': sum(e['after']['expensePaid'] - e['before']['expensePaid'] for e in actions if e['op'] == 'cost' and e['args']['id'].startswith('tax-')),
            'growth_ledger': [{'cohort': o['index'], 'order_id': o['id'], 'accepted_hour': o['accepted_hour'],
                               'settled_hour': o['settled_hour'], 'matured_hour': o['matured_hour'], 'price': o['price'],
                               'production_cost': o['production_cost'], 'premium': o['premium'], 'payment_fee': o['payment_fee'], 'tax': o['tax'],
                               'native_profit_microUSD': per_order[o['id']],
                               'funding': o['funding_receipt']['funding']} for o in state['orders']],
            'retention': None, 'market_conversion_calibration': None, 'actual_frontier_model_billing': None, 'actual_host_billing': None,
            'actual_customers': 0, 'actual_collections': 0, 'actual_profit': None,
            'profit_status': 'CONDITIONAL_ON_DECLARED_COMPLETE_RESOURCE_INVOICES_AND_UNKNOWN_ACTUAL_BILLING',
            'limits': ['Narrow deterministic synthetic reconciliation service, no paid frontier model call.',
                       'Authored finite buyer opportunities, prices and prospective terms; no empirical market or legal calibration.',
                       'Setup/resource invoice includes modeled verification, failures and support; actual host/model billing remains unknown.',
                       'No inference about annual profit, all services, actual commerce, or capability compounding.']}


def audit_business(output, business=None):
    from adaptive_enterprise.instruments import execute_job
    output = Path(output).resolve(); business = output / 'business' if business is None else Path(business)
    frozen, registration, manifest = read_registration(output); cfg = frozen['config']; result = _read(business / 'RESULT.json')
    if result['registration_sha256'] != registration['sha256'] or result['source_sha256'] != frozen['source']['sha256']:
        raise ValueError('NATIVE_CAPITAL_RESULT_AUTHORITY_CHANGED')
    checked = audit_journal(result['owned_account'], root=output / 'source', manifest=manifest)
    if result['summary'] != checked['summary'] or result['state']['registration_sha256'] != registration['sha256']:
        raise ValueError('NATIVE_CAPITAL_SUMMARY_OR_STATE_CHANGED')
    actions = result['owned_account']['ledger']['actions']; jobs = {j['id']: j for j in manifest['jobs']}
    native_config = result['owned_account']['ledger']['config']
    expected_contract = 'native-capital-p0/' + digest({'registration': registration['sha256'], 'recycling_enabled': result['recycling_enabled']})
    if (type(result['recycling_enabled']) is not bool or result['state']['recycling_enabled'] is not result['recycling_enabled']
            or native_config['opening'] != cfg['opening_microUSD'] or native_config['working'] != cfg['working_microUSD'] or native_config['contract'] != expected_contract):
        raise ValueError('NATIVE_CAPITAL_ACCOUNT_OR_POLICY_IDENTITY_CHANGED')
    if not frozen['comparison'] and result['recycling_enabled'] is not cfg['recycling_enabled']:
        raise ValueError('NATIVE_CAPITAL_REGISTERED_RECYCLING_POLICY_CHANGED')
    decisions = result['state']['decisions']; orders = result['state']['orders']
    if len({d['index'] for d in decisions}) != len(decisions) or len({o['id'] for o in orders}) != len(orders):
        raise ValueError('UNIQUE_NATIVE_CAPITAL_OPPORTUNITIES_REQUIRED')
    if [d['index'] for d in decisions] != list(range(len(decisions))) or len(decisions) > cfg['arrivals']:
        raise ValueError('ORDERED_REGISTERED_NATIVE_CAPITAL_ARRIVALS_REQUIRED')
    scheduled = _initial(frozen, registration, result['recycling_enabled'])
    for order in orders:
        _queue(scheduled, 'settle', order['hour'] + cfg['settlement_hours'], 'settle-' + order['id'], order_id=order['id'])
        if order['settled_hour'] is not None:
            _queue(scheduled, 'mature', order['terms']['maturity_day'] + 1, 'maturity-' + order['id'], order_id=order['id'])
    observed_events = result['state']['events']
    if (len({e['id'] for e in observed_events}) != len(observed_events)
            or len(observed_events) > len(scheduled['queue']) or result['state']['processed_events'] != len(observed_events)
            or result['state']['current'] is not None):
        raise ValueError('NATIVE_CAPITAL_PROCESSED_EVENT_PREFIX_REQUIRED')
    for observed, expected in zip(observed_events, scheduled['queue']):
        if any(observed.get(k) != expected[k] for k in ['id', 'kind', 'hour']):
            raise ValueError('NATIVE_CAPITAL_REGISTERED_EVENT_PRECEDENCE_CHANGED')
    if result['state']['queue'] != scheduled['queue'][len(observed_events):] or result['complete'] is not (not result['state']['queue']):
        raise ValueError('NATIVE_CAPITAL_REMAINING_REGISTERED_EVENTS_CHANGED')
    if [e['id'] for e in observed_events if e['kind'] == 'arrival'] != ['arrival-' + d['order_id'] for d in decisions]:
        raise ValueError('NATIVE_CAPITAL_ARRIVAL_DECISION_PREFIX_CHANGED')
    for decision in decisions:
        opportunity = registration['opportunities'][decision['index']]
        if decision['buyer'] != _choice(cfg, decision['index']) or decision['hour'] != opportunity['hour'] or decision['order_id'] != opportunity['id']:
            raise ValueError('NATIVE_CAPITAL_VOLUNTARY_BUYER_DECISION_CHANGED')
        before = decision['audited_before']; seq = before['sequence']
        if type(seq) is not int or not 1 <= seq <= len(actions):
            raise ValueError('NATIVE_CAPITAL_DECISION_PREFIX_REQUIRED')
        prior = actions[seq - 1]['after']; prefix_hash = digest(actions[:seq])
        if (before['summary'] != prior or before['actions_sha256'] != prefix_hash
                or before['state_digest'] != digest({'config': native_config, 'actions_sha256': prefix_hash, 'summary': prior})):
            raise ValueError('NATIVE_CAPITAL_DECISION_AUDITED_STATE_CHANGED')
        fee = (cfg['price_microUSD'] * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed_microUSD']
        expected_profit = cfg['price_microUSD'] - cfg['production_cost_microUSD'] - cfg['premium_microUSD'] - fee
        tax_bound = max(0, expected_profit) * cfg['tax_bps'] // 10000
        seed = max(0, cfg['opening_microUSD'] - cfg['working_microUSD'] - prior['expensePaid'] - prior['payables'] - prior['reservedInvestment'])
        affordable = prior['available'] >= cfg['production_cost_microUSD'] + cfg['premium_microUSD'] + fee + cfg['price_microUSD'] + tax_bound
        policy_funded = result['recycling_enabled'] or seed >= cfg['production_cost_microUSD'] + cfg['premium_microUSD'] + fee + tax_bound
        admitted = decision['buyer']['choice'] == 'us' and affordable and policy_funded and expected_profit > 0 and not prior['investmentStopped']
        if (decision['remaining_original_seed_spend_cap'] != seed or decision['affordable'] is not affordable
                or decision['policy_funded'] is not policy_funded or decision['admitted'] is not admitted):
            raise ValueError('NATIVE_CAPITAL_FUNDING_POLICY_NOT_REDERIVED')
    offers = {e['args']['id']: e for e in actions if e['op'] == 'offer'}
    if set(offers) != {o['id'] for o in orders} or {d['order_id'] for d in decisions if d['admitted']} != set(offers):
        raise ValueError('NATIVE_CAPITAL_ORDERS_NOT_BOUND_TO_NATIVE_OFFERS')
    native_claims = {e['args']['claim_id']: e for e in actions if e['op'] == 'claim'}
    observed_by_id = {e['id']: e for e in observed_events}
    expected_claims = {}
    for index, claim in enumerate(cfg['claims']):
        claim_id = 'registered-claim-' + str(index)
        if claim_id not in observed_by_id:
            continue
        order_id = 'capital-order-' + str(claim['order_index']).zfill(3)
        order = next((o for o in orders if o['id'] == order_id), None)
        activated = order is not None and order['settled_hour'] is not None and order['settled_hour'] < claim['hour']
        observed = observed_by_id[claim_id]
        if observed.get('order_id') != order_id or observed.get('claim_recorded') is not activated:
            raise ValueError('NATIVE_CAPITAL_REGISTERED_CLAIM_DISPOSITION_CHANGED')
        if activated:
            expected_claims[claim_id] = {'id': order_id, 'claim_id': claim_id, 'amount': claim['amount'], 'kind': claim['kind']}
            native = native_claims.get(claim_id)
            if native is None or native['args'] != expected_claims[claim_id] or native['day'] != claim['hour']:
                raise ValueError('NATIVE_CAPITAL_REGISTERED_CLAIM_OMITTED_OR_CHANGED')
            maturity = next((e for e in actions if e['op'] == 'mature' and e['args']['id'] == order_id and e['day'] == claim['hour']), None)
            if maturity is not None and native['seq'] >= maturity['seq']:
                raise ValueError('NATIVE_CAPITAL_CLAIM_MUST_PRECEDE_SAME_HOUR_MATURITY')
        elif observed.get('reason') != 'NO_ACTIVATED_COLLECTED_CONTRACT':
            raise ValueError('NATIVE_CAPITAL_UNACTIVATED_CLAIM_REASON_REQUIRED')
    if set(native_claims) != set(expected_claims):
        raise ValueError('NATIVE_CAPITAL_UNREGISTERED_CLAIM_OR_OMITTED_CLAIM')
    if any(e['op'] in {'recover_claim', 'resolve_claim'} for e in actions):
        raise ValueError('NATIVE_CAPITAL_UNREGISTERED_CLAIM_REMEDY')
    taxes = 0
    tax_actions = {e['args']['id']: e for e in actions if e['op'] == 'cost' and e['args']['id'].startswith('tax-')}
    expected_taxes = {}
    for event in actions:
        if event['op'] == 'event' and event['args']['action'] == 'release':
            due = max(0, max(0, event['after']['profit'] + taxes) * cfg['tax_bps'] // 10000 - taxes)
            expected_taxes[event['args']['id']] = due; taxes += due
    for order in orders:
        opportunity = registration['opportunities'][order['index']]
        if any(order[k] != opportunity[k] for k in opportunity) or order['terms_sha256'] != digest(order['terms']):
            raise ValueError('NATIVE_CAPITAL_ORDER_SOURCE_CHANGED')
        offer = offers[order['id']]
        if (offer['args']['job_id'] != order['job_id'] or offer['args']['price'] != cfg['price_microUSD']
                or offer['args']['buyer'] != opportunity['buyer_id'] or offer['day'] != opportunity['hour']):
            raise ValueError('NATIVE_CAPITAL_NATIVE_QUOTE_CHANGED')
        expected_fee = (cfg['price_microUSD'] * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed_microUSD']
        expected_terms = prospective_terms(order['id'], cfg['price_microUSD'], opportunity['hour'] + cfg['settlement_hours'] + cfg['protection_hours'],
                                           opportunity['hour'] + cfg['settlement_hours'], premium=cfg['premium_microUSD'], fee=expected_fee)
        registered_terms = next((e for e in actions if e['op'] == 'register_terms' and e['args']['id'] == 'terms-' + order['id']), None)
        if (order['terms'] != expected_terms or registered_terms is None or registered_terms['args']['terms'] != expected_terms
                or order['production_cost'] != cfg['production_cost_microUSD'] or order['premium'] != cfg['premium_microUSD']
                or order['payment_fee'] != expected_fee or order['price'] != cfg['price_microUSD']):
            raise ValueError('NATIVE_CAPITAL_COMPLETE_COST_TERMS_CHANGED')
        execution = execute_job(output / 'source', jobs[order['job_id']])
        if not execution['accepted'] or order['execution'].get('accepted') is not True or order['execution']['artifact_sha256'] != execution['artifact_sha256'] or order['execution'].get('reexecuted') is not True:
            raise ValueError('NATIVE_CAPITAL_PRODUCTION_NOT_REEXECUTED')
        prepare = next((e for e in actions if e['op'] == 'event' and e['args']['id'] == order['id'] and e['args']['action'] == 'prepare'), None)
        if prepare is None or order['accepted_hour'] != prepare['day']:
            raise ValueError('NATIVE_CAPITAL_ACCEPTANCE_TIME_NOT_BOUND_TO_NATIVE_PREPARE')
        release = next((e for e in actions if e['op'] == 'event' and e['args']['id'] == order['id'] and e['args']['action'] == 'release'), None)
        mature = next((e for e in actions if e['op'] == 'mature' and e['args']['id'] == order['id']), None)
        if order['settled_hour'] != (None if release is None else release['day']) or order['matured_hour'] != (None if mature is None else mature['day']):
            raise ValueError('NATIVE_CAPITAL_OPERATION_TIMING_CHANGED')
        tax = expected_taxes.get(order['id'], 0)
        if order['tax'] != tax or (tax and tax_actions.get('tax-' + order['id'], {}).get('args', {}).get('amount') != tax):
            raise ValueError('NATIVE_CAPITAL_TAX_PROVISION_CHANGED')
        funding = next((e for e in result['owned_account']['connected_journal']['entries'] if e['key'] == 'spend:production-' + order['id']), None)
        if funding is None or funding['receipt'] != order['funding_receipt'] or funding['request']['amount'] != cfg['production_cost_microUSD']:
            raise ValueError('NATIVE_CAPITAL_PRODUCTION_FUNDING_CHANGED')
        first_production = (next(e['seq'] for e in actions if e['op'] == 'reserve' and e['args']['id'] == funding['receipt']['plan_id'])
                            if funding['funding'] == 'EARNED' else funding['receipt']['native_event_sequence'])
        if funding['request']['work'].get('terms_sha256') != order['terms_sha256'] or registered_terms['seq'] >= first_production:
            raise ValueError('NATIVE_CAPITAL_TERMS_MUST_PRECEDE_BOUND_PRODUCTION_COMMITMENT')
        if not result['recycling_enabled'] and funding['funding'] != 'SEED':
            raise ValueError('RECYCLING_DISABLED_CONTROL_CANNOT_SPEND_EARNED_FUNDS')
    if result['complete']:
        if result['state']['queue'] or len(decisions) != cfg['arrivals'] or any(o['settled_hour'] is None or o['matured_hour'] is None for o in orders):
            raise ValueError('NATIVE_CAPITAL_COMPLETION_REQUIRES_SETTLEMENT_AND_MATURITY_DRAIN')
    scoreboard = _score(result, cfg)
    if result['state']['tax_provisioned'] != scoreboard['tax_provisioned_microUSD']:
        raise ValueError('NATIVE_CAPITAL_TAX_PROVISION_TOTAL_CHANGED')
    if sum(scoreboard['per_order_native_profit_microUSD'].values()) - cfg['setup_microUSD'] != result['summary']['profit']:
        raise ValueError('NATIVE_CAPITAL_ALL_COST_ORDER_PROFIT_RECONCILIATION_FAILED')
    return {'schema': 'agi-alpha/native-capital-audit/v1', 'accepted': True, 'source_sha256': frozen['source']['sha256'],
            'registration_sha256': registration['sha256'], 'native_audit': checked, 'scoreboard': scoreboard,
            'independence': 'Separate reconstruction and service reexecution; shared author/model/host/code and synthetic data, not external certification.'}


def audit_output(output):
    output = Path(output).resolve(); frozen = read_freeze(output)
    if frozen['comparison']:
        arms = {name: audit_business(output, output / 'arms' / name) for name in ['recycling_enabled', 'recycling_disabled']}
        if arms['recycling_enabled']['scoreboard']['recycling_enabled'] is not True or arms['recycling_disabled']['scoreboard']['recycling_enabled'] is not False:
            raise ValueError('NATIVE_CAPITAL_COMPARISON_ARM_IDENTITY_CHANGED')
        if (output / 'COMPARISON.json').exists() and _read(output / 'COMPARISON.json') != _comparison_report(frozen, {name: item['scoreboard'] for name, item in arms.items()}):
            raise ValueError('NATIVE_CAPITAL_COMPARISON_REPORT_NOT_REDERIVED')
        return {'accepted': all(v['accepted'] for v in arms.values()), 'arms': arms}
    return audit_business(output)


def _comparison_report(frozen, arms):
    enabled, disabled = arms['recycling_enabled'], arms['recycling_disabled']
    return {'schema': 'agi-alpha/native-capital-comparison/v1', 'scope': 'CONDITIONAL_ENGINEERING_MATCHED_FINANCING_EFFECT',
            'frozen_sha256': frozen['sha256'], 'arms': arms,
            'settled_order_delta': enabled['settled_orders'] - disabled['settled_orders'],
            'profit_delta_microUSD': enabled['native_summary']['profit'] - disabled['native_summary']['profit'],
            'terms_effect_tested': False, 'capability_effect_tested': False,
            'outside_options': 'The same authored human, rival, self-service and no-purchase choices in both arms.',
            'account_scope': 'Distinct named experimental allocations; neither replaces a continuing business or erases its obligations.'}


def comparison(output):
    output = Path(output).resolve(); frozen = read_freeze(output)
    if not frozen['comparison']:
        raise ValueError('DISTINCT_REGISTERED_COMPARISON_REQUIRED')
    if not (output / 'REGISTRATION.json').exists():
        register(output)
    for name, enabled in [('recycling_enabled', True), ('recycling_disabled', False)]:
        operate(output, business=output / 'arms' / name, enabled=enabled)
    audited = audit_output(output); arms = {name: item['scoreboard'] for name, item in audited['arms'].items()}
    result = _comparison_report(frozen, arms)
    _write(output / 'COMPARISON.json', result)
    return result
