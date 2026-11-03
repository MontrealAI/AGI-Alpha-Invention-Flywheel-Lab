from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import random
import shutil
from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.finance import audit_journal
from .native import BusinessAccount
from . import service
from .world import SCHEDULES, make_world, public_task
from .study import ROOT, FOLDER, ARMS, save, construct_program

USD = 1_000_000


def protocol():
    return strict_json((FOLDER/'ECONOMIC_PROTOCOL.json').read_bytes())


def cases(development=False):
    specs = []
    for i in range(8 if not development else 2):
        spec = make_world('economic-K1/v1/' + str(i), 'K1', i)
        spec['operating_schedule'] = SCHEDULES[i % 4]
        specs.append(spec)
    if not development:
        for stratum in range(6):
            for replicate in range(2):
                seed = f'OUTLEARN-20261102-906c4f4d/confirmation/v1/{stratum}/{replicate}'
                spec = make_world(seed, 'K2', stratum)
                spec['operating_schedule'] = SCHEDULES[(stratum*2+replicate) % 4]
                specs.append(spec)
    return specs


def public_quotes(stage, seen, cfg):
    percent = max(60, 100 - 5*(seen//6))
    return {name: value*USD*percent//100 for name, value in cfg['initial_complete_rival_quotes_usd'][stage].items()}


def choose_price(stage, quotes, floor, cfg):
    allowed = [price*USD for price in cfg['price_menus_usd'][stage] if floor < price*USD <= min(quotes.values())]
    return max(allowed, default=None)


def buyer_response(region, stage, index, price, quotes, cfg):
    env = cfg['demand'][region]
    rng = random.Random(int(hashlib.sha256(f'outlearning-market-v1/{region}/{index}'.encode()).hexdigest(), 16))
    benefit = rng.randint(*env['benefit_ranges_usd'][stage])*USD
    budget = rng.randint(*env['budget_ranges_usd'][stage])*USD
    effort = rng.randint(*env['self_service_effort_usd'])*USD
    options = {'no_purchase': 0}
    for name, cost in quotes.items():
        if cost <= budget:
            options[name] = benefit-cost-(effort if name == 'self_service' else 0)
    if price is not None and price <= budget:
        options['seller'] = benefit-price
    best = max(options.values())
    outside = {key: value for key, value in options.items() if key != 'seller'}
    winner = 'seller' if options.get('seller', -1) > max(outside.values()) else max(outside, key=lambda k: (outside[k], k))
    if best <= 0:
        winner = 'no_purchase'
    collection = rng.randrange(100) < env['collection_success_per_100']
    return {'choice': winner, 'budget_microUSD': budget, 'benefit_microUSD': benefit,
            'options_utility_microUSD': options, 'collection_success': collection,
            'delay_hours': env['delay_hours']}


def supplier_response(task, region, index, cfg):
    rng = random.Random(int(hashlib.sha256(f'outlearning-suppliers-v1/{region}/{index}'.encode()).hexdigest(), 16))
    bounds = {'positive': (30, 60), 'weak': (60, 90), 'adverse': (90, 140)}[region]
    rows = []
    for provider in task['providers']:
        quote = 48*provider['call_microUSD']
        production_cost = quote*rng.randint(*bounds)//100
        outside_surplus = quote*rng.randint(10, 30)//100
        accepted = quote-production_cost > outside_surplus
        rows.append({'provider': provider['id'], 'capacity_calls': 48, 'quote_microUSD': quote,
                     'modeled_private_cost_microUSD': production_cost, 'outside_surplus_microUSD': outside_surplus,
                     'voluntary_acceptance': accepted, 'lead_hours': 1})
    return {'contracts': rows, 'all_accept': all(row['voluntary_acceptance'] for row in rows),
            'price_microUSD': sum(row['quote_microUSD'] for row in rows),
            'scope': 'AUTHORED_VOLUNTARY_SUPPLIER_CAPACITY_CHOICES_NOT_REAL_CONTRACTS'}


def source_copy(path):
    from connected_enterprise.runner import source_paths
    path.mkdir(parents=True, exist_ok=True)
    for name in source_paths(ROOT):
        destination = path/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT/name).read_bytes()
        if destination.exists() and destination.read_bytes() != raw:
            raise ValueError('EXISTING_NATIVE_SOURCE_CHANGED:' + name)
        if not destination.exists():
            destination.write_bytes(raw)


def request_rows(specs):
    return [{'id': f'order-{i:02d}', 'case_spec': spec,
             'acceptance': 'SAFE_ACROSS_CHALLENGES_AND_ACTUAL_COMPLETE'} for i, spec in enumerate(specs)]


def operate(output, source, specs, arm, region, capital, expected_freeze, development=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cfg = protocol()
    identity = f"{arm.replace('_', '-')}-{region}-{capital}" + ('-development' if development else '')
    manifest_path, checkpoint_path = output/'MANIFEST.json', output/'CHECKPOINT.json'
    manifest = service.prepare_manifest(source, request_rows(specs), identity)
    if manifest_path.exists() and strict_json(manifest_path.read_bytes()) != manifest:
        raise ValueError('EXISTING_NATIVE_MANIFEST_CHANGED')
    save(manifest_path, manifest)
    env = cfg['demand'][region]
    multiplier = env['cost_multiplier']
    with BusinessAccount(source, manifest, output/'account.sqlite', capital*USD) as business:
        if checkpoint_path.exists():
            envelope = strict_json(checkpoint_path.read_bytes())
            business.verify(envelope)
            state = envelope['body']['state']
        else:
            state = {'schema': 'outlearning-native-queue/v1', 'identity': identity, 'freeze_sha256': expected_freeze,
                     'index': 0, 'events': [], 'complete': False, 'k1_financial_state': None, 'successor_funding': None}
            save(checkpoint_path, business.seal(state))
        if state['identity'] != identity or state['freeze_sha256'] != expected_freeze:
            raise ValueError('ORIGINAL_ACCOUNT_IDENTITY_REQUIRED')
        if state['complete']:
            record = business.export()
            audit = business.audit()
            if not audit['accepted']:
                raise ValueError('NATIVE_ACCOUNT_AUDIT_REJECTED')
            save(output/'PUBLIC_ACCOUNT.json', record)
            result = summarize(record, state, audit, capital, arm, region)
            save(output/'RESULT.json', result)
            return result
        setup = (cfg['opening_research_usd']+cfg['economic_modeling_cost_usd'])*USD*multiplier
        if not business.spend('initial-development', setup, 0,
                              {'declared_research_envelope_microUSD': setup, 'includes_K1_observation_probes_USD': 35,
                               'includes_failed_attempts': True, 'billing_provenance': 'AUTHORED_NOT_MEASURED'}):
            state.update(complete=True, stopped='INITIAL_FUNDING_UNAVAILABLE')
            save(checkpoint_path, business.seal(state))
        if arm == 'no_deploy':
            state.update(index=len(specs), no_deploy_reference=True)
            save(checkpoint_path, business.seal(state))
        for index in range(state['index'], len(specs)) if not state['complete'] else ():
            spec, hour = specs[index], 24+index*168
            job_id = f'order-{index:02d}'
            if index == 8:
                if state['k1_financial_state'] is None:
                    state['k1_financial_state'] = business.snapshot()
                    save(checkpoint_path, business.seal(state))
                amount = (cfg['K2_retained_deployment_usd'] if arm == 'treatment' else cfg['ordinary_retention_usd'])*USD*multiplier
                if amount:
                    receipt = business.spend('K2-retained-deployment', amount, hour,
                                             {'capability': 'K1-derived executable interoperation constructor',
                                              'work': 'K2-specific qualification, installation and support contract',
                                              'cost_provenance': 'AUTHORED_INCREMENTAL_ENVELOPE_NOT_INITIAL_CONSTRUCTION'}, expected_net=600*USD)
                    if receipt is None:
                        state.update(stopped='SUCCESSOR_NOT_AFFORDABLE', index=len(specs))
                        save(checkpoint_path, business.seal(state))
                        break
                    state['successor_funding'] = {'amount_microUSD': amount, 'funding': receipt['funding'],
                                                  'receipt_sha256': digest(receipt), 'before': state['k1_financial_state']}
                else:
                    state['successor_funding'] = {'amount_microUSD': 0, 'funding': 'NO_INCREMENTAL_CONSTRUCTOR_CHARGE',
                                                  'before': state['k1_financial_state']}
                save(checkpoint_path, business.seal(state))
            quotes = public_quotes(spec['stage'], index, cfg)
            fixed = sum(cfg[key] for key in ('acquisition_per_opportunity_usd', 'qualification_per_opportunity_usd', 'maintenance_per_opportunity_usd'))*USD*multiplier
            if business.spend(job_id+'-qualification', fixed, hour, {'public_quotes': quotes, 'purpose': 'costed channel access and qualification'}) is None:
                state['events'].append({'index': index, 'stage': spec['stage'], 'outcome': 'NO_AVAILABLE_FUNDS'})
                state['index'] = index+1
                save(checkpoint_path, business.seal(state))
                continue

            def charge_probe(probe_index, provider, sequence, cost):
                receipt = business.spend(f'{job_id}-probe-{probe_index}', cost, hour,
                                         {'provider': provider, 'sequence': sequence, 'unit_price_scope': 'synthetic instrument contract'})
                return receipt is not None

            constructed = construct_program(spec, arm, charge_probe, multiplier)
            program = constructed['program']
            graph_aborts = program['nodes'][program['entry']].get('finish') == 'aborted'
            task = constructed['task']
            suppliers = supplier_response(task, region, index, cfg)
            capacity = suppliers['price_microUSD']
            direct = sum(cfg[key] for key in ('onboarding_per_purchase_usd', 'production_per_purchase_usd', 'verification_per_purchase_usd', 'support_per_purchase_usd'))*USD*multiplier
            price = None if graph_aborts or not suppliers['all_accept'] else choose_price(spec['stage'], quotes, direct+capacity+24*USD, cfg)
            response = buyer_response(region, spec['stage'], index, price, quotes, cfg)
            event = {'index': index, 'stage': spec['stage'], 'public_quotes': quotes, 'price_microUSD': price,
                     'probe_cost_microUSD': constructed['probe_cost_microUSD'], 'suppliers': suppliers,
                     'program_sha256': digest(program), 'buyer_choice': response['choice'],
                     'outcome': 'NO_PURCHASE' if suppliers['all_accept'] else 'SUPPLIER_DECLINED',
                     'retained_procedure_called': arm == 'treatment'}
            if response['choice'] == 'seller' and price is not None:
                fee = (price*cfg['payment_bps']+9999)//10000 + int(round(cfg['payment_fixed_usd']*USD))
                complete_cost = direct+capacity+fee
                funding = business.spend(job_id+'-production', complete_cost, hour,
                                         {'capacity_calls_per_provider': 48, 'supplier_contracts': suppliers['contracts'],
                                          'capacity_contract': 'prepaid nonrefundable bounded production capacity',
                                          'onboarding_production_verification_support_microUSD': direct, 'fee_microUSD': fee},
                                         expected_net=max(1, price-complete_cost))
                if funding is None:
                    event['outcome'] = 'PRODUCTION_DEFERRED_NO_FUNDS'
                else:
                    times = business.begin_order(job_id, job_id, price, response['budget_microUSD'], hour,
                                                  response['delay_hours'], cfg['support_hours'])
                    receipt = business.produce(job_id, job_id, program, hour+1)
                    paid = receipt['accepted'] and response['collection_success']
                    business.settle(job_id, paid, times['collection_hour'])
                    actual = receipt['evaluation']['actual_outcome']
                    loss = actual['residual_exposure_microUSD'] if actual else 0
                    if actual and actual['harm']:
                        loss += cfg['unsafe_extra_correction_usd']*USD*multiplier
                    if loss:
                        business.account.cost(job_id+'-harm-and-correction', loss, times['collection_hour'])
                    business.advance(times['maturity_hour']+1)
                    event.update(outcome='ACCEPTED_AND_COLLECTED' if paid else 'REFUNDED',
                                 technically_accepted=receipt['accepted'], collection_success=response['collection_success'],
                                 actual_outcome=actual, safety_qualified=receipt['evaluation']['all_safe'],
                                 production_funding=funding['funding'], capacity_fee_microUSD=capacity,
                                 production_cost_microUSD=complete_cost, loss_microUSD=loss,
                                 actual_operation_units_cost_microUSD=actual['operation_cost_microUSD']*multiplier if actual else 0,
                                 artifact_sha256=receipt['artifact_sha256'], **times)
                    save(output/'deliveries'/f'{job_id}.json', service.delivery(source, manifest, job_id))
            event['financial_after'] = business.snapshot()
            state['events'].append(event)
            state['index'] = index+1
            save(output/'construction'/f'{job_id}.json', constructed)
            save(checkpoint_path, business.seal(state))
        if 'tax_microUSD' not in state:
            state['tax_microUSD'] = max(0, business.snapshot()['profit'])*cfg['tax_on_positive_pre_tax_profit_bps']//10000
            save(checkpoint_path, business.seal(state))
        end_hour = 24+len(specs)*168+240
        if state['tax_microUSD']:
            business.account.cost('tax-provision', state['tax_microUSD'], end_hour)
        business.advance(end_hour+1)
        state['complete'] = True
        save(checkpoint_path, business.seal(state))
        audit = business.audit()
        if not audit['accepted']:
            raise ValueError('NATIVE_ACCOUNT_AUDIT_REJECTED')
        record = business.export()
        save(output/'PUBLIC_ACCOUNT.json', record)
        result = summarize(record, state, audit, capital, arm, region)
        save(output/'RESULT.json', result)
        return result


def summarize(record, state, audit, capital, arm, region):
    financial = record['ledger']['summary']
    events = state['events']
    accepted = [row for row in events if row['outcome'] == 'ACCEPTED_AND_COLLECTED']
    k2 = [row for row in accepted if row['stage'] == 'K2']
    residuals = [row for row in events if (row.get('actual_outcome') or {}).get('residual_obligations')]
    commerce = (audit['accepted'] and financial['profit'] > 0 and bool(accepted) and not residuals
                and financial['payables'] == 0 and financial['available'] >= 0)
    development = protocol()['opening_research_usd']+protocol()['economic_modeling_cost_usd']
    return {'identity': state['identity'], 'arm': arm, 'region': region, 'capital_USD': capital,
            'complete': state['complete'], 'native_audit_accepted': audit['accepted'],
            'native_export_sha256': digest(record), 'native_actions_sha256': record['ledger']['actions_sha256'],
            'action_count': len(record['ledger']['actions']), 'financial_microUSD': financial,
            'offered_opportunities': len(events), 'accepted_and_collected': len(accepted),
            'K1_accepted': sum(row['stage'] == 'K1' for row in accepted), 'K2_accepted': len(k2),
            'refunded': sum(row['outcome'] == 'REFUNDED' for row in events),
            'commercial_success_conditional': commerce, 'successor_funding': state['successor_funding'],
            'retained_procedure_called_on_K2': any(row['stage'] == 'K2' and row.get('retained_procedure_called') for row in events),
            'useful_retained_transfer': arm == 'treatment' and bool(k2),
            'unresolved_protocol_orders': len(residuals),
            'residual_protocol_exposure_microUSD': sum(row['actual_outcome']['residual_exposure_microUSD'] for row in residuals),
            'residual_scope': 'Charging harm/correction does not repair protocol effects; unresolved effects veto closed commercial success.',
            'equity_opportunity_cost': {'measured_USD': None, 'noncash_sensitivity_only': True,
                                        'at_5_percent_annual_USD': capital*0.05*(24+state['index']*168)/8760},
            'operating_hours': 24+state['index']*168, 'trailing_365_day_milestone': 'NOT_ESTABLISHED_SHORT_COHORT',
            'scale_track': {'finite_acquired_opportunities': len(events), 'validated_unbounded_demand': False,
                            'first_use_costs_expensed': True, 'construction_amortization_used_in_native_profit': False,
                            'unknown_real_market_demand': True},
            'cost_sensitivity': [{'multiplier': m, 'revenue_held_fixed_profit_microUSD': financial['revenue']-m*financial['expenses'],
                                 'scope': 'static conditional sensitivity, no claim buyers or operating policy unchanged in reality'}
                                for m in (1, 3, 10)]}


def run_portfolio(output, expected_freeze, development=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source = output/'source'
    source_copy(source)
    cfg, specs, rows = protocol(), cases(development), []
    capitals = [cfg['primary_capital_usd']] if development else cfg['capital_usd']
    regions = ['positive'] if development else cfg['regions']
    for capital in capitals:
        for region in regions:
            for arm in (ARMS if development else (*ARMS, 'no_deploy')):
                name = f"{arm.replace('_', '-')}-{region}-{capital}"
                rows.append(operate(output/name, source, specs, arm, region, capital, expected_freeze, development))
                save(output/'PROGRESS.json', {'completed': len(rows), 'rows': rows, 'independent_accounts_not_pooled': True})
    return {'schema': 'outlearning-native-economics/v1', 'freeze_sha256': expected_freeze,
            'scope': 'AUDITED_CONDITIONAL_SIMULATION', 'accounts': rows, 'independent_accounts_not_pooled': True,
            'actual_revenue_USD': 0, 'actual_customers': 0, 'actual_model_and_host_billing': None,
            'billing_is_not_zero': 'Included access; monetary resource envelopes are hypothetical, not measured invoices.',
            'development': development, 'native_recovery': 'Signed checkpoints and existing JournalAccount identities; no reseeding.'}
