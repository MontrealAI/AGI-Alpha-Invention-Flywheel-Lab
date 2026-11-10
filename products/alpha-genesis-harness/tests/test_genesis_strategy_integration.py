# SPDX-License-Identifier: Apache-2.0
"""Cross-feature regressions for GENESIS evidence and isolated strategies."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge import genesis_next, workflow_strategies
from bridge.genesis_next import EvidenceIndex, GenesisNextService, construct_candidate, load_candidate
from bridge.workflow_demo import FixtureRuntime, instrument, proposal, specification
from bridge.workflows import WorkflowService


class GenesisStrategyIntegrationTests(unittest.TestCase):
    def test_adjudicated_counterexample_cannot_reuse_an_earlier_passing_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidate = load_candidate(construct_candidate(root / 'candidate')['path'])
            index = EvidenceIndex('integration-checker')
            service = candidate(FixtureRuntime([]), root / 'runs', index, {'checker': 'a' * 64})
            self.addCleanup(service.close)
            spec = specification()
            spec['roles'].pop('critic')
            spec['adversarial_oracles'] = {'affine.json': instrument(True)}
            state = service._load(service.create(spec)['id'])
            faulty = instrument(True)
            faulty['outputs']['result'] = {'op': 'if', 'args': [{'op': 'lt', 'args': [{'field': 'x'}, 0]}, 0, faulty['outputs']['result']]}
            service._write(state, 'affine.json', json.dumps(faulty), 'instrument')
            service._verify(state)
            self.assertTrue(state['verification']['passed'])
            service._verify(state)
            self.assertEqual(index.verification_calls, 1)
            service._adversarial_review(state, {'counterexamples': [{'artifact': 'affine.json', 'input': {'x': -2, 'gain': 3, 'offset': 4}, 'reason': 'Negative boundary'}], 'feedback': 'Check this boundary.'})
            self.assertFalse(state['verification']['passed'])
            self.assertNotEqual(state['status'], 'complete')
            self.assertEqual(len(state['verification']['checks']), 3)
            self.assertEqual(index.verification_calls, 2)
            self.assertIsNone(state['capability_id'])
            service._write(state, 'affine.json', json.dumps(instrument(True)), 'instrument')
            service._verify(state)
            self.assertTrue(state['verification']['passed'])
            self.assertEqual(index.verification_calls, 3)

    def test_parallel_trace_counts_losing_work_and_each_request_once(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = FixtureRuntime([proposal(False), proposal(True)])
            generate = runtime.generate
            def generate_reported(data):
                result = generate(data)
                result['reported_model'] = 'actual-served-fixture-revision'
                return result
            runtime.generate = generate_reported
            service = WorkflowService(runtime, folder)
            self.addCleanup(service.close)
            spec = specification()
            spec['roles'].pop('critic')
            spec.update(strategy='parallel-exploration', approaches=['Direct equation', 'Expanded equation'], max_iterations=2, max_actions=2)
            state = service.create(spec)
            while state['status'] == 'ready':
                state = service.step(state['id'])
            self.assertEqual(state['status'], 'complete')
            observed = GenesisNextService(service).status()['observations']
            self.assertEqual(observed['model_calls'], 2)
            self.assertEqual(observed['unknown_model_costs'], 2)
            self.assertEqual(observed['failed_verifications'], 1)
            self.assertEqual(len(observed['runs']), 3)
            parent = next(r for r in observed['runs'] if r['run_id'] == state['id'])
            self.assertEqual(parent['model_routes'], [])
            routes = [route for run in observed['runs'] for route in run['model_routes']]
            self.assertEqual(len({route['run_id'] for route in routes}), 2)
            self.assertTrue(all(route['reported_model'] == 'actual-served-fixture-revision' for route in routes))
            self.assertTrue(all(r['event_chain_sha256'] for r in observed['runs']))
            self.assertIn('exhausted', [r['status'] for r in observed['runs']])

    def test_transport_error_and_explicit_resume_keep_both_attempts(self):
        runtime = FixtureRuntime([proposal(True)])
        generate = runtime.generate
        failed = False
        def generate_with_error(data):
            nonlocal failed
            if not failed:
                failed = True
                raise BridgeError('FIXTURE_TRANSPORT', 'Authored transport failure.')
            return generate(data)
        runtime.generate = generate_with_error
        with tempfile.TemporaryDirectory() as folder:
            service = WorkflowService(runtime, folder)
            self.addCleanup(service.close)
            spec = specification()
            spec['roles'].pop('critic')
            state = service.step(service.create(spec)['id'])
            self.assertEqual(state['status'], 'paused')
            service.resume(state['id'], background=False)
            state = service.step(state['id'])
            self.assertEqual(state['status'], 'complete')
            observed = GenesisNextService(service).status()['observations']
            self.assertEqual(observed['model_calls'], 2)
            self.assertEqual(observed['unknown_model_costs'], 2)
            routes = observed['runs'][0]['model_routes']
            self.assertEqual([r['event_kind'] for r in routes], ['model_error', 'model_completed'])
            self.assertEqual(len({r['run_id'] for r in routes}), 2)

    def test_strategy_executor_is_a_loaded_source_dependency(self):
        identities = genesis_next.source_identity()
        expected = hashlib.sha256(Path(workflow_strategies.__file__).read_bytes()).hexdigest()
        self.assertEqual(identities['workflow_strategies.py'], expected)
        self.assertEqual(workflow_strategies.LOADED_SOURCE_SHA256, expected)
        with patch.object(workflow_strategies, 'LOADED_SOURCE_SHA256', '0' * 64):
            with self.assertRaises(BridgeError) as error:
                genesis_next.source_identity()
        self.assertEqual(error.exception.code, 'GENESIS_SOURCE_DRIFT')

    def test_changed_strategy_bytes_are_refused_after_module_load(self):
        regular = genesis_next._regular
        def changed(path, *args):
            data = regular(path, *args)
            return data + b'\n# changed source\n' if Path(path).name == 'workflow_strategies.py' else data
        with patch.object(genesis_next, '_regular', side_effect=changed):
            with self.assertRaises(BridgeError) as error:
                genesis_next.require_current_source()
        self.assertEqual(error.exception.code, 'GENESIS_SOURCE_DRIFT')


if __name__ == '__main__':
    unittest.main()
