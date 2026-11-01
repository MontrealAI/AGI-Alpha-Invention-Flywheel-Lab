"""Source-frozen cooperation experiment through the existing native enterprise.

Developer-authored finite opportunity/means experiment, not a new simulator,
financial authority, autonomous invention claim, or real commerce. Run each arm
separately, then independently re-audit both before publishing a comparison.
"""
from __future__ import annotations
import argparse
import copy
import importlib.metadata
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

MICRO = 1_000_000
SCHEMA = 'agi-alpha/cooperation044/v1'
ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = {
    'schema': SCHEMA, 'seed': 341014, 'cohort_seed': 341014,
    'horizon_days': 42, 'opening_microUSD': 100_000 * MICRO,
    'customer_pool': 4, 'primitive_jobs_per_service': 32,
    'packet_jobs': 8, 'packet_rows': 12, 'inherited_operations_bundle_jobs': 8,
    'cases': ['central', 'no_demand'], 'arms': ['fixed_capacity', 'earned_capacity'],
    'evidence_role': 'EXPOSED_DEVELOPMENT_NOT_FRESH_CONFIRMATION',
    'stop': 'Run the registered finite horizon and drain; no seed replacement or early success stopping.',
    'scope': 'Native deterministic production and independent checking; authored buyers, prices and resource envelopes. No real customers or transactions.',
    'cost_scope': 'Native whole-business envelopes include setup, failed quotes, production, checking, fees, taxes, maintenance and investment invoices. Actual host/model/developer billing remains unknown.',
    'comparison': 'Matched complete-offer optimizer with capacity quantity zero versus at most two earned-funded complementary units. This is a targeted action-set ablation, not a strongest-unrestricted/global optimum claim.',
    'origin': 'Integration of released native complete-offer and capacity-menu mechanisms; developer-authored fixture and witness, not machine-invented algorithms.'
}


def _read(path):
    from commercial.ledger import strict_json
    return strict_json(Path(path).read_bytes())


def _write(path, value):
    from commercial.ledger import canonical
    from commercial.persistence import atomic_bytes
    atomic_bytes(Path(path), canonical(value) + b'\n')


def _digest(value):
    from commercial.ledger import digest
    return digest(value)


