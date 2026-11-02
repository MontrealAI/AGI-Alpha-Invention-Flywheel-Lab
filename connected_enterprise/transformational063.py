"""Evidence-scoped decisions derived from the canonical native account.

This module is a read-only projection, not a second money ledger. Immediate
expensing is the canonical accounting policy; no amortization is added later.
All monetary values are exact simulated micro-USD.
"""
from __future__ import annotations

from commercial.ledger import amount, digest
from connected_enterprise.finance import audit_journal

SCHEMA = 'agi-alpha/transformational063-decisions/v1'


def _integer(value, name, *, signed=False):
    if type(value) is not int or (not signed and value < 0):
        raise ValueError('EXACT_' + name.upper() + '_REQUIRED')
    return value


def _decision(name, tests, *, scope='CONDITIONAL_SIMULATION'):
    failures = [test for test in tests if not test['passed']]
    return {'decision': name, 'verdict': 'CONDITIONAL_GO' if not failures else 'NOT_ESTABLISHED',
            'scope': scope, 'conditions': tests, 'failed_conditions': failures}


def _condition(metric, value, threshold, passed, comparator):
    return {'metric': metric, 'value': value, 'threshold': threshold,
            'passed': bool(passed), 'comparator': comparator}


def financial_states(record, *, root, manifest, development_ids=(), period_start_sequence=0,
                     accounting_policy='expense-immediately'):
    """Audit first, then derive profit, cash payback, availability and funding."""
    if accounting_policy != 'expense-immediately':
        raise ValueError('NATIVE_IMMEDIATE_EXPENSE_POLICY_REQUIRED_NO_DUPLICATE_AMORTIZATION')
    audit = audit_journal(record, root=root, manifest=manifest)
    if not audit['accepted']:
        raise ValueError('ACCEPTED_NATIVE_AUDIT_REQUIRED')
    tape = record['ledger']
    actions, summary = tape['actions'], tape['summary']
    _integer(period_start_sequence, 'period_start_sequence')
    if period_start_sequence > len(actions):
        raise ValueError('PERIOD_START_OUTSIDE_NATIVE_HISTORY')
    if not isinstance(development_ids, (list, tuple)) or len(set(development_ids)) != len(development_ids):
        raise ValueError('UNIQUE_DEVELOPMENT_COST_IDENTIFIERS_REQUIRED')
    development, development_paid = 0, 0
    for ident in development_ids:
        matches = [(i, row) for i, row in enumerate(actions)
                   if row['op'] == 'cost' and row['args']['id'] == ident]
        if len(matches) != 1:
            raise ValueError('DEVELOPMENT_MUST_REFERENCE_ONE_INCURRED_NATIVE_COST')
        i, row = matches[0]
        development += row['args']['amount']
        development_paid += row['after']['expensePaid'] - (actions[i-1]['after']['expensePaid'] if i else 0)
    baseline = actions[period_start_sequence-1]['after'] if period_start_sequence else {}
    period = {key: summary[key] - baseline.get(key, 0)
              for key in ('revenue', 'expenses', 'recoveryIncome', 'profit', 'collections', 'expensePaid')}
    opening = record['ledger']['config']['opening']
    cash_paid = opening + summary['collections'] + summary['recoveryIncome'] - summary['cash']
    project_cash_returns = summary['collections'] + summary['recoveryIncome'] - (cash_paid-development_paid)
    recovered = min(development_paid, max(0, project_cash_returns))
    spending = []
    for row in record['connected_journal']['entries']:
        if row['request']['operation'] == 'spend' and row['status'] == 'COMPLETE':
            receipt = row['receipt']
            spending.append({'id': row['request']['id'], 'amount_microUSD': row['request']['amount'],
                             'funding': receipt['funding'],
                             'native_receipt_sha256': digest(receipt)})
    released = {row['id'] for row in tape['orders'] if row['state'] == 'released'}
    releases = [row for row in actions[period_start_sequence:]
                if row['op'] == 'event' and row['args']['action'] == 'release'
                and row['args']['id'] in released]
    return {'schema': SCHEMA, 'scope': 'AUDITED_CONDITIONAL_NATIVE_SIMULATION',
            'native_export_sha256': digest(record), 'native_audit': audit,
            'accounting_profit': {'policy': accounting_policy, 'lifetime_microUSD': summary['profit'],
                                  'period_start_sequence': period_start_sequence, 'period': period,
                                  'unpaid_expense_and_refund_liabilities_microUSD': summary['payables']},
            'project_payback': {'development_incurred_microUSD': development,
                               'development_paid_microUSD': development_paid,
                               'unpaid_development_microUSD': development-development_paid,
                               'attributable_enterprise_cash_returns_microUSD': project_cash_returns,
                               'recovered_microUSD': recovered,
                               'unrecovered_microUSD': development-recovered,
                               'unrecovered_paid_outlay_microUSD': development_paid-recovered,
                               'scope': 'ALL_ENTERPRISE_CASH_RETURNS_NO_CAUSAL_PROJECT_ALLOCATION_CLAIM'},
            'available_cash': {key: summary[key] for key in
                               ('cash', 'available', 'unrestrictedEarned', 'payables', 'custodyReserve',
                                'tailReserve', 'workingCapital', 'reservedInvestment')},
            'investment_funding': spending,
            'native_delivery_counts': {'accepted_and_released': len(releases),
                                       'distinct_release_times': len({row['day'] for row in releases})},
            'actual_host_and_model_billing_microUSD': None,
            'actual_customers_or_collections': False}


