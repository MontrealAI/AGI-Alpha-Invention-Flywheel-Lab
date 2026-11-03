"""Authored finite SIM offers executed only through the canonical owned account."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from commercial.terms_exact_v2 import prospective_terms
from .native import BusinessAccount, audit_export
from . import service

USD = 1_000_000
ECONOMIC_PLAN = {
    'schema': 'outlearning073/economic-plan/v1',
    'scope': 'AUTHORED_CONDITIONAL_SIMULATION_NOT_CUSTOMER_OR_BILLING_EVIDENCE',
    'opening_microUSD': 2_000 * USD,
    'reference_opening_microUSD': 100_000 * USD,
    'underfunded_opening_microUSD': 1_000 * USD,
    'capital_justification': 'K1 requires $500 preoffer resources plus $1,000 producer collateral plus $100 remaining production resources plus $0.20 explicit payment fee; $2,000 funds that $1,600.20 peak with $399.80 contingency. The $1,000 comparison defers before an unfunded order.',
    'capital_policy': 'Fresh equity; no debt, dilution, top-ups or pooled accounts; no-entry is allowed.',
    'accounting': 'Immediate expensing of all construction and tools; no capital assets; 20% tax on each positive closed-stage operating margin; taxes are authored, not jurisdictional advice.',
    'K1': {'price_microUSD': 1_000 * USD, 'budget_microUSD': 1_200 * USD,
           'outside_quote_microUSD': 1_100 * USD,
           'costs_USD': {'research_construction': 360, 'inference_envelope': 80,
                        'failed_attempts_corrections': 40, 'acquisition_onboarding': 20,
                        'production': 30, 'independent_verification': 30,
                        'support': 20, 'maintenance_tools_infrastructure': 20}},
    'K2': {'price_microUSD': 1_200 * USD, 'budget_microUSD': 1_500 * USD,
           'outside_quote_microUSD': 1_350 * USD,
           'costs_USD': {'adaptation_construction': 40, 'inference_envelope': 40,
                        'failed_attempts_corrections': 10, 'acquisition_onboarding': 20,
                        'production': 40, 'independent_verification': 40,
                        'support': 30, 'maintenance_tools_infrastructure': 30}},
    'tax_numerator': 1, 'tax_denominator': 5,
    'modeled_payment_fee_microUSD_per_order': 200_000,
    'payment_fee_scope': 'Authored $0.20 fee explicitly passed into prospective terms and charged by the canonical offer; it is not inferred from the native exposure allowance.',
    'collection_hours': {'K1': 24, 'K2': 72},
    'maturity_hours': {'K1': 25, 'K2': 96},
    'residual_microUSD': 0,
    'capacity': 'One sequential K1 then one K2; no modeled expansion beyond the executed pair.',
    'sunk_research_USD_before_entry_decision': 480,
    'no_entry_reference': 'Halt after the already-incurred $480 research/inference/failed-construction envelope; ex ante no campaign would cost zero but is not this post-research decision.',
    'distribution': 'One paid acquisition/onboarding attempt per stage; no organic demand multiplier or repeat sales.',
    'assumptions': ['Prices, budgets, outside quotes, all monetary resource categories, tax and collection timing are authored uncertain assumptions.',
                    'Actual included-model token usage, service billing and host billing are UNKNOWN; monetary inference entries are complete-cost envelopes, not measured bills.',
                    'No observed human labor was used inside the operation; no empirical human-only productivity advantage is asserted.',
                    'The human-only and human-plus-AI outside alternatives may use the same conventional compiler at machine speed; any labor/inference benefit remains an uncalibrated sensitivity.',
                    'Technical acceptance establishes only the finite executable sandbox contract; buyer usefulness outside that contract and real willingness to pay are unmeasured.',
                    'All support/remedy envelope costs are expensed and paid upfront; finite contractual claims expire at declared maturity; no real legal enforceability or unbounded liability guarantee.'],
    'scenarios': [
        {'id': 'positive', 'outside_fraction': [1, 1], 'resource_multiplier': 1, 'collect_K1': True, 'enter': True},
        {'id': 'weak-demand', 'outside_fraction': [1, 2], 'resource_multiplier': 1, 'collect_K1': True, 'enter': True},
        {'id': 'adverse-cost', 'outside_fraction': [1, 1], 'resource_multiplier': 2, 'collect_K1': True, 'enter': True},
        {'id': 'delayed-collection', 'outside_fraction': [1, 1], 'resource_multiplier': 1, 'collect_K1': False, 'enter': True},
        {'id': 'no-entry', 'outside_fraction': [1, 1], 'resource_multiplier': 1, 'collect_K1': False, 'enter': False}
    ],
    'selection': 'Fixed complete offers, with voluntary no-purchase when public modeled outside quote or buyer budget is better; no hidden reservation values, future outcomes or scenario label enter technical policy.',
    'economic_decision': 'Fund K2 only after K1 collection, complete incurred costs and tax, with canonical EARNED reservation and no seed fallback. If unsupported, preserve accounts and defer.',
    'method_comparison': 'Strong equal-content ordinary reuse has the same permitted artifact, delivery terms and uncertain complete resource envelopes. No advantage is imputed from authorship.'
}


def _write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value))


def _buyer_accepts(offer, fraction):
    numerator, denominator = fraction
    return offer['price_microUSD'] <= offer['budget_microUSD'] and offer['price_microUSD'] * denominator < offer['outside_quote_microUSD'] * numerator


def _costs(stage, multiplier):
    return {name: value * USD * multiplier for name, value in ECONOMIC_PLAN[stage]['costs_USD'].items()}


def _stage_terms(stage, order_id):
    offer = ECONOMIC_PLAN[stage]
    return prospective_terms(order_id, offer['price_microUSD'], ECONOMIC_PLAN['maturity_hours'][stage],
                             ECONOMIC_PLAN['collection_hours'][stage], residual=ECONOMIC_PLAN['residual_microUSD'],
                             fee=ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order'],
                             counterparty_obligations='Buyer voluntarily chooses this fixed finite sandbox workflow contract; producer corrects/refunds failed acceptance; all declared support and remedy envelope costs are paid upfront; claims remain protected through maturity.')


def run_scenario(root, output, manifest, produce, scenario, *, opening=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('OUTLEARNING073_NEW_SCENARIO_DIRECTORY_REQUIRED')
    if scenario not in ECONOMIC_PLAN['scenarios']:
        raise ValueError('OUTLEARNING073_REGISTERED_SCENARIO_REQUIRED')
    output.mkdir(parents=True)
    private = output / 'private'; private.mkdir(mode=0o700)
    _write(output / 'MANIFEST.json', manifest)
    result = {'schema': 'outlearning073/native-economic-result/v1', 'scope': ECONOMIC_PLAN['scope'],
              'case_id': output.name, 'scenario': copy.deepcopy(scenario), 'plan_sha256': digest(ECONOMIC_PLAN),
              'opening_microUSD': ECONOMIC_PLAN['opening_microUSD'] if opening is None else opening,
              'orders': [], 'costs': [], 'funding': [], 'decisions': [],
              'actual_model_and_host_billing': 'UNKNOWN', 'commercial_observations': 0,
              'retained_method_advantage': 'NOT_INFERRED_FROM_ECONOMICS',
              'scale': 'Two bounded modeled offers; no annualization, market validation or US$3B claim.'}
    with BusinessAccount(root, manifest, private / 'account.sqlite', opening=result['opening_microUSD'],
                         contract='outlearning073-' + scenario['id']) as account:
        if not scenario['enter']:
            sunk = ECONOMIC_PLAN['sunk_research_USD_before_entry_decision'] * USD
            receipt = account.spend('sunk-research', 'research_already_incurred', sunk, 0,
                {'scope': 'Declared already-incurred campaign research envelope', 'plan_sha256': digest(ECONOMIC_PLAN)},
                expected_net=0, allow_seed=True)
            if receipt is None: raise ValueError('OUTLEARNING073_SUNK_RESEARCH_UNFUNDED')
            result['funding'].append(receipt)
            result['costs'].append({'stage': 'K1', 'sunk_research_microUSD': sunk, 'total_microUSD': sunk})
            result['decisions'].append({'stage': 'K1', 'decision': 'NO_ENTRY_AFTER_SUNK_RESEARCH'})
        else:
            for stage, day in [('K1', 0), ('K2', 48)]:
                offer = ECONOMIC_PLAN[stage]; chosen = _buyer_accepts(offer, scenario['outside_fraction'])
                costs = _costs(stage, scenario['resource_multiplier'])
                if stage == 'K2':
                    account.advance(day)
                pre_names = {'research_construction', 'adaptation_construction', 'inference_envelope', 'failed_attempts_corrections', 'acquisition_onboarding'}
                pre_costs = {name: value for name, value in costs.items() if name in pre_names}
                production_costs = {name: value for name, value in costs.items() if name not in pre_names}
                upfront = sum(costs.values())
                funding = account.spend('preoffer-' + stage, 'research_and_acquisition_resources', sum(pre_costs.values()), day,
                    {'stage': stage, 'categories_microUSD': pre_costs, 'plan_sha256': digest(ECONOMIC_PLAN),
                     'manifest_sha256': digest(manifest)}, expected_net=offer['price_microUSD'] - upfront,
                    allow_seed=stage == 'K1')
                if funding is None:
                    result['decisions'].append({'stage': stage, 'decision': 'DEFER_UNFUNDED',
                                                'required_microUSD': sum(pre_costs.values()), 'snapshot': account.snapshot()})
                    break
                result['funding'].append(funding)
                result['costs'].append({'stage': stage, 'categories_microUSD': pre_costs, 'total_microUSD': sum(pre_costs.values())})
                if not chosen:
                    result['decisions'].append({'stage': stage, 'decision': 'NO_PURCHASE',
                        'reason': 'Buyer chooses no purchase or the better public modeled outside option.'})
                    break
                if account.snapshot()['summary']['available'] < offer['price_microUSD'] + sum(production_costs.values()) + ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order']:
                    result['decisions'].append({'stage': stage, 'decision': 'DEFER_UNFUNDED_BEFORE_ORDER',
                                                'required_microUSD': offer['price_microUSD'] + sum(production_costs.values()) + ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order'], 'snapshot': account.snapshot()})
                    break
                job = next((row for row in manifest['jobs'] if row['request']['stage'] == stage), None)
                if job is None:
                    raise ValueError('OUTLEARNING073_EXACT_STAGE_REQUEST_REQUIRED')
                order_id = stage + '-order'
                account.begin_order(job['id'], order_id, stage + '-buyer', offer['price_microUSD'],
                                    offer['budget_microUSD'], day, ECONOMIC_PLAN['collection_hours'][stage],
                                    terms=_stage_terms(stage, order_id))
                result['costs'][-1]['payment_fee_microUSD'] = ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order']
                production = account.spend('production-' + stage, 'production_verification_support_resources', sum(production_costs.values()), day,
                    {'stage': stage, 'categories_microUSD': production_costs, 'plan_sha256': digest(ECONOMIC_PLAN),
                     'manifest_sha256': digest(manifest)}, expected_net=offer['price_microUSD'] - upfront,
                    allow_seed=stage == 'K1')
                if production is None:
                    account.refund(order_id, day)
                    result['decisions'].append({'stage': stage, 'decision': 'REFUND_PRODUCTION_UNFUNDED'})
                    break
                result['funding'].append(production)
                result['costs'][-1]['categories_microUSD'] = costs
                result['costs'][-1]['total_microUSD'] = upfront
                artifact = produce(copy.deepcopy(job['request']))
                checked = account.complete_order(order_id, job['id'], artifact, day + 1)
                result['orders'].append({'stage': stage, 'order_id': order_id, 'job_id': job['id'],
                    'artifact_sha256': digest(artifact), 'acceptance': checked})
                if not checked['accepted']:
                    account.refund(order_id, day + 2)
                    result['decisions'].append({'stage': stage, 'decision': 'REFUND_FAILED_ACCEPTANCE'})
                    break
                if stage == 'K1' and not scenario['collect_K1']:
                    before = account.export()
                    attempted = account.spend('uncollected-K2-counterfactual', 'complete_workflow_resources',
                        sum(_costs('K2', scenario['resource_multiplier']).values()), 48,
                        {'stage': 'K2', 'matched_counterfactual': 'K1 accepted but uncollected', 'plan_sha256': digest(ECONOMIC_PLAN)},
                        expected_net=ECONOMIC_PLAN['K2']['price_microUSD'] - sum(_costs('K2', scenario['resource_multiplier']).values()), allow_seed=False)
                    if attempted is not None or account.export() != before:
                        raise ValueError('OUTLEARNING073_UNCOLLECTED_FUNDING_OR_HISTORY_CHANGED')
                    result['uncollected_successor_refusal'] = {'funding_receipt': None, 'unchanged_native_record_sha256': digest(before),
                        'requested_microUSD': sum(_costs('K2', scenario['resource_multiplier']).values()), 'allow_seed': False}
                    result['decisions'].append({'stage': stage, 'decision': 'COLLECTION_UNRESOLVED_NO_SUCCESSOR_FUNDING'})
                    break
                account.release(order_id, ECONOMIC_PLAN['collection_hours'][stage])
                stage_margin = offer['price_microUSD'] - upfront - ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order']
                tax = max(stage_margin, 0) * ECONOMIC_PLAN['tax_numerator'] // ECONOMIC_PLAN['tax_denominator']
                if tax:
                    account.cost('tax-' + stage, tax, ECONOMIC_PLAN['collection_hours'][stage])
                result['costs'][-1]['tax_microUSD'] = tax
                result['decisions'].append({'stage': stage, 'decision': 'ACCEPTED_COLLECTED',
                                            'collected_price_microUSD': offer['price_microUSD'],
                                            'tax_microUSD': tax})
                account.advance(ECONOMIC_PLAN['maturity_hours'][stage] + 1)
        result['snapshot'] = account.snapshot()
        expected_expenses = sum(row['total_microUSD'] + row.get('payment_fee_microUSD', 0) + row.get('tax_microUSD', 0) for row in result['costs'])
        if result['snapshot']['summary']['expenses'] != expected_expenses:
            raise ValueError('OUTLEARNING073_COMPLETE_MODELED_EXPENSE_RECONCILIATION_FAILED')
        result['expense_reconciliation'] = {'expected_microUSD': expected_expenses,
            'native_microUSD': result['snapshot']['summary']['expenses'], 'equal': True,
            'scope': 'Declared resource envelopes, explicit payment fees and paid modeled tax; actual bills unknown.'}
        result['K2_funding_scope'] = 'Incremental K2 resource reservations require EARNED funding; original seed equity may still back producer collateral and is not represented as earned money.'
        result['audit'] = account.audit()
        if not result['audit'].get('accepted'): raise ValueError('OUTLEARNING073_NATIVE_AUDIT_REFUSED')
        record = account.export()
    result['public_replay'] = audit_export(record, root=root, manifest=manifest)
    if not result['public_replay'].get('accepted'): raise ValueError('OUTLEARNING073_PUBLIC_REPLAY_REFUSED')
    result['record_sha256'] = digest(record)
    result['commercial_verdict'] = 'CONDITIONAL_COMPLETE_COST_SIM_PROFIT' if result['snapshot']['summary']['profit'] > 0 and all(row['decision'] == 'ACCEPTED_COLLECTED' for row in result['decisions']) else 'NO_CONNECTED_COMMERCIAL_SUCCESS'
    _write(output / 'ACCOUNT_PUBLIC.json', record)
    _write(output / 'RESULT.json', result)
    return result


def write_plan(path):
    if sum(ECONOMIC_PLAN['K1']['costs_USD'].values()) != 600 or sum(ECONOMIC_PLAN['K2']['costs_USD'].values()) != 250:
        raise ValueError('OUTLEARNING073_COST_ENVELOPE_SUM_CHANGED')
    _write(path, ECONOMIC_PLAN)


def run_all(root, output, manifest_factory, produce):
    root, output = Path(root).resolve(), Path(output).resolve()
    specs = [(scenario['id'], scenario, ECONOMIC_PLAN['opening_microUSD']) for scenario in ECONOMIC_PLAN['scenarios']]
    specs.append(('positive-1000-underfunded', ECONOMIC_PLAN['scenarios'][0], ECONOMIC_PLAN['underfunded_opening_microUSD']))
    specs.append(('positive-100k-reference', ECONOMIC_PLAN['scenarios'][0], ECONOMIC_PLAN['reference_opening_microUSD']))
    queue_path = output / 'QUEUE.json'
    expected = {'schema': 'outlearning073/native-operation-queue/v1', 'plan_sha256': digest(ECONOMIC_PLAN),
                'source_hashes': service._source_hashes(root),
                'cases': [{'directory': name, 'scenario': scenario, 'opening_microUSD': opening} for name, scenario, opening in specs],
                'recovery_scope': 'Completed scenarios are independently audited and reopened with original authority; an incomplete scenario is preserved and refuses automatic phase rerun.'}
    if output.exists():
        if not queue_path.is_file() or queue_path.is_symlink(): raise ValueError('OUTLEARNING073_EXISTING_QUEUE_REQUIRED')
        queue = strict_json(queue_path.read_bytes())
        if any(queue.get(key) != value for key, value in expected.items()): raise ValueError('OUTLEARNING073_QUEUE_SOURCE_OR_PLAN_CHANGED')
    else:
        output.mkdir(parents=True)
        queue = dict(expected, completed={})
        _write(queue_path, queue)
    results = []
    for name, scenario, opening in specs:
        target = output / name
        manifest = manifest_factory(name)
        if target.exists():
            result = _resume_completed(root, target, manifest, scenario, opening)
        else:
            if name in queue['completed']: raise ValueError('OUTLEARNING073_COMPLETED_ACCOUNT_MISSING')
            result = run_scenario(root, target, manifest, produce, scenario, opening=opening)
        result_digest = digest(result)
        if name in queue['completed'] and queue['completed'][name] != result_digest:
            raise ValueError('OUTLEARNING073_COMPLETED_RESULT_CHANGED')
        queue['completed'][name] = result_digest
        _write(queue_path, queue)
        results.append(result)
    compact = {'schema': 'outlearning073/native-economic-summary/v1', 'plan_sha256': digest(ECONOMIC_PLAN),
               'scope': ECONOMIC_PLAN['scope'], 'cases': [{k: row[k] for k in ['case_id','scenario','opening_microUSD','snapshot','commercial_verdict','record_sha256']} for row in results]}
    _write(output / 'SUMMARY.json', compact)
    return compact


def _resume_completed(root, output, manifest, scenario, opening):
    required = [output / name for name in ['RESULT.json', 'MANIFEST.json', 'ACCOUNT_PUBLIC.json',
                'private/account.sqlite', 'private/account.sqlite.connected-journal.json', 'private/account.sqlite.actions.jsonl']]
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise ValueError('OUTLEARNING073_INCOMPLETE_SCENARIO_PRESERVED_NO_AUTOMATIC_PHASE_RERUN')
    result = strict_json((output / 'RESULT.json').read_bytes())
    frozen_manifest = strict_json((output / 'MANIFEST.json').read_bytes())
    if frozen_manifest != manifest or result['scenario'] != scenario or result['opening_microUSD'] != opening or result['plan_sha256'] != digest(ECONOMIC_PLAN):
        raise ValueError('OUTLEARNING073_COMPLETED_SCENARIO_IDENTITY_CHANGED')
    record = strict_json((output / 'ACCOUNT_PUBLIC.json').read_bytes())
    if result['record_sha256'] != digest(record): raise ValueError('OUTLEARNING073_COMPLETED_RECORD_CHANGED')
    if not audit_export(record, root=root, manifest=manifest).get('accepted'):
        raise ValueError('OUTLEARNING073_COMPLETED_PUBLIC_AUDIT_REFUSED')
    with BusinessAccount(root, manifest, output / 'private/account.sqlite', opening=opening,
                         contract='outlearning073-' + scenario['id']) as account:
        if account.export() != record or account.snapshot() != result['snapshot']:
            raise ValueError('OUTLEARNING073_RESUME_NATIVE_HISTORY_CHANGED')
        account.audit()
    return result
