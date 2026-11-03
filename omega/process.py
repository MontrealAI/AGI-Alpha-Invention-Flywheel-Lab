"""Finite process experiment construction and an offline, resumable buyer path."""
from __future__ import annotations

import argparse
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3

from commercial.ledger import strict_json
from mechanism_harness.core import SCHEMA, audit, canonical, compose, digest

ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'AUTHORED_FINITE_PROCESS_SIMULATION_NOT_PHYSICAL_OPERATION'


def validate(request):
    fields = {'schema', 'name', 'ambition', 'currency', 'models', 'experiments', 'recipes',
              'observations', 'target_minimum', 'max_total_cost_cents', 'max_experiments', 'consent'}
    if type(request) is not dict or set(request) != fields:
        raise ValueError('EXACT_REQUEST_FIELDS_REQUIRED')
    if request['schema'] != 'omega/process-request/v1' or request['currency'] != 'USD':
        raise ValueError('REQUEST_SCHEMA_OR_CURRENCY')
    if any(type(request[k]) is not str or not request[k].strip() for k in ('name', 'ambition')):
        raise ValueError('AMBITION_AND_NAME_REQUIRED')
    if type(request['consent']) is not bool:
        raise ValueError('EXPLICIT_BUYER_CHOICE_REQUIRED')
    for k, lo in [('target_minimum', 1), ('max_total_cost_cents', 0), ('max_experiments', 0)]:
        if type(request[k]) is not int or request[k] < lo:
            raise ValueError('EXACT_NONNEGATIVE_INTEGER_REQUIRED:' + k)
    if request['max_experiments'] > 4:
        raise ValueError('RESOURCE_LIMIT_MAX_FOUR_EXPERIMENTS_NOT_INFEASIBILITY')
    for key, minimum, rowfields in [('models', 1, {'id', 'responses', 'yields'}),
                                    ('experiments', 0, {'id', 'cost_cents'}),
                                    ('recipes', 1, {'id', 'cost_cents'})]:
        rows = request[key]
        if type(rows) is not list or not minimum <= len(rows) <= 8:
            raise ValueError('RESOURCE_OR_CARDINALITY_BOUND:' + key)
        ids = []
        for row in rows:
            if type(row) is not dict or set(row) != rowfields or type(row['id']) is not str or not row['id'].strip():
                raise ValueError('EXACT_NAMED_ROWS_REQUIRED:' + key)
            ids.append(row['id'])
            if key != 'models' and (type(row['cost_cents']) is not int or row['cost_cents'] < 0):
                raise ValueError('EXACT_NONNEGATIVE_COST_REQUIRED')
        if len(ids) != len(set(ids)):
            raise ValueError('UNIQUE_IDENTITIES_REQUIRED')
    tests, recipes = {r['id'] for r in request['experiments']}, {r['id'] for r in request['recipes']}
    for model in request['models']:
        for field, ids in [('responses', tests), ('yields', recipes)]:
            if type(model[field]) is not dict or set(model[field]) != ids or any(type(v) is not int for v in model[field].values()):
                raise ValueError('COMPLETE_EXACT_RESPONSE_TABLE_REQUIRED')
    if type(request['observations']) is not list:
        raise ValueError('OBSERVATIONS_LIST_REQUIRED')
    for row in request['observations']:
        if (type(row) is not dict or set(row) != {'experiment_id', 'value'} or
                type(row['experiment_id']) is not str or row['experiment_id'] not in tests or type(row['value']) is not int):
            raise ValueError('DECLARED_EXACT_OBSERVATION_REQUIRED')
    return request


