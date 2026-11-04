"""Run a separately registered, simulated paid-reach account. All money uses JournalAccount."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from adaptive_enterprise import instruments
from adaptive_enterprise.checkers import audit_delivery
from commercial.ledger import digest
from connected_enterprise.channels import ChannelBook
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS
from . import cart_campaign as campaign, cart_decision, cart_native, cart_program
from . import reach_policy as policy
from .cart_native import CENT, OPENING, checked_path, fractions_of_price, read, save

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = 'campaign/omega-paid-reach-20261104/PROTOCOL.md'
TARIFF = {key: value for key, value in cart_native.TARIFF.items() if key != 'successor_cents'}
LAST_DAY = 364
SCHEMA = 'omega/earned-paid-reach/v1'


def source_identity():
    names = {PROTOCOL, 'connected_enterprise/channels.py'}
    for suffix in ('native', 'policy', 'verify'):
        names.update((f'mechanism_harness/reach_{suffix}.py', f'tests/test_omega_reach_{suffix}.py'))
    files = cart_native.source_identity()
    for name in sorted(names):
        path = ROOT / name
        if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('REGULAR_SOURCE_REQUIRED:' + name)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def contract(arm, scenario, source):
    if arm not in policy.ARMS or scenario not in policy.SCENARIOS:
        raise ValueError('REGISTERED_ARM_AND_SCENARIO_REQUIRED')
    return {'schema': SCHEMA, 'arm': arm, 'scenario': scenario, 'source_sha256': digest(source),
            'opening_microUSD': OPENING, 'working_microUSD': 0, 'tariff': TARIFF,
            'supplier_contracts': policy.contracts(scenario), 'clock': {'start_day': 0, 'end_day_exclusive': 365}}


def native_contract(terms):
    return 'omega-earned-paid-reach-v1-' + digest(terms)


def _prepare(out):
    runtime = out / 'runtime'
    if not runtime.exists():
        with tempfile.TemporaryDirectory(dir=out, prefix='preparing-') as stage:
            staged = Path(stage) / 'runtime'
            for name in sorted(set(SOURCE_PATHS) | set(instruments.SOURCE_PATHS)):
                target = staged / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            instruments.prepare_services(staged, 'services', cohort_seed=policy.JOB_SEED,
                                         jobs_per_service=policy.JOBS_PER_SERVICE)
            staged.rename(runtime)
    manifest = read(runtime / 'services/MANIFEST.json')
    if (out / 'MANIFEST.json').exists() and read(out / 'MANIFEST.json') != manifest:
        raise ValueError('EXISTING_SERVICE_MANIFEST_CHANGED')
    if not (out / 'MANIFEST.json').exists():
        save(out / 'MANIFEST.json', manifest)
    return runtime, manifest


def _study(out):
    path = out / 'STUDY.json'
    if path.exists():
        result = read(path)
        cart_decision.verify(result['study'], result['selection'])
        return result
    study = campaign.execute()
    study['source'] = campaign.source_identity()
    result = {'study': study, 'selection': cart_decision.select(study)}
    save(path, result)
    return result


def _spend(account, ident, kind, amount, day, work, expected=1, *, allow_seed=True):
    receipt = account.spend(ident, kind, amount, day, work, expected, allow_seed=allow_seed)
    if receipt is None:
        raise ValueError('NATIVE_SPEND_UNFUNDED:' + ident)
    return receipt


def _event(account, order_id, action, day):
    account.execute('event', {'id': order_id, 'action': action, 'event_id': order_id + '-' + action}, day)


def _prefix(account, day):
    # In recovery later actions may already exist. Read the actual native sequence
    # before this decision day, never current terminal cash or future collections.
    tape = account.export()['ledger']['actions']
    count = next((i for i, action in enumerate(tape) if action['day'] >= day), len(tape))
    if not count:
        raise ValueError('MISSING_NATIVE_PREPERIOD')
    summary = tape[count - 1]['after']
    return {'sequence': count, 'actions_sha256': digest(tape[:count]),
            'available_microUSD': summary['available'], 'earned_microUSD': summary['unrestrictedEarned']}


def _decision(account, book, terms, day, decisions, rows):
    prefix = _prefix(account, day)
    first = decisions[0]['funding'] if decisions else None
    paid = [r for r in rows if first and r['source_plan_id'] == first['plan_id'] and r['source'] == 'paid']
    exclusive = [r for r in paid if r['paid_exclusive'] and r['status'] == 'SETTLED']
    warm = [r for r in rows if r['source'] == 'warm']
    observed = policy.decide(
        terms['arm'], day, prefix['available_microUSD'], prefix['earned_microUSD'],
        sum(r['status'] == 'SETTLED' for r in warm),
        first['amount'] if first else 0, len(exclusive), sum(r['collections_microUSD'] for r in exclusive),
        sum(r['quote_microUSD'] + r['production_microUSD'] + r['fee_microUSD'] for r in paid),
        sum(r['collections_microUSD'] - r['production_microUSD'] - r['fee_microUSD'] for r in warm))
    funding = purchase = None
    if observed['action'] == 'BUY':
        supplier = terms['supplier_contracts']['pilot']
        invoice = supplier['price_microUSD'] + supplier['support_microUSD']
        work = {'source_sha256': terms['source_sha256'], 'decision_sha256': digest(observed), 'contract_id': 'pilot'}
        ident = policy.tranche_id(day)
        funding = _spend(account, ident, 'paid_reach', invoice, day, work,
                         observed['expected_net_microUSD'], allow_seed=False)
        if funding['funding'] != 'EARNED' or not funding['plan_id']:
            raise ValueError('EARNED_NATIVE_CHANNEL_INVOICE_REQUIRED')
        purchase = book.purchase('pilot', day, funding['plan_id'])
        if purchase['invoice_microUSD'] != funding['amount']:
            raise ValueError('SUPPLIER_NATIVE_INVOICE_CHANGED')
    return {'day': day, 'prefix': prefix, 'policy': observed, 'funding': funding, 'purchase': purchase}


def _components(runtime, inventory, market, outcome, price, slot, ordinal):
    rows = []
    for j, (service, part) in enumerate(zip(outcome['services'], fractions_of_price(price, outcome['services'], market))):
        job = inventory[service][slot]
        raw = instruments._read(runtime, job['input'], job['input_sha256'])
        rows.append((job, raw, {'service': service, 'job_id': job['id'], 'order_id': f'reach-order-{ordinal}-{j}',
                                'price_cents': part, 'artifact': None, 'verification': None, 'admitted_outcome_equal': None}))
    return rows


def _checkout(account, runtime, terms, market, program, candidate, row, prior, initial, liquid):
    day = row['day']
    buyer = row['buyer']
    ordinal = row['ordinal']
    choice = row['choice']
    outcome = next(o for o in market['outcomes'] if o['id'] == choice['outcome_id'])
    components = [component for _, _, component in candidate]
    row['components'] = components
    services = outcome['services']
    attempted = [r for r in prior if r['status'] in ('SETTLED', 'REFUNDED')]
    day_units = sum(len(r['components']) for r in attempted if r['day'] == day)
    if (day_units + len(services) > policy.DAILY_UNITS or
            any(sum(c['service'] == s for r in attempted for c in r['components']) >= policy.ANNUAL_UNITS
                for s in services)):
        return 'CAPACITY'
    if any(j['service_id'] == 'reconciliation' and not all(raw['units'].get(t) for t in ('invoices', 'payments'))
           for j, raw, _ in candidate):
        return 'UNSUPPORTED'
    price = choice['price_cents']
    fee = cart_program.fee(price, market['payment_bps'])
    if liquid < (price + fee + outcome['cost_cents']) * CENT:
        return 'ILLIQUID'
    if not any(r['buyer'] == buyer for r in attempted):
        account.execute('wallet', {'buyer': buyer, 'amount': initial * CENT}, day)
    for c in components:
        ident = c['order_id']
        account.execute('offer', {'id': ident, 'buyer': buyer, 'price': c['price_cents'] * CENT,
                                  'job_id': c['job_id'], 'deadline': day + 5}, day)
        _event(account, ident, 'consent', day)
        _event(account, ident, 'fund', day)
    work = {'source_sha256': terms['source_sha256'], 'program_sha256': digest(program),
            'order_ids': [c['order_id'] for c in components], 'job_ids': [c['job_id'] for c in components]}
    row['production_microUSD'] = outcome['cost_cents'] * CENT
    _spend(account, f'reach-production-{ordinal}', 'production_contract', row['production_microUSD'], day,
           work, max(1, choice['seller_contribution_cents'] * CENT))
    for job, raw, c in candidate:
        artifact = instruments.produce(raw, 'generated_schema', mode='conventional')
        reference = instruments._read(runtime, job['artifact'], job['artifact_sha256'])
        c.update(artifact=artifact, verification=audit_delivery(c['service'], raw, artifact),
                 admitted_outcome_equal=instruments._semantics(reference) == instruments._semantics(artifact))
    settlement_day = day + (row['source'] == 'warm')
    if not all(c['verification']['accepted'] and c['artifact']['outcome_scope'] == 'complete_outcome'
               and c['admitted_outcome_equal'] for c in components):
        for c in components:
            _event(account, c['order_id'], 'refund', settlement_day)
        return 'REFUNDED'
    row['fee_microUSD'] = fee * CENT
    account.cost(f'reach-fee-{ordinal}', row['fee_microUSD'], day)
    for c in components:
        _event(account, c['order_id'], 'prepare', settlement_day)
        _event(account, c['order_id'], 'release', settlement_day)
    row['remaining_after_cents'] -= price
    row['collections_microUSD'] = price * CENT
    return 'SETTLED'


def _contact(account, runtime, inventory, terms, study, menus, route, day, prior):
    buyer = route['customer_id']
    ordinal = len(prior) + 1
    warm = route['source'] == 'warm'
    if warm:
        warm_index = int(buyer.removeprefix('warm-')) - 1
        case_index, type_index = divmod(warm_index, 9)
    else:
        case_index = 0
    market = study['study']['cases'][case_index]['market']
    program = menus[case_index]
    row = {key: route[key] for key in ('source', 'source_plan_id', 'paid_exclusive', 'exposure_id')}
    row.update(day=day, ordinal=ordinal, buyer=buyer, market_sha256=digest(market), program_sha256=digest(program),
               remaining_before_cents=None, remaining_after_cents=None, private=None, choice=None, components=[],
               status='NONENTRY', quote_id=None, quote_microUSD=0, production_microUSD=0,
               fee_microUSD=0, collections_microUSD=0)
    if study['selection']['decisions'][case_index]['action'] == 'NONENTRY':
        return row
    work = {'source_sha256': terms['source_sha256'], 'market_sha256': digest(market), 'program_sha256': digest(program),
            'day': day, 'ordinal': ordinal, 'buyer': buyer, 'source': route['source'], 'exposure_id': route['exposure_id']}
    amount = TARIFF['quote_cents'] * CENT
    row.update(quote_id=f'reach-quote-{ordinal}', quote_microUSD=amount)
    quote = _spend(account, row['quote_id'], 'acquisition', amount, day, work)
    previous = [r for r in prior if r['buyer'] == buyer and r['status'] == 'SETTLED']
    if not warm and not policy.qualification(buyer, day, len(previous)):
        row['status'] = 'UNQUALIFIED'
        return row
    spent = sum(r['collections_microUSD'] // CENT for r in previous)
    if warm:
        typ = market['types'][type_index]
        initial = typ['budget_cents']
        slot = 8 + warm_index
        private = cart_native.private_type(typ, market, program, 'central')
    else:
        initial = policy.lifetime_budget(market, buyer)
        index = int(buyer.removeprefix('reach-'))
        prior_paid = sum(r['buyer'] == buyer and r['source'] == 'paid' for r in prior)
        slot = 36 + 4 * index + (prior_paid + 1 if route['source'] == 'paid' else 0)
        private = policy.profile(market, program, buyer, day, terms['scenario'], spent)
    remaining = initial - spent
    row.update(remaining_before_cents=remaining, remaining_after_cents=remaining)
    if private['budget_cents'] != (remaining if warm else min(initial // 2, remaining)):
        raise ValueError('LIFETIME_CUSTOMER_BUDGET_CHANGED')
    row['private'] = private
    choice = cart_program.buyer_choose(market, program, private)
    row['choice'] = choice
    if choice['declined']:
        row['status'] = 'DECLINED'
        return row
    outcome = next(o for o in market['outcomes'] if o['id'] == choice['outcome_id'])
    jobs = _components(runtime, inventory, market, outcome, choice['price_cents'], slot, ordinal)
    liquid = account.export()['ledger']['actions'][quote['native_event_sequence']]['after']['available']
    row['status'] = _checkout(account, runtime, terms, market, program, jobs, row, prior, initial, liquid)
    return row


def _operate(out, account, runtime, manifest, terms):
    work = {'source_sha256': terms['source_sha256'], 'tariff': TARIFF}
    setup = TARIFF['setup_cents'] * CENT
    research = len(campaign.CASES) * TARIFF['discovery_per_market_cents'] * CENT
    _spend(account, 'reach-setup', 'setup', setup, 0, work)
    _spend(account, 'reach-discovery', 'discovery', research, 0, work)
    study = _study(out)
    menus = [cart_decision.selected_program(study['study'], study['selection'], index)
             for index in range(len(study['study']['cases']))]
    study_hash = digest(campaign.logical(study))
    account.cost('reach-freeze-' + study_hash[:24], 0, 1)
    inventory = {}
    for job in manifest['jobs']:
        inventory.setdefault(job['service_id'], []).append(job)
    book = ChannelBook(policy.CHANNEL_SEED, terms['supplier_contracts'])
    buyers = policy.population()
    rows = []
    decisions = []
    for day in range(LAST_DAY + 1):
        if day in policy.DECISION_DAYS:
            decisions.append(_decision(account, book, terms, day, decisions, rows))
        paid = book.expose(day, buyers)
        routes = []
        for warm_ordinal in policy.warm(day):
            buyer = f'warm-{warm_ordinal:03d}'
            routes.append({'customer_id': buyer, 'source': 'warm', 'source_plan_id': None,
                           'exposure_id': buyer, 'paid_exclusive': False})
        routes.extend(policy.route(day, policy.organic(day), paid))
        for route in routes:
            rows.append(_contact(account, runtime, inventory, terms, study, menus, route, day, rows))
    maintenance = TARIFF['maintenance_cents'] * CENT
    account.cost('reach-maintenance', maintenance, LAST_DAY)
    invoice = sum(d['funding']['amount'] for d in decisions if d['funding'])
    variable = sum(r['quote_microUSD'] + r['production_microUSD'] + r['fee_microUSD'] for r in rows)
    collections = sum(r['collections_microUSD'] for r in rows)
    pretax = collections - setup - research - maintenance - invoice - variable
    tax = max(0, pretax) * TARIFF['tax_bps'] // 10000
    account.cost('reach-modeled-tax', tax, LAST_DAY)
    channel = book.export()
    plan = {'decisions': decisions}
    exported = account.export()
    report = {**terms, 'study_sha256': study_hash, 'plan_sha256': digest(plan), 'orders_sha256': digest(rows),
              'channel_sha256': digest(channel), 'manifest_sha256': digest(manifest),
              'native_export_sha256': digest(exported), 'native_summary': account.snapshot()['summary'],
              'settled': sum(r['status'] == 'SETTLED' for r in rows), 'contacts': len(rows),
              'invoice_microUSD': invoice, 'tax_microUSD': tax, 'actual_revenue_usd': 0}
    if report['native_summary']['profit'] != pretax - tax or terms['source_sha256'] != digest(source_identity()):
        raise ValueError('SOURCE_OR_NATIVE_ECONOMICS_CHANGED')
    outputs = [('PLAN', plan), ('ORDERS', rows), ('CHANNEL', channel), ('NATIVE_EXPORT', exported)]
    for name, value in outputs:
        path = out / (name + '.json')
        if path.exists() and digest(read(path)) != digest(value):
            raise ValueError('PRESERVE_DIVERGENT_INTERRUPTED_EVIDENCE:' + name)
    for name, value in outputs + [('REPORT', report)]:
        path = out / (name + '.json')
        if not path.exists():
            save(path, value)
    return report


def audit(output):
    from .reach_verify import verify_reach
    checked = verify_reach(checked_path(output))
    if checked.get('accepted') is not True:
        raise ValueError('REACH_AUDIT_REJECTED')
    return checked


def run(output, *, arm='organic', scenario='central', resume=False):
    out = checked_path(output)
    source = source_identity()
    terms = contract(arm, scenario, source)
    if resume:
        if read(out / 'SOURCE.json') != source or read(out / 'CONTRACT.json') != terms:
            raise ValueError('SOURCE_MATCHED_EXISTING_ACCOUNT_REQUIRED')
        history = (any((out / name).exists() for name in
                       ('STUDY.json', 'REPORT.json', 'CHANNEL.json', 'PLAN.json', 'ORDERS.json', 'NATIVE_EXPORT.json')) or
                   any(p.name != 'account.sqlite.writer.lock' for p in out.glob('account.sqlite*')))
        if history:
            cart_native.require_existing_native_authority(out)
            if not (out / 'MANIFEST.json').is_file() or not (out / 'runtime/services/MANIFEST.json').is_file():
                raise ValueError('EXISTING_NATIVE_RUNTIME_REQUIRED_FOR_RESUME')
    else:
        out.mkdir(parents=True, exist_ok=False)
        save(out / 'SOURCE.json', source)
        save(out / 'CONTRACT.json', terms)
    completed = (out / 'REPORT.json').exists()
    if completed:
        audit(out)
        runtime, manifest = out / 'runtime', read(out / 'MANIFEST.json')
    else:
        runtime, manifest = _prepare(out)
    account = JournalAccount(runtime, manifest, out / 'account.sqlite', opening=OPENING, working=0,
                             contract=native_contract(terms))
    try:
        if completed:
            if account.export() != read(out / 'NATIVE_EXPORT.json'):
                raise ValueError('COMPLETED_NATIVE_ACCOUNT_DIFFERS_FROM_RECORDED_EXPORT')
            return read(out / 'REPORT.json')
        report = _operate(out, account, runtime, manifest, terms)
        audit(out)
        return report
    finally:
        account.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'resume', 'audit'))
    parser.add_argument('output', type=Path)
    parser.add_argument('--arm', choices=policy.ARMS)
    parser.add_argument('--scenario', choices=policy.SCENARIOS)
    args = parser.parse_args(argv)
    if args.command == 'audit':
        result = audit(args.output)
    else:
        terms = read(checked_path(args.output) / 'CONTRACT.json') if args.command == 'resume' else {}
        report = run(args.output, arm=args.arm or terms.get('arm', 'organic'),
                     scenario=args.scenario or terms.get('scenario', 'central'), resume=args.command == 'resume')
        result = {k: report[k] for k in ('arm', 'scenario', 'contacts', 'settled', 'invoice_microUSD',
                                         'tax_microUSD', 'native_summary', 'actual_revenue_usd')}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
