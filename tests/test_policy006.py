import copy
import hashlib
from pathlib import Path
import unittest
from flywheel import sandbox
from mechanisms import policy006 as policy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'mechanisms/policy006.py'
SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()


def action(identity, gain, cost, kind='measure'):
    return {'id': identity, 'kind': kind,
            'features': {'gain': gain, 'cost': cost / 10, 'rarity': .2, 'redundancy': .1, 'breadth': .5, 'remaining': 1},
            'feature_provenance': {name: 'development_prediction' if name == 'gain' else 'observed' for name in policy.FEATURES},
            'source_identities': ['a' * 64], 'cost_units': cost}


def payload(priority=None):
    return {'policy': {'language': policy.LANGUAGE, 'priority': priority or ['div', 'gain', 'cost'], 'stop_below': 0},
            'observation': {'actions': [action('expensive', .9, 9), action('cheap', .5, 2)], 'evidence_sha256': 'b' * 64},
            'budget': {'steps': 4, 'cost_units': 10, 'kinds': {kind: 4 for kind in policy.KINDS}},
            'spent': {'steps': 0, 'cost_units': 0, 'kinds': {kind: 0 for kind in policy.KINDS}}}


class PolicyTests(unittest.TestCase):
    def test_generated_compositions_execute_in_actual_sandbox(self):
        proposals = policy.generate(seed=17, count=24)
        self.assertEqual(len({str(x) for x in proposals['programs']}), 24)
        self.assertTrue(any(isinstance(x['priority'], list) and x['priority'] != ['div', 'gain', 'cost'] for x in proposals['programs']))
        value = payload()
        result = sandbox.run(SOURCE, 'interpret', value, SHA)
        self.assertEqual(result['state'], 'COMPLETE')
        self.assertEqual(result['worker']['confinement'], 'linux-seccomp-default-deny')
        self.assertEqual(result['worker']['result']['selected']['action_id'], 'cheap')
        value['policy']['priority'] = 'gain'
        result = sandbox.run(SOURCE, 'interpret', value, SHA)
        self.assertEqual(result['worker']['result']['selected']['action_id'], 'expensive')

    def test_unchanged_external_budget_blocks_highest_score(self):
        value = payload('gain')
        value['budget']['cost_units'] = 3
        result = policy.interpret(value)
        self.assertEqual(result['selected']['action_id'], 'cheap')
        self.assertEqual(result['budget_blocked'], ['expensive'])
        value['spent']['steps'] = 4
        self.assertEqual(policy.interpret(value)['state'], 'STOP')
        value['spent']['cost_units'] = 4
        with self.assertRaisesRegex(ValueError, 'ALREADY_OVERRUN'):
            policy.interpret(value)

    def test_forbidden_effects_and_protected_truth_are_refused(self):
        edits = [('features', {'truth': 1}), ('kind', 'shell'), ('feature_provenance', {x: 'protected_truth' for x in policy.FEATURES}), ('cost_units', 0)]
        for field, wrong in edits:
            with self.subTest(field=field):
                value = payload()
                value['observation']['actions'][0][field] = wrong
                with self.assertRaises(ValueError):
                    policy.interpret(value)
        value = payload()
        value['policy']['judge'] = 'accept'
        with self.assertRaisesRegex(ValueError, 'POLICY_SCHEMA'):
            policy.interpret(value)

    def test_numeric_depth_and_identity_boundaries(self):
        for expression in [float('nan'), float('inf'), ['pow', 2, 8], '__import__', ['add', 1, True]]:
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    policy.validate({'language': policy.LANGUAGE, 'priority': expression, 'stop_below': 0})
        value = payload()
        value['observation']['actions'].append(copy.deepcopy(value['observation']['actions'][0]))
        with self.assertRaisesRegex(ValueError, 'ACTION_ID_OR_KIND'):
            policy.interpret(value)
        with self.assertRaisesRegex(ValueError, 'SOURCE_IDENTITY_MISMATCH'):
            sandbox.run(SOURCE, 'interpret', payload(), '0' * 64)

    def test_external_broker_records_actual_effect_and_stops_with_budget(self):
        class Broker:
            def __init__(self):
                self.ids = []
            def observe(self):
                value = payload()['observation']
                value['actions'] = [item for item in value['actions'] if item['id'] not in self.ids]
                return value
            def execute(self, identity):
                self.ids.append(identity)
                item = next(x for x in payload()['observation']['actions'] if x['id'] == identity)
                return {'action_id': identity, 'kind': item['kind'], 'cost_units': item['cost_units'],
                        'artifact_sha256': 'c' * 64, 'observation_sha256': 'd' * 64}
        broker = Broker()
        value = payload()
        result = policy.run(value['policy'], broker, value['budget'], SOURCE, SHA)
        self.assertEqual(broker.ids, ['cheap'])
        self.assertEqual(result['spent']['cost_units'], 2)
        self.assertEqual(result['state'], 'STOP')
        self.assertEqual(result['records'][0]['outcome']['artifact_sha256'], 'c' * 64)

    def test_failed_broker_does_not_refund_or_hide_failure(self):
        class Broker:
            def observe(self):
                return payload()['observation']
            def execute(self, identity):
                raise RuntimeError('observed experimental failure')
        value = payload()
        result = policy.run(value['policy'], Broker(), value['budget'], SOURCE, SHA)
        self.assertEqual(result['state'], 'FAILED')
        self.assertEqual(result['spent']['cost_units'], 2)
        self.assertEqual(result['records'][0]['state'], 'BROKER_FAILED')


if __name__ == '__main__':
    unittest.main()