def qualifications(states, *, accepted_deliveries, completed_cycles, minimum_cycles=3,
                   modeled_cost_scope_complete, kernel_comparison=None, investment=None,
                   successor_comparison=None):
    """Four independent decisions; technical wins never override losing accounts.

    Comparison records are scoped experimental measurements, not external
    certification. Missing matched evidence cannot silently become a GO.
    """
    for name, value in [('accepted_deliveries', accepted_deliveries), ('completed_cycles', completed_cycles),
                        ('minimum_cycles', minimum_cycles)]:
        _integer(value, name)
    if minimum_cycles < 1 or type(modeled_cost_scope_complete) is not bool:
        raise ValueError('DECLARED_REPEATED_CYCLE_AND_COST_SCOPE_REQUIRED')
    if (not isinstance(states, dict) or states.get('schema') != SCHEMA
        or states.get('scope') != 'AUDITED_CONDITIONAL_NATIVE_SIMULATION'
        or states.get('native_audit', {}).get('accepted') is not True):
        raise ValueError('AUDITED_FINANCIAL_STATES_REQUIRED')
    counts = states['native_delivery_counts']
    if accepted_deliveries != counts['accepted_and_released'] or completed_cycles > counts['distinct_release_times']:
        raise ValueError('QUALIFICATION_COUNTS_MUST_MATCH_AUDITED_NATIVE_RELEASES')
    profit = states['accounting_profit']['period']['profit']
    cash = states['available_cash']
    protected = sum(cash[k] for k in ('payables', 'custodyReserve', 'tailReserve', 'workingCapital', 'reservedInvestment'))
    commercial = _decision('COMMERCIAL', [
        _condition('period_complete_cost_profit_microUSD', profit, '> 0', profit > 0, 'native recognized revenue minus incurred expenses'),
        _condition('accepted_deliveries', accepted_deliveries, '> 0', accepted_deliveries > 0, 'independent delivery checks'),
        _condition('completed_competitive_cycles', completed_cycles, minimum_cycles, completed_cycles >= minimum_cycles, 'registered repeated cycles'),
        _condition('declared_modeled_cost_scope_complete', modeled_cost_scope_complete, True, modeled_cost_scope_complete, 'registered AI-native cost envelope'),
        _condition('unpaid_liabilities_microUSD', cash['payables'], 0, cash['payables'] == 0, 'native preserved liabilities'),
        _condition('cash_covers_obligations_and_reserves_microUSD', cash['cash'], protected, cash['cash'] >= protected, 'native custody, tail, working capital, commitments and payables'),
    ])
    blue = _comparison_decision('BLUE_SKY_FLAGSHIP', kernel_comparison)
    successor = _comparison_decision('SUCCESSOR', successor_comparison)
    if investment is None:
        invest = _decision('INVESTMENT', [_condition('registered_incremental_economic_case', None, 'required', False, 'no proposed investment')])
    else:
        cost = amount(investment['cost_microUSD'], positive=True)
        benefit = _integer(investment['incremental_benefit_microUSD'], 'incremental_benefit', signed=True)
        allow_seed = investment.get('allow_seed', False)
        if type(allow_seed) is not bool:
            raise ValueError('EXPLICIT_SEED_AUTHORITY_REQUIRED')
        earned = cash['unrestrictedEarned'] >= cost
        invest = _decision('INVESTMENT', [
            _condition('incremental_net_benefit_microUSD', benefit-cost, '> 0', benefit > cost, 'registered matched alternative'),
            _condition('available_microUSD', cash['available'], cost, cash['available'] >= cost, 'native obligations and reserves already excluded'),
            _condition('funding_authority', 'EARNED' if earned else 'SEED', 'earned or explicitly allowed seed', earned or allow_seed, 'native unrestrictedEarned'),
        ])
        invest['prospective_funding'] = 'EARNED' if earned else 'SEED' if allow_seed else 'UNFUNDED'
        invest['project_payback_complete'] = states['project_payback']['unrecovered_microUSD'] == 0
    return {'schema': SCHEMA, 'commercial': commercial, 'blue_sky_flagship': blue,
            'investment': invest, 'successor': successor,
            'technical_advantage': 'SEPARATE_COMPARISON_NO_AUTOMATIC_COMMERCIAL_VETO',
            'observed_commerce': 'NOT_ESTABLISHED'}