def configuration(manifest, case, arm, *, root=ROOT):
    from connected_enterprise.engine import fresh_account_config, validate_config
    from portfolio25.pricing import SCENARIOS
    if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:
        raise ValueError('REGISTERED_CASE_AND_ARM_REQUIRED')
    cfg, manifest = fresh_account_config(manifest, root=root)
    scenarios = copy.deepcopy(list(SCENARIOS))
    for scenario in scenarios:
        scenario.update(repeat_horizon=0, cost_shock=1)
    services = ['reconciliation', 'kpi_variance', 'evidence_matrix', 'receivables_packet']
    values = dict.fromkeys(services, 30 * MICRO)
    values['receivables_packet'] = 100 * MICRO
    packet = {
        'id': 'declared-capacity-opportunity', 'services': services,
        'price_grids': {s: [50 * MICRO] if s == 'receivables_packet' else [20 * MICRO] for s in services},
        'atoms': [{'weight_bps': 10000, 'budget_microUSD': 600 * MICRO, 'values': values}],
        'outside_options': [
            {'name': 'competent-human-packet', 'provider': 'human', 'service_id': 'receivables_packet', 'price': 80 * MICRO, 'quality_bps': 10000, 'delay_cost': 0},
            {'name': 'autonomous-packet', 'provider': 'rival', 'service_id': 'receivables_packet', 'price': 65 * MICRO, 'quality_bps': 10000, 'delay_cost': 0},
            {'name': 'self-service-packet', 'provider': 'self_service', 'service_id': 'receivables_packet', 'price': 15 * MICRO, 'quality_bps': 6000, 'delay_cost': 5 * MICRO}
        ]
    }
    basic = {
        'id': 'declared-basic-work', 'services': services[:3],
        'price_grids': {s: [20 * MICRO] for s in services[:3]},
        'atoms': [{'weight_bps': 10000, 'budget_microUSD': 600 * MICRO, 'values': dict.fromkeys(services[:3], 40 * MICRO)}],
        'outside_options': [
            {'name': 'human-basic', 'provider': 'human', 'service_id': 'reconciliation', 'price': 30 * MICRO, 'quality_bps': 10000, 'delay_cost': 0},
            {'name': 'self-service-basic', 'provider': 'self_service', 'service_id': 'reconciliation', 'price': 15 * MICRO, 'quality_bps': 7500, 'delay_cost': 0}
        ]
    }
    if case == 'no_demand':
        for profile in (basic, packet):
            profile['atoms'][0]['values'] = dict.fromkeys(profile['services'], 0)
    indexes = {s: {ident: i for i, ident in enumerate(sorted(j['id'] for j in manifest['jobs'] if j['service_id'] == s))} for s in sorted({j['service_id'] for j in manifest['jobs']})}
    requested = {f'SIM-customer-{i:03d}': [j['id'] for j in manifest['jobs'] if indexes[j['service_id']][j['id']] % 4 == i] for i in range(4)}
    cfg.update(horizon_days=PROTOCOL['horizon_days'], customer_pool=4, opening=PROTOCOL['opening_microUSD'],
               initial_slots=1, maximum_slots=3, arrival_bps=10000, retention_bps=10000,
               nonpayment_bps=0, capacity_price=3 * MICRO, clearing_hours=24)
    cfg['strategic_policy'] = {
        'schema': 'connected-strategic-commerce/v1',
        'public_basis': 'Exposed finite public synthetic request distributions; not actual demand, private atoms or future draws.',
        'price_bps': [5500, 6999, 8999, 9299, 9999], 'rival_price_bps': [5500, 7000, 9000, 10000],
        'rival_cost_bps': 3000, 'rival_response': 'observed_quote', 'scenarios': scenarios,
        'demand_model': 'connected_range',
        'connected_beliefs': {s['id']: {'min_value_bps': 7000, 'max_value_bps': 21000, 'min_budget_microUSD': 0,
                                      'max_budget_microUSD': 600 * MICRO, 'rival_available_bps': 8000} for s in scenarios}
    }
    cfg['strategic_allocation_policy'] = {
        'max_customers': 4,
        'risk': {'scenarios': {'baseline': 5000, 'ai_parity_price_war': 3000, 'differentiated_verified_service': 2000},
                 'worst_loss_limit': cfg['opening'], 'downside_penalty_bps': 2500, 'max_states': 262144,
                 'authorized_allocation': cfg['opening'], 'interactions': []},
        'capacity_menu': {'max_quantity': 2 if arm == 'earned_capacity' else 0,
                          'opportunity_delay_hours': 24, 'retention_bps': 10000}
    }
    cfg['complete_offer_policy'] = {'schema': 'connected-complete-offer-market/v1', 'selection': 'menu',
                                    'profiles': [basic, packet], 'requested_jobs': requested}
    return validate_config(cfg), manifest


def _links(order):
    many = order.get('capacity_source_plan_ids', [])
    if not isinstance(many, list):
        raise ValueError('INVALID_CAPACITY_PLAN_LINKS')
    items = [order.get('acquisition_source_plan_id'), order.get('capacity_source_plan_id'), *many]
    if any(p is not None and (not isinstance(p, str) or not p) for p in items):
        raise ValueError('INVALID_SOURCE_PLAN_ID')
    # Repeated IDs represent separately used units of ONE purchased contract.
    return {p for p in items if p is not None}


def attributed_component(result, initial_plans):
    """Close the linked order/investment component; count every loss and invoice."""
    plans = {i['plan_id']: i for i in result['investments']}
    if len(plans) != len(result['investments']):
        raise ValueError('DUPLICATE_NATIVE_INVESTMENT_PLAN')
    required = set(initial_plans)
    while True:
        orders = [o for o in result['orders'] if required & _links(o)]
        expanded = required | set().union(*(_links(o) for o in orders)) if orders else required
        if expanded == required:
            break
        required = expanded
    if not required or any(p not in plans for p in required):
        raise ValueError('MISSING_NATIVE_ENABLER')
    if any(plans[p]['funding_receipt'].get('funding') != 'EARNED' for p in required):
        raise ValueError('UNRESTRICTED_EARNED_FUNDING_REQUIRED')
    invoice = sum(plans[p]['cost'] for p in required)
    contribution = sum((o['price'] if o['outcome'] == 'SETTLED' and o['collection_time'] is not None else 0)
                       - o['complete_cost'] for o in orders)
    return {'plan_ids': sorted(required), 'order_ids': sorted(o['id'] for o in orders),
            'all_enabler_invoices_microUSD': invoice,
            'order_contribution_including_losses_microUSD': contribution,
            'net_attributed_contribution_microUSD': contribution - invoice,
            'scope': 'Source-linked component contribution, NOT full-business profit or independently identified causal uplift.'}