def construct(request):
    validate(request)
    empty = {'schema': 'omega/process-policy/v1', 'request_sha256': digest(request),
             'status': None, 'worst_cost_cents': None, 'tree': None}
    if not request['consent']:
        return {**empty, 'status': 'BUYER_DECLINED'}
    models = request['models']
    survivors = tuple(i for i, m in enumerate(models) if all(
        m['responses'][o['experiment_id']] == o['value'] for o in request['observations']))
    if not survivors:
        return {**empty, 'status': 'MODEL_MISMATCH'}
    observed = {o['experiment_id'] for o in request['observations']}
    available = tuple(sorted(e['id'] for e in request['experiments'] if e['id'] not in observed))
    costs = {e['id']: e['cost_cents'] for e in request['experiments']}
    states = 0

    @lru_cache(None)
    def search(compatible, remaining, depth):
        nonlocal states
        states += 1
        if states > 100000:
            raise RuntimeError('RESOURCE_EXHAUSTED_NOT_INFEASIBILITY')
        best = None
        for recipe in sorted(request['recipes'], key=lambda r: r['id']):
            if all(models[i]['yields'][recipe['id']] >= request['target_minimum'] for i in compatible):
                candidate = (recipe['cost_cents'], {'kind': 'produce', 'recipe_id': recipe['id']})
                if best is None or candidate[0] < best[0]:
                    best = candidate
        if depth:
            for name in remaining:
                partitions = {}
                for i in compatible:
                    partitions.setdefault(models[i]['responses'][name], []).append(i)
                if len(partitions) < 2:
                    continue
                children, worst = {}, 0
                for value, group in sorted(partitions.items()):
                    child = search(tuple(group), tuple(x for x in remaining if x != name), depth - 1)
                    if child is None:
                        break
                    worst = max(worst, child[0])
                    children[str(value)] = child[1]
                else:
                    value = costs[name] + worst
                    if best is None or value < best[0]:
                        best = (value, {'kind': 'test', 'experiment_id': name, 'branches': children})
        return best

    answer = search(survivors, available, request['max_experiments'])
    if answer is None or answer[0] > request['max_total_cost_cents']:
        return {**empty, 'status': 'NO_QUALIFIED_POLICY'}
    return {**empty, 'status': 'QUALIFIED_POLICY', 'worst_cost_cents': answer[0], 'tree': copy.deepcopy(answer[1])}


def fixture(successor=False):
    models = []
    for i, (a, b) in enumerate([(1, 0), (0, 1), (1, 1), (0, 0)], 1):
        models.append({'id': 'm' + str(i), 'responses': {'passive': 10, 'a': a, 'b': b},
                       'yields': {'a': 10 if a else 0, 'b': 10 if b else 0,
                                  'c': 10 if i == 4 else 0, 'robust': 10}})
    return {'schema': 'omega/process-request/v1', 'name': 'Fresh successor' if successor else 'Ambiguous process',
            'ambition': 'Choose an accepted production recipe after an affordable discriminating experiment.',
            'currency': 'USD', 'models': models,
            'experiments': [{'id': k, 'cost_cents': v} for k, v in
                            [('passive', 1), ('a', 8 if successor else 4), ('b', 3 if successor else 5)]],
            'recipes': [{'id': k, 'cost_cents': v} for k, v in
                        zip(['a', 'b', 'c', 'robust'], [6, 24, 7, 100] if successor else [18, 20, 22, 100])],
            'observations': [], 'target_minimum': 10, 'max_total_cost_cents': 40,
            'max_experiments': 3, 'consent': True}


def pathway():
    ops = [('construct', ['request'], ['policy']), ('check', ['policy', 'request'], ['checked_policy']),
           ('observe', ['checked_policy'], ['observations']), ('produce', ['observations'], ['output']),
           ('accept', ['output'], ['accepted_output']), ('cost', ['accepted_output'], ['costed_outcome'])]
    spec = {'schema': SCHEMA, 'purpose': {'initial': ['request'], 'goal': ['costed_outcome'],
            'max_cost': 10, 'max_steps': 8, 'max_states': 128, 'allowed_effects': ['pure']},
            'mechanisms': [{'id': name, 'requires': sorted(requires), 'provides': provides,
                            'cost': 1, 'effect': 'pure', 'origin': 'developer_supplied'} for name, requires, provides in ops],
            'candidate_bridges': []}
    plan = compose(spec)
    return {'plan': plan, 'audit': audit(spec, plan), 'scope': 'EXISTING_HARNESS_SYMBOLIC_PLAN_NO_EXTERNAL_AUTHORITY'}