def _comparison_decision(name, comparison):
    if comparison is None:
        return _decision(name, [_condition('matched_fresh_comparison', None, 'required', False, 'missing evidence')])
    required = {'with_asset_accepted', 'without_asset_accepted', 'with_asset_complete_cost_microUSD',
                'without_asset_complete_cost_microUSD', 'matched_resources', 'fresh_work', 'evidence_sha256'}
    if name == 'BLUE_SKY_FLAGSHIP':
        required |= {'consequential_outcome', 'minimum_accepted_outcomes'}
    if set(comparison) != required:
        raise ValueError('EXACT_MATCHED_COMPARISON_REQUIRED')
    for key in ('with_asset_accepted', 'without_asset_accepted', 'with_asset_complete_cost_microUSD',
                'without_asset_complete_cost_microUSD'):
        _integer(comparison[key], key)
    if any(type(comparison[k]) is not bool for k in ('matched_resources', 'fresh_work')):
        raise ValueError('EXPLICIT_MATCHED_AND_FRESH_FLAGS_REQUIRED')
    if (not isinstance(comparison['evidence_sha256'], str) or len(comparison['evidence_sha256']) != 64
        or any(c not in '0123456789abcdef' for c in comparison['evidence_sha256'])):
        raise ValueError('BOUND_COMPARISON_EVIDENCE_REQUIRED')
    added = comparison['with_asset_accepted']-comparison['without_asset_accepted']
    savings = comparison['without_asset_complete_cost_microUSD']-comparison['with_asset_complete_cost_microUSD']
    benefit = added > 0 or (comparison['with_asset_accepted'] > 0 and added == 0 and savings > 0)
    if name == 'BLUE_SKY_FLAGSHIP':
        threshold = _integer(comparison['minimum_accepted_outcomes'], 'minimum_accepted_outcomes')
        if threshold < 1 or not isinstance(comparison['consequential_outcome'], str) or not comparison['consequential_outcome'].strip():
            raise ValueError('REGISTERED_CONSEQUENTIAL_OUTCOME_AND_BINDING_THRESHOLD_REQUIRED')
        benefit = comparison['without_asset_accepted'] < threshold <= comparison['with_asset_accepted']
    tests = [
        _condition('matched_resources', comparison['matched_resources'], True, comparison['matched_resources'], 'equal starting resources and permissions'),
        _condition('fresh_work', comparison['fresh_work'], True, comparison['fresh_work'], 'held-out accepted work'),
        _condition('incremental_accepted_or_economic_value', {'additional_accepted': added, 'cost_saving_microUSD': savings}, '> 0', benefit, 'strongest declared route without asset'),
    ]
    if name == 'BLUE_SKY_FLAGSHIP':
        tests[-1] = _condition('consequential_feasibility_threshold',
            {'before': comparison['without_asset_accepted'], 'after': comparison['with_asset_accepted'],
             'outcome': comparison['consequential_outcome']}, threshold, benefit,
            'strongest declared matched route without construction must fall below threshold')
    return _decision(name, tests, scope='DECLARED_BOUND_MATCHED_COMPARISON_NOT_EXTERNAL_CERTIFICATION')


def _save(path, value):
    from pathlib import Path
    from commercial.ledger import canonical
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(canonical(value))


def registered_protocol():
    usd = 1_000_000
    return {'schema': 'flexibility063/commerce-protocol/v1', 'scope': 'SYNTHETIC_PLANNING_CONTRACTS_ONLY',
        'primary_scenario': 'central', 'opening_per_separate_account_microUSD': 100_000*usd,
        'accounts_pooled': False, 'planning_price_menu_microUSD': [30*usd, 50*usd, 60*usd, 70*usd, 90*usd],
        'development_expense_microUSD': 100*usd, 'acquisition_per_attempt_microUSD': 5*usd,
        'positive_income_tax_numerator': 1, 'positive_income_tax_denominator': 4,
        'tax_scope': 'Authored25percent positive cumulative modeled income provision; scenario assumption, not an actual tax assessment.',
        'maintenance_per_period_microUSD': 2*usd, 'production_and_verification_prepaid_microUSD': 3*usd,
        'development_billing_status': 'CONDITIONAL_AI_NATIVE_ENVELOPE_NOT_OBSERVED_BILL',
        'participant_payment_boundary': 'Artifact computes hypothetical compensation; no physical energy service or participant cash transfer is executed or booked as enterprise revenue/cost.',
        'buyer_choice': 'Buy only if planning quote is strictly below eligible rival or self-service and planning fee plus modeled participant compensation upper bound fits budget; decline valid.',
        'supplier_behavior': 'Central fixed prepaid computational service; adverse supplier charges 4x and produces a checked rejected artifact in cycle one.',
        'competitor_behavior': 'Central rivals lower published quotes across cycles; copycat rival can adopt same public solver and undercut all offered prices.',
        'forecast_information': 'Only current cycle public rival price, request and current cash; no future draw access.',
        'complete_cost_status': 'COMPLETE_FOR_DECLARED_MODEL_ACTUAL_HOST_AND_MODEL_BILLING_UNKNOWN',
        'scenarios': {'central': {'rival': [80*usd, 70*usd, 60*usd, 80*usd], 'supplier_multiple': 1, 'budget': 200*usd},
                      'copycat': {'rival': [20*usd]*4, 'supplier_multiple': 1, 'budget': 200*usd},
                      'no_purchase': {'rival': [80*usd]*4, 'supplier_multiple': 1, 'budget': 0},
                      'supplier_failure': {'rival': [80*usd, 70*usd, 60*usd, 80*usd], 'supplier_multiple': 4, 'budget': 200*usd}},
        'investment': {'cost_microUSD': 15*usd, 'incremental_benefit_microUSD': 20*usd,
                       'allow_seed': False, 'objective': 'Construct portable request/checker-bound planning tool manifest; projected20USD is an authored hypothesis, not verified successor gain.'}}


