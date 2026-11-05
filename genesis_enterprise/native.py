"""GENESIS funded execution over existing JournalAccount and flexibility063.

An engineering pilot: actual computational artifacts, synthetic demand/costs,
canonical simulated money, separate acceptance and earned-funded repetition.
No new ledger, provider call, customer contact, hardware actuation or migration.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import shutil
import time
from .policy import canonical, digest, loads, money, choose, independently_choose

SCHEMA = 'genesis-enterprise/native-pilot/v1'


def _safe(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('SYMLINK_REFUSED')
    return path


def _read(path):
    data = _safe(path).read_bytes()
    if len(data) > 32_000_000:
        raise ValueError('BOUNDED_OPERATING_RECORD_REQUIRED')
    return loads(data)


def _save(path, data):
    from commercial.persistence import atomic_bytes
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(data))


def validate_protocol(p):
    expected = {'schema', 'evidence_scope', 'opening', 'development', 'acquisition', 'maintenance',
        'income_tax_numerator', 'income_tax_denominator', 'first_delivery_may_use_seed',
        'tools', 'offer', 'boundaries', 'cost_scope', 'purpose'}
    if set(p) != expected or p['schema'] != 'genesis-enterprise/operating-protocol/v1' or p['evidence_scope'] != 'AUTHORED_SIMULATED_DEMAND_AND_COSTS':
        raise ValueError('EXACT_SIMULATION_PROTOCOL_REQUIRED')
    for k in ('opening', 'development', 'acquisition', 'maintenance', 'income_tax_numerator', 'income_tax_denominator'):
        money(p[k])
    if p['opening'] < p['development'] or p['income_tax_denominator'] <= 0 or p['income_tax_numerator'] > p['income_tax_denominator']:
        raise ValueError('FUNDED_DEVELOPMENT_AND_VALID_TAX_ASSUMPTION_REQUIRED')
    if type(p['first_delivery_may_use_seed']) is not bool:
        raise ValueError('EXPLICIT_SEED_AUTHORITY_REQUIRED')
    if p['boundaries'] != {'buyer_evidence': 'hypothetical', 'actual_host_model_billing': 'unknown',
            'physical_delivery': False, 'real_transactions': False, 'frontier_exhaustiveness': False,
            'discovery_superiority': False, 'retained_tool_advantage': False}:
        raise ValueError('UNSUPPORTED_SCOPE_ESCALATION')
    if p['offer']['reserve'] < p['offer']['fee']:
        raise ValueError('RESERVE_MUST_COVER_FEE')
    choose(p['offer'], p['tools'], available=p['opening'], earned=0, seed_allowed=p['first_delivery_may_use_seed'])
    # Refuse unusable native terms before making a workspace or account. The
    # policy's full-price collateral rule relies on this native price floor.
    from commercial.terms_exact_v2 import prospective_terms
    for price in p['offer']['prices']:
        prospective_terms('genesis-registration-validation', price, 10, 2,
                          residual=p['offer']['reserve'] - p['offer']['fee'],
                          fee=p['offer']['fee'])


def source_files(root):
    from connected_enterprise.finance import source_paths_for_manifest
    names = set(source_paths_for_manifest({'schema': 'flexibility063/native-services/v1'}))
    names.update(p.relative_to(root).as_posix() for p in (root / 'genesis_enterprise').glob('*.py'))
    names.add('connected_enterprise/genesis.py')
    return sorted(names)


def register(root, output, protocol_path):
    from flexibility063.service import prepare_manifest
    root, output = _safe(root), _safe(output)
    if output.exists():
        raise ValueError('NEW_WORKSPACE_REQUIRED_USE_RESUME_FOR_EXISTING_ACCOUNTS')
    p = _read(protocol_path)
    validate_protocol(p)
    output.mkdir(parents=True)
    frozen = output / 'source'
    files = {}
    for name in source_files(root):
        source = _safe(root / name)
        target = frozen / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    profiles = _read(frozen / 'flexibility063/profiles.json')
    requests = [{'id': r['id'], 'delivery_path': 'flexibility063/deliveries/genesis002/' + r['id'] + '.json'} for r in profiles]
    manifest = prepare_manifest(frozen, requests)
    _save(output / 'PROTOCOL.json', p)
    _save(output / 'MANIFEST.json', manifest)
    source = {'files': files, 'sha256': digest(files)}
    _save(output / 'SOURCE.json', source)
    binding = digest({'source': source, 'protocol': p, 'manifest': manifest})
    _save(output / 'REGISTRATION.json', {'schema': SCHEMA, 'binding': binding, 'fresh_account': True,
        'prior_account_migrated': False, 'mode': 'REGISTERED_NOT_FUNDED', 'contract': 'genesis002-' + binding[:20]})
    return {'workspace': str(output), 'binding': binding, 'registered_jobs': len(requests), 'accounts_created': 0}


def _bound(output):
    output = _safe(output)
    p, manifest, source, reg = (_read(output / n) for n in ('PROTOCOL.json', 'MANIFEST.json', 'SOURCE.json', 'REGISTRATION.json'))
    validate_protocol(p)
    frozen = output / 'source'
    required = source_files(Path(__file__).resolve().parents[1])
    if set(source['files']) != set(required):
        raise ValueError('COMPLETE_FROZEN_SOURCE_REQUIRED')
    actual = {name: hashlib.sha256(_safe(frozen / name).read_bytes()).hexdigest() for name in required}
    if actual != source['files'] or digest(actual) != source['sha256']:
        raise ValueError('FROZEN_SOURCE_CHANGED')
    executing = Path(__file__).resolve().parents[1]
    for name in required:
        if hashlib.sha256(_safe(executing / name).read_bytes()).hexdigest() != actual[name]:
            raise ValueError('EXECUTE_FROM_EXACT_REGISTERED_SOURCE')
    expected = digest({'source': source, 'protocol': p, 'manifest': manifest})
    if reg != {'schema': SCHEMA, 'binding': expected, 'fresh_account': True,
               'prior_account_migrated': False, 'mode': 'REGISTERED_NOT_FUNDED', 'contract': 'genesis002-' + expected[:20]}:
        raise ValueError('REGISTRATION_CHANGED')
    return p, manifest, source, reg


def _tax(account, p, ident, hour):
    tape = account.export()['ledger']
    charged = sum(a['args']['amount'] for a in tape['actions'] if a['op'] == 'cost' and a['args']['id'].startswith('genesis-tax-'))
    taxable = max(0, tape['summary']['profit'] + charged)
    due = (taxable * p['income_tax_numerator'] + p['income_tax_denominator'] - 1) // p['income_tax_denominator']
    if due > charged:
        account.cost('genesis-tax-' + ident, due - charged, hour)


def operate(output, *, max_steps=None, fault=None):
    """Resume the same native account; deterministic IDs survive interruption.

    max_steps is an explicit checkpoint request, not a mission lifetime limit.
    fault is a test-only injected callback, never part of a registration or CLI.
    """
    import fcntl
    from flexibility063.native import BusinessAccount
    from flexibility063.kernel import solve
    from flexibility063.verify import verify
    from commercial.terms_exact_v2 import prospective_terms
    output = _safe(output)
    p, manifest, source, reg = _bound(output)
    if max_steps is not None and (type(max_steps) is not int or max_steps < 1):
        raise ValueError('POSITIVE_CHECKPOINT_STEPS_REQUIRED')
    lock_path = _safe(output / '.writer.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        private = output / 'private'
        private.mkdir(mode=0o700, exist_ok=True)
        account_path = private / 'account'
        checkpoint = private / 'STATE.json'
        # Refuse loss of operating authority before opening a nonempty account.
        tape_path = account_path.with_name(account_path.name + '.actions.jsonl')
        if not checkpoint.exists() and tape_path.exists() and tape_path.stat().st_size:
            raise ValueError('OPERATING_CHECKPOINT_MISSING_PRESERVE_ACCOUNT')
        with BusinessAccount(output / 'source', manifest, account_path, opening=p['opening'],
                             working=0, contract=reg['contract']) as account:
            if checkpoint.exists():
                state = account.verify_checkpoint(_read(checkpoint))
            else:
                state = {'binding': reg['binding'], 'index': 0, 'phase': 'setup', 'rows': [], 'active': None}
                _save(checkpoint, account.seal_checkpoint(state))
            if state['binding'] != reg['binding']:
                raise ValueError('OPERATING_STATE_BINDING_CHANGED')
            steps = 0
            while state['phase'] != 'complete' and (max_steps is None or steps < max_steps):
                if (output / 'STOP').exists():
                    break
                _bound(output)
                phase, i = state['phase'], state['index']
                if phase == 'setup':
                    if p['development']:
                        account.cost('genesis-development', p['development'], 0)
                    state['phase'] = 'overhead'
                elif i == len(manifest['jobs']):
                    account.advance(24 * (i + 1))
                    state['phase'] = 'complete'
                else:
                    job = manifest['jobs'][i]
                    ident, hour = job['id'], 24 * (i + 1)
                    order = 'g002-' + ident
                    if phase == 'overhead':
                        # Apply only the existing contract's eligible, dated
                        # maturities. The native ledger keeps residual claims
                        # protected; time passing does not create revenue.
                        account.advance(hour)
                        if p['acquisition']:
                            account.cost('genesis-acquisition-' + ident, p['acquisition'], hour)
                        if p['maintenance']:
                            account.cost('genesis-maintenance-' + ident, p['maintenance'], hour)
                        state['phase'] = 'choose'
                    elif phase == 'choose':
                        # Read authoritative native summary, never manufacture an earned balance.
                        native = account.export()['ledger']['summary']
                        decision = choose(p['offer'], p['tools'], available=native['available'],
                            earned=native['unrestrictedEarned'], seed_allowed=(i == 0 and p['first_delivery_may_use_seed']))
                        reference = independently_choose(p['offer'], p['tools'], available=native['available'],
                            earned=native['unrestrictedEarned'], seed_allowed=(i == 0 and p['first_delivery_may_use_seed']))
                        if decision['selected'] != reference:
                            raise ValueError('INDEPENDENT_POLICY_DISAGREEMENT')
                        state['active'] = {'job_id': ident, 'decision': decision,
                            'decision_state': {k: native[k] for k in ('available', 'unrestrictedEarned')},
                            'accepted': False, 'resource_receipt': None, 'artifact_sha256': None,
                            'ordinary_accepted': None, 'construction_cpu_seconds': None}
                        state['phase'] = 'order' if decision['selected'] else 'finish'
                    elif phase == 'order':
                        picked = state['active']['decision']['selected']
                        terms = prospective_terms(order, picked['price'], hour + 10, hour + 2,
                            residual=p['offer']['reserve'] - p['offer']['fee'], fee=p['offer']['fee'],
                            counterparty_obligations='Synthetic purchase of independently checked computational dispatch only. No physical energy delivery or real customer money.')
                        account.begin_order(ident, order, 'buyer-' + order, picked['price'],
                                            p['offer']['budget'], hour, hour + 3, terms)
                        state['phase'] = 'fund'
                    elif phase == 'fund':
                        picked = state['active']['decision']['selected']
                        receipt = account.spend('genesis-production-' + ident, 'qualified-computational-delivery',
                            picked['resource_cost'], hour, {'binding': reg['binding'], 'request_sha256': digest(job['request']),
                                'executor': picked['tool'], 'scope': 'COMPUTATIONAL_ONLY'},
                            expected_net=picked['contribution'], allow_seed=(i == 0 and p['first_delivery_may_use_seed']))
                        state['active']['resource_receipt'] = receipt
                        state['phase'] = 'produce' if receipt is not None else 'refund'
                    elif phase == 'produce':
                        picked = state['active']['decision']['selected']
                        path = output / 'source' / job['delivery_path']
                        before = time.process_time()
                        artifact = _read(path) if path.exists() else solve(job['request'], picked['mode'])
                        receipt = account.complete_order(order, ident, artifact, hour + 1)
                        # Strong ordinary route can win and always receives the same task.
                        ordinary = solve(job['request'], 'conventional')
                        ordinary_result = verify(job['request'], ordinary)
                        _save(output / 'public' / 'controls' / (ident + '.json'), ordinary)
                        state['active'].update(accepted=receipt['accepted'], artifact_sha256=digest(artifact),
                            ordinary_accepted=ordinary_result['accepted'], construction_cpu_seconds=time.process_time() - before)
                        state['phase'] = 'release' if receipt['accepted'] else 'refund'
                    elif phase == 'release':
                        account.release(order, hour + 2)
                        state['phase'] = 'finish'
                    elif phase == 'refund':
                        account.refund(order, hour + 2)
                        state['phase'] = 'finish'
                    elif phase == 'finish':
                        _tax(account, p, ident, hour + 3)
                        state['rows'].append(state['active'])
                        state['active'] = None
                        state['index'] += 1
                        state['phase'] = 'overhead'
                    else:
                        raise ValueError('UNKNOWN_OPERATING_PHASE')
                if fault is not None:
                    fault(phase, i)
                _save(checkpoint, account.seal_checkpoint(state))
                steps += 1
            exported = account.export()
            account.audit()
            # The export is intentionally key-free; STATE.json stays private.
            _save(output / 'public' / 'native-export.json', exported)
            _save(output / 'public' / 'execution.json', state)
    return audit(output)


def _audit_fixed_costs(p, jobs, execution, actions):
    # Reconcile the reached producer phases, not just selected/completed rows:
    # choose has already paid overhead but has not created an active row yet.
    phase, index = execution['phase'], execution['index']
    active_phases = {'order', 'fund', 'produce', 'release', 'refund', 'finish'}
    if (type(index) is not int or not 0 <= index <= len(jobs)
            or index != len(execution['rows'])
            or phase not in active_phases | {'setup', 'overhead', 'choose', 'complete'}
            or (execution['active'] is not None) != (phase in active_phases)
            or (phase == 'setup' and index != 0)
            or (phase == 'complete' and index != len(jobs))
            or (phase in active_phases | {'choose'} and index == len(jobs))):
        raise ValueError('REGISTERED_EXECUTION_PHASE_CHANGED')
    expected = {}
    if phase != 'setup' and p['development']:
        expected['genesis-development'] = (0, p['development'])
    reached = index + int(phase in active_phases | {'choose'})
    for i, job in enumerate(jobs[:reached]):
        for kind in ('acquisition', 'maintenance'):
            if p[kind]:
                ident = 'genesis-' + kind + '-' + job['id']
                if ident in expected:
                    raise ValueError('REGISTERED_FIXED_COST_CHANGED')
                expected[ident] = (24 * (i + 1), p[kind])
    seen = set()
    for action in actions:
        if action['op'] != 'cost':
            continue
        ident = action['args']['id']
        if (ident != 'genesis-development'
                and not ident.startswith(('genesis-acquisition-', 'genesis-maintenance-'))):
            # Native seed-production costs and tax provisions have their own
            # journal/receipt and tax-prefix reconciliation, respectively.
            continue
        if (ident not in expected or ident in seen
                or (action['day'], action['args']['amount']) != expected[ident]):
            raise ValueError('REGISTERED_FIXED_COST_CHANGED')
        seen.add(ident)
    if seen != set(expected):
        raise ValueError('REGISTERED_FIXED_COST_CHANGED')


def _audit_tax_prefixes(p, jobs, rows, actions):
    # Native replay has verified each before/after state. Reconstruct the
    # provision at each completed job boundary, not from the final total or
    # the producer's _tax helper. A later cost cannot erase an earlier debt.
    taxes = [a for a in actions if a['op'] == 'cost'
             and a['args']['id'].startswith('genesis-tax-')]
    expected_ids = set()
    provision = 0
    for i, row in enumerate(rows):
        hour = 24 * (i + 1) + 3
        prefix = [a for a in actions if a['day'] <= hour]
        charged = sum(a['args']['amount'] for a in taxes if a['day'] <= hour)
        pretax = (prefix[-1]['after']['profit'] if prefix else 0) + charged
        due = (max(0, pretax) * p['income_tax_numerator']
               + p['income_tax_denominator'] - 1) // p['income_tax_denominator']
        increment = max(0, due - provision)
        ident = 'genesis-tax-' + jobs[i]['id']
        actual = [a for a in taxes if a['args']['id'] == ident]
        if increment:
            expected_ids.add(ident)
            if (len(actual) != 1 or actual[0]['day'] != hour
                    or actual[0]['args']['amount'] != increment):
                raise ValueError('REGISTERED_TAX_PROVISION_CHANGED')
        elif actual:
            raise ValueError('REGISTERED_TAX_PROVISION_CHANGED')
        provision += increment
    if {a['args']['id'] for a in taxes} != expected_ids:
        raise ValueError('REGISTERED_TAX_PROVISION_CHANGED')


def _audit_native_offer(p, ident, i, selected, actions, *, ordered):
    order, hour = 'g002-' + ident, 24 * (i + 1)
    offers = [a for a in actions if a['op'] == 'offer' and a['args']['id'] == order]
    terms = [a for a in actions if a['op'] == 'register_terms' and a['args']['id'] == order + '-terms']
    wallets = [a for a in actions if a['op'] == 'wallet' and a['args']['buyer'] == 'buyer-' + order]
    if not ordered or selected is None:
        if offers or terms or wallets:
            raise ValueError('REGISTERED_NATIVE_OFFER_CHANGED')
        return
    expected_offer = {'id': order, 'buyer': 'buyer-' + order, 'price': selected['price'],
                      'job_id': ident, 'deadline': hour + 3, 'terms_id': order + '-terms'}
    if (len(offers) != 1 or offers[0]['day'] != hour or offers[0]['args'] != expected_offer
            or len(wallets) != 1 or wallets[0]['day'] != hour
            or wallets[0]['args'] != {'buyer': 'buyer-' + order, 'amount': p['offer']['budget']}):
        raise ValueError('REGISTERED_NATIVE_OFFER_CHANGED')
    # Deliberately spell out the registered contract independently of the
    # prospective_terms producer. Native-valid terms alone do not establish
    # that the buyer received the selected GENESIS arrangement.
    expected_terms = {
        'schema': 'agi-alpha/native-prospective-terms/v1', 'clock_unit': 'INTEGER_HOURS',
        'version': 1, 'order_id': order, 'price_microUSD': selected['price'],
        'payment_schedule': 'ON_NATIVE_ACCEPTED_RELEASE',
        'expected_collection_day': hour + 2, 'exposure_microUSD': selected['price'] + 200000,
        'maturity_day': hour + 10, 'residual_microUSD': p['offer']['reserve'] - p['offer']['fee'],
        'acceptance_rule': 'INDEPENDENT_NATIVE_PREPARE_AND_RELEASE',
        'dispute_rule': 'CLAIMS_THROUGH_MATURITY_INCLUSIVE',
        'late_claim_rule': 'RETAIN_ALL_CLAIMS_EXCESS_OVER_RESIDUAL_STOPS_INVESTMENT',
        'premium_microUSD': 0, 'fee_microUSD': p['offer']['fee'], 'coverage_limit_microUSD': 0,
        'deductible_microUSD': 0, 'coverage_exclusions': [], 'payout_delay_hours': 0,
        'default_rule': 'RETAIN_UNPAID_LIABILITY_AND_STOP_INVESTMENT',
        'counterparty_obligations': 'Synthetic purchase of independently checked computational dispatch only. No physical energy delivery or real customer money.',
        'jurisdiction': 'Authored synthetic jurisdiction; no legal finality established',
        'legal_status': 'HYPOTHETICAL_SIMULATION_NO_ENFORCEABILITY_OR_PROVIDER_GUARANTEE',
        'accounting_policy': 'INCURRED_COST_COLLECTED_RECOVERY_MATURITY_NOT_INCOME_V1'}
    if (len(terms) != 1 or terms[0]['day'] != hour
            or terms[0]['args'] != {'id': order + '-terms', 'terms': expected_terms}):
        raise ValueError('REGISTERED_NATIVE_TERMS_CHANGED')


def audit(output):
    """Independent native replay plus registered policy/cost/delivery reconciliation."""
    from connected_enterprise.finance import audit_journal
    output = _safe(output)
    p, manifest, source, reg = _bound(output)
    exported = _read(output / 'public/native-export.json')
    result = audit_journal(exported, root=output / 'source', manifest=manifest)
    if result['accepted'] is not True:
        raise ValueError('NATIVE_AUDIT_REJECTED')
    # A correctly replayed native ledger and connected journal may agree with
    # one another while both originate from an unauthorized opening balance,
    # working-capital allocation, or contract. Neither is the GENESIS
    # registration. Check the authenticated replayed account's configuration
    # against its immutable source-bound registration before policy conclusions.
    registered_native = {'opening': p['opening'], 'working': 0,
                         'contract': reg['contract']}
    actual_native = exported['ledger'].get('config')
    if (not isinstance(actual_native, dict)
            or any(type(actual_native.get(key)) is not type(value)
                   or actual_native.get(key) != value
                   for key, value in registered_native.items())):
        raise ValueError('REGISTERED_NATIVE_ACCOUNT_CONFIGURATION_CHANGED')
    execution = _read(output / 'public/execution.json')
    tape = exported['ledger']; actions = tape['actions']; summary = tape['summary']
    if execution['binding'] != reg['binding'] or execution['index'] != len(execution['rows']):
        raise ValueError('EXECUTION_BINDING_OR_COVERAGE_CHANGED')
    rows = execution['rows'] + ([execution['active']] if execution['active'] is not None else [])
    if len(rows) > len(manifest['jobs']):
        raise ValueError('INCOMPLETE_JOB_COVERAGE')
    allowed_orders = {'g002-' + job['id'] for job in manifest['jobs'][:len(rows)]}
    for a in actions:
        if a['op'] == 'register_terms' and a['args']['id'] not in {k + '-terms' for k in allowed_orders}:
            raise ValueError('UNREGISTERED_TERMS')
        if a['op'] == 'offer' and a['args']['id'] not in allowed_orders:
            raise ValueError('UNREGISTERED_ORDER')
        if a['op'] == 'wallet' and a['args']['buyer'] not in {'buyer-' + k for k in allowed_orders}:
            raise ValueError('UNREGISTERED_BUYER')
    allowed_spends = {'genesis-production-' + job['id'] for job in manifest['jobs']}
    for e in exported['connected_journal']['entries']:
        r = e['request']
        if r['operation'] == 'spend' and r['id'] not in allowed_spends:
            raise ValueError('UNREGISTERED_RESOURCE_COMMITMENT')
        if r['operation'] == 'execute' and r['op'] == 'cost':
            ident = r['args']['id']
            if ident != 'genesis-development' and ident not in {
                    'genesis-' + kind + '-' + job['id']
                    for kind in ('acquisition', 'maintenance', 'tax') for job in manifest['jobs']}:
                raise ValueError('UNREGISTERED_COST')
    releases = [a for a in actions if a['op'] == 'event' and a['args']['action'] == 'release']
    _audit_fixed_costs(p, manifest['jobs'], execution, actions)
    _audit_tax_prefixes(p, manifest['jobs'], execution['rows'], actions)
    for i, row in enumerate(rows):
        job = manifest['jobs'][i]
        ident = job['id']; order = 'g002-' + ident
        if row['job_id'] != ident:
            raise ValueError('REGISTERED_JOB_ORDER_CHANGED')
        # Reconstruct the snapshot at selection from the last overhead action.
        overhead = [a for a in actions if a['op'] == 'cost' and a['args']['id'] in
                    {'genesis-acquisition-' + ident, 'genesis-maintenance-' + ident}]
        if overhead:
            observed = overhead[-1]['after']
        else:
            prior = [a for a in actions if a['day'] < 24*(i+1)
                     or (a['day'] == 24*(i+1) and a['op'] == 'mature')]
            observed = prior[-1]['after'] if prior else {'available': p['opening'], 'unrestrictedEarned': 0}
        state = {k: observed[k] for k in ('available', 'unrestrictedEarned')}
        if row['decision_state'] != state:
            raise ValueError('DECISION_SNAPSHOT_CHANGED')
        expected = choose(p['offer'], p['tools'], available=state['available'], earned=state['unrestrictedEarned'],
                          seed_allowed=(i == 0 and p['first_delivery_may_use_seed']))
        if row['decision'] != expected:
            raise ValueError('REGISTERED_OPTIMAL_DECISION_CHANGED')
        _audit_native_offer(p, ident, i, expected['selected'], actions,
                            ordered=(i < len(execution['rows']) or execution['phase'] != 'order'))
        if i == len(execution['rows']):
            continue  # Active delivery/settlement is not yet a completed row.
        released = [a for a in releases if a['args']['id'] == order]
        if row['artifact_sha256'] is not None:
            from flexibility063.verify import verify
            artifact = _read(output / 'source' / job['delivery_path'])
            if digest(artifact) != row['artifact_sha256']:
                raise ValueError('DELIVERED_BYTES_CHANGED')
            ordinary = _read(output / 'public' / 'controls' / (ident + '.json'))
            if verify(job['request'], ordinary)['accepted'] != row['ordinary_accepted']:
                raise ValueError('ORDINARY_CONTROL_CHANGED')
        if type(row['accepted']) is not bool or row['accepted'] != bool(released):
            raise ValueError('ACCEPTANCE_COLLECTION_MISMATCH')
        if expected['selected'] is None and any(a['op'] == 'offer' and a['args']['id'] == order for a in actions):
            raise ValueError('DECLINED_OPPORTUNITY_TRADED')
        spends = [e for e in exported['connected_journal']['entries'] if e['request']['operation'] == 'spend'
                  and e['request']['id'] == 'genesis-production-' + ident and e['status'] == 'COMPLETE']
        if row['resource_receipt'] is None:
            if spends or row['accepted']:
                raise ValueError('UNFUNDED_DELIVERY_OR_MISSING_RECEIPT')
        else:
            if len(spends) != 1 or spends[0]['receipt'] != row['resource_receipt']:
                raise ValueError('RESOURCE_RECEIPT_CHANGED')
            if i > 0 and spends[0]['receipt']['funding'] != 'EARNED':
                raise ValueError('SUCCESSOR_NOT_FUNDED_FROM_EARNINGS')
            if spends[0]['request']['amount'] != expected['selected']['resource_cost']:
                raise ValueError('COMPLETE_RESOURCE_COST_CHANGED')
    complete = execution['phase'] == 'complete'
    if complete and len(execution['rows']) != len(manifest['jobs']):
        raise ValueError('INCOMPLETE_JOB_COVERAGE')
    earned = [r for r in execution['rows'] if r['accepted'] and r['resource_receipt'] and r['resource_receipt']['funding'] == 'EARNED']
    verdict = {'schema': SCHEMA, 'binding': reg['binding'], 'accepted': True, 'complete': complete,
        'native_audit_accepted': True, 'accepted_collected_deliveries': len(releases),
        'earned_funded_deliveries': len(earned),
        'simulated_profit_microUSD': summary['profit'],
        'simulated_collections_microUSD': summary['collections'],
        'native_financial_state': {k: summary[k] for k in ('cash', 'available', 'unrestrictedEarned', 'payables', 'custodyReserve', 'tailReserve', 'workingCapital', 'reservedInvestment')},
        'conditional_self_funding': complete and len(releases) > 1 and bool(earned) and summary['profit'] > 0 and summary['payables'] == 0,
        'actual_revenue': 0, 'actual_model_billing': None,
        'autonomous_discovery_superiority': 'NOT_ESTABLISHED', 'blue_sky_flagship': 'NOT_ESTABLISHED',
        'successor_causal_advantage': 'NOT_ESTABLISHED_ORDINARY_TECHNICAL_CONTROL_PRESENT',
        'scope': 'NATIVE_SIMULATION_WITH_ACTUAL_COMPUTATIONAL_ARTIFACTS_NOT_REAL_COMMERCE'}
    _save(output / 'public/AUDIT.json', verdict)
    from .report import render
    (output / 'public/index.html').write_text(render(verdict, execution), encoding='utf-8')
    return verdict


def export_public(output, destination):
    """Create a key-free, auditable copy. Never copy private recovery authority."""
    output, destination = _safe(output), _safe(destination)
    verdict = audit(output)
    if not verdict['complete']:
        raise ValueError('COMPLETE_AUDITED_RUN_REQUIRED_FOR_EXPORT')
    if destination.exists():
        raise ValueError('NEW_PUBLIC_DESTINATION_REQUIRED')
    destination.mkdir(parents=True)
    for name in ('PROTOCOL.json', 'MANIFEST.json', 'SOURCE.json', 'REGISTRATION.json'):
        shutil.copyfile(output / name, destination / name)
    # Whitelist exact registered public files. Never recursively copy a workspace:
    # arbitrary local notes, credentials or recovery files may be present in it.
    source = _read(output / 'SOURCE.json')
    manifest = _read(output / 'MANIFEST.json')
    names = ['source/' + name for name in source['files']]
    names += ['public/' + name for name in ('native-export.json', 'execution.json', 'AUDIT.json', 'index.html')]
    for job in manifest['jobs']:
        for name in ('source/' + job['delivery_path'], 'public/controls/' + job['id'] + '.json'):
            if (output / name).exists():
                names.append(name)
    for relative in names:
        file = _safe(output / relative)
        target = _safe(destination / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    check = audit(destination)
    if check != verdict:
        raise ValueError('EXPORTED_AUDIT_CHANGED')
    return {'public_path': str(destination), 'accepted': True, 'binding': verdict['binding'],
            'contains_recovery_authority': False, 'can_resume_original_account': False}
