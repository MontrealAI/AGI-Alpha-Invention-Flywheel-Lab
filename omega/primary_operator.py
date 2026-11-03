"""One resumable, prefix-faithful conditional account; never original recovery."""
from __future__ import annotations

from collections import defaultdict
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, audit_journal, source_paths_for_manifest
from connected_enterprise.scale import trailing_profit
from experiments.commerce006 import PINS
from omega import competitive, operate, product, strategy, successor

MICRO = 1_000_000
CENT = 10_000
SELECTION = 'campaign/omega-corrected-232221a5/PRIMARY.json'
PROTOCOL = 'campaign/omega-corrected-232221a5/PROTOCOL.md'
HISTORY = 'campaign/omega-water-20261103/HISTORICAL_RESULT.json'
HISTORY_SHA256 = '811093877ce65ea5cde27d10b1091916137729e6dcfb2ef82011b16a079afdb0'
HISTORY_ACTIONS = 'abd9b0b7fe7339684b9099f4e8c56c99a09bf24503059767bc62bdf8d24688ef'
TASK_IDS = ['quality-successor', 'withdrawal', 'external-unavailable']


def read(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('REGULAR_PRIMARY_INPUT_REQUIRED')
    raw = path.read_bytes()
    if len(raw) > 24_000_000:
        raise ValueError('BOUNDED_PRIMARY_INPUT_REQUIRED')
    return strict_json(raw)


def write(path, value):
    atomic_bytes(path, canonical(value) + b'\n')


def history(root):
    path = Path(root) / HISTORY
    if hashlib.sha256(path.read_bytes()).hexdigest() != HISTORY_SHA256:
        raise ValueError('EXACT_PUBLISHED_HISTORICAL_EVIDENCE_REQUIRED')
    historical = read(path)
    if (digest(historical['seller_registration']) != historical['seller_public_replay']['registration_sha256']
            or historical['seller_public_replay']['native_actions_sha256'] != HISTORY_ACTIONS
            or historical['seller_registration']['opening_microUSD'] != 100_000 * MICRO):
        raise ValueError('HISTORICAL_REGISTRATION_BINDING_CHANGED')
    return historical


def history_commands(root):
    rows = history(root)['seller_registration']['cash_cost_schedule']
    commands = [{'op': 'cost', 'args': {'id': r['id'], 'amount': r['microUSD']}, 'hour': r['hour']} for r in rows]
    commands.append({'op': 'cost', 'args': {'id': 'registered-year-end-observation', 'amount': 0}, 'hour': 8759})
    if len(commands) != 42:
        raise ValueError('EXACT_FORTY_TWO_HISTORICAL_ACTIONS_REQUIRED')
    return commands


def source_hashes(root):
    root = Path(root)
    names = set(source_paths_for_manifest({'schema': product.SCHEMA})) | set(PINS)
    names |= {p.relative_to(root).as_posix() for p in (root / 'omega').glob('*.py')}
    names |= {SELECTION, PROTOCOL, HISTORY}
    return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in sorted(names)}


def game_for(selection):
    profile = selection['cost_profile']
    if profile not in {'autonomous_low', 'autonomous_central', 'autonomous_high'}:
        raise ValueError('REGISTERED_AUTONOMOUS_COST_PROFILE_REQUIRED')
    return competitive.make_game(cost_scenario=profile.split('_', 1)[1], operation='autonomous')


def registration(root, selection=None):
    selected = read(Path(root) / SELECTION) if selection is None else copy.deepcopy(selection)
    if (canonical(selected) != canonical(read(Path(root) / SELECTION))
            or selected['opening_microUSD'] != 100_000 * MICRO
            or selected['historical_actions_sha256'] != HISTORY_ACTIONS
            or selected['operating_start_hour'] != 8760 or selected['operating_end_hour_exclusive'] != 17520
            or len(selected['reach']) != 4 or any(type(x) is not bool for x in selected['reach'])
            or selected['policy_mode'] not in competitive.MODES
            or selected['prospective_successor_tasks'] != len(TASK_IDS)
            or type(selected['successor_task_value_microUSD']) is not int or selected['successor_task_value_microUSD'] < 0
            or type(selected['income_tax_bps']) is not int or not 0 <= selected['income_tax_bps'] <= 10000):
        raise ValueError('EXACT_PRIMARY_HORIZON_CAPITAL_AND_SCENARIO_REQUIRED')
    game = game_for(selected)
    if selected['world_id'] not in {w.id for w in game.worlds}:
        raise ValueError('REGISTERED_WORLD_REQUIRED')
    old = history(root)
    return {'schema': 'omega/primary-counterpart-registration/v1', 'selection': selected,
            'source_hashes': source_hashes(root), 'competitive_registration': competitive.registration(),
            'game': strategy.model_disclosure(game), 'historical_record_sha256': HISTORY_SHA256,
            'historical_noncash_founder_opportunity_microUSD': old['seller_registration']['noncash_founder_opportunity_cost']['microUSD'],
            'historical_account_authentication': 'UNAVAILABLE; ORIGINAL ACCOUNT NOT OPENED OR RECREATED',
            'account_role': 'ONE DISTINCT RECONSTRUCTED COUNTERPART; HISTORICAL ACTIONS EXACT, ORIGINAL IDENTITY NOT CLAIMED',
            'successor_decision': {'future_task_ids': TASK_IDS, 'direct_each_microUSD': 2_100_000,
                                   'kit_construction_microUSD': 2_100_000, 'reuse_qualification_each_microUSD': 1_000_000,
                                   'task_value_microUSD': selected['successor_task_value_microUSD'],
                                   'selected_method': 'ORDINARY_EQUIVALENT_REUSE', 'forced_investment': False,
                                   'basis': 'Prospectively authored resource envelope, no market or actual-billing inference'},
            'tax_policy': 'Authored income-tax sensitivity on positive corrected-year native accounting profit; subtracted from successor funding availability and expensed at final hour. This is not a native segregated tax reserve during commerce.',
            'actual_complete_cost_profit_microUSD': None}