def _inventory_identity(manifest):
    """Only measured preparation CPU is nondeterministic, not workload or billing."""
    value = copy.deepcopy(manifest)
    timing = value.get('resource_receipt', {}).pop('process_cpu_seconds', None)
    if timing is not None:
        import math
        if type(timing) not in (int, float) or not math.isfinite(timing) or timing < 0:
            raise ValueError('VALID_PREPARATION_CPU_TELEMETRY_REQUIRED')
    return _digest(value)


def _decision_witness(result, successor, investments):
    """Require recorded prospective choices, not a retrospective causal story."""
    plans = result.get('joint_actions', {})
    decisions = []
    for investment in investments:
        matching = [p for p in plans.values() if p['time'] == investment['purchased_time']
                    and investment['id'] in p['allocation']['decision']['selected']]
        if len(matching) != 1:
            raise ValueError('RECORDED_PREINVESTMENT_SELECTION_REQUIRED')
        plan = matching[0]
        recourse = plan.get('capacity_recourse', {}).get('recourse', [])
        selected = [row for row in recourse if row.get('quantity') == investment.get('capacity_units')
                    and any(w['job_id'] == successor['job_id'] for w in row.get('selected_work', []))]
        if investment['kind'] != 'capacity' or len(selected) != 1:
            raise ValueError('PROSPECTIVE_SUCCESSOR_CAPACITY_LINK_REQUIRED')
        decisions.append({'decision_id': plan['id'], 'time': plan['time'],
            'observed_need_ids': plan['observed_need_ids'],
            'selected_action_ids': plan['allocation']['decision']['selected'],
            'states_evaluated': plan['allocation']['decision']['states_evaluated'],
            'optimality_scope': plan['allocation']['decision']['optimality_scope'],
            'capacity_alternatives': [{k: row[k] for k in ('quantity', 'invoice', 'slots', 'scenario_net', 'selected_work', 'status')} for row in recourse],
            'forecast_scope': 'Public-model planning values only; none is booked as a receipt.'})
    delivery = plans.get(successor.get('joint_allocation_sha256'))
    if not delivery or delivery['time'] != successor['qualified_time'] or successor.get('joint_option_id') not in delivery['allocation']['decision']['selected']:
        raise ValueError('RECORDED_SUCCESSOR_DELIVERY_SELECTION_REQUIRED')
    choice = [d for d in result['decisions'] if d.get('kind') == 'offer'
              and d.get('joint_allocation_sha256') == successor.get('joint_allocation_sha256')
              and d.get('joint_option_id') == successor.get('joint_option_id')
              and d.get('customer_id') == successor['customer_id']]
    if len(choice) != 1 or choice[0].get('chosen') is not True or choice[0].get('buyer_choice') != 'us':
        raise ValueError('VOLUNTARY_NATIVE_SUCCESSOR_PURCHASE_REQUIRED')
    return {'investment_decisions': decisions, 'successor_decision_id': delivery['id'],
            'successor_choice': 'us', 'outside_options': choice[0]['market_context']['profile']['outside_options'],
            'participation_scope': 'Synthetic buyer chose the completed outcome against declared outside offers and refusal; not real consent.'}


