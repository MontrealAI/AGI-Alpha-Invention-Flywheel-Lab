import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from omega.compatibility import (ActiveLearner, ALPHABET, CASES, QueryLimit, accept_product,
    build_product, buyer_contract, canonical, diagnose, digest, execute_adapter, independent_acceptance, local_oracle,
    package_contract, successor_comparison)


class CompatibilityTests(unittest.TestCase):
    def test_complete_buyer_journey_and_standalone_install(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = package_contract()
            result = build_product(directory, contract)
            self.assertTrue(result['accepted'])
            self.assertEqual(result['acceptance']['long_holdout_traces'], 40)
            self.assertEqual(result['total_query_count'], result['query_count'] + result['acceptance']['oracle_calls'])
            run = subprocess.run([sys.executable, str(Path(directory) / 'runner.py'),
                                  'start', 'append', 'commit'], capture_output=True, text=True, check=True)
            self.assertEqual(run.stdout.splitlines(), ['opened', 'appended', 'committed'])
            self.assertTrue(accept_product(directory, contract)['accepted'])

    def test_downloaded_learner_constructs_fresh_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            package, successor = Path(directory) / 'package', Path(directory) / 'successor'
            build_product(package)
            run = subprocess.run([sys.executable, str(package / 'compatibility.py'), '--output',
                                  str(successor), '--case', 'queue_revision'], capture_output=True, text=True, check=True)
            self.assertTrue(json.loads(run.stdout)['accepted'])
            self.assertTrue((successor / 'compatibility.py').is_file())

    def test_buyer_local_callable_and_explicit_assumptions(self):
        # Independently authored two-state local protocol; not in supplied CASES.
        def query(word):
            state, output = False, []
            for a in word:
                if a == 'toggle':
                    state = not state
                output.append('on' if state else 'off')
            return tuple(output)
        assumptions = package_contract()['buyer_supplied_assumptions']
        contract = buyer_contract('buyer-local-toggle-v1', ['toggle', 'read'], max_states=2,
                                  assumptions=assumptions)
        adapter = ActiveLearner(query, contract).learn()
        self.assertTrue(independent_acceptance(adapter, contract, query)['accepted'])
        with self.assertRaisesRegex(ValueError, 'BUYER_LOCAL_QUERY_CALLABLE_REQUIRED'):
            independent_acceptance(adapter, contract)
        with self.assertRaisesRegex(ValueError, 'BUYER_MUST_ESTABLISH_ALL_ASSUMPTIONS'):
            buyer_contract('buyer-v1', ['toggle'], max_states=2)

    def test_decline_has_no_delivery_or_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'not-created'
            result = build_product(target, proceed=False)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['query_count'], 0)
            self.assertFalse(target.exists())

    def test_each_authored_protocol_recovered_without_state_access(self):
        for case in CASES:
            observed = []
            oracle = local_oracle(case)
            def query(word):
                observed.append(tuple(word))
                return oracle(word)
            learner = ActiveLearner(query, package_contract(case))
            adapter = learner.learn()
            verdict = independent_acceptance(adapter, package_contract(case))
            self.assertTrue(verdict['accepted'])
            self.assertEqual(len(observed), len(learner.cache))
            self.assertTrue(all(len(w) <= 7 for w in observed))

    def test_unknown_input_fails_closed(self):
        learner = ActiveLearner(local_oracle(), package_contract())
        adapter = learner.learn()
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_INPUT'):
            execute_adapter(adapter, ['delete_all'])
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_AUTHORED_CASE'):
            package_contract('unrecognized ambition')

    def test_local_oracle_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = build_product(directory, unavailable=True)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['query_count'], 0)
            self.assertFalse((Path(directory) / 'adapter.json').exists())

    def test_learning_and_verification_resource_limits(self):
        learner = ActiveLearner(local_oracle(), package_contract(max_queries=2))
        with self.assertRaises(QueryLimit):
            learner.learn()
        self.assertEqual(len(learner.cache), 2)
        learner = ActiveLearner(local_oracle(), package_contract())
        adapter = learner.learn()
        calls = []
        def counted(word):
            calls.append(word)
            return local_oracle()(word)
        result = independent_acceptance(adapter, package_contract(max_verification_queries=3), counted)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'VERIFICATION_BUDGET_EXHAUSTED')
        self.assertEqual(len(calls), 0)

    def test_interrupted_repeat_and_resume_reuse_only_same_oracle_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            first = build_product(directory, stop_after_queries=8)
            self.assertFalse(first['accepted'])
            self.assertEqual(first['query_count'], 8)
            resumed = build_product(directory)
            self.assertTrue(resumed['accepted'])
            self.assertEqual(resumed['new_queries'] + 8, resumed['query_count'])
            repeated = build_product(directory)
            self.assertEqual(repeated['new_queries'], 0)
            self.assertEqual(repeated['manifest'], resumed['manifest'])
            with self.assertRaisesRegex(ValueError, 'CHECKPOINT_ORACLE_OR_CONTRACT_CHANGED'):
                build_product(directory, package_contract('queue_revision'))

    def test_missing_permission_or_unknown_assumptions_rejected(self):
        for assumption in ('deterministic', 'state_bound_valid', 'reliable_reset', 'local_probe_authorized'):
            contract = package_contract()
            contract['buyer_supplied_assumptions'][assumption] = False
            with self.assertRaisesRegex(ValueError, 'CONTRACT_CHANGED_OR_PERMISSION_MISSING'):
                ActiveLearner(local_oracle(), contract)

    def test_permission_flags_cannot_be_numeric_proxies(self):
        contract = package_contract()
        contract['buyer_supplied_assumptions']['local_probe_authorized'] = 1
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_BOOLEAN_ASSUMPTIONS_REQUIRED'):
            ActiveLearner(local_oracle(), contract)

    def test_wrong_observed_state_bound_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DECLARED_STATE_BOUND_CONTRADICTED'):
            ActiveLearner(local_oracle(), package_contract(max_states=2)).learn()

    def test_repeated_reset_failure_rejected(self):
        learner = ActiveLearner(local_oracle(), package_contract())
        adapter = learner.learn()
        count = [0]
        def inconsistent(word):
            count[0] += 1
            values = list(local_oracle()(word))
            if count[0] % 2 and values:
                values[-1] = 'changed'
            return values
        self.assertFalse(independent_acceptance(adapter, package_contract(), inconsistent)['accepted'])

    def test_self_report_and_updated_hash_cannot_authorize_wrong_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            build_product(directory)
            path = Path(directory)
            adapter = json.loads((path / 'adapter.json').read_text())
            adapter['transitions']['0']['start']['output'] = 'wrong'
            raw = canonical(adapter) + b'\n'
            (path / 'adapter.json').write_bytes(raw)
            manifest = json.loads((path / 'manifest.json').read_text())
            manifest['files']['adapter.json'] = hashlib.sha256(raw).hexdigest()
            manifest['accepted'] = True
            (path / 'manifest.json').write_bytes(canonical(manifest))
            verdict = accept_product(path, package_contract())
            self.assertFalse(verdict['accepted'])
            self.assertEqual(verdict['reason'], 'COUNTEREXAMPLE')

    def test_package_integrity_and_runner_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            build_product(directory)
            path = Path(directory)
            (path / 'runner.py').write_text('print("approved")')
            self.assertFalse(accept_product(path, package_contract())['accepted'])
            manifest = json.loads((path / 'manifest.json').read_text())
            manifest['files']['runner.py'] = hashlib.sha256((path / 'runner.py').read_bytes()).hexdigest()
            (path / 'manifest.json').write_bytes(canonical(manifest))
            self.assertEqual(accept_product(path, package_contract())['reason'], 'UNSUPPORTED_RUNNER')

    def test_successor_equal_content_conventional_control(self):
        results = successor_comparison()
        self.assertEqual(len(results['rows']), 8)
        for case in ('queue_revision', 'strict_revision'):
            rows = {r['arm']: r for r in results['rows'] if r['case'] == case}
            self.assertTrue(all(r['accepted'] for r in rows.values()))
            self.assertEqual(rows['retained_probe_content']['queries'], rows['ordinary_equal_content']['queries'])
            self.assertEqual(rows['retained_probe_content']['adapter_sha256'], rows['ordinary_equal_content']['adapter_sha256'])

    def test_local_help_uses_actual_documentation_and_admits_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            build_product(directory)
            guidance = diagnose('oracle_unavailable', directory)
            self.assertEqual(guidance['external_calls'], 0)
            self.assertTrue(guidance['passages'])
            self.assertEqual(diagnose('unrecognized failure', directory)['status'], 'UNRESOLVED')
            path = Path(directory) / 'README.md'
            path.write_text('Reset requires an authorized local sandbox.\n')
            changed = diagnose('oracle_unavailable', directory)
            self.assertEqual(changed['passages'][0]['text'], 'Reset requires an authorized local sandbox.')
            self.assertNotEqual(changed['source_sha256'], guidance['source_sha256'])
            result = subprocess.run([sys.executable, str(Path(directory) / 'compatibility.py'),
                                     '--help-topic', 'oracle_unavailable'], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['passages'][0]['text'], changed['passages'][0]['text'])

    def test_invalid_resource_values_rejected(self):
        for value in (0, -1, True, 3.4, None):
            with self.assertRaises(ValueError):
                package_contract(max_states=value)
            with self.assertRaises(ValueError):
                package_contract(max_queries=value)


if __name__ == '__main__':
    unittest.main()