def public_observation(state, summary, selection):
    return {'quarter': state['quarter'], 'available_cents': summary['available'] // CENT,
            'built_products': list(state['built']), 'content_available': state['successor_status'] == 'QUALIFIED',
            'research_signal': state['signal'], 'observed_delivery_outcome': state['outcome'],
            'founder_minutes_available': selection['founder_minutes_per_quarter']}


def check_joint_budgets(row):
    groups = defaultdict(list)
    for order in row['orders']:
        if order['status'] in {'accepted', 'rejected_refunded'}:
            groups[order['buyer_group_id']].append(order)
    choices = {b['buyer_group_id']: b for b in row['buyer_decisions']}
    for group, orders in groups.items():
        buyer = choices[group]
        if (buyer.get('synthetic_consent') is not True or buyer['provider'] != 'us'
                or sorted(o['product'] for o in orders) != sorted(buyer['selected_package'])
                or len({o['product'] for o in orders}) != len(orders)
                or sum(o['price_cents'] for o in orders) != buyer['total_price_cents']
                or buyer['spent_before_cents'] + buyer['total_price_cents'] > buyer['budget_cents']):
            raise ValueError('WHOLE_BUYER_PACKAGE_CONSENT_AND_BUDGET_REQUIRED')
    return True


def _manifest(source, game, destination=None):
    products, outcomes, sessions, index = [], [], [], {}
    for quarter in range(4):
        for prospect in range(3):
            for kind in strategy.PRODUCTS:
                for accepted in (False, True):
                    index[f'{quarter}:{prospect}:{kind}:{int(accepted)}'] = len(products)
                    products.append(kind); outcomes.append({'accepted': accepted})
                    sessions.append(f'quarter-{quarter}' if kind == 'group_webinar' else None)
    manifest = product.prepare_manifest(source, destination or source / 'products', jobs=products, outcomes=outcomes,
                                        costs=operate.costs(game), session_ids=sessions, hypothetical_rights=True)
    return manifest, index


def validate_manifest(source, game, manifest, index):
    """Rebuild the registered catalog using the existing typed product constructor."""
    source = Path(source)
    if (manifest.get('native_engine') != 'exact-prospective-v2' or manifest.get('claim_window_hours') != 720
            or manifest.get('residual_bps') != 100):
        raise ValueError('REGISTERED_PRODUCT_TERMS_CHANGED')
    with tempfile.TemporaryDirectory(prefix='primary-catalog-check-', dir=source) as directory:
        expected, expected_index = _manifest(source, game, Path(directory) / 'products')
        for job in expected['jobs']:
            job['input'] = 'products/' + Path(job['input']).name
            job['output'] = 'products/' + Path(job['output']).name
    if canonical(manifest) != canonical(expected) or canonical(index) != canonical(expected_index):
        raise ValueError('REGISTERED_FIXED_PRODUCT_CATALOG_CHANGED')
    product.load_contracts(source, manifest)
    return True


def fixed_commands(decision, ident, hour):
    return [{'kind': 'native', 'op': 'cost', 'args': {'id': ident + ':' + name, 'amount': amount * CENT}, 'hour': hour}
            for name, amount in decision['fixed_costs_cents'].items()]