def sequence_witness(result):
    """Deterministic evidence extraction. Caller MUST independently audit first."""
    orders = sorted(result['orders'], key=lambda o: (o['qualified_time'], o['id']))
    for second in orders:
        required = _links(second)
        if (not required or second['outcome'] != 'SETTLED' or second['collection_time'] is None
                or second['acceptance_time'] is None or not second['service_receipt'].get('accepted')
                or second.get('capacity_units', 1) <= result['config']['initial_slots']):
            continue
        component = attributed_component(result, required)
        investments = [i for i in result['investments'] if i['plan_id'] in component['plan_ids']]
        if any(i['activation_time'] > second['qualified_time']
               or second['production_time'] >= i['expiry_time'] for i in investments):
            continue
        purchase = min(i['purchased_time'] for i in investments)
        prior = [o for o in orders if o['outcome'] == 'SETTLED' and o['collection_time'] is not None
                 and o['acceptance_time'] is not None and o['service_receipt'].get('accepted') is True
                 and o['acceptance_time'] <= o['collection_time'] < purchase
                 and o['price'] > o['complete_cost'] and o['offer']['service_id'] != second['offer']['service_id']]
        if not prior or component['net_attributed_contribution_microUSD'] <= 0:
            continue
        first = max(prior, key=lambda o: (o['collection_time'], o['id']))
        reserves = [a for a in result['owned_account']['ledger']['actions']
                    if a['op'] == 'reserve' and a.get('args', {}).get('id') in component['plan_ids']]
        if len(reserves) != len(component['plan_ids']):
            raise ValueError('ONE_NATIVE_RESERVATION_PER_ENABLER_REQUIRED')
        for investment in investments:
            reserve = next(a for a in reserves if a['args']['id'] == investment['plan_id'])
            if reserve['args']['amount'] != investment['cost'] or reserve['day'] != investment['purchased_time'] or min(reserve['before']['available'], reserve['before']['unrestrictedEarned']) < investment['cost']:
                raise ValueError('PRESENT_EARNED_LIQUIDITY_REQUIRED')
        prospective = _decision_witness(result, second, investments)
        return {
            'prospective_decisions': prospective,
            'first_order': first['id'], 'first_service': first['offer']['service_id'],
            'first_collection_hour': first['collection_time'], 'first_collected_microUSD': first['price'],
            'first_order_contribution_microUSD': first['price'] - first['complete_cost'],
            'constraint': 'Actual complete-outcome capacity requirement exceeds original supplier capacity.',
            'initial_capacity_units': result['config']['initial_slots'],
            'required_successor_capacity_units': second['capacity_units'],
            'investments': [{k: i[k] for k in ('id', 'plan_id', 'cost', 'purchased_time', 'activation_time', 'expiry_time', 'capacity_units')} for i in investments],
            'unrestricted_earned_before_each_reservation_microUSD': [a['before']['unrestrictedEarned'] for a in reserves],
            'funding': 'EARNED', 'funding_scope': 'Native aggregate earned pool; no claim that one fungible earlier receipt uniquely funded the invoice.',
            'successor_order': second['id'], 'successor_service': second['offer']['service_id'],
            'successor_job': second['job_id'], 'successor_acceptance_hour': second['acceptance_time'],
            'successor_collection_hour': second['collection_time'], 'successor_collected_microUSD': second['price'],
            'successor_complete_order_cost_microUSD': second['complete_cost'],
            'successor_order_contribution_microUSD': second['price'] - second['complete_cost'],
            'successor_artifact_sha256': second['service_receipt']['actual_execution_artifact_sha256'],
            'higher_order_contribution': second['price'] - second['complete_cost'] > first['price'] - first['complete_cost'],
            'component': component,
            'scope': 'Native financed cross-service continuation under the registered model; not novel invention or global economic optimality.'
        }
    return None