def route(choice='deterministic_local', *, memory_mib=128, external_authorized=False,
          external_max_usd=None, data_scope=None):
    if type(memory_mib) is not int or memory_mib < 32:
        raise ValueError('INSUFFICIENT_RESOURCES_DECLARED_MEMORY_PREFLIGHT')
    if choice == 'local_model':
        raise ValueError('MODEL_UNAVAILABLE_NO_LOCAL_LLM_ADAPTER_IMPLEMENTED')
    if choice == 'external_model':
        if not external_authorized or external_max_usd is None or not data_scope:
            raise ValueError('EXTERNAL_PROCESSING_REQUIRES_EXPLICIT_DATA_AND_COST_AUTHORIZATION')
        raise ValueError('EXTERNAL_PROVIDER_NOT_IMPLEMENTED_NO_NETWORK_OR_SPEND')
    if choice != 'deterministic_local':
        raise ValueError('UNKNOWN_MODEL_ROUTE')
    return {'route': choice, 'model_api_calls': 0, 'network_calls': 0, 'scope': 'DETERMINISTIC_NOT_LLM_INFERENCE',
            'memory_preflight_mib': 32, 'memory_basis': 'Declared minimum envelope, not universal measured bound',
            'hardware_electricity_and_host_cost': None, 'buyer_owns_compute': True}