def order_commands(row, manifest, index, offset):
    check_joint_budgets(row)
    commands, groups, paid = [], set(), set()
    hour = offset + row['hour']
    for order in row['orders']:
        if order['status'] not in {'accepted', 'rejected_refunded'}:
            continue
        accepted = order['status'] == 'accepted'
        key = f"{row['quarter']}:{order['prospect']}:{order['product']}:{int(accepted)}"
        job = manifest['jobs'][index[key]]
        ident = f"q{row['quarter']}-p{order['prospect']}-{order['product']}"
        group = order['buyer_group_id']
        if group not in groups:
            peers = [o for o in row['orders'] if o['buyer_group_id'] == group]
            requirement = sum(o['price_cents'] + o['cost_cents'] + 20 for o in peers) * CENT
            commands.append({'kind': 'group_preflight', 'required': requirement, 'group': group, 'hour': hour})
            groups.add(group)
        for cid, amount in product.cost_rows(job, ident, manifest['costs']):
            if cid not in paid:
                commands.append({'kind': 'native', 'op': 'cost', 'args': {'id': cid, 'amount': amount}, 'hour': hour})
                paid.add(cid)
        terms = product.terms_for(manifest, ident, job['product'], hour)
        for op, args in [('register_terms', {'id': ident + ':terms', 'terms': terms}),
                         ('wallet', {'buyer': ident + ':wallet', 'amount': order['price_cents'] * CENT}),
                         ('offer', {'id': ident, 'buyer': ident + ':wallet', 'price': order['price_cents'] * CENT,
                                    'job_id': job['id'], 'deadline': hour + 24, 'terms_id': ident + ':terms'})]:
            commands.append({'kind': 'native', 'op': op, 'args': args, 'hour': hour})
        for action in ['consent', 'fund']:
            commands.append({'kind': 'native', 'op': 'event', 'args': {'id': ident, 'action': action, 'event_id': ident + ':' + action}, 'hour': hour})
        commands.append({'kind': 'produce', 'job': job['id'], 'accepted': accepted, 'hour': hour})
        if accepted:
            commands.append({'kind': 'prepare', 'order': ident, 'job': job['id'], 'hour': hour})
        action = 'release' if accepted else 'refund'
        commands.append({'kind': 'native', 'op': 'event', 'args': {'id': ident, 'action': action, 'event_id': ident + ':' + action}, 'hour': hour})
    commands.append({'kind': 'mature', 'hour': offset + row['maturity_hour']})
    return commands


def _perform(account, command, source, manifest, interrupt_after):
    kind = command['kind']
    if kind == 'native':
        if command['op'] == 'cost' and account.snapshot()['summary']['available'] < command['args']['amount']:
            existing = [e for e in account.export()['ledger']['actions'] if e['op'] == 'cost' and e['args']['id'] == command['args']['id']]
            if not existing:
                raise ValueError('CURRENT_NATIVE_CASH_BEFORE_SELECTED_COST_REQUIRED')
        account.execute(command['op'], command['args'], command['hour'])
        if interrupt_after == 'first-fund' and command['op'] == 'event' and command['args']['action'] == 'fund':
            os._exit(75)
    elif kind == 'group_preflight':
        if account.snapshot()['summary']['available'] < command['required']:
            raise ValueError('WHOLE_PACKAGE_CURRENT_CASH_PREFLIGHT_FAILED')
    elif kind == 'produce':
        artifact = product.produce(source, manifest, command['job'])
        accepted = product.check_delivery(source, manifest, command['job'], artifact)['accepted']
        if accepted is not command['accepted']:
            raise ValueError('REGISTERED_ENVIRONMENT_AND_PRODUCT_ACCEPTANCE_DIVERGED')
    elif kind == 'prepare':
        artifact = product.delivery(source, manifest, command['job'])
        account.execute('event', {'id': command['order'], 'action': 'prepare', 'event_id': command['order'] + ':prepare',
                                 'artifact_sha256': digest(artifact)}, command['hour'])
    elif kind == 'mature':
        account.advance_financial(command['hour'])
    else:
        raise ValueError('REGISTERED_PRIMARY_COMMAND_REQUIRED')


def successor_choice(summary, registration, plan):
    policy = registration['successor_decision']
    count = len(policy['future_task_ids'])
    if plan['quoted_construction_max_microUSD'] != policy['kit_construction_microUSD']:
        raise ValueError('REGISTERED_SUCCESSOR_QUOTE_CHANGED')
    direct = count * policy['direct_each_microUSD']
    cost = plan['quoted_construction_max_microUSD'] + count * policy['reuse_qualification_each_microUSD']
    value = count * policy['task_value_microUSD']
    corrected_profit = summary['profit'] + 24_800 * MICRO
    tax_reserve = max(0, corrected_profit) * registration['selection']['income_tax_bps'] // 10000
    available = min(summary['available'], summary['unrestrictedEarned']) - tax_reserve
    return {'method': 'ORDINARY_EQUIVALENT_REUSE', 'direct_microUSD': direct, 'complete_cost_microUSD': cost,
            'expected_resource_saving_microUSD': direct - cost, 'tax_reserve_microUSD': tax_reserve,
            'authored_task_value_microUSD': value, 'withdrawal_net_microUSD': 0,
            'direct_expected_net_microUSD': value - direct, 'reuse_expected_net_microUSD': value - cost,
            'earned_available_after_tax_reserve_microUSD': max(0, available),
            'selected': value > cost and cost < direct and available >= cost and not summary['investmentStopped'],
            'basis': 'Authored prospective task utility and resource envelope; withdrawal competes, utility is not income; ordinary reuse ties'}


def check_successor_uses(uses, specification, policy):
    ids = policy['future_task_ids']
    if (uses.get('artifact_sha256') != specification['artifact_sha256'] or uses.get('task_ids') != ids
            or uses.get('case_count') != len(ids) or uses.get('accepted_case_count') != len(ids)
            or [row.get('task_id') for row in uses.get('tasks', [])] != ids
            or uses.get('task_cost_each_microUSD') != policy['reuse_qualification_each_microUSD']
            or uses.get('total_task_cost_microUSD') != len(ids) * policy['reuse_qualification_each_microUSD']):
        raise ValueError('SUCCESSOR_FUTURE_TASK_ACCEPTANCE_REJECTED')
    for row in uses['tasks']:
        if (row.get('acceptance', {}).get('accepted') is not True
                or row['acceptance'].get('id') != row['task_id']
                or row.get('result_sha256') != digest(row.get('result'))
                or not isinstance(row.get('request_sha256'), str) or len(row['request_sha256']) != 64):
            raise ValueError('SUCCESSOR_FUTURE_TASK_ACCEPTANCE_REJECTED')
    return True