def _new_directory(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('NORMALIZED_NON_SYMLINK_OUTPUT_REQUIRED')
    path.mkdir(parents=True, exist_ok=False)
    return path


def prepare(output, case, arm):
    from adaptive_enterprise.instruments import prepare_complete_offer_services
    from connected_enterprise.runner import source_paths, identity
    if case not in PROTOCOL['cases'] or arm not in PROTOCOL['arms']:
        raise ValueError('REGISTERED_CASE_AND_ARM_REQUIRED')
    output = _new_directory(output)
    frozen = output / 'source'
    frozen.mkdir()
    for name in source_paths(ROOT):
        source, target = ROOT / name, frozen / name
        if source.is_symlink():
            raise ValueError('SOURCE_SYMLINK_REFUSED')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if identity(ROOT) != identity(frozen):
        raise ValueError('SOURCE_FREEZE_NOT_IDENTICAL')
    manifest = prepare_complete_offer_services(frozen, 'workloads/cooperation044', cohort_seed=PROTOCOL['cohort_seed'],
        jobs_per_service=PROTOCOL['primitive_jobs_per_service'], packet_jobs=PROTOCOL['packet_jobs'], packet_rows=PROTOCOL['packet_rows'])
    cfg, manifest = configuration(manifest, case, arm, root=frozen)
    plan = {'schema': SCHEMA, 'protocol': PROTOCOL, 'case': case, 'arm': arm, 'source': identity(frozen),
            'config': cfg, 'manifest': manifest}
    _write(output / 'REGISTERED.json', plan)
    return output


def _plan(output):
    from connected_enterprise.runner import identity
    output = Path(output).absolute()
    if '..' in output.parts or any(p.is_symlink() for p in [output, *output.parents]):
        raise ValueError('NORMALIZED_NON_SYMLINK_OUTPUT_REQUIRED')
    plan = _read(output / 'REGISTERED.json')
    if plan.get('schema') != SCHEMA or plan.get('protocol') != PROTOCOL:
        raise ValueError('REGISTERED_PROTOCOL_CHANGED')
    source = output / 'source'
    if identity(source) != plan['source'] or identity(ROOT) != plan['source']:
        raise ValueError('EXECUTING_AND_FROZEN_SOURCE_MUST_MATCH')
    cfg, manifest = configuration(plan['manifest'], plan['case'], plan['arm'], root=source)
    if cfg != plan['config'] or manifest != plan['manifest']:
        raise ValueError('REGISTERED_MARKET_OR_MANIFEST_CHANGED')
    return output, plan


def certify(output):
    from connected_enterprise.verify import audit
    output, plan = _plan(output)
    result = _read(output / 'private' / 'RESULT.json')
    if result['source'] != plan['source'] or result['config'] != plan['config'] or result['seed'] != PROTOCOL['seed'] or result['arm'] != 'competitive_growth':
        raise ValueError('NATIVE_RUN_REGISTRATION_MISMATCH')
    checked = audit(output / 'source', plan['manifest'], result)
    if checked.get('accepted') is not True or result['complete'] is not True:
        raise ValueError('COMPLETE_INDEPENDENT_NATIVE_AUDIT_REQUIRED')
    summary = result['summary']
    if summary['profit'] != summary['revenue'] - summary['expenses']:
        raise ValueError('PROFIT_RECONCILIATION_FAILED')
    covered = (summary['payables'] == 0 and summary['reservedInvestment'] == 0
        and summary['cash'] >= sum(summary[k] for k in ('custodyReserve', 'tailReserve', 'workingCapital'))
        and not summary['investmentStopped'])
    witness = sequence_witness(result)
    return {'schema': SCHEMA, 'case': plan['case'], 'arm': plan['arm'], 'protocol_sha256': _digest(PROTOCOL),
        'source_sha256': plan['source']['sha256'], 'registration_sha256': _digest(plan), 'result_sha256': _digest(result),
        'seed': PROTOCOL['seed'], 'scope': PROTOCOL['scope'], 'evidence_role': PROTOCOL['evidence_role'],
        'cost_scope': PROTOCOL['cost_scope'], 'initial_capital_microUSD': plan['config']['opening'],
        'horizon_days': plan['config']['horizon_days'], 'independent_native_audit_accepted': True,
        'complete': True, 'paid_accepted_orders': result['paid_jobs'], 'summary': summary,
        'obligations_covered': covered, 'sequence': witness,
        'connected_sequence_established': bool(witness and witness['higher_order_contribution'] and summary['profit'] > 0 and covered),
        'new_invention_established': False, 'better_inventor_established': False, 'real_customers': 0,
        'real_collections_microUSD': 0, 'actual_host_model_developer_billing': None,
        'runtime': {'python': sys.version, 'cryptography': importlib.metadata.version('cryptography')}}


def execute(output):
    from connected_enterprise.engine import run_world
    output, plan = _plan(output)
    start, wall = time.process_time(), time.monotonic()
    try:
        run_world(output / 'source', plan['manifest'], plan['config'], PROTOCOL['seed'], 'competitive_growth',
                  output / 'private', source=plan['source'])
        public = certify(output)
        (output / 'public').mkdir(exist_ok=True)
        _write(output / 'public' / 'SUMMARY.json', public)
        _write(output / 'public' / 'LESSON.json', {
            'schema': 'agi-alpha/cooperation-applicability044/v1', 'source_sha256': public['source_sha256'],
            'registered_case': plan['case'], 'supported_sequence': public['connected_sequence_established'],
            'when_to_test': 'Profitable accepted smaller work, an independently accepted larger requested outcome, missing complementary capacity and sufficient unrestricted earned funds.',
            'mechanism': 'Joint complete-offer selection plus existing costed capacity-menu enumeration; reserve only from present native funds, then reobserve buyer choice.',
            'avoid': 'No demand, negative full costs, missing earnings, expired capacity, unverified work, omitted linked losses or hidden competing alternatives.',
            'authority': 'NONE', 'autonomous_discovery_claim': False,
            'scope': 'Inert applicability record. It neither moves funds nor proves successor-method improvement.'})
        return public
    finally:
        _write(output / 'RESOURCE.json', {'process_cpu_seconds': time.process_time() - start,
            'wall_seconds': time.monotonic() - wall, 'max_rss_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'scope': 'This process only; telemetry is not monetary billing.'})


def compare(control, candidate):
    a, b = certify(control), certify(candidate)
    ca, cb = _read(Path(control) / 'REGISTERED.json'), _read(Path(candidate) / 'REGISTERED.json')
    left, right = copy.deepcopy(ca['config']), copy.deepcopy(cb['config'])
    left['strategic_allocation_policy']['capacity_menu']['max_quantity'] = 0
    right['strategic_allocation_policy']['capacity_menu']['max_quantity'] = 0
    if a['arm'] != 'fixed_capacity' or b['arm'] != 'earned_capacity' or a['case'] != b['case'] or a['source_sha256'] != b['source_sha256'] or left != right or _inventory_identity(ca['manifest']) != _inventory_identity(cb['manifest']):
        raise ValueError('MATCHED_SOURCE_MARKET_CAPITAL_AND_INVENTORY_REQUIRED')
    delta = b['summary']['profit'] - a['summary']['profit']
    return {'schema': SCHEMA, 'control': a, 'candidate': b, 'profit_delta_microUSD': delta,
            'status': 'DEMONSTRATED_IN_EXPOSED_SIMULATION' if b['connected_sequence_established'] and delta > 0 else 'NOT_ESTABLISHED',
            'scope': PROTOCOL['comparison'], 'annual_profit_claim': None, 'global_optimality_claim': False,
            'physical_expansion_claim': False, 'real_commerce_claim': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run'); run.add_argument('--output', type=Path, required=True)
    run.add_argument('--case', choices=PROTOCOL['cases'], default='central')
    run.add_argument('--arm', choices=PROTOCOL['arms'], required=True)
    internal = sub.add_parser('_execute'); internal.add_argument('--output', type=Path, required=True)
    verify = sub.add_parser('verify'); verify.add_argument('--output', type=Path, required=True)
    comp = sub.add_parser('compare'); comp.add_argument('--control', type=Path, required=True)
    comp.add_argument('--candidate', type=Path, required=True); comp.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'run':
        output = prepare(args.output, args.case, args.arm)
        subprocess.run([sys.executable, '-m', 'connected_enterprise.cooperation044', '_execute', '--output', str(output)],
                       cwd=output / 'source', check=True, timeout=180)
        report = _read(output / 'public' / 'SUMMARY.json')
        print(json.dumps({'status': 'COMPLETED', 'case': report['case'], 'arm': report['arm'],
            'profit_microUSD': report['summary']['profit'], 'sequence': report['connected_sequence_established']}))
    elif args.command == '_execute':
        execute(args.output)
    elif args.command == 'verify':
        report = certify(args.output)
        stored = _read(args.output / 'public' / 'SUMMARY.json')
        if report != stored:
            raise ValueError('STORED_PUBLIC_SUMMARY_CHANGED')
        print(json.dumps({'accepted': True, 'case': report['case'], 'arm': report['arm']}))
    else:
        if args.report.exists():
            raise ValueError('NEW_COMPARISON_REPORT_PATH_REQUIRED')
        report = compare(args.control, args.candidate); _write(args.report, report)
        print(json.dumps({k: report[k] for k in ('status', 'profit_delta_microUSD', 'scope')}))


if __name__ == '__main__':
    main()