def help_for(code):
    path = ROOT / 'omega/PROCESS_HELP.json'
    rows = strict_json(path.read_bytes())
    entry = rows.get(code)
    return {'code': code, 'known_diagnostic': entry is not None, 'resolved': False,
            'guidance': entry or 'No documented resolution. Preserve the diagnostic and stop or request bounded review.',
            'documentation_path': 'omega/PROCESS_HELP.json', 'documentation_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'scope': 'LOCAL_DOCUMENTATION_LOOKUP_NOT_LANGUAGE_MODEL_OR_UNIVERSAL_SUPPORT'}


def source_binding():
    names = ['omega/process.py', 'omega/process_verify.py', 'omega/PROCESS_HELP.json',
             'omega/__init__.py', 'mechanism_harness/core.py', 'mechanism_harness/__init__.py',
             'mechanism_harness/evidence.py', 'mechanism_harness/experiment.py',
             'commercial/__init__.py', 'commercial/ledger.py', 'commercial/native_engine.py',
             'experiments/__init__.py', 'experiments/commerce006.py']
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


class BuyerSession:
    def __init__(self, path, request=None, *, model_route='deterministic_local', memory_mib=128):
        from .process_verify import verify_policy
        self.path = Path(path).absolute()
        if any(p.is_symlink() for p in [self.path, *self.path.parents]):
            raise ValueError('REGULAR_BUYER_PATH_REQUIRED')
        exists = self.path.is_file()
        if request is None and not exists:
            raise ValueError('EXISTING_SESSION_REQUIRED_NO_AUTOMATIC_RESET')
        if request is not None:
            validate(request)
            route(model_route, memory_mib=memory_mib)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not exists:
            with self.path.open('xb'):
                pass
        self.db = sqlite3.connect(self.path, isolation_level=None)
        try:
            self.db.execute('PRAGMA synchronous=FULL')
            if not exists:
                self.db.execute('CREATE TABLE meta (id INTEGER PRIMARY KEY, value BLOB NOT NULL)')
                self.db.execute('CREATE TABLE events (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, request BLOB NOT NULL, receipt BLOB NOT NULL)')
            elif {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")} != {'meta', 'events'}:
                raise ValueError('EXISTING_FILE_IS_NOT_A_BUYER_SESSION')
            row = self.db.execute('SELECT value FROM meta WHERE id=1').fetchone()
            if row is None:
                if request is None or exists:
                    raise ValueError('EXISTING_SESSION_METADATA_MISSING')
                policy = construct(request)
                self.meta = {'schema': 'omega/buyer-session/v1', 'request': request, 'policy': policy,
                             'source_files': source_binding(), 'route': route(model_route, memory_mib=memory_mib),
                             'verification': verify_policy(request, policy), 'pathway': pathway(), 'scope': SCOPE}
                self.db.execute('INSERT INTO meta VALUES (1,?)', (canonical(self.meta),))
            else:
                self.meta = strict_json(row[0])
                if request is not None and canonical(request) != canonical(self.meta['request']):
                    raise ValueError('REQUEST_CHANGED_USE_DISTINCT_SESSION')
            self._verify_meta()
            self.report()
        except BaseException:
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.db.close()

    def _verify_meta(self):
        from .process_verify import verify_policy
        if set(self.meta) != {'schema', 'request', 'policy', 'source_files', 'route', 'verification', 'pathway', 'scope'} or self.meta['schema'] != 'omega/buyer-session/v1' or self.meta['scope'] != SCOPE:
            raise ValueError('EXACT_BUYER_METADATA_REQUIRED')
        if self.meta['source_files'] != source_binding():
            raise ValueError('SOURCE_CHANGED_RETAIN_ORIGINAL_SESSION')
        if self.meta['route'] != route() or self.meta['pathway'] != pathway():
            raise ValueError('STORED_ROUTE_OR_PATHWAY_CHANGED')
        if canonical(verify_policy(self.meta['request'], self.meta['policy'])) != canonical(self.meta['verification']):
            raise ValueError('STORED_ACCEPTANCE_CHANGED')
        stored = self.db.execute('SELECT value FROM meta WHERE id=1').fetchone()
        if stored is None or stored[0] != canonical(self.meta):
            raise ValueError('ACTIVE_BUYER_METADATA_CHANGED')

    def _initial(self):
        policy = self.meta['policy']
        return {'status': 'WAITING' if policy['status'] == 'QUALIFIED_POLICY' else policy['status'],
                'node': copy.deepcopy(policy['tree']), 'cost_cents': 0, 'observations': [], 'yield': None}

    def _apply(self, state, event):
        if type(event) is not dict or set(event) != {'operation', 'payload'} or type(event['operation']) is not str or type(event['payload']) is not dict:
            raise ValueError('EXACT_BUYER_EVENT_REQUIRED')
        op, payload = event['operation'], event['payload']
        if state['status'] != 'WAITING':
            raise ValueError('SESSION_TERMINAL_NO_MORE_ACTIONS')
        if op == 'decline':
            if payload:
                raise ValueError('DECLINE_HAS_NO_ACTION_PAYLOAD')
            state['status'], state['node'] = 'BUYER_DECLINED', None
        elif op == 'observe':
            node = state['node']
            if node['kind'] != 'test' or set(payload) != {'experiment_id', 'value'} or payload['experiment_id'] != node['experiment_id'] or type(payload['value']) is not int:
                raise ValueError('EXPECTED_EXACT_OBSERVATION_REQUIRED')
            costs = {r['id']: r['cost_cents'] for r in self.meta['request']['experiments']}
            state['cost_cents'] += costs[payload['experiment_id']]
            state['observations'].append(payload)
            state['node'] = node['branches'].get(str(payload['value']))
            if state['node'] is None:
                state['status'] = 'MODEL_MISMATCH'
        elif op == 'accept':
            node = state['node']
            if node['kind'] != 'produce' or set(payload) != {'recipe_id', 'observed_yield', 'evidence_scope'} or payload['recipe_id'] != node['recipe_id'] or type(payload['observed_yield']) is not int or payload['evidence_scope'] != 'SIMULATED_OR_BUYER_SUPPLIED_OBSERVATION':
                raise ValueError('EXPLICIT_TERMINAL_OBSERVATION_REQUIRED')
            costs = {r['id']: r['cost_cents'] for r in self.meta['request']['recipes']}
            state['cost_cents'] += costs[payload['recipe_id']]
            state['yield'] = payload['observed_yield']
            state['status'] = 'ACCEPTED' if state['yield'] >= self.meta['request']['target_minimum'] else 'PRODUCTION_REJECTED'
        else:
            raise ValueError('KNOWN_BUYER_OPERATION_REQUIRED')
        if state['cost_cents'] > self.meta['request']['max_total_cost_cents']:
            raise ValueError('EXECUTED_COST_EXCEEDS_DECLARED_BUDGET')
        return copy.deepcopy(state)

    def _replay(self):
        state = self._initial()
        for raw, receipt in self.db.execute('SELECT request,receipt FROM events ORDER BY seq'):
            expected = self._apply(state, strict_json(raw))
            if canonical(expected) != receipt:
                raise ValueError('BUYER_RECEIPT_REPLAY_MISMATCH')
        return state

    def act(self, action_id, operation, **payload):
        if type(action_id) is not str or not action_id.strip() or len(action_id) > 160:
            raise ValueError('BOUNDED_ACTION_ID_REQUIRED')
        event = {'operation': operation, 'payload': payload}
        raw = canonical(event)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self._verify_meta()
            state = self._replay()
            prior = self.db.execute('SELECT request,receipt FROM events WHERE id=?', (action_id,)).fetchone()
            if prior:
                if prior[0] != raw:
                    raise ValueError('ACTION_ID_REUSED_WITH_CHANGED_INPUT')
                result = strict_json(prior[1])
            else:
                result = self._apply(state, event)
                self.db.execute('INSERT INTO events (id,request,receipt) VALUES (?,?,?)', (action_id, raw, canonical(result)))
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def report(self):
        self._verify_meta()
        state = self._replay()
        return {'scope': SCOPE, 'request_sha256': digest(self.meta['request']), 'policy': self.meta['policy'],
                'state': state, 'events': self.db.execute('SELECT count(*) FROM events').fetchone()[0],
                'buyer_value_before_fees_usd': None, 'buyer_net_benefit_usd': None,
                'modeled_observation_and_recipe_cost_cents': state['cost_cents'],
                'adoption_instrumentation_compute_verification_complete_cost_usd': None,
                'independent_physical_acceptance': False, 'model_api_calls': 0,
                'permission_to_reuse_customer_data': False,
                'next_action': 'Obtain a real authorized process and independent measurement/acceptance contract before commissioning claims.'}


def run_simulated_buyer(path, request, responses, yields, *, interrupt=False):
    from .process_verify import independent_execution
    with BuyerSession(path, request) as session:
        policy = copy.deepcopy(session.meta['policy'])
        state = session.report()['state']
        if state['status'] == 'WAITING' and state['node']['kind'] == 'test' and interrupt:
            name = state['node']['experiment_id']
            payload = {'experiment_id': name, 'value': responses[name]}
            first = session.act('probe-1', 'observe', **payload)
            if session.act('probe-1', 'observe', **payload) != first:
                raise AssertionError('DUPLICATE_ACTION_CHANGED_RECEIPT')
    with BuyerSession(path) as session:
        while session.report()['state']['status'] == 'WAITING':
            state = session.report()['state']
            node = state['node']
            if node['kind'] == 'test':
                name = node['experiment_id']
                session.act('probe-' + str(session.report()['events'] + 1), 'observe', experiment_id=name, value=responses[name])
            else:
                name = node['recipe_id']
                session.act('terminal-acceptance', 'accept', recipe_id=name, observed_yield=yields[name], evidence_scope='SIMULATED_OR_BUYER_SUPPLIED_OBSERVATION')
        result = session.report()
    independent = independent_execution(request, policy, responses, yields)
    if (independent['production_accepted'] != (result['state']['status'] == 'ACCEPTED') or
            independent['cost_cents'] != result['state']['cost_cents']):
        raise AssertionError('INDEPENDENT_END_USE_ACCEPTANCE_DISAGREES')
    return {'buyer': result, 'independent_execution': independent, 'interruption_and_duplicate_exercised': interrupt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('new', 'status', 'observe', 'accept', 'decline'):
        item = sub.add_parser(command)
        item.add_argument('--session', required=True)
        if command == 'new':
            item.add_argument('--request', required=True)
        if command in ('observe', 'accept', 'decline'):
            item.add_argument('--action-id', required=True)
        if command == 'observe':
            item.add_argument('--experiment', required=True); item.add_argument('--value', required=True, type=int)
        if command == 'accept':
            item.add_argument('--recipe', required=True); item.add_argument('--yield-value', required=True, type=int)
    helper = sub.add_parser('help'); helper.add_argument('code')
    sample = sub.add_parser('example'); sample.add_argument('--successor', action='store_true')
    args = parser.parse_args()
    if args.command == 'example':
        result = fixture(args.successor)
    elif args.command == 'help':
        result = help_for(args.code)
    else:
        request = strict_json(Path(args.request).read_bytes()) if args.command == 'new' else None
        with BuyerSession(args.session, request) as session:
            if args.command == 'observe':
                session.act(args.action_id, 'observe', experiment_id=args.experiment, value=args.value)
            elif args.command == 'accept':
                session.act(args.action_id, 'accept', recipe_id=args.recipe, observed_yield=args.yield_value, evidence_scope='SIMULATED_OR_BUYER_SUPPLIED_OBSERVATION')
            elif args.command == 'decline':
                session.act(args.action_id, 'decline')
            result = session.report()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