def report_header(protocol, source_sha256):
    usd = 1_000_000
    return {'schema': 'flexibility063/native-campaign/v1', 'scope': protocol['scope'],
              'protocol_sha256': digest(protocol), 'source_sha256': source_sha256, 'scenarios': {},
              'primary_seed_microUSD': 100_000*usd, 'real_customers': 0, 'actual_model_host_billing': None,
              'human_market_benchmark': 'NOT_ESTABLISHED_NO_EQUIVALENT_SCOPED_QUOTE',
              'direct_frontier_ai_comparator': 'INCLUDED_GENERALIST_TECHNICAL_SUCCESSOR_ONLY_FULL_COST_UNKNOWN_SEE_CAMPAIGN_DIRECT_GENERALIST',
              'three_billion_trailing_year_profit': 'NOT_ESTABLISHED_FINITE_FOUR_PERIOD_EXPERIMENT',
              'physical_or_new_industry_enablement': 'NOT_ESTABLISHED'}


def charge_tax(account, protocol, ident, hour):
    exported = account.export()
    charged = sum(a['args']['amount'] for a in exported['ledger']['actions']
                  if a['op'] == 'cost' and a['args']['id'].startswith('income-tax-'))
    pretax = exported['ledger']['summary']['profit']+charged
    divisor = protocol['positive_income_tax_denominator']
    due = (max(0, pretax)*protocol['positive_income_tax_numerator']+divisor-1)//divisor
    if due > charged:
        account.cost('income-tax-'+ident, due-charged, hour)


