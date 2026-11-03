"""Diagnostic stronger-specialist check; not fresh market confirmation.

One fixed method (AALpy L* + bounded W-method), all three existing authored
protocols, unchanged independent checker, only a reset-and-query callable.
No private target tables, future models, paid calls, or financial state.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import time

DEPENDENCIES = {
    'pydot': ('4.0.1', '763f3c2041d9ca7a3f6edd974e7459553569a29922c7e6d2a8bc210760dd15f8'),
    'pyparsing': ('3.3.3', '34659f5c8ce47b2dec6f79b2c547681da5674cbb29c41bbe432cee25dfdc1065')}


def dependency_identities():
    result = {}
    for name, (version, expected_hash) in DEPENDENCIES.items():
        distribution = importlib.metadata.distribution(name)
        if distribution.version != version:
            raise ValueError('EXACT_DEPENDENCY_VERSION_REQUIRED:' + name)
        root = Path(distribution.locate_file(''))
        files = {q.relative_to(root).as_posix(): hashlib.sha256(q.read_bytes()).hexdigest()
                 for q in (root/name).rglob('*.py')}
        source_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if source_hash != expected_hash:
            raise ValueError('EXACT_DEPENDENCY_SOURCE_REQUIRED:' + name)
        result[name] = {'version': version, 'python_source_manifest_sha256': source_hash,
                        'python_files': len(files)}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab-root', required=True)
    p.add_argument('--aalpy-root', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    lab, specialist = Path(a.lab_root).resolve(), Path(a.aalpy_root).resolve()
    expected = '4c7b4a8746460fd84eaccb48d4891e5e0ac90883'
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=specialist, text=True).strip()
    if actual != expected or subprocess.check_output(['git','status','--porcelain'],cwd=specialist,text=True):
        raise ValueError('EXACT_UNMODIFIED_SPECIALIST_SOURCE_REQUIRED')
    compatibility_hash = hashlib.sha256((lab/'omega/compatibility.py').read_bytes()).hexdigest()
    if compatibility_hash != '1fd025189b6473a1a568b62a4273139819a8a26857ca7cb2f0dfb47a6cf7ebbf':
        raise ValueError('EXACT_REGISTERED_LEARNER_AND_CHECKER_REQUIRED')
    dependencies = dependency_identities()
    sys.path[:0] = [str(lab), str(specialist)]
    from omega.compatibility import (ActiveLearner, ALPHABET, CASES, SCHEMA,
        RUNNER, independent_acceptance, local_oracle, package_contract)
    from aalpy.base import SUL
    from aalpy.learning_algs import run_Lstar
    from aalpy.oracles import WMethodEqOracle

    class Counter:
        def __init__(self, query):
            self.call = query
            self.calls = self.symbols = 0
        def __call__(self, word):
            self.calls += 1
            self.symbols += len(word)
            if self.calls > 20000:
                raise RuntimeError('LEARNING_QUERY_BUDGET_EXCEEDED')
            return self.call(word)

    class WordSUL(SUL):
        def __init__(self, query):
            super().__init__()
            self.query_word = query
            self.prefix = ()
        def pre(self): self.prefix = ()
        def post(self): pass
        def query(self, word):
            self.num_queries += 1
            self.num_steps += len(word)
            return list(self.query_word(tuple(word)))
        def step(self, letter):
            # Same callable interface as our learner. Re-execute the whole
            # prefix for a step; count this extra cost, expose no target state.
            self.prefix += (letter,)
            return self.query_word(self.prefix)[-1]

    rows = []
    for case in CASES:
        contract = package_contract(case)
        for method in ('registered_learner', 'aalpy_lstar_wmethod'):
            pipeline_start = time.perf_counter()
            counter = Counter(local_oracle(case))
            start, cpu = time.perf_counter(), time.process_time()
            if method == 'registered_learner':
                adapter = ActiveLearner(counter, contract).learn()
            else:
                sul = WordSUL(counter)
                oracle = WMethodEqOracle(list(ALPHABET), sul, max_number_of_states=4)
                learned = run_Lstar(list(ALPHABET), sul, oracle, 'mealy', print_level=0)
                numbers = {state: i for i, state in enumerate(learned.states)}
                adapter = {'schema': SCHEMA, 'alphabet': list(ALPHABET),
                    'initial': numbers[learned.initial_state],
                    'transitions': {str(numbers[s]): {symbol: {
                        'next': numbers[s.transitions[symbol]], 'output': s.output_fun[symbol]}
                        for symbol in ALPHABET} for s in learned.states}}
            learning_wall, learning_cpu = time.perf_counter()-start, time.process_time()-cpu
            check_counter = Counter(local_oracle(case))
            acceptance = independent_acceptance(adapter, contract, check_counter)
            with tempfile.TemporaryDirectory(prefix='omega-specialist-diagnostic-') as d:
                target = Path(d)
                (target/'adapter.json').write_text(json.dumps(adapter, sort_keys=True))
                (target/'runner.py').write_text(RUNNER)
                output = subprocess.check_output([sys.executable,str(target/'runner.py'),
                    'start','append','commit'], text=True).splitlines()
                if tuple(output) != local_oracle(case)(('start','append','commit')):
                    raise ValueError('PORTABLE_EXECUTION_MISMATCH')
            rows.append({'case': case, 'method': method,
                'learning_oracle_calls': counter.calls,
                'learning_input_symbols': counter.symbols,
                'checking_oracle_calls': check_counter.calls,
                'checking_input_symbols': check_counter.symbols,
                'portable_smoke_oracle_calls': 1,
                'portable_smoke_input_symbols': 3,
                'all_measured_oracle_calls': counter.calls + check_counter.calls + 1,
                'all_measured_input_symbols': counter.symbols + check_counter.symbols + 3,
                'accepted': acceptance['accepted'],
                'portable_runner_accepted': True,
                'learning_wall_seconds': learning_wall,
                'learning_cpu_seconds': learning_cpu,
                'pipeline_wall_seconds': time.perf_counter() - pipeline_start,
                'adapter_sha256': hashlib.sha256(json.dumps(adapter,sort_keys=True,separators=(',',':')).encode()).hexdigest()})
    report = {'scope': 'EXPOSED_AUTHORED_DIAGNOSTIC_NOT_FRESH_CONFIRMATION_OR_DEMAND',
        'method_selected_before_run': 'AALpy L* defaults, bounded W-method state bound4; no tuning',
        'specialist_commit': actual, 'specialist_license': 'MIT; no specialist source redistributed',
        'specialist_tree': subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=specialist,text=True).strip(),
        'dependencies': dependencies,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'compatibility_sha256': compatibility_hash,
        'same_query_interface': True, 'same_acceptance': True,
        'cases_selected': list(CASES), 'rows': rows,
        'limitations': ['No full setup or human-effort comparison',
                       'Existing authored cases, no new external protocol',
                       'All determinism/reset/state-bound prerequisites unchanged',
                       'Wall/CPU telemetry on shared host, not controlled speedup',
                       'No simulated or real revenue; no current account changed']}
    Path(a.output).write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps(report,sort_keys=True))


if __name__ == '__main__': main()
