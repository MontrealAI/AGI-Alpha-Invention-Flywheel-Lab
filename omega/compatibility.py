"""Resettable finite-state compatibility recovery, using ordinary active learning.

Only local authored protocol oracles are shipped. The buyer must supply a valid
state bound, reset, deterministic observations and permission before adapting this
method to a real system. Those assumptions are not inferred by this program.
No network access, models, paid calls or customer information are used.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path
import time

SCHEMA = 'omega/finite-compatibility/v1'
ALPHABET = ('start', 'append', 'commit')
CASES = ('legacy_queue', 'queue_revision', 'strict_revision')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def words(alphabet, maximum):
    yield ()
    for size in range(1, maximum + 1):
        yield from itertools.product(alphabet, repeat=size)


def package_contract(case='legacy_queue', *, max_states=4, max_queries=20000, max_verification_queries=20000):
    if case not in CASES:
        raise ValueError('UNKNOWN_AUTHORED_CASE')
    if type(max_states) is not int or max_states < 1 or type(max_queries) is not int or max_queries < 1 or type(max_verification_queries) is not int or max_verification_queries < 1:
        raise ValueError('POSITIVE_BUYER_SUPPLIED_STATE_AND_QUERY_BOUNDS_REQUIRED')
    return {'schema': SCHEMA, 'case': case, 'oracle_version': 'authored-' + case + '-1',
            'alphabet': list(ALPHABET), 'max_states': max_states, 'max_queries': max_queries,
            'max_verification_queries': max_verification_queries, 'long_holdout_count': 40,
            'query_budget_semantics': 'max_queries=learning; max_verification_queries=independent checks',
            'buyer_supplied_assumptions': {'deterministic': True, 'reliable_reset': True,
                                         'state_bound_valid': True, 'local_probe_authorized': True},
            'scope': 'AUTHORED_LOCAL_SIMULATION_NOT_PHYSICAL_QUALIFICATION'}


def buyer_contract(oracle_version, alphabet, *, max_states, max_queries=20000,
                   max_verification_queries=20000, assumptions=None):
    """Explicit local-only integration contract; caller owns the query callable.

    No callable is imported, invoked, networked or authorized by this constructor.
    A buyer must independently establish these assumptions before probing.
    """
    base = package_contract(max_states=max_states, max_queries=max_queries,
                            max_verification_queries=max_verification_queries)
    if (not isinstance(oracle_version, str) or not oracle_version.strip()
            or not isinstance(alphabet, (tuple, list)) or not alphabet
            or any(not isinstance(a, str) or not a for a in alphabet)
            or len(set(alphabet)) != len(alphabet)):
        raise ValueError('EXPLICIT_ORACLE_ID_AND_FINITE_DISTINCT_ALPHABET_REQUIRED')
    if (not isinstance(assumptions, dict) or any(type(v) is not bool for v in assumptions.values())
            or assumptions != base['buyer_supplied_assumptions']):
        raise ValueError('BUYER_MUST_ESTABLISH_ALL_ASSUMPTIONS')
    return {**base, 'case': 'buyer_local', 'oracle_version': oracle_version,
            'alphabet': list(alphabet), 'scope': 'BUYER_LOCAL_ORACLE_CONDITIONAL_ON_SUPPLIED_ASSUMPTIONS'}


def validate_contract(contract):
    if not isinstance(contract, dict):
        raise ValueError('EXPLICIT_CONTRACT_REQUIRED')
    assumptions = contract.get('buyer_supplied_assumptions')
    if not isinstance(assumptions, dict) or any(type(v) is not bool for v in assumptions.values()):
        raise ValueError('EXPLICIT_BOOLEAN_ASSUMPTIONS_REQUIRED')
    if contract.get('case') == 'buyer_local':
        expected = buyer_contract(contract.get('oracle_version'), contract.get('alphabet'),
                                  max_states=contract.get('max_states'), max_queries=contract.get('max_queries'),
                                  max_verification_queries=contract.get('max_verification_queries'),
                                  assumptions=contract.get('buyer_supplied_assumptions'))
        if contract != expected:
            raise ValueError('CONTRACT_CHANGED_OR_PERMISSION_MISSING')
        return
    expected = package_contract(contract.get('case'), max_states=contract.get('max_states'),
                                max_queries=contract.get('max_queries'),
                                max_verification_queries=contract.get('max_verification_queries'))
    if contract != expected:
        raise ValueError('CONTRACT_CHANGED_OR_PERMISSION_MISSING')


def local_oracle(case='legacy_queue', *, unavailable=False):
    """Return ONLY a reset-and-query callable; tables are not learner inputs."""
    if case not in CASES:
        raise ValueError('UNKNOWN_AUTHORED_CASE')
    # State order: idle, empty transaction, populated transaction, error state.
    table = [
        [(1, 'opened'), (3, 'no_transaction'), (0, 'nothing_to_commit')],
        [(3, 'nested_start'), (2, 'appended'), (0, 'empty_commit')],
        [(3, 'nested_start'), (2, 'appended'), (0, 'committed')],
        [(1, 'recovered'), (3, 'recovery_required'), (0, 'aborted')],
    ]
    if case == 'queue_revision':
        table[1][0] = (1, 'already_open')
        table[3][2] = (3, 'recovery_required')
    elif case == 'strict_revision':
        table[1][2] = (3, 'empty_rejected')
        table[2][0] = (2, 'already_open')
    def query(sequence):
        if unavailable:
            raise ConnectionError('LOCAL_ORACLE_UNAVAILABLE')
        state, outputs = 0, []
        for symbol in sequence:
            if symbol not in ALPHABET:
                raise ValueError('UNSUPPORTED_INPUT')
            state, value = table[state][ALPHABET.index(symbol)]
            outputs.append(value)
        return tuple(outputs)
    return query


def execute_adapter(adapter, sequence):
    state, result = adapter['initial'], []
    for symbol in sequence:
        if symbol not in adapter['alphabet']:
            raise ValueError('UNSUPPORTED_INPUT')
        step = adapter['transitions'][str(state)][symbol]
        result.append(step['output'])
        state = step['next']
    return tuple(result)


class QueryLimit(RuntimeError):
    pass


class Paused(RuntimeError):
    pass


class ActiveLearner:
    """Ordinary closed/consistent observation table plus bounded equivalence.

    The interface supplies only reset-and-query(word). No table/state count is
    inspected. Query limit is a buyer resource constraint, not a market ceiling.
    A retained suffix set is generic test content, never inherited authority.
    """
    def __init__(self, query, contract, *, checkpoint=None, prior_suffixes=None,
                 stop_after_queries=None):
        validate_contract(contract)
        self.oracle, self.contract = query, contract
        self.alphabet = tuple(contract['alphabet'])
        self.checkpoint = Path(checkpoint) if checkpoint else None
        self.cache = {}
        self.start_queries = 0
        self.stop_after_queries = stop_after_queries
        self.suffixes = [tuple([a]) for a in self.alphabet]
        for suffix in prior_suffixes or []:
            suffix = tuple(suffix)
            if not suffix or any(a not in self.alphabet for a in suffix):
                raise ValueError('INVALID_RETAINED_SUFFIX')
            if suffix not in self.suffixes:
                self.suffixes.append(suffix)
        if self.checkpoint and self.checkpoint.exists():
            saved = json.loads(self.checkpoint.read_text())
            if saved['contract_sha256'] != digest(contract):
                raise ValueError('CHECKPOINT_ORACLE_OR_CONTRACT_CHANGED')
            if saved['payload_sha256'] != digest(saved['queries']):
                raise ValueError('CHECKPOINT_CORRUPTION')
            for word, outputs in saved['queries']:
                key = tuple(word)
                if key in self.cache or len(word) != len(outputs) or any(a not in self.alphabet for a in word):
                    raise ValueError('INVALID_CHECKPOINT')
                self.cache[key] = tuple(outputs)
            self.start_queries = len(self.cache)
        self.counterexamples = []

    def save(self):
        if self.checkpoint:
            rows = [[list(k), list(v)] for k, v in sorted(self.cache.items())]
            value = {'contract_sha256': digest(self.contract), 'queries': rows,
                     'payload_sha256': digest(rows)}
            self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
            temp = self.checkpoint.with_suffix('.pending')
            temp.write_bytes(canonical(value) + b'\n')
            temp.replace(self.checkpoint)

    def query(self, word):
        word = tuple(word)
        if word not in self.cache:
            if len(self.cache) >= self.contract['max_queries']:
                self.save()
                raise QueryLimit('BUYER_QUERY_BUDGET_EXHAUSTED')
            if self.stop_after_queries is not None and len(self.cache) - self.start_queries >= self.stop_after_queries:
                self.save()
                raise Paused('CHECKPOINTED_BEFORE_NEXT_QUERY')
            result = tuple(self.oracle(word))
            if len(result) != len(word) or any(not isinstance(x, str) for x in result):
                raise ValueError('MALFORMED_ORACLE_RESPONSE')
            self.cache[word] = result
        return self.cache[word]

    def row(self, prefix):
        return tuple(self.query(prefix + suffix)[len(prefix):] for suffix in self.suffixes)

    def learn(self):
        prefixes = [()]
        while True:
            changed = True
            while changed:
                changed = False
                rows = [self.row(p) for p in prefixes]
                for prefix in list(prefixes):
                    for a in self.alphabet:
                        extension = prefix + (a,)
                        if self.row(extension) not in rows:
                            prefixes.append(extension)
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    continue
                for i, left in enumerate(prefixes):
                    for right in prefixes[i + 1:]:
                        if self.row(left) != self.row(right):
                            continue
                        for a in self.alphabet:
                            lrow, rrow = self.row(left + (a,)), self.row(right + (a,))
                            if lrow != rrow:
                                j = next(k for k, (l, r) in enumerate(zip(lrow, rrow)) if l != r)
                                self.suffixes.append((a,) + self.suffixes[j])
                                changed = True
                                break
                        if changed:
                            break
                    if changed:
                        break
            unique, representatives = [], []
            for prefix in prefixes:
                row = self.row(prefix)
                if row not in unique:
                    unique.append(row)
                    representatives.append(prefix)
            if len(unique) > self.contract['max_states']:
                raise ValueError('DECLARED_STATE_BOUND_CONTRADICTED')
            transitions = {}
            for i, prefix in enumerate(representatives):
                transitions[str(i)] = {a: {'next': unique.index(self.row(prefix + (a,))),
                                           'output': self.query(prefix + (a,))[-1]}
                                       for a in self.alphabet}
            adapter = {'schema': SCHEMA, 'alphabet': list(self.alphabet),
                       'initial': unique.index(self.row(())), 'transitions': transitions}
            counterexample = None
            # For deterministic resettable machines with at most N states each,
            # inequivalence has a distinguishing word shorter than their total
            # state count. Exhaustion is a finite conditional guarantee only.
            for word in words(self.alphabet, 2 * self.contract['max_states'] - 1):
                if execute_adapter(adapter, word) != self.query(word):
                    counterexample = word
                    break
            if counterexample is None:
                self.save()
                return adapter
            self.counterexamples.append(counterexample)
            for size in range(1, len(counterexample) + 1):
                prefix = counterexample[:size]
                if prefix not in prefixes:
                    prefixes.append(prefix)


def independent_acceptance(adapter, contract, query=None):
    """Independent from learner cache, table, successful flags and self-report.

    Fresh reset observations are exhaustively compared for the declared bound.
    This cannot establish that an unknown real system obeys that supplied bound.
    """
    validate_contract(contract)
    if query is None and contract['case'] == 'buyer_local':
        raise ValueError('BUYER_LOCAL_QUERY_CALLABLE_REQUIRED')
    query = local_oracle(contract['case']) if query is None else query
    if (adapter.get('schema') != SCHEMA or adapter.get('alphabet') != contract['alphabet']
            or not 1 <= len(adapter.get('transitions', {})) <= contract['max_states']):
        return {'accepted': False, 'reason': 'INVALID_ADAPTER'}
    checked, holdout_checked = 0, 0
    # Saturating preflight avoids materializing an unaffordable exponential test
    # set or enormous long traces. It is a declared buyer budget, not a fixed N cap.
    exhaustive_count, level = 0, 1
    for _ in range(2 * contract['max_states']):
        exhaustive_count += level
        if 2 * (exhaustive_count + contract['long_holdout_count']) > contract['max_verification_queries']:
            return {'accepted': False, 'reason': 'VERIFICATION_BUDGET_EXHAUSTED',
                    'checked': 0, 'oracle_calls': 0}
        level *= len(contract['alphabet'])
    rng = random.Random('omega-compatibility-long-traces:' + contract['case'])
    holdouts = [tuple(rng.choice(contract['alphabet']) for _ in range(2 * contract['max_states'] + 7))
                for _ in range(contract['long_holdout_count'])]
    try:
        tests = itertools.chain(words(tuple(contract['alphabet']), 2 * contract['max_states'] - 1), holdouts)
        for word in tests:
            if 2 * checked + 2 > contract['max_verification_queries']:
                return {'accepted': False, 'reason': 'VERIFICATION_BUDGET_EXHAUSTED',
                        'checked': checked, 'oracle_calls': 2 * checked}
            checked += 1
            holdout_checked += checked > exhaustive_count
            expected = tuple(query(word))
            # A repeated reset check detects some nondeterminism, not all of it.
            if expected != tuple(query(word)):
                return {'accepted': False, 'reason': 'NONDETERMINISTIC_OR_RESET_FAILURE', 'checked': checked}
            if execute_adapter(adapter, word) != expected:
                return {'accepted': False, 'reason': 'COUNTEREXAMPLE', 'word': list(word), 'checked': checked}
    except (KeyError, TypeError, ValueError, ConnectionError) as exc:
        return {'accepted': False, 'reason': type(exc).__name__, 'checked': checked}
    return {'accepted': True, 'checked': checked, 'oracle_calls': 2 * checked, 'long_holdout_traces': holdout_checked,
            'scope': contract['scope'], 'conditional_on_buyer_assumptions': True}


RUNNER = '''"""Portable local protocol adapter. Standard library only; no network."""
import json
import sys
from pathlib import Path
adapter = json.loads(Path(__file__).with_name("adapter.json").read_text())
state = adapter["initial"]
for symbol in sys.argv[1:]:
    if symbol not in adapter["alphabet"]:
        raise SystemExit("unsupported input: " + symbol)
    step = adapter["transitions"][str(state)][symbol]
    print(step["output"])
    state = step["next"]
'''


def build_product(outputdir, contract=None, *, prior_suffixes=None, proceed=True,
                  unavailable=False, stop_after_queries=None):
    contract = package_contract() if contract is None else contract
    validate_contract(contract)
    if proceed is not True:
        return {'accepted': False, 'status': 'BUYER_DECLINED', 'query_count': 0, 'manifest': {}, 'outputs': {}}
    outputdir = Path(outputdir)
    outputdir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    learner = ActiveLearner(local_oracle(contract['case'], unavailable=unavailable), contract,
                            checkpoint=outputdir / 'checkpoint.json', prior_suffixes=prior_suffixes,
                            stop_after_queries=stop_after_queries)
    try:
        adapter = learner.learn()
    except (QueryLimit, Paused, ConnectionError, ValueError) as exc:
        learner.save()
        return {'accepted': False, 'status': str(exc), 'query_count': len(learner.cache),
                'manifest': {}, 'outputs': {}, 'telemetry': {'seconds': time.perf_counter() - start}}
    payloads = {'adapter.json': canonical(adapter) + b'\n', 'runner.py': RUNNER.encode(),
                'compatibility.py': Path(__file__).read_bytes(),
                'README.md': ("# Local finite-state compatibility adapter\n\n"
                "Run `python3 runner.py start append commit`. Python 3 standard library only.\n"
                "Construct a fresh supplied workflow: `python3 compatibility.py --case queue_revision --output fresh-adapter`.\n"
                "For an authorized buyer-owned local system, import `buyer_contract`, `ActiveLearner`, and `independent_acceptance` from compatibility. "
                "Supply an explicit version ID, alphabet, state/query bounds, and all four verified assumptions to buyer_contract. "
                "Pass a reset-and-query callable to ActiveLearner; call learn(); pass a fresh callable to independent_acceptance. "
                "No third-party adapter, model, hardware or reset capability is included. Establish probe safety separately.\n"
                "This edition reconstructs authored resettable API simulations. The buyer supplies a valid finite state bound, "
                "safe reset, deterministic responses and probe authorization. No general device compatibility or physical safety is certified.\n"
                "Query limits separately bound learning and independent checking. Graceful pause stores observations; sudden termination may repeat safe reset probes.\n"
                "Changed oracle version requires a fresh output directory and complete revalidation; do not edit a checkpoint.\n"
                "Local help: `python3 compatibility.py --help-topic oracle_unavailable`. Unknown issues remain unresolved.\n"
                "Unknown commands fail closed. No external model routing or paid account is implemented.\n"
                "No ongoing updates or personal support are promised. Stop if reset, permissions, resources or the bound are unknown.\n").encode()}
    for name, raw in payloads.items():
        path = outputdir / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('EXISTING_DELIVERY_CHANGED')
        path.write_bytes(raw)
    manifest = {'schema': SCHEMA, 'contract_sha256': digest(contract),
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}}
    (outputdir / 'manifest.json').write_bytes(canonical(manifest) + b'\n')
    acceptance = accept_product(outputdir, contract)
    return {'accepted': acceptance['accepted'], 'status': 'BUILT', 'manifest': manifest,
            'outputs': {'adapter': str(outputdir / 'adapter.json'), 'runner': str(outputdir / 'runner.py')},
            'query_count': len(learner.cache), 'new_queries': len(learner.cache) - learner.start_queries,
            'total_query_count': len(learner.cache) + acceptance.get('oracle_calls', 0),
            'retained_suffixes': [list(s) for s in learner.suffixes], 'acceptance': acceptance,
            'telemetry': {'seconds': time.perf_counter() - start, 'cost_basis': 'MEASURED_WALL_TIME_NOT_HUMAN_LABOR_OR_BILL',
                          'paid_model_calls': 0, 'network_calls': 0},
            'next_action': 'USE_ONLY_WITHIN_ACCEPTED_CONTRACT; REVALIDATE_CHANGED_ORACLE'}


def accept_product(path, contract):
    path = Path(path)
    try:
        manifest = json.loads((path / 'manifest.json').read_text())
        if manifest['schema'] != SCHEMA or manifest['contract_sha256'] != digest(contract):
            return {'accepted': False, 'reason': 'CONTRACT_BINDING_CHANGED'}
        if set(manifest['files']) != {'adapter.json', 'runner.py', 'README.md', 'compatibility.py'}:
            return {'accepted': False, 'reason': 'INCOMPLETE_PACKAGE'}
        for name, sha in manifest['files'].items():
            if (path / name).is_symlink() or hashlib.sha256((path / name).read_bytes()).hexdigest() != sha:
                return {'accepted': False, 'reason': 'PACKAGE_INTEGRITY'}
        if (path / 'compatibility.py').read_bytes() != Path(__file__).read_bytes():
            return {'accepted': False, 'reason': 'LEARNER_EDITION_CHANGED'}
        # Runner is part of the promised usable package, not arbitrary supplied code.
        if (path / 'runner.py').read_text() != RUNNER:
            return {'accepted': False, 'reason': 'UNSUPPORTED_RUNNER'}
        return independent_acceptance(json.loads((path / 'adapter.json').read_text()), contract)
    except (OSError, KeyError, ValueError, TypeError):
        return {'accepted': False, 'reason': 'MISSING_OR_INVALID_PACKAGE'}


def successor_comparison():
    """Fresh revision; inherited probe content competes with ordinary equal reuse."""
    predecessor = ActiveLearner(local_oracle(), package_contract())
    predecessor.learn()
    rows = []
    for case in ('queue_revision', 'strict_revision'):
        for arm, suffixes in [('no_inheritance', None), ('cash_only', None),
                              ('retained_probe_content', predecessor.suffixes),
                              ('ordinary_equal_content', predecessor.suffixes)]:
            contract = package_contract(case)
            learner = ActiveLearner(local_oracle(case), contract, prior_suffixes=suffixes)
            adapter = learner.learn()
            verdict = independent_acceptance(adapter, contract)
            rows.append({'case': case, 'arm': arm, 'accepted': verdict['accepted'],
                         'queries': len(learner.cache), 'independent_queries': verdict['oracle_calls'],
                         'adapter_sha256': digest(adapter)})
    return {'predecessor_queries': len(predecessor.cache), 'rows': rows,
            'scope': 'ORDINARY_ACTIVE_LEARNING_AND_EQUAL_CONTENT_CONTROL; NO_METHOD_ADVANTAGE_ASSUMED'}


def diagnose(topic, package_dir=None):
    """Deterministic local documentation lookup; not an all-purpose assistant."""
    if package_dir is not None:
        document = Path(package_dir) / 'README.md'
    else:
        here = Path(__file__).parent
        document = here / ('README.md' if (here / 'adapter.json').exists() else 'COMPATIBILITY.md')
    markers = {'unknown_input': 'Unknown', 'oracle_unavailable': 'reset',
               'insufficient_resources': 'query', 'changed_oracle': 'version',
               'unclear_ambition': 'authored'}
    if topic not in markers:
        return {'status': 'UNRESOLVED', 'guidance': 'No known diagnosis. Pause the workflow and investigate locally; no external action is authorized.'}
    try:
        raw = document.read_bytes()
    except OSError:
        return {'status': 'UNRESOLVED', 'guidance': 'Product documentation is unavailable. Restore the verified edition before proceeding.'}
    matches = [{'line': i, 'text': line.strip()} for i, line in enumerate(raw.decode().splitlines(), 1)
               if markers[topic].lower() in line.lower() and line.strip()]
    if not matches:
        return {'status': 'UNRESOLVED', 'guidance': 'No matching guidance in the actual product documentation.'}
    return {'status': 'DOCUMENTED_GUIDANCE_NOT_GUARANTEED_RESOLUTION', 'topic': topic,
            'source': str(document), 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'passages': matches[:3], 'external_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--help-topic', choices=['unknown_input', 'oracle_unavailable', 'insufficient_resources', 'changed_oracle', 'unclear_ambition', 'unknown'])
    parser.add_argument('--case', choices=CASES, default='legacy_queue')
    parser.add_argument('--max-states', type=int, default=4)
    parser.add_argument('--max-queries', type=int, default=20000)
    parser.add_argument('--decline', action='store_true')
    args = parser.parse_args()
    if args.help_topic:
        print(json.dumps(diagnose(args.help_topic, args.output), sort_keys=True))
        return 0
    if not args.output:
        parser.error('--output is required for construction')
    result = build_product(args.output, package_contract(args.case, max_states=args.max_states,
                                                        max_queries=args.max_queries), proceed=not args.decline)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['accepted'] or args.decline else 2


if __name__ == '__main__':
    raise SystemExit(main())
