"""Independent audit of paid audience rights, buyer choice, work and native cash.

ChannelBook records access to a prospect. A sale requires a separate cart
choice, accepted source-bound delivery and native financial settlement.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery
from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.channels import ChannelBook, SCHEMA as CHANNEL_SCHEMA, audit_channel_history
from connected_enterprise.finance import audit_journal

from . import cart_program as cart

CENT = 10_000


def _require(condition, error):
    if not condition:
        raise ValueError(error)


def _equal(actual, expected, error):
    # Canonical encoding distinguishes JSON booleans, integers and floats.
    _require(canonical(actual) == canonical(expected), error)


def _safe_path(root, relative):
    name = PurePosixPath(relative)
    _require(isinstance(relative, str) and name.parts and not name.is_absolute()
             and '..' not in name.parts and '\\' not in relative,
             'SAFE_RELATIVE_REACH_FILE_REQUIRED')
    path = root.joinpath(*name.parts)
    _require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
             'REGULAR_REACH_FILE_REQUIRED')
    return path


def _read(root, name):
    return strict_json(_safe_path(root, name).read_bytes())


class JournalCursor:
    """Consume the full audited native journal in the order operations were due.

    Native finance validates reserves, account authority and its action tape.
    This cursor checks each simulated business obligation against independently
    reconstructed requests, exposing economically unnecessary but valid debits.
    """

    def __init__(self, export):
        self.entries = export['connected_journal']['entries']
        self.actions = export['ledger']['actions']
        self.index = 0
        self.native_sequence = 0
        self.summary = self.actions[0]['before'] if self.actions else export['ledger']['summary']
        self.expense = 0

    def consume(self, expected):
        _require(self.index < len(self.entries), 'MISSING_EXPECTED_REACH_TRANSACTION')
        entry = self.entries[self.index]
        _require(entry['status'] == 'COMPLETE', 'INCOMPLETE_REACH_TRANSACTION')
        _equal(entry['request'], expected, 'UNEXPECTED_REACH_TRANSACTION')
        receipt = entry['receipt']
        last = (receipt['native_event_sequence'] if expected['operation'] == 'spend'
                else receipt['sequence'] - 1)
        _require(type(last) is int and 0 <= last < len(self.actions), 'BAD_REACH_TRANSACTION_INDEX')
        _require(last + 1 > self.native_sequence, 'REACH_JOURNAL_ORDER_CHANGED')
        self.native_sequence = last + 1
        self.summary = self.actions[last]['after']
        self.index += 1
        return receipt

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed):
        liquid = self.summary['available']
        earned = expected_net > 0 and min(liquid, self.summary['unrestrictedEarned']) >= amount
        _require(amount > 0 and liquid >= amount and (allow_seed or earned), 'UNFUNDED_REACH_OBLIGATION')
        receipt = self.consume({'operation': 'spend', 'id': ident, 'kind': kind,
                                'amount': amount, 'day': day, 'work': work,
                                'expected_net': expected_net, 'allow_seed': allow_seed})
        expected_id = 'connected014-resource-' + digest(ident)[:32] if earned else None
        _equal([receipt['funding'], receipt['plan_id']], ['EARNED' if earned else 'SEED', expected_id],
               'REACH_FUNDING_SOURCE_OR_PLAN_CHANGED')
        self.expense += amount
        return receipt

    def execute(self, op, args, day):
        receipt = self.consume({'operation': 'execute', 'op': op, 'args': args, 'day': day})
        if op == 'cost':
            self.expense += args['amount']
        return receipt

    def cost(self, ident, amount, day):
        return self.execute('cost', {'id': ident, 'amount': amount}, day)

    def prefix(self):
        return {'sequence': self.native_sequence,
                'actions_sha256': digest(self.actions[:self.native_sequence]),
                'available_microUSD': self.summary['available'],
                'earned_microUSD': self.summary['unrestrictedEarned']}

    def finish(self):
        _require(self.index == len(self.entries) and self.native_sequence == len(self.actions),
                 'HIDDEN_EXTRA_REACH_TRANSACTION')


def verify_channel(book, contracts, seed, buyers, days, plan_ids=()):
    _require(set(book) == {'schema', 'binding_sha256', 'instances', 'contacts', 'events',
                           'last_day', 'exposures_by_day', 'purchase_receipts'}
             and book['schema'] == CHANNEL_SCHEMA, 'REACH_CHANNEL_SCHEMA_CHANGED')
    _equal(sorted(book['exposures_by_day']), sorted(str(d) for d in days),
           'INCOMPLETE_CHANNEL_DAYS')
    expected_plans = set(plan_ids)
    _require(set(book['purchase_receipts']) == expected_plans, 'UNDECLARED_CHANNEL_RIGHT')
    return audit_channel_history(book, contracts, seed, buyers)


def _check_artifact(runtime, job, component):
    raw_path = _safe_path(runtime, job['input'])
    artifact_path = _safe_path(runtime, job['artifact'])
    _require(hashlib.sha256(raw_path.read_bytes()).hexdigest() == job['input_sha256'] and
             hashlib.sha256(artifact_path.read_bytes()).hexdigest() == job['artifact_sha256'],
             'REACH_JOB_SOURCE_CHANGED')
    raw = strict_json(raw_path.read_bytes())
    artifact = substrate.produce(raw, 'generated_schema', mode='conventional')
    _equal(component['artifact'], artifact, 'REACH_PRODUCT_CHANGED')
    verification = audit_delivery(job['service_id'], raw, artifact)
    _equal(component['verification'], verification, 'REACH_ACCEPTANCE_CHANGED')
    reference = strict_json(artifact_path.read_bytes())
    equivalent = substrate._semantics(reference) == substrate._semantics(artifact)
    _equal(component['admitted_outcome_equal'], equivalent, 'REACH_REFERENCE_OUTCOME_CHANGED')
    return verification['accepted'] and artifact['outcome_scope'] == 'complete_outcome' and equivalent


def _component_prices(price, services, market):
    single_cost = {o['services'][0]: max(1, o['cost_cents'])
                   for o in market['outcomes'] if len(o['services']) == 1}
    weights = [single_cost.get(name, 1) for name in services]
    parts = [price * w // sum(weights) for w in weights]
    parts[-1] += price - sum(parts)
    _require(all(p > 0 for p in parts), 'POSITIVE_REACH_COMPONENTS_REQUIRED')
    return parts


def _audit_checkout(row, source_hash, journal, market, program, jobs, runtime,
                    lifetime, initialized_wallets):
    """Reconstruct one funded union delivery, charges and conditional settlement."""
    day, ordinal, buyer = row['day'], row['ordinal'], row['buyer']
    choice = row['choice']
    outcome = next(o for o in market['outcomes'] if o['id'] == choice['outcome_id'])
    prices = _component_prices(choice['price_cents'], outcome['services'], market)
    components = row['components']
    _require(len(components) == len(jobs) == len(prices), 'REACH_UNION_CARDINALITY_CHANGED')
    if buyer not in initialized_wallets:
        journal.execute('wallet', {'buyer': buyer, 'amount': lifetime * CENT}, day)
        initialized_wallets.add(buyer)
    identities = []
    for i, (comp, job, price) in enumerate(zip(components, jobs, prices)):
        ident = f'reach-order-{ordinal}-{i}'
        _require(set(comp) == {'service', 'order_id', 'job_id', 'price_cents', 'artifact',
                              'verification', 'admitted_outcome_equal'}, 'UNREGISTERED_COMPONENT_FIELD')
        _equal([comp['service'], comp['order_id'], comp['job_id'], comp['price_cents']],
               [outcome['services'][i], ident, job['id'], price], 'REACH_COMPONENT_BINDING_CHANGED')
        journal.execute('offer', {'id': ident, 'buyer': buyer, 'price': price * CENT,
                                  'job_id': job['id'], 'deadline': day + 5}, day)
        for action in ('consent', 'fund'):
            journal.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, day)
        identities.append(ident)
    production = outcome['cost_cents'] * CENT
    work = {'source_sha256': source_hash, 'program_sha256': digest(program),
            'order_ids': identities, 'job_ids': [job['id'] for job in jobs]}
    journal.spend(f'reach-production-{ordinal}', 'production_contract', production, day, work,
                  max(1, choice['seller_contribution_cents'] * CENT), True)
    accepted = all([_check_artifact(runtime, job, comp) for job, comp in zip(jobs, components)])
    fee = cart.fee(choice['price_cents'], market['payment_bps']) * CENT if accepted else 0
    if accepted:
        journal.cost(f'reach-fee-{ordinal}', fee, day)
    settlement_day = day + (1 if row['source'] == 'warm' else 0)
    for ident in identities:
        for action in (('prepare', 'release') if accepted else ('refund',)):
            journal.execute('event', {'id': ident, 'action': action, 'event_id': ident + '-' + action}, settlement_day)
    _equal(row['status'], 'SETTLED' if accepted else 'REFUNDED', 'REACH_FALSE_DELIVERY_OR_REFUND')
    return production, fee, choice['price_cents'] * CENT if accepted else 0


def _private_profile(seed, buyer, day, market, program, scenario, remaining, repeat):
    """Build the registered buyer draw without the operator's sampling code."""
    def draw(purpose, at_day):
        key = canonical([seed, purpose, buyer, at_day])
        return int.from_bytes(hashlib.sha256(key).digest()[:8], 'big')
    eligible = draw('qualify', day) % 10000 < (5000 if repeat else 7500)
    if not eligible:
        return None, False, None
    threshold = draw('type', 0) % sum(t['weight'] for t in market['types'])
    for typ in market['types']:
        threshold -= typ['weight']
        if threshold < 0:
            break
    initial = 2 * typ['budget_cents']
    available = initial if remaining is None else remaining
    values = list(typ['values'])
    if scenario == 'weak':
        values = [v // 2 for v in values]
    elif scenario == 'no_demand':
        values = [0] * len(values)
    private = {'values': values, 'budget_cents': min(typ['budget_cents'], available), 'outside_utility': typ['outside_utility']}
    if scenario == 'copycat':
        private['outside_utility'] += cart.oracle_choose(market, program, private)['utility_cents']
    return initial, eligible, private


def _verify_runtime(out, source, manifest):
    from connected_enterprise.finance import SOURCE_PATHS
    from . import reach_policy as policy
    runtime = out / 'runtime'
    _equal(manifest, _read(runtime, 'services/MANIFEST.json'), 'REACH_MANIFEST_CHANGED')
    for name in set(SOURCE_PATHS) | set(substrate.SOURCE_PATHS):
        path = _safe_path(runtime, name)
        _require(hashlib.sha256(path.read_bytes()).hexdigest() == source.get(name),
                 'REACH_RUNTIME_BYTES_CHANGED')
    expected = manifest['cohort_provenance'].get('finite_admission', {})
    _require('native_engine' not in manifest and expected.get('packet_jobs') == 0
             and expected.get('primitive_jobs_per_service') == policy.JOBS_PER_SERVICE,
             'REACH_ADMITTED_INVENTORY_CHANGED')
    substrate.audit_admission(runtime, manifest, cohort_seed=policy.JOB_SEED)
    return runtime


def _initial_journal(export, source_hash, terms, study):
    from . import cart_campaign
    tariff = terms['tariff']
    cursor = JournalCursor(export)
    work = {'source_sha256': source_hash, 'tariff': tariff}
    cursor.spend('reach-setup', 'setup', tariff['setup_cents'] * CENT, 0, work, 1, True)
    cursor.spend('reach-discovery', 'discovery',
                 len(cart_campaign.CASES) * tariff['discovery_per_market_cents'] * CENT, 0, work, 1, True)
    cursor.cost('reach-freeze-' + digest(cart_campaign.logical(study))[:24], 0, 1)
    return cursor


def _audit_balances(export, cursor, terms, rows):
    tariff = terms['tariff']
    cursor.cost('reach-maintenance', tariff['maintenance_cents'] * CENT, 364)
    revenue = sum(r['collections_microUSD'] for r in rows)
    tax = max(0, revenue - cursor.expense) * tariff['tax_bps'] // 10000
    cursor.cost('reach-modeled-tax', tax, 364)
    cursor.finish()
    summary = export['ledger']['summary']
    expected = {'revenue': revenue, 'collections': revenue,
                'expenses': cursor.expense, 'profit': revenue - cursor.expense}
    for field, amount in expected.items():
        _equal(summary[field], amount, 'REACH_COMPLETE_COST_IDENTITY_CHANGED')
    _equal(cursor.summary, summary, 'STALE_REACH_TERMINAL_EXPORT')
    return tax


def _audit_row(row, route, day, ordinal, terms, market, program, slot, state, runtime, inventory, journal, warm_type=None, entered=True):
    """Reproduce the private decision only after paying for its eligible contact."""
    from . import reach_policy as policy
    buyer = route['buyer']
    expected = {**route, 'day': day, 'ordinal': ordinal, 'market_sha256': digest(market),
                'program_sha256': digest(program)}
    empty = {'private': None, 'choice': None, 'components': [], 'remaining_before_cents': None,
             'remaining_after_cents': None, 'quote_id': None, 'quote_microUSD': 0,
             'production_microUSD': 0, 'fee_microUSD': 0, 'collections_microUSD': 0}
    _require(set(row) == set(expected) | set(empty) | {'status'}, 'UNREGISTERED_REACH_ROW_FIELD')
    if not entered:
        _equal(row, {**expected, **empty, 'status': 'NONENTRY'}, 'UNAUTHORIZED_NONENTRY_QUOTE')
        return
    for key, value in {**expected, 'quote_id': f'reach-quote-{ordinal}'}.items():
        _equal(row[key], value, 'REACH_CONTACT_OR_PROGRAM_CHANGED')
    quote = terms['tariff']['quote_cents'] * CENT
    work = {k: row[k] for k in ('market_sha256', 'program_sha256', 'day', 'ordinal', 'buyer', 'source', 'exposure_id')}
    work['source_sha256'] = terms['source_sha256']
    journal.spend(row['quote_id'], 'acquisition', quote, day, work, 1, True)
    if warm_type is None:
        initial, eligible, private = _private_profile(policy.COHORT_SEED, buyer, day, market, program,
                                                       terms['scenario'], state['remaining'].get(buyer),
                                                       buyer in state['collected_buyers'])
    else:
        initial = warm_type['budget_cents']
        eligible = True
        private = {key: warm_type[key] for key in ('values', 'budget_cents', 'outside_utility')}
    if not eligible:
        _equal(row, {**expected, **empty, 'status': 'UNQUALIFIED',
                     'quote_id': f'reach-quote-{ordinal}', 'quote_microUSD': quote},
               'UNQUALIFIED_CONTACT_BECAME_ORDER')
        return
    before = state['remaining'].get(buyer, initial)
    _equal(row['remaining_before_cents'], before, 'BUYER_LIFETIME_WALLET_CHANGED')
    _equal(row['private'], private, 'REACH_PRIVATE_OBSERVATION_CHANGED')
    choice = cart.oracle_choose(market, program, private)
    _equal(row['choice'], choice, 'REACH_BUYER_ORACLE_DISAGREES')
    status = 'DECLINED'
    production = fee = collected = 0
    if choice['declined']:
        _equal(row['components'], [], 'UNORDERED_COMPONENT')
    else:
        services = choice['services']
        jobs = [inventory[s][slot] for s in services]
        outcome = next(o for o in market['outcomes'] if o['id'] == choice['outcome_id'])
        prices = _component_prices(choice['price_cents'], services, market)
        wanted = [{'service': s, 'job_id': j['id'], 'order_id': f'reach-order-{ordinal}-{i}',
                   'price_cents': price, 'artifact': None, 'verification': None, 'admitted_outcome_equal': None}
                  for i, (s, j, price) in enumerate(zip(services, jobs, prices))]
        raws = [_read(runtime, job['input']) for job in jobs]
        cost = (choice['price_cents'] + outcome['cost_cents'] + cart.fee(choice['price_cents'], market['payment_bps'])) * CENT
        day_full = state['daily_units'].get(day, 0) + len(services) > policy.DAILY_UNITS
        service_full = any(state['annual_units'].get(s, 0) >= policy.ANNUAL_UNITS for s in services)
        if day_full or service_full:
            status = 'CAPACITY'
        elif any(s == 'reconciliation' and not all(raw['units'].get(t) for t in ('invoices', 'payments')) for s, raw in zip(services, raws)):
            status = 'UNSUPPORTED'
        elif journal.summary['available'] < cost:
            status = 'ILLIQUID'
        else:
            production, fee, collected = _audit_checkout(row, terms['source_sha256'], journal, market, program,
                                                         jobs, runtime, initial, state['wallets'])
            status = row['status']
            state['daily_units'][day] = state['daily_units'].get(day, 0) + len(services)
            for s in services:
                state['annual_units'][s] = state['annual_units'].get(s, 0) + 1
            for job in jobs:
                _require(job['id'] not in state['used_jobs'], 'REPEATED_REACH_JOB')
                state['used_jobs'].add(job['id'])
        if status in ('CAPACITY', 'UNSUPPORTED', 'ILLIQUID'):
            _equal(row['components'], wanted, 'UNFUNDED_COMPONENT_OR_OUTPUT')
    after = before - collected // CENT
    _require(after >= 0, 'BUYER_EXCEEDS_LIFETIME_BUDGET')
    if collected:
        state['collected_buyers'].add(buyer)
    state['remaining'][buyer] = after
    _equal([row['status'], row['quote_microUSD'], row['production_microUSD'], row['fee_microUSD'],
            row['collections_microUSD'], row['remaining_after_cents']],
           [status, quote, production, fee, collected, after], 'REACH_ORDER_FINANCES_CHANGED')


def _owned_route(buyer, kind, exposure):
    return {'buyer': buyer, 'source': kind, 'source_plan_id': None,
            'exposure_id': exposure, 'paid_exclusive': False}


def _daily_routes(day, book):
    """Generate organic first, deduplicate a same-day overlapping paid exposure."""
    organic = {92 + 7 * n: f'reach-{n:03d}' for n in range(12)}
    owner = organic.get(day)
    if owner is not None:
        yield _owned_route(owner, 'organic', 'organic-' + str(day) + '-' + owner)
    for exposure in book['exposures_by_day'][str(day)]['exposures']:
        buyer = exposure['customer_id']
        if buyer != owner:
            yield {'buyer': buyer, 'source': 'paid', 'source_plan_id': exposure['source_plan_id'],
                   'exposure_id': exposure['exposure_id'], 'paid_exclusive': int(buyer[-3:]) >= 12}


def _attribution(rows, first):
    paid = [r for r in rows if first and r['source'] == 'paid' and r['source_plan_id'] == first['plan_id']]
    # Roster membership is permanent. A contact's paid label alone is insufficient.
    exclusive = [r for r in paid if int(r['buyer'][-3:]) >= 12 and r['status'] == 'SETTLED']
    warm = [r for r in rows if r['source'] == 'warm']
    return {
        'warm_settled': sum(r['status'] == 'SETTLED' for r in warm),
        'warm_contribution_microUSD': sum(r['collections_microUSD'] - r['production_microUSD'] -
                                         r['fee_microUSD'] for r in warm),
        'first_invoice_microUSD': first['amount'] if first else 0,
        'first_exclusive_settled': len(exclusive),
        'first_exclusive_collections_microUSD': sum(r['collections_microUSD'] for r in exclusive),
        'first_paid_variable_costs_microUSD': sum(r['quote_microUSD'] + r['production_microUSD'] +
                                                 r['fee_microUSD'] for r in paid),
    }


def _audit_decision(record, day, terms, rows, first, cursor, book, grants):
    from . import reach_policy as policy
    _require(all(r['day'] < day for r in rows), 'FUTURE_REACH_OBSERVATION')
    prefix = cursor.prefix()
    _equal(record['prefix'], prefix, 'REACH_PREPURCHASE_BALANCE_CHANGED')
    inputs = _attribution(rows, first)
    available, earned = prefix['available_microUSD'], prefix['earned_microUSD']
    receipt = policy.decide(terms['arm'], day, available, earned, **inputs)
    supplier = terms['supplier_contracts']['pilot']
    invoice = supplier['price_microUSD'] + supplier['support_microUSD']
    n = inputs['warm_settled']
    prior = inputs['first_exclusive_collections_microUSD'] - inputs['first_paid_variable_costs_microUSD'] - inputs['first_invoice_microUSD']
    projection = (2 * inputs['warm_contribution_microUSD'] // n if n else 0) - invoice - 42 * 10 * CENT
    expected = projection if day == 90 else prior
    # Independent of the producer's decision, a one-tranche treatment may
    # buy the exact incumbent first plan but never the second. Other arms' gates
    # and all financial/acceptance requirements remain unchanged.
    should_buy = (terms['arm'] in ('pilot', 'trial_once') and
                  (terms['arm'] == 'pilot' or day == 90) and
                  n > 0 and expected > 0 and earned >= invoice
                  and available >= invoice + 1200 * CENT
                  and (day == 90 or (inputs['first_invoice_microUSD'] == invoice
                                     and inputs['first_exclusive_settled'] > 0)))
    _equal([receipt['action'], receipt['expected_net_microUSD'], receipt['attributed_pretax_microUSD']],
           ['BUY' if should_buy else 'SKIP', expected, prior], 'REACH_POLICY_ECONOMICS_CHANGED')
    funding = purchase = None
    if should_buy:
        ident = 'reach-pilot-1' if day == 90 else 'reach-pilot-2'
        work = {'source_sha256': terms['source_sha256'], 'decision_sha256': digest(receipt), 'contract_id': 'pilot'}
        funding = cursor.spend(ident, 'paid_reach', invoice, day, work, expected, False)
        plan_id = funding['plan_id']
        _require(plan_id not in grants and funding['amount'] == invoice, 'REACH_INVOICE_REUSED')
        purchase = ChannelBook(policy.CHANNEL_SEED, terms['supplier_contracts']).purchase('pilot', day, plan_id)
        _equal(book['purchase_receipts'][plan_id], purchase, 'REACH_RIGHT_WITHOUT_DATED_INVOICE')
        grants.add(plan_id)
    _equal(record, {'day': day, 'policy': receipt, 'prefix': prefix, 'funding': funding, 'purchase': purchase},
           'REACH_DECISION_OR_GRANT_CHANGED')
    return funding


def verify_reach(output: Path):
    """Reconstruct the registered year from public artifacts and the native tape."""
    from . import cart_campaign, cart_decision, reach_native as native, reach_policy as policy

    out = Path(output)
    source = _read(out, 'SOURCE.json')
    _equal(source, native.source_identity(), 'REACH_SOURCE_CHANGED')
    terms = _read(out, 'CONTRACT.json')
    _equal(terms, native.contract(terms['arm'], terms['scenario'], source), 'REACH_CONTRACT_CHANGED')
    _equal([terms['opening_microUSD'], terms['working_microUSD'], terms['clock']],
           [100_000_000_000, 0, {'start_day': 0, 'end_day_exclusive': 365}], 'REACH_TRIAL_CAPITAL_OR_WINDOW_CHANGED')
    manifest = _read(out, 'MANIFEST.json')
    runtime = _verify_runtime(out, source, manifest)
    study = _read(out, 'STUDY.json')
    cart_decision.verify(study['study'], study['selection'])
    cases = study['study']['cases']
    programs = [cart_decision.selected_program(study['study'], study['selection'], i) for i in range(len(cases))]
    rows, plan, book, export = [_read(out, f'{name}.json') for name in ['ORDERS', 'PLAN', 'CHANNEL', 'NATIVE_EXPORT']]
    cfg = export['ledger']['config']
    _equal([cfg['contract'], cfg['opening'], cfg['working']],
           [native.native_contract(terms), 100_000_000_000, 0], 'WRONG_REACH_NATIVE_ACCOUNT')
    audit_journal(export, root=runtime, manifest=manifest)
    journal = _initial_journal(export, digest(source), terms, study)
    inventory = {}
    for job in manifest['jobs']:
        inventory.setdefault(job['service_id'], []).append(job)
    _require(set(plan) == {'decisions'} and len(plan['decisions']) == 2, 'TWO_REACH_DECISIONS_REQUIRED')
    claims = [d['funding']['plan_id'] for d in plan['decisions'] if d['funding']]
    checked_channel = verify_channel(book, terms['supplier_contracts'], policy.CHANNEL_SEED,
                                     [{'id': f'reach-{n:03d}'} for n in range(24)], range(365), claims)
    state = {'wallets': set(), 'remaining': {}, 'daily_units': {}, 'annual_units': {},
             'collected_buyers': set(), 'used_jobs': set()}
    grants = set()
    paid_routes = {}
    cursor = 0
    first = None
    for day in range(365):
        if day in (90, 118):
            d = plan['decisions'][0 if day == 90 else 1]
            result = _audit_decision(d, day, terms, rows[:cursor], first, journal, book, grants)
            if day == 90:
                first = result
        routes = list(_daily_routes(day, book))
        if 5 <= day <= 83 and (day - 2) % 3 == 0:
            warm = f'warm-{(day - 2) // 3:03d}'
            routes.insert(0, _owned_route(warm, 'warm', warm))
        for route in routes:
            _require(cursor < len(rows), 'MISSING_REACH_CONTACT')
            buyer = route['buyer']
            index = int(buyer[-3:])
            warm_type = None
            if route['source'] == 'warm':
                case_index, type_index = divmod(index - 1, 9)
                warm_type = cases[case_index]['market']['types'][type_index]
                slot = 7 + index
            else:
                case_index = 0
                slot = 36 + 4 * index
                if route['source'] == 'paid':
                    _require(route['source_plan_id'] in grants, 'REACH_BEFORE_INVOICE')
                    paid_routes[buyer] = paid_routes.get(buyer, 0) + 1
                    slot += paid_routes[buyer]
            entered = study['selection']['decisions'][case_index]['action'] != 'NONENTRY'
            _audit_row(rows[cursor], route, day, cursor + 1, terms, cases[case_index]['market'],
                       programs[case_index], slot, state, runtime, inventory, journal, warm_type, entered)
            cursor += 1
    _require(cursor == len(rows) and grants == set(claims), 'UNEXPOSED_REACH_CONTACT_OR_UNPAID_RIGHT')
    tax = _audit_balances(export, journal, terms, rows)
    invoice = sum(book['purchase_receipts'][g]['invoice_microUSD'] for g in grants)
    report = {**terms, 'study_sha256': digest(cart_campaign.logical(study)), 'plan_sha256': digest(plan),
              'orders_sha256': digest(rows), 'channel_sha256': digest(book), 'manifest_sha256': digest(manifest),
              'native_export_sha256': digest(export), 'native_summary': export['ledger']['summary'],
              'settled': sum(r['status'] == 'SETTLED' for r in rows), 'contacts': len(rows),
              'invoice_microUSD': invoice, 'tax_microUSD': tax, 'actual_revenue_usd': 0}
    _equal(_read(out, 'REPORT.json'), report, 'REACH_REPORT_STALE_OR_UNSUPPORTED')
    return {'accepted': True, 'report_sha256': digest(report), 'native_export_sha256': digest(export),
            'channel_exposure_days': checked_channel['exposure_days_checked'], 'contacts': cursor,
            'accepted_orders': report['settled'], 'financial_actions': journal.native_sequence,
            'native_grants': len(grants), 'service_attempts': state['annual_units']}