def run(root, output):
    """Execute finite strategic planning contracts through existing owned accounts."""
    import copy
    import hashlib
    import json
    from pathlib import Path
    import resource
    import shutil
    import time
    from commercial.terms_exact_v2 import prospective_terms
    from connected_enterprise.finance import source_paths_for_manifest
    from flexibility063.kernel import solve
    from flexibility063.native import BusinessAccount
    from flexibility063.service import prepare_manifest
    from flexibility063.verify import verify
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('NEW_TRANSFORMATIONAL063_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    frozen = output/'source'
    frozen.mkdir()
    paths = source_paths_for_manifest({'schema': 'flexibility063/native-services/v1'})
    for name in paths:
        path = frozen/name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/name, path)
    source = {name: hashlib.sha256((frozen/name).read_bytes()).hexdigest() for name in paths}
    profiles = json.loads((frozen/'flexibility063/profiles.json').read_text())
    usd = 1_000_000
    protocol = registered_protocol()
    _save(output/'PROTOCOL.json', protocol)
    _save(output/'SOURCE.json', {'files': source, 'sha256': digest(source)})
    report = report_header(protocol, digest(source))
    for arm, scenario in protocol['scenarios'].items():
        manifest = prepare_manifest(frozen, [{'id': p['id'], 'delivery_path': 'flexibility063/deliveries/'+arm+'/'+p['id']+'.json'} for p in profiles])
        folder = output/'public'/arm
        _save(folder/'manifest.json', manifest)
        private = output/'private'/arm
        private.mkdir(parents=True)
        row = {'attempts': [], 'investment': None, 'successor': None}
        with BusinessAccount(frozen, manifest, private/'account', working=0, contract='transformational063-'+arm) as account:
            account.cost('development', protocol['development_expense_microUSD'], 0)
            for index, request in enumerate(profiles):
                hour = 24*(index+1)
                account.advance(hour)
                if index == 3:
                    states = financial_states(account.export(), root=frozen, manifest=manifest, development_ids=['development'])
                    before = qualifications(states, accepted_deliveries=states['native_delivery_counts']['accepted_and_released'],
                        completed_cycles=sum(a.get('accepted', False) for a in row['attempts']),
                        modeled_cost_scope_complete=True, investment=protocol['investment'])
                    if before['investment']['verdict'] == 'CONDITIONAL_GO':
                        receipt = account.spend('portable-instrument', 'retained_planning_instrument',
                            protocol['investment']['cost_microUSD'], hour,
                            {'kernel_sha256': source['flexibility063/kernel.py'], 'checker_sha256': source['flexibility063/verify.py'],
                             'action': 'Construct portable manifest after native commitment; fresh successor is free to rebuild ordinary solver.'},
                            expected_net=protocol['investment']['incremental_benefit_microUSD']-protocol['investment']['cost_microUSD'])
                        if receipt is not None:
                            asset = {'schema': 'flexibility063/portable-instrument/v1', 'kernel_sha256': source['flexibility063/kernel.py'],
                                     'checker_sha256': source['flexibility063/verify.py'], 'request_schema': 'flexibility063/request/v1'}
                            _save(folder/'portable-instrument.json', asset)
                            row['investment'] = {'receipt': receipt, 'asset_sha256': digest(asset), 'forecast_decision': before['investment'],
                                                 'realized_incremental_advantage': 'TESTED_SEPARATELY_NOT_ASSUMED'}
                account.cost('acquisition-'+request['id'], protocol['acquisition_per_attempt_microUSD'], hour)
                account.cost('maintenance-'+request['id'], protocol['maintenance_per_period_microUSD'], hour)
                rival = scenario['rival'][index]
                supplier = protocol['production_and_verification_prepaid_microUSD']*scenario['supplier_multiple']
                # This exact upper bound is visible from the request before production.
                event_slots = [i for i, q in enumerate(request['target_wh']) if q]
                participant_bound = sum(sum(device['baseline_wh'][t] for t in event_slots)*device['disutility_microUSD_per_wh']+request['participant_margin_microUSD'] for device in request['devices'])
                budget = min(scenario['budget'], request['buyer_budget_microUSD'])
                choices = [p for p in protocol['planning_price_menu_microUSD'] if p > supplier+2*usd and p < rival and p < 95*usd and p+participant_bound <= budget]
                quote = max(choices) if choices else None
                attempt = {'request_id': request['id'], 'hour': hour, 'rival_planning_quote_microUSD': rival,
                           'self_service_alternative_microUSD': 95*usd, 'buyer_budget_microUSD': budget,
                           'participant_compensation_upper_bound_microUSD': participant_bound,
                           'quote_microUSD': quote, 'buyer_choice': 'PURCHASE' if quote is not None else 'DECLINE',
                           'accepted': False, 'artifact_sha256': None}
                if quote is None:
                    attempt['failed_condition'] = {'metric': 'feasible_buyer_preferred_quote_count', 'value': 0, 'threshold': '>0', 'comparator': 'current rival, self-service, budget and no purchase'}
                    row['attempts'].append(attempt)
                    charge_tax(account, protocol, request['id'], hour+3)
                    continue
                order = arm+'-'+request['id']
                terms = prospective_terms(order, quote, hour+10, hour+2, residual=usd, fee=200_000,
                    counterparty_obligations='Conditional purchase of independently checked synthetic planning artifact only; no energy delivery, grid access or live participant payment. Producer retains modeled residual risk.')
                account.begin_order(request['id'], order, 'buyer-'+order, quote, budget, hour, hour+3, terms)
                payment = account.spend('production-'+request['id'], 'autonomous_planning_and_independent_check', supplier, hour,
                    {'request_sha256': digest(request), 'modeled_supplier_cost_microUSD': supplier}, expected_net=quote-supplier-200_000, allow_seed=True)
                if payment is None:
                    account.refund(order, hour+1)
                    attempt['failed_condition'] = {'metric': 'native_funded_production', 'value': 0, 'threshold': 1, 'comparator': 'current unrestricted cash'}
                    row['attempts'].append(attempt)
                    charge_tax(account, protocol, request['id'], hour+3)
                    continue
                start, cpu_before = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
                artifact = solve(request, 'pooled')
                if arm == 'supplier_failure' and index == 0:
                    artifact = copy.deepcopy(artifact)
                    first = request['devices'][0]['id']
                    artifact['dispatch_wh'][first][0] += 1
                receipt = account.complete_order(order, request['id'], artifact, hour+1)
                cpu_after = resource.getrusage(resource.RUSAGE_SELF)
                attempt.update(accepted=receipt['accepted'], artifact_sha256=digest(artifact), acceptance=receipt,
                    funded_before_production=True, native_resource_receipt=payment,
                    actual_cpu_seconds=cpu_after.ru_utime+cpu_after.ru_stime-cpu_before.ru_utime-cpu_before.ru_stime,
                    actual_wall_seconds=time.monotonic()-start, measured_model_calls=0,
                    participant_compensation_microUSD=sum(artifact['payments_microUSD'].values()),
                    physical_participant_payment_booked=False)
                if receipt['accepted']:
                    account.release(order, hour+2)
                else:
                    account.refund(order, hour+2)
                if index == 3:
                    alternative = solve(request, 'conventional')
                    ordinary = verify(request, alternative)
                    _save(folder/'ordinary-successor.json', alternative)
                    comparison = {'with_asset_accepted': int(receipt['accepted']), 'without_asset_accepted': int(ordinary['accepted']),
                        'with_asset_complete_cost_microUSD': supplier+(protocol['investment']['cost_microUSD'] if row['investment'] else 0),
                        'without_asset_complete_cost_microUSD': supplier,
                        'matched_resources': True, 'fresh_work': True,
                        'evidence_sha256': digest({'inherited': receipt, 'ordinary': ordinary})}
                    row['successor'] = {'comparison': comparison, 'ordinary_acceptance': ordinary,
                        'ordinary_artifact_sha256': digest(alternative), 'retained_asset_required': False,
                        'ordinary_free_to_rebuild_same_solver': True}
                row['attempts'].append(attempt)
                charge_tax(account, protocol, request['id'], hour+3)
            account.advance(120)
            exported = account.export()
            states = financial_states(exported, root=frozen, manifest=manifest, development_ids=['development'])
            accepted = states['native_delivery_counts']['accepted_and_released']
            decisions = qualifications(states, accepted_deliveries=accepted,
                completed_cycles=sum(a['accepted'] for a in row['attempts'][:3]), modeled_cost_scope_complete=True,
                successor_comparison=row['successor']['comparison'] if row['successor'] else None)
            row.update(financial_states=states, qualifications=decisions, native_export_sha256=digest(exported),
                       native_audit=account.audit())
            _save(folder/'native-export.json', exported)
            _save(folder/'result.json', row)
            report['scenarios'][arm] = {'result_path': str((folder/'result.json').relative_to(output)),
                'manifest_path': str((folder/'manifest.json').relative_to(output)),
                'native_export_path': str((folder/'native-export.json').relative_to(output)),
                'result_sha256': digest(row), 'profit_microUSD': states['accounting_profit']['lifetime_microUSD'],
                'accepted_deliveries': accepted, 'commercial': decisions['commercial']['verdict'],
                'investment_funding': row['investment']['receipt']['funding'] if row['investment'] else None,
                'successor': decisions['successor']['verdict']}
    _save(output/'REPORT.json', report)
    audit(output)
    return report