def stable_evidence(value):
    """Timing telemetry varies across independent executions; output facts must not."""
    if isinstance(value, dict):
        return {k: stable_evidence(v) for k, v in value.items() if k != 'execution'}
    if isinstance(value, list):
        return [stable_evidence(v) for v in value]
    return value


def successor_request(intent, reg):
    work = {'specification_sha256': digest(intent['specification']), 'artifact_sha256': intent['specification']['artifact_sha256'],
            'future_task_ids': reg['successor_decision']['future_task_ids'], 'basis': 'PREPAID_CONSTRUCTION_AND_THREE_VERIFICATIONS_NOT_YET_ACCEPTED_OUTPUT'}
    return {'operation': 'spend', 'id': 'ordinary-successor-kit', 'kind': 'prepaid_construction',
            'amount': intent['decision']['complete_cost_microUSD'], 'day': intent['hour'], 'work': work,
            'expected_net': intent['decision']['reuse_expected_net_microUSD'], 'allow_seed': False}


def _successor(account, state, source, output, reg, hour):
    if state['successor_status'] in {'QUALIFIED', 'REJECTED'}:
        return
    if state.get('successor_intent') is None:
        specification = successor.plan(source)
        decision = successor_choice(account.snapshot()['summary'], reg, specification)
        state['successor_checks'].append({'hour': hour, 'native_sequence': account.snapshot()['sequence'], 'decision': decision})
        if not decision['selected']:
            return
        state['successor_intent'] = {'hour': hour, 'specification': specification, 'decision': decision,
                                     'native_sequence_before': account.snapshot()['sequence'], 'funded': False}
        write(output / 'STATE.json', account.seal_checkpoint(state))
    intent = state['successor_intent']
    request = successor_request(intent, reg)
    receipt = account.spend(request['id'], request['kind'], request['amount'], request['day'], request['work'], request['expected_net'], allow_seed=False)
    if receipt is None or receipt['funding'] != 'EARNED':
        raise ValueError('EARNED_ONLY_SUCCESSOR_FUNDING_REQUIRED')
    intent['funded'] = True; intent['funding_receipt'] = receipt
    write(output / 'STATE.json', account.seal_checkpoint(state))
    destination = output / 'successor-kit'
    try:
        if not destination.exists():
            successor.construct(source, destination, specification=intent['specification'])
        qualification = successor.verify(source, destination)
        if qualification.get('accepted') is not True or qualification.get('artifact_sha256') != intent['specification']['artifact_sha256']:
            raise ValueError('SUCCESSOR_INDEPENDENT_QUALIFICATION_REJECTED')
        uses = successor.operate_tasks(source, destination, task_ids=reg['successor_decision']['future_task_ids'])
        check_successor_uses(uses, intent['specification'], reg['successor_decision'])
        intent['qualification'] = qualification; intent['uses'] = uses
        state['successor_status'] = 'QUALIFIED'
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        intent['failure_type'] = type(error).__name__
        state['successor_status'] = 'REJECTED'
    intent['native_sequence_after'] = account.snapshot()['sequence']
    write(output / 'STATE.json', account.seal_checkpoint(state))


