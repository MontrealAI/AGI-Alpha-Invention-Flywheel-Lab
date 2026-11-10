# SPDX-License-Identifier: Apache-2.0
"""Executable policy qualification with explicitly authored model responses."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.workflow_demo import FixtureRuntime, instrument, proposal, specification
from bridge.workflows import WorkflowService, portable_digest
from bridge.adapters import BridgeError


class RoutedRuntime(FixtureRuntime):
    max_concurrent = 4
    def __init__(self, responder):
        super().__init__([])
        self.responder = responder
    def generate(self, data):
        self.calls.append(data)
        payload = json.loads(data['prompt'].split('UNTRUSTED_WORKSPACE_DATA\n', 1)[1])
        response = self.responder(data, payload)
        return {'text': json.dumps(response), 'provider': data['provider'], 'model': data['model'], 'cost': {'amount': None, 'basis': 'AUTHORED_FIXTURE'}, 'usage': {}}


class StrategyTests(unittest.TestCase):
    def service(self, runtime):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        service = WorkflowService(runtime, temp.name)
        self.addCleanup(service.close)
        return service

    def spec(self, strategy='parallel-exploration'):
        spec = specification()
        spec['roles'].pop('critic')
        spec.update(strategy=strategy, approaches=['Direct affine equation.', 'Sum repeated products and explicit offset.'], max_iterations=3, max_actions=6)
        return spec

    def finish(self, service, state):
        for _ in range(30):
            if state['status'] != 'ready':
                return state
            state = service.step(state['id'])
        self.fail('Strategy failed to terminate within allocated calls.')

    def test_parallel_concurrent_isolated_and_deterministically_selected(self):
        barrier = threading.Barrier(2)
        def respond(data, payload):
            barrier.wait(timeout=3)
            self.assertEqual(payload['artifacts'], {})
            return proposal(True)
        runtime = RoutedRuntime(respond)
        service = self.service(runtime)
        state = self.finish(service, service.create(self.spec()))
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['model_calls'], 2)
        self.assertEqual(state['actions'], 2)
        self.assertEqual(state['selected_branch'], state['branches'][0]['run_id'])
        self.assertEqual(len(service.list()['runs']), 1)
        self.assertEqual(len(service.capabilities()['capabilities'][0]['costs']), 2)
        for branch in state['branches']:
            self.assertEqual(branch['verification']['artifact_hashes'], state['verification']['artifact_hashes'])
            with self.assertRaises(BridgeError):
                service.step(branch['run_id'])

    def test_adaptive_switch_uses_failure_and_preserves_total_allocation(self):
        def respond(data, payload):
            return proposal('direct conventional approach' not in payload['context'])
        runtime = RoutedRuntime(respond)
        service = self.service(runtime)
        state = self.finish(service, service.create(self.spec('adaptive')))
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['model_calls'], 3)
        self.assertEqual(state['iteration'], 3)
        self.assertEqual(state['branches'][0]['status'], 'exhausted')
        switch = next(e['detail'] for e in state['events'] if e['kind'] == 'strategy_switched')
        self.assertTrue(switch['evidence'])
        self.assertFalse(switch['permissions_changed'])
        self.assertTrue(all(row['roles'] == state['roles'] for row in state['branches']))

    def test_parallel_archive_keeps_loser_and_rejects_extra_authority(self):
        runtime = RoutedRuntime(lambda data, p: proposal('Direct affine' in p['context']))
        service = self.service(runtime)
        state = self.finish(service, service.create(self.spec()))
        archive = service.export(state['id'])
        self.assertEqual(len(archive['branch_exports']), 2)
        self.assertIn('exhausted', [a['state']['status'] for a in archive['branch_exports']])
        imported = service.import_archive(archive)
        self.assertEqual(imported['status'], 'paused')
        self.assertFalse(imported['verification']['passed'])
        self.assertTrue(set(b['run_id'] for b in imported['branches']).isdisjoint(b['run_id'] for b in state['branches']))
        bad = copy.deepcopy(archive)
        child = bad['branch_exports'][0]
        child['state']['spec']['max_actions'] += 1
        child['sha256'] = portable_digest({k:v for k,v in child.items() if k != 'sha256'})
        bad['sha256'] = portable_digest({k:v for k,v in bad.items() if k != 'sha256'})
        with self.assertRaises(BridgeError):
            service.import_archive(bad)

    def test_adversary_executes_frozen_reference_counterexample_then_repair(self):
        bad = instrument(True)
        bad['outputs']['result'] = {'op':'if', 'args':[{'op':'lt','args':[{'field':'x'},0]}, 0, bad['outputs']['result']]}
        response = proposal(True)
        response['actions'][0]['spec'] = bad
        adversary = {'counterexamples':[{'artifact':'affine.json','input':{'x':-2,'gain':3,'offset':4},'expected':{'result':999},'reason':'Negative x boundary'}], 'feedback':'Test negative input against reference.'}
        runtime = FixtureRuntime([response, adversary, proposal(True), adversary])
        service = self.service(runtime)
        spec = specification()
        spec['roles'].pop('critic')
        spec['roles']['adversary'] = {'provider':'fixture','model':'authored-adversary'}
        spec['strategy'] = 'adversarial-review'
        spec['adversarial_oracles'] = {'affine.json':instrument(True)}
        state = self.finish(service, service.create(spec))
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(state['model_calls'], 4)
        self.assertEqual(state['adversarial_cases'][0]['expected'], {'result':-2})
        verdicts = [e['detail']['findings'][0]['verdict'] for e in state['events'] if e['kind']=='adversarial_review']
        self.assertEqual(verdicts, ['COUNTEREXAMPLE_CONFIRMED','COUNTEREXAMPLE_REJECTED'])
        self.assertEqual(len(state['verification']['checks']), 3)

    def test_unadjudicated_claim_stops_without_model_expected_becoming_test(self):
        runtime = FixtureRuntime([proposal(True), {'counterexamples':[{'artifact':'affine.json','input':{'x':-2,'gain':3,'offset':4},'expected':{'result':999},'reason':'Unknown boundary'}], 'feedback':'Unproven expected'}])
        service = self.service(runtime)
        spec = specification()
        spec['roles'].pop('critic')
        spec['roles']['adversary'] = {'provider':'fixture','model':'authored-adversary'}
        spec['strategy'] = 'adversarial-review'
        state = self.finish(service, service.create(spec))
        self.assertEqual(state['status'], 'needs_review')
        self.assertEqual(state['adversarial_cases'], [])
        self.assertIsNone(state['capability_id'])

    def test_paired_source_comparison_preserves_abstention_and_strong_control(self):
        from bridge.strategy_demo import demonstrate
        with tempfile.TemporaryDirectory() as root:
            evidence = demonstrate(root)
        control, treatment = evidence['arms']
        self.assertTrue(control['honest_abstention'])
        self.assertFalse(control['matches_withheld_source'])
        self.assertEqual(control['fixture_source_fetches'], 0)
        self.assertTrue(treatment['matches_withheld_source'])
        self.assertEqual(treatment['fixture_source_fetches'], 1)
        for arm in evidence['arms']:
            self.assertEqual((arm['model_calls'], arm['actions']), (2, 2))
            self.assertEqual(arm['failed_initial_checks'], 1)
            self.assertEqual(arm['status'], 'complete')
        ordinary = evidence['competent_conventional_control']
        self.assertTrue(ordinary['matches_withheld_source'])
        self.assertEqual(ordinary['model_calls'], 0)


if __name__ == '__main__':
    unittest.main()