def audit(output):
    """Replay key-free source/manifest/deliveries and reject changed reports."""
    import hashlib
    from pathlib import Path
    from commercial.ledger import strict_json
    from connected_enterprise.finance import source_paths_for_manifest
    output = Path(output).resolve()
    frozen = output/'source'
    source = strict_json((output/'SOURCE.json').read_bytes())
    required = set(source_paths_for_manifest({'schema': 'flexibility063/native-services/v1'}))
    if set(source.get('files', {})) != required:
        raise ValueError('TRANSFORMATIONAL063_COMPLETE_SOURCE_COVERAGE_REQUIRED')
    actual = {name: hashlib.sha256((frozen/name).read_bytes()).hexdigest() for name in source['files']}
    if actual != source['files'] or digest(actual) != source['sha256']:
        raise ValueError('TRANSFORMATIONAL063_FROZEN_SOURCE_CHANGED')
    report = strict_json((output/'REPORT.json').read_bytes())
    protocol = strict_json((output/'PROTOCOL.json').read_bytes())
    if protocol != registered_protocol() or set(report.get('scenarios', {})) != set(protocol['scenarios']):
        raise ValueError('TRANSFORMATIONAL063_EXACT_REGISTERED_PROTOCOL_AND_SCENARIO_COVERAGE_REQUIRED')
    if {k: v for k, v in report.items() if k != 'scenarios'} != {k: v for k, v in report_header(protocol, source['sha256']).items() if k != 'scenarios'}:
        raise ValueError('TRANSFORMATIONAL063_REPORT_SCOPE_OR_CAPITAL_CHANGED')
    if digest(protocol) != report['protocol_sha256'] or source['sha256'] != report['source_sha256']:
        raise ValueError('TRANSFORMATIONAL063_PROTOCOL_OR_SOURCE_CHANGED')
    checked = {}
    for arm, item in report['scenarios'].items():
        folder = output/'public'/arm
        manifest = strict_json((folder/'manifest.json').read_bytes())
        exported = strict_json((folder/'native-export.json').read_bytes())
        row = strict_json((folder/'result.json').read_bytes())
        if digest(row) != item['result_sha256'] or digest(exported) != row['native_export_sha256']:
            raise ValueError('TRANSFORMATIONAL063_RESULT_CHANGED')
        _audit_economy(frozen, folder, arm, protocol, manifest, exported, row)
        states = financial_states(exported, root=frozen, manifest=manifest, development_ids=['development'])
        if states != row['financial_states']:
            raise ValueError('TRANSFORMATIONAL063_FINANCIAL_PROJECTION_CHANGED')
        counts = states['native_delivery_counts']['accepted_and_released']
        decisions = qualifications(states, accepted_deliveries=counts,
            completed_cycles=sum(a['accepted'] for a in row['attempts'][:3]), modeled_cost_scope_complete=True,
            successor_comparison=row['successor']['comparison'] if row['successor'] else None)
        if decisions != row['qualifications'] or item['profit_microUSD'] != states['accounting_profit']['lifetime_microUSD']:
            raise ValueError('TRANSFORMATIONAL063_QUALIFICATION_CHANGED')
        expected_item = {'result_path': 'public/'+arm+'/result.json', 'manifest_path': 'public/'+arm+'/manifest.json',
            'native_export_path': 'public/'+arm+'/native-export.json', 'result_sha256': digest(row),
            'profit_microUSD': states['accounting_profit']['lifetime_microUSD'], 'accepted_deliveries': counts,
            'commercial': decisions['commercial']['verdict'],
            'investment_funding': row['investment']['receipt']['funding'] if row['investment'] else None,
            'successor': decisions['successor']['verdict']}
        if item != expected_item:
            raise ValueError('TRANSFORMATIONAL063_PUBLIC_SUMMARY_CHANGED')
        checked[arm] = {'accepted': True, 'native_export_sha256': digest(exported), 'summary': states['available_cash']}
    receipt = {'schema': 'flexibility063/key-free-campaign-audit/v1', 'accepted': True,
               'scope': 'INDEPENDENT_NATIVE_REPLAY_NOT_EXTERNAL_MARKET_VALIDATION', 'scenarios': checked}
    _save(output/'AUDIT.json', receipt)
    return receipt