def _operate(output, interrupt_after=None):
    output = Path(output).resolve(); source = output / 'source'
    reg = read(output / 'registration.json'); selected = reg['selection']; manifest = read(output / 'manifest.json'); index = read(output / 'jobs.json')
    if source != Path(__file__).resolve().parents[1] or canonical(reg) != canonical(registration(source, selected)):
        raise ValueError('EXACT_FROZEN_PRIMARY_SOURCE_AND_REGISTRATION_REQUIRED')
    game = game_for(selected)
    validate_manifest(source, game, manifest, index)
    state_path = output / 'STATE.json'; account_path = output / 'account.sqlite'
    if state_path.exists():
        if not account_path.with_name('account.sqlite.adaptive-simulation-key').is_file():
            raise ValueError('SAME_COUNTERPART_PRIVATE_AUTHORITY_REQUIRED')
        required = [account_path.with_name('account.sqlite' + suffix) for suffix in
                    ('.actions.jsonl', '.adaptive-account.json', '.connected-journal.json')]
        if any(not path.is_file() or path.stat().st_size == 0 for path in required):
            raise ValueError('SAME_COUNTERPART_ACTION_TAPE_AND_SIGNED_AUTHORITY_REQUIRED')
    with JournalAccount(source, manifest, account_path, opening=selected['opening_microUSD'], working=0,
                        contract='omega-primary-counterpart:' + digest(reg)) as account:
        if state_path.exists():
            state = account.verify_checkpoint(read(state_path))
        else:
            if account.export()['ledger']['actions']:
                raise ValueError('NONEMPTY_COUNTERPART_WITHOUT_CHECKPOINT_REFUSED')
            state = {'history_index': 0, 'quarter': 0, 'built': [], 'signal': None, 'outcome': None, 'trace': [], 'task': None,
                     'successor_status': 'NOT_FUNDED', 'successor_intent': None, 'successor_checks': [], 'complete': False}
            write(state_path, account.seal_checkpoint(state))
        historical = history_commands(source)
        while state['history_index'] < len(historical):
            command = historical[state['history_index']]
            account.execute(command['op'], command['args'], command['hour'])
            state['history_index'] += 1
            write(state_path, account.seal_checkpoint(state))
        record = account.export()
        if digest(record['ledger']['actions'][:42]) != HISTORY_ACTIONS or record['ledger']['actions'][41]['after'] != history(source)['seller']['native_summary_microUSD']:
            raise ValueError('EXACT_HISTORICAL_NATIVE_PREFIX_REQUIRED')
        while state['quarter'] < 4:
            if state['task'] is None:
                public = public_observation(state, account.snapshot()['summary'], selected)
                decision = competitive.decide(public, selected['policy_mode'], game)
                ident = f"q{state['quarter']}-decision-{len(state['trace'])}"
                hour = selected['operating_start_hour'] + state['quarter'] * 2160
                state['task'] = {'public': public, 'decision': decision, 'hour': hour, 'id': ident,
                                 'start_sequence': account.snapshot()['sequence'], 'fixed_index': 0,
                                 'fixed_commands': fixed_commands(decision, ident, hour), 'row': None,
                                 'commands': None, 'command_index': 0}
                write(state_path, account.seal_checkpoint(state))
            task = state['task']
            while task['fixed_index'] < len(task['fixed_commands']):
                _perform(account, task['fixed_commands'][task['fixed_index']], source, manifest, interrupt_after)
                task['fixed_index'] += 1; write(state_path, account.seal_checkpoint(state))
            kind = task['decision']['action']['kind']
            if kind == 'research':
                if state['signal'] is not None:
                    raise ValueError('PAID_INFORMATION_ALREADY_OBSERVED')
                state['signal'] = competitive.environment_signal(selected['world_id'], game)
                task['signal'] = state['signal']; task['end_sequence'] = account.snapshot()['sequence']
                state['trace'].append(task); state['task'] = None
                write(state_path, account.seal_checkpoint(state)); continue
            if kind == 'operate':
                if task['row'] is None:
                    task['fixed_paid_sequence'] = account.snapshot()['sequence']
                    task['row'] = competitive.realize(task['decision'], selected['world_id'], selected['reach'][state['quarter']], game)
                    task['commands'] = order_commands(task['row'], manifest, index, selected['operating_start_hour'])
                    write(state_path, account.seal_checkpoint(state))
                while task['command_index'] < len(task['commands']):
                    _perform(account, task['commands'][task['command_index']], source, manifest, interrupt_after)
                    task['command_index'] += 1; write(state_path, account.seal_checkpoint(state))
                current_ids = {c['args']['id'] for c in task['commands'] if c['kind'] == 'native' and c.get('op') == 'offer'}
                actual_orders = [o for o in account.export()['ledger']['orders'] if o['id'] in current_ids]
                observed = {'accepted' if o['state'] == 'released' else 'rejected_refunded' if o['state'] == 'refunded' else 'UNSETTLED' for o in actual_orders}
                if len(observed) > 1 or 'UNSETTLED' in observed:
                    raise ValueError('DECLARED_CONSTANT_WORLD_DELIVERY_OBSERVATION_INCONSISTENT')
                if observed:
                    state['outcome'] = next(iter(observed))
                task['observed_delivery_outcome'] = state['outcome']
                state['built'] = sorted(set(state['built']) | set(task['decision']['action']['build']))
                _successor(account, state, source, output, reg, selected['operating_start_hour'] + task['row']['maturity_hour'])
            task['end_sequence'] = account.snapshot()['sequence']
            state['trace'].append(task); state['task'] = None; state['quarter'] += 1
            write(state_path, account.seal_checkpoint(state))
        if not state['complete']:
            if 'tax' not in state:
                current = account.snapshot()['summary']
                taxable = max(0, current['profit'] + 24_800 * MICRO)
                state['tax'] = {'taxable_native_profit_microUSD': taxable,
                                'tax_microUSD': taxable * selected['income_tax_bps'] // 10000}
                write(state_path, account.seal_checkpoint(state))
            account.cost('corrected-year-tax-sensitivity', state['tax']['tax_microUSD'], selected['operating_end_hour_exclusive'] - 1)
            if interrupt_after == 'tax':
                os._exit(75)
            account.cost('corrected-year-complete-observation', 0, selected['operating_end_hour_exclusive'] - 1)
            state['complete'] = True; write(state_path, account.seal_checkpoint(state))
        record = account.export()
        write(output / 'public-native.json', record); write(output / 'public-operation.json', state)
        report = derive_report(output, reg, manifest, record, state)
        write(output / 'result.json', report)
        return report


def _native_for_command(command, source, manifest):
    if command['kind'] == 'native':
        return [(command['op'], command['args'], command['hour'])]
    if command['kind'] == 'prepare':
        return [('event', {'id': command['order'], 'action': 'prepare', 'event_id': command['order'] + ':prepare',
                           'artifact_sha256': digest(product.delivery(source, manifest, command['job']))}, command['hour'])]
    return []


def derive_report(output, reg, manifest, record, state):
    output = Path(output); source = output / 'source'; selected = reg['selection']; game = game_for(selected)
    if canonical(reg) != canonical(registration(source, selected)):
        raise ValueError('PRIMARY_SOURCE_POLICY_CHANGED')
    validate_manifest(source, game, manifest, read(output / 'jobs.json'))
    if (not state['complete'] or state['quarter'] != 4 or state['task'] is not None
            or record['ledger']['config']['opening'] != 100_000 * MICRO
            or record['ledger']['config']['contract'] != 'omega-primary-counterpart:' + digest(reg)):
        raise ValueError('COMPLETE_SAME_REGISTERED_COUNTERPART_REQUIRED')
    audit = audit_journal(record, root=source, manifest=manifest); actions = record['ledger']['actions']
    if digest(actions[:42]) != HISTORY_ACTIONS or actions[41]['after'] != history(source)['seller']['native_summary_microUSD']:
        raise ValueError('HISTORICAL_PREFIX_CHANGED')
    if canonical(manifest['costs']) != canonical(operate.costs(game)):
        raise ValueError('REGISTERED_PRODUCT_COSTS_CHANGED')
    built, signal, outcome, quarter, content = [], None, None, 0, False
    expected = [(c['op'], c['args'], c['hour']) for c in history_commands(source)]
    noncash = 0; accepted = 0; refunded = 0; minute_total = 0; expected_start = 42
    successor_intent = state.get('successor_intent')
    consumed_successor = False; expected_successor_checks = []
    for trace_index, task in enumerate(state['trace']):
        if task['start_sequence'] != expected_start:
            raise ValueError('PRIMARY_TRACE_NATIVE_COVERAGE_CHANGED')
        summary = actions[expected_start - 1]['after']
        public = {'quarter': quarter, 'available_cents': summary['available'] // CENT, 'built_products': built,
                  'content_available': content, 'research_signal': signal, 'observed_delivery_outcome': outcome,
                  'founder_minutes_available': selected['founder_minutes_per_quarter']}
        decision = competitive.decide(public, selected['policy_mode'], game)
        if canonical(task['public']) != canonical(public) or canonical(task['decision']) != canonical(decision):
            raise ValueError('PUBLIC_INFORMATION_POLICY_CHANGED')
        ident = f'q{quarter}-decision-{trace_index}'
        hour = selected['operating_start_hour'] + quarter * 2160
        fixed = fixed_commands(decision, ident, hour)
        if (task['id'] != ident or task['hour'] != hour or task['fixed_index'] != len(fixed)
                or canonical(task['fixed_commands']) != canonical(fixed)):
            raise ValueError('ACTION_DEPENDENT_FIXED_COSTS_CHANGED')
        for command in fixed:
            expected += _native_for_command(command, source, manifest)
        kind = decision['action']['kind']
        if kind == 'research':
            signal = competitive.environment_signal(selected['world_id'], game)
            if task.get('signal') != signal or task['end_sequence'] != len(expected):
                raise ValueError('PAID_INFORMATION_NATIVE_TIMING_CHANGED')
        elif kind == 'operate':
            row = competitive.realize(decision, selected['world_id'], selected['reach'][quarter], game)
            if canonical(row) != canonical(task['row']) or task['fixed_paid_sequence'] != len(expected):
                raise ValueError('POST_COST_ENVIRONMENT_RESPONSE_CHANGED')
            check_joint_budgets(row)
            commands = order_commands(row, manifest, read(output / 'jobs.json'), selected['operating_start_hour'])
            if canonical(task['commands']) != canonical(commands) or task['command_index'] != len(commands):
                raise ValueError('REGISTERED_ORDER_COMMANDS_CHANGED')
            for command in commands:
                expected += _native_for_command(command, source, manifest)
                if command['kind'] == 'mature':
                    pending = []
                    for op, args, hour in expected:
                        if op == 'register_terms':
                            term = args['terms']; ident = term['order_id']
                            released = any(o == 'event' and a.get('id') == ident and a.get('action') == 'release' for o, a, _ in expected)
                            matured = any(o == 'mature' and a.get('id') == ident for o, a, _ in expected)
                            if released and not matured and command['hour'] > term['maturity_day']:
                                pending.append((ident, term))
                    for ident, term in sorted(pending):
                        expected.append(('mature', {'id': ident, 'event_id': 'maturity:' + ident + ':' + digest(term)[:20]}, command['hour']))
            built = sorted(set(built) | set(decision['action']['build']))
            observed = {o['status'] for o in row['orders'] if o['status'] in {'accepted', 'rejected_refunded'}}
            if len(observed) > 1:
                raise ValueError('CONSTANT_WORLD_MIXED_OUTCOMES_REFUSED')
            if observed:
                outcome = next(iter(observed))
            if task.get('observed_delivery_outcome') != outcome:
                raise ValueError('POST_NATIVE_DELIVERY_OBSERVATION_CHANGED')
            noncash += row['noncash_founder_opportunity_cents'] * CENT; minute_total += row['founder_minutes']
            accepted += sum(o['status'] == 'accepted' for o in row['orders'])
            refunded += sum(o['status'] == 'rejected_refunded' for o in row['orders'])
            if not consumed_successor:
                before = actions[len(expected) - 1]['after']; specification = successor.plan(source)
                choice = successor_choice(before, reg, specification)
                expected_successor_checks.append({'hour': selected['operating_start_hour'] + row['maturity_hour'],
                                                   'native_sequence': len(expected), 'decision': choice})
                if choice['selected'] and (not successor_intent or successor_intent['native_sequence_before'] != len(expected)):
                    raise ValueError('SELECTED_SUCCESSOR_ACTION_MISSING')
            if successor_intent and successor_intent['native_sequence_before'] == len(expected):
                consumed_successor = True
                before = actions[len(expected) - 1]['after']; specification = successor.plan(source)
                choice = successor_choice(before, reg, specification)
                if (not choice['selected'] or canonical(choice) != canonical(successor_intent['decision'])
                        or canonical(successor_intent['specification']) != canonical(specification)
                        or successor_intent['hour'] != selected['operating_start_hour'] + row['maturity_hour']
                        or successor_intent['funded'] is not True):
                    raise ValueError('SUCCESSOR_UNEARNED_OR_UNECONOMIC_ADMISSION')
                entries = [e for e in record['connected_journal']['entries'] if e['key'] == 'spend:ordinary-successor-kit']
                if (len(entries) != 1 or entries[0]['funding'] != 'EARNED'
                        or canonical(entries[0]['request']) != canonical(successor_request(successor_intent, reg))
                        or canonical(entries[0]['receipt']) != canonical(successor_intent['funding_receipt'])):
                    raise ValueError('CANONICAL_EARNED_SUCCESSOR_COMMITMENT_REQUIRED')
                segment = actions[len(expected):successor_intent['native_sequence_after']]
                if [a['op'] for a in segment] != ['reserve', 'finish']:
                    raise ValueError('EXACT_NATIVE_SUCCESSOR_SPEND_REQUIRED')
                expected += [(a['op'], a['args'], a['day']) for a in segment]
                if state['successor_status'] == 'QUALIFIED':
                    checked = successor.verify(source, output / 'successor-kit')
                    uses = successor.operate_tasks(source, output / 'successor-kit', task_ids=reg['successor_decision']['future_task_ids'])
                    check_successor_uses(uses, specification, reg['successor_decision'])
                    if not checked['accepted'] or checked['artifact_sha256'] != specification['artifact_sha256']:
                        raise ValueError('SUCCESSOR_OUTPUT_QUALIFICATION_CHANGED')
                    if (canonical(stable_evidence(checked)) != canonical(stable_evidence(successor_intent.get('qualification')))
                            or canonical(stable_evidence(uses)) != canonical(stable_evidence(successor_intent.get('uses')))):
                        raise ValueError('SUCCESSOR_STORED_EVIDENCE_CHANGED')
                    content = True
                elif state['successor_status'] == 'REJECTED':
                    if 'qualification' in successor_intent or 'uses' in successor_intent:
                        raise ValueError('REJECTED_SUCCESSOR_CANNOT_CLAIM_ACCEPTANCE')
                    failed = None
                    try:
                        successor.verify(source, output / 'successor-kit')
                        successor.operate_tasks(source, output / 'successor-kit', task_ids=reg['successor_decision']['future_task_ids'])
                    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
                        failed = type(error).__name__
                    if failed is None or failed != successor_intent.get('failure_type'):
                        raise ValueError('SUCCESSOR_REJECTION_NOT_REPRODUCIBLE')
            quarter += 1
        else:
            quarter += 1
        if task['end_sequence'] != len(expected):
            raise ValueError('UNACCOUNTED_PRIMARY_ACTIONS')
        expected_start = len(expected)
    if (quarter != 4 or state['built'] != built or state['signal'] != signal or state['outcome'] != outcome
            or state['history_index'] != 42 or bool(successor_intent) != consumed_successor
            or canonical(state['successor_checks']) != canonical(expected_successor_checks)
            or state['successor_status'] not in ({'QUALIFIED', 'REJECTED'} if consumed_successor else {'NOT_FUNDED'})
            or (state['successor_status'] == 'QUALIFIED') != content):
        raise ValueError('FINAL_PRIMARY_CONTROL_STATE_CHANGED')
    before_tax = actions[len(expected) - 1]['after']['profit']
    taxable = max(0, before_tax + 24_800 * MICRO); tax = taxable * selected['income_tax_bps'] // 10000
    if state['tax'] != {'taxable_native_profit_microUSD': taxable, 'tax_microUSD': tax}:
        raise ValueError('TAX_SENSITIVITY_CHANGED')
    expected += [('cost', {'id': 'corrected-year-tax-sensitivity', 'amount': tax}, 17519),
                 ('cost', {'id': 'corrected-year-complete-observation', 'amount': 0}, 17519)]
    if canonical(expected) != canonical([(a['op'], a['args'], a['day']) for a in actions]):
        raise ValueError('COMPLETE_PRIMARY_NATIVE_SEQUENCE_CHANGED')
    annual = trailing_profit(record['ledger'], operating_end_hour=17520, operating_complete=True)
    return {'schema': 'omega/primary-counterpart-result/v1', 'registration_sha256': digest(reg),
            'selection': selected, 'account_role': reg['account_role'], 'original_account_recovered': False,
            'historical_prefix_actions_sha256': HISTORY_ACTIONS, 'historical_native_loss_microUSD': 24_800 * MICRO,
            'historical_noncash_founder_opportunity_microUSD': reg['historical_noncash_founder_opportunity_microUSD'],
            'native_audit_accepted': audit['accepted'], 'native_actions_sha256': record['ledger']['actions_sha256'],
            'native_summary_microUSD': record['ledger']['summary'], 'trailing_profit': annual,
            'accepted_component_orders': accepted, 'refunded_component_orders': refunded,
            'corrected_noncash_founder_opportunity_microUSD': noncash, 'modeled_founder_minutes': minute_total,
            'modeled_corrected_economic_profit_microUSD': annual['trailing_365_day_profit_microUSD'] - noncash,
            'successor_status': state['successor_status'], 'successor_intent': successor_intent,
            'decision_trace': state['trace'], 'actual_complete_cost_profit_microUSD': None,
            'actual_tax_treatment_verified': False, 'three_billion_objective_achieved': False,
            'limits': ['Author-defined demand, reach, prices and costs; not real commerce or actual complete profit.',
                       'Financial historical prefix is exact; original account authority and identity are not recovered.',
                       'Four quarterly decision epochs and explicit inactivity through the full ending-year window; no annualization.',
                       'Provisional tax is protected only at successor admission; it is not a native segregated reserve across all commerce actions.',
                       'Independent verifier reruns are audit work, not extra simulated sales or operating expenses.']}


def replay(output):
    output = Path(output).resolve()
    result = derive_report(output, read(output / 'registration.json'), read(output / 'manifest.json'),
                           read(output / 'public-native.json'), read(output / 'public-operation.json'))
    if canonical(result) != canonical(read(output / 'result.json')):
        raise ValueError('PRIMARY_REPORTED_RESULT_CHANGED')
    return {'accepted': result['native_audit_accepted'], 'native_actions_sha256': result['native_actions_sha256'],
            'registration_sha256': result['registration_sha256'], 'scope': result['account_role']}


def run(output, *, root=None, resume=False, interrupt_after=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve(); output = Path(output).absolute()
    if not resume:
        if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
            raise ValueError('FRESH_COUNTERPART_DESTINATION_REQUIRED_NEVER_RESEED')
        reg = registration(root); output.mkdir(parents=True)
        for name in reg['source_hashes']:
            target = output / 'source' / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(root / name, target)
        write(output / 'registration.json', reg)
        initialize = subprocess.run([sys.executable, '-m', 'omega.primary_operator', '--output', str(output), '--frozen', '--initialize'],
                                    cwd=output / 'source', capture_output=True, text=True)
        if initialize.returncode:
            raise ValueError('PRIMARY_INITIALIZATION_FAILED:' + initialize.stderr[-3000:])
    elif not (output / 'STATE.json').is_file():
        raise ValueError('SAME_COUNTERPART_CHECKPOINT_REQUIRED')
    command = [sys.executable, '-m', 'omega.primary_operator', '--output', str(output), '--frozen']
    if interrupt_after:
        command += ['--interrupt-after', interrupt_after]
    process = subprocess.run(command, cwd=output / 'source', capture_output=True, text=True)
    if process.returncode == 75:
        return {'complete': False, 'interrupted_after': interrupt_after, 'scope': 'SAME_REGISTERED_COUNTERPART_MUST_RESUME'}
    if process.returncode:
        raise ValueError('PRIMARY_EXECUTION_FAILED:' + process.stderr[-4000:])
    return read(output / 'result.json')


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True); parser.add_argument('--resume', action='store_true')
    parser.add_argument('--frozen', action='store_true'); parser.add_argument('--initialize', action='store_true')
    parser.add_argument('--audit', action='store_true'); parser.add_argument('--interrupt-after', choices=['first-fund', 'tax'])
    args = parser.parse_args(); output = Path(args.output).resolve()
    if args.frozen and args.initialize:
        if (output / 'manifest.json').exists():
            raise ValueError('PRIMARY_MANIFEST_ALREADY_EXISTS')
        reg = read(output / 'registration.json'); manifest, index = _manifest(output / 'source', game_for(reg['selection']))
        write(output / 'manifest.json', manifest); write(output / 'jobs.json', index); result = {'initialized': True}
    elif args.frozen:
        result = replay(output) if args.audit else _operate(output, args.interrupt_after)
    elif args.audit:
        process = subprocess.run([sys.executable, '-m', 'omega.primary_operator', '--output', str(output), '--frozen', '--audit'],
                                 cwd=output / 'source', capture_output=True, text=True, check=True)
        print(process.stdout, end=''); return
    else:
        result = run(output, resume=args.resume, interrupt_after=args.interrupt_after)
    print(json.dumps({'complete': result.get('complete', True), 'scope': result.get('account_role', result.get('scope')),
                      'native_actions_sha256': result.get('native_actions_sha256'), 'accepted': result.get('accepted')}, sort_keys=True))


if __name__ == '__main__':
    main()