def _audit_economy(frozen, folder, arm, protocol, manifest, exported, row):
    """Reconstruct declared choices/contracts from protocol and native history."""
    from commercial.ledger import strict_json
    from commercial.terms_exact_v2 import prospective_terms
    from flexibility063.service import prepare_manifest, delivery, verify_delivery
    from flexibility063.verify import verify
    profiles = strict_json((frozen/'flexibility063/profiles.json').read_bytes())
    expected_manifest = prepare_manifest(frozen, [{'id': p['id'], 'delivery_path': 'flexibility063/deliveries/'+arm+'/'+p['id']+'.json'} for p in profiles])
    if manifest != expected_manifest or len(row.get('attempts', [])) != len(profiles):
        raise ValueError('TRANSFORMATIONAL063_EXACT_REQUEST_COVERAGE_REQUIRED')
    scenario, usd = protocol['scenarios'][arm], 1_000_000
    if exported['ledger']['config']['opening'] != 100_000*usd or exported['ledger']['config']['working'] != 0:
        raise ValueError('TRANSFORMATIONAL063_EXACT_SEPARATE_INITIAL_CAPITAL_REQUIRED')
    expected_exec, expected_spend = [], []
    def command(op, args, day):
        expected_exec.append({'operation': 'execute', 'op': op, 'args': args, 'day': day})
    command('cost', {'id': 'development', 'amount': protocol['development_expense_microUSD']}, 0)
    investment_entries = [e for e in exported['connected_journal']['entries']
                          if e['request']['operation'] == 'spend' and e['request']['id'] == 'portable-instrument']
    for index, (request, attempt) in enumerate(zip(profiles, row['attempts'])):
        hour = 24*(index+1)
        command('cost', {'id': 'acquisition-'+request['id'], 'amount': protocol['acquisition_per_attempt_microUSD']}, hour)
        command('cost', {'id': 'maintenance-'+request['id'], 'amount': protocol['maintenance_per_period_microUSD']}, hour)
        rival = scenario['rival'][index]
        supplier = protocol['production_and_verification_prepaid_microUSD']*scenario['supplier_multiple']
        slots = [i for i, q in enumerate(request['target_wh']) if q]
        bound = sum(sum(d['baseline_wh'][t] for t in slots)*d['disutility_microUSD_per_wh']+request['participant_margin_microUSD'] for d in request['devices'])
        budget = min(scenario['budget'], request['buyer_budget_microUSD'])
        options = [p for p in protocol['planning_price_menu_microUSD'] if p > supplier+2*usd and p < rival and p < 95*usd and p+bound <= budget]
        quote = max(options) if options else None
        declared = {'request_id': request['id'], 'hour': hour, 'rival_planning_quote_microUSD': rival,
                    'self_service_alternative_microUSD': 95*usd, 'buyer_budget_microUSD': budget,
                    'participant_compensation_upper_bound_microUSD': bound, 'quote_microUSD': quote,
                    'buyer_choice': 'PURCHASE' if quote is not None else 'DECLINE'}
        if any(attempt.get(k) != v for k, v in declared.items()):
            raise ValueError('TRANSFORMATIONAL063_BUYER_CHOICE_OR_QUOTE_CHANGED')
        if quote is None:
            if attempt.get('accepted') is not False or attempt.get('artifact_sha256') is not None:
                raise ValueError('TRANSFORMATIONAL063_DECLINED_ORDER_CANNOT_DELIVER')
            continue
        order = arm+'-'+request['id']
        terms = prospective_terms(order, quote, hour+10, hour+2, residual=usd, fee=200_000,
            counterparty_obligations='Conditional purchase of independently checked synthetic planning artifact only; no energy delivery, grid access or live participant payment. Producer retains modeled residual risk.')
        command('wallet', {'buyer': 'buyer-'+order, 'amount': budget}, hour)
        command('register_terms', {'id': order+'-terms', 'terms': terms}, hour)
        command('offer', {'id': order, 'buyer': 'buyer-'+order, 'price': quote,
                         'job_id': request['id'], 'deadline': hour+3, 'terms_id': order+'-terms'}, hour)
        for action in ('consent', 'fund'):
            command('event', {'id': order, 'action': action, 'event_id': order+'-'+action}, hour)
        expected_spend.append({'operation': 'spend', 'id': 'production-'+request['id'],
            'kind': 'autonomous_planning_and_independent_check', 'amount': supplier, 'day': hour,
            'work': {'request_sha256': digest(request), 'modeled_supplier_cost_microUSD': supplier},
            'expected_net': quote-supplier-200_000, 'allow_seed': True})
        artifact = delivery(frozen, manifest, request['id'])
        receipt = verify_delivery(frozen, manifest, request['id'], artifact)
        must_accept = not (arm == 'supplier_failure' and index == 0)
        if receipt['accepted'] is not must_accept or attempt.get('acceptance') != receipt or attempt.get('artifact_sha256') != digest(artifact) or attempt.get('accepted') is not receipt['accepted']:
            raise ValueError('TRANSFORMATIONAL063_ACCEPTANCE_OR_ACTUAL_ARTIFACT_CHANGED')
        if attempt.get('funded_before_production') is not True or attempt.get('participant_compensation_microUSD') != sum(artifact['payments_microUSD'].values()) or attempt.get('physical_participant_payment_booked') is not False:
            raise ValueError('TRANSFORMATIONAL063_DELIVERY_BOUNDARY_CHANGED')
        resource_entries = [e for e in exported['connected_journal']['entries'] if e['request']['operation'] == 'spend' and e['request']['id'] == 'production-'+request['id']]
        if len(resource_entries) != 1 or attempt.get('native_resource_receipt') != resource_entries[0]['receipt']:
            raise ValueError('TRANSFORMATIONAL063_PRODUCTION_RECEIPT_CHANGED')
        if receipt['accepted']:
            command('event', {'id': order, 'action': 'prepare', 'event_id': order+'-prepare', 'artifact_sha256': digest(artifact)}, hour+1)
        final = 'release' if receipt['accepted'] else 'refund'
        command('event', {'id': order, 'action': final, 'event_id': order+'-'+final}, hour+2)
        if receipt['accepted']:
            next_time = hour+24
            command('mature', {'id': order, 'event_id': 'maturity:'+order+':'+digest(terms)[:20]}, next_time)
        if index == 3:
            ordinary = strict_json((folder/'ordinary-successor.json').read_bytes())
            acceptance = verify(request, ordinary)
            if acceptance['accepted'] is not True:
                raise ValueError('TRANSFORMATIONAL063_STRONG_ORDINARY_SUCCESSOR_MUST_BE_ACCEPTED')
            comparison = {'with_asset_accepted': int(receipt['accepted']), 'without_asset_accepted': int(acceptance['accepted']),
                'with_asset_complete_cost_microUSD': supplier+(protocol['investment']['cost_microUSD'] if row['investment'] else 0),
                'without_asset_complete_cost_microUSD': supplier, 'matched_resources': True, 'fresh_work': True,
                'evidence_sha256': digest({'inherited': receipt, 'ordinary': acceptance})}
            expected_successor = {'comparison': comparison, 'ordinary_acceptance': acceptance,
                'ordinary_artifact_sha256': digest(ordinary), 'retained_asset_required': False,
                'ordinary_free_to_rebuild_same_solver': True}
            if row.get('successor') != expected_successor:
                raise ValueError('TRANSFORMATIONAL063_SUCCESSOR_COMPARISON_CHANGED')
    tax_charged = 0
    for request in profiles:
        index = profiles.index(request)
        hour = 24*(index+1)
        period_actions = [a for a in exported['ledger']['actions'] if hour <= a['day'] <= hour+3 and not (a['op'] == 'cost' and a['args']['id'].startswith('income-tax-'))]
        if not period_actions:
            raise ValueError('TRANSFORMATIONAL063_COMPLETE_TAX_PERIOD_REQUIRED')
        pretax = period_actions[-1]['after']['profit']+tax_charged
        divisor = protocol['positive_income_tax_denominator']
        tax_due = (max(0, pretax)*protocol['positive_income_tax_numerator']+divisor-1)//divisor
        if tax_due > tax_charged:
            command('cost', {'id': 'income-tax-'+request['id'], 'amount': tax_due-tax_charged}, hour+3)
            tax_charged = tax_due
    actual_exec = [e['request'] for e in exported['connected_journal']['entries'] if e['request']['operation'] == 'execute']
    actual_spend = [e['request'] for e in exported['connected_journal']['entries'] if e['request']['operation'] == 'spend' and e['request']['id'] != 'portable-instrument']
    if sorted(map(digest, actual_exec)) != sorted(map(digest, expected_exec)) or sorted(map(digest, actual_spend)) != sorted(map(digest, expected_spend)):
        raise ValueError('TRANSFORMATIONAL063_REGISTERED_NATIVE_ACTIONS_OR_COSTS_CHANGED')
    # The fixed policy must invest exactly when native earned funds permit it.
    before = [a['before'] for a in exported['ledger']['actions'] if a['day'] == 96 and not (a['op'] == 'mature')]
    if not before:
        raise ValueError('TRANSFORMATIONAL063_SUCCESSOR_PERIOD_MISSING')
    eligible = min(before[0]['available'], before[0]['unrestrictedEarned']) >= protocol['investment']['cost_microUSD']
    if bool(row['investment']) is not eligible or len(investment_entries) != int(eligible):
        raise ValueError('TRANSFORMATIONAL063_NATIVE_INVESTMENT_ELIGIBILITY_CHANGED')
    if eligible:
        entry = investment_entries[0]
        expected_investment = {'operation': 'spend', 'id': 'portable-instrument', 'kind': 'retained_planning_instrument',
            'amount': protocol['investment']['cost_microUSD'], 'day': 96,
            'work': {'kernel_sha256': manifest['source_hashes']['flexibility063/kernel.py'],
                     'checker_sha256': manifest['source_hashes']['flexibility063/verify.py'],
                     'action': 'Construct portable manifest after native commitment; fresh successor is free to rebuild ordinary solver.'},
            'expected_net': protocol['investment']['incremental_benefit_microUSD']-protocol['investment']['cost_microUSD'], 'allow_seed': False}
        if entry['request'] != expected_investment or entry['receipt']['funding'] != 'EARNED' or row['investment']['receipt'] != entry['receipt']:
            raise ValueError('TRANSFORMATIONAL063_INVESTMENT_FUNDING_CHANGED')
        asset = strict_json((folder/'portable-instrument.json').read_bytes())
        expected_asset = {'schema': 'flexibility063/portable-instrument/v1',
            'kernel_sha256': manifest['source_hashes']['flexibility063/kernel.py'],
            'checker_sha256': manifest['source_hashes']['flexibility063/verify.py'], 'request_schema': 'flexibility063/request/v1'}
        if asset != expected_asset or digest(asset) != row['investment']['asset_sha256']:
            raise ValueError('TRANSFORMATIONAL063_RETAINED_INSTRUMENT_CHANGED')


def main():
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'audit'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.output) if args.command == 'run' else audit(args.output)
    print(json.dumps({'output': str(args.output), 'accepted': result.get('accepted', True),
                      'scenarios': result.get('scenarios')}, sort_keys=True))


if __name__ == '__main__':
    main()
