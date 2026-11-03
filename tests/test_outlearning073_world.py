import copy
import hashlib
import unittest
from outlearning073.worlds import ToolSandbox, _spec, development_requests, identity, make_session
from outlearning073.verify import grade_execution, verify


def archive_artifact(public, shared=False):
    output = {r['intent']: {'content': r['content'], 'sha256': hashlib.sha256(r['content'].encode()).hexdigest()} for r in public['objects']}
    steps = []
    for intent in public['intents']:
        write = {'op': 'write', 'intent': intent, 'key': 'shared' if shared else 'unit-test/' + intent, 'value': '$output:' + intent}
        steps += [write, {'op': 'if', 'test': {'intent': intent, 'is': 'committed'}, 'then': [], 'else': [copy.deepcopy(write)]}]
    return {'steps': steps, 'output': output}


class WorldAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.request = development_requests()[0]
        self.public = make_session(self.request).public

    def test_correct_exact_archive_and_wrong_product(self):
        artifact = archive_artifact(self.public)
        self.assertTrue(verify(self.request, artifact)['accepted'])
        artifact['output']['archive0']['content'] = 'wrong-content'
        receipt = verify(self.request, artifact)
        self.assertFalse(receipt['accepted'])
        self.assertFalse(receipt['output_ok'])

    def test_shared_key_suppresses_other_required_intent(self):
        receipt = verify(self.request, archive_artifact(self.public, shared=True))
        self.assertFalse(receipt['accepted'])
        self.assertTrue(any(0 in row['counts'].values() for row in receipt['results']))

    def test_pending_effects_are_drained_and_duplicate_loss_retained(self):
        request = development_requests()[2]
        receipt = verify(request, archive_artifact(make_session(request).public))
        late = next(row for row in receipt['results'] if row['faults'] == {'archive0': 'late', 'archive1': 'late'})
        self.assertFalse(late['accepted'])
        self.assertEqual(late['counts'], {'archive0': 2, 'archive1': 2})
        self.assertEqual(late['avoidable_loss_units'], 14)

    def test_refusal_is_not_accepted_delivery(self):
        artifact = archive_artifact(self.public)
        artifact['steps'] = [{'op': 'stop', 'reason': 'unresolved'}]
        receipt = verify(self.request, artifact)
        self.assertEqual(receipt['decision'], 'REFUSE')
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['maximum_avoidable_loss_units'], 0)

    def test_missing_payload_does_not_pass_policy_only(self):
        artifact = archive_artifact(self.public)
        artifact['output'] = {}
        self.assertFalse(verify(self.request, artifact)['accepted'])

    def test_malformed_and_prospective_operation_envelope(self):
        artifact = archive_artifact(self.public)
        artifact['steps'] = [{'op': 'undeclared'}]
        receipt = verify(self.request, artifact)
        self.assertFalse(receipt['accepted'])
        self.assertTrue(all(row['error'] for row in receipt['results']))
        sandbox = ToolSandbox(_spec(self.request), {})
        with self.assertRaisesRegex(ValueError, 'OPERATION_ENVELOPE_EXCEEDED'):
            sandbox.execute([{'op': 'wait', 'ticks': 40}] * 3)
        self.assertEqual(sandbox.cost_units, 80)

    def test_unaffordable_probe_produces_no_observation_or_budget_charge(self):
        session = make_session(self.request)
        receipt = session.probe([{'op': 'wait', 'ticks': 40}])
        self.assertEqual(receipt['status'], 'unaffordable')
        self.assertEqual(receipt['observations'], [])
        self.assertIsNone(receipt['effects'])
        self.assertEqual(session.units_spent, 0)

    def k2_handcrafted(self):
        spec = copy.deepcopy(_spec(self.request))
        public = {'id': 'unscored-structural-k2-fixture', 'stage': 'K2', 'rows': [2, -3, 5], 'intents': ['reserve', 'publish'], 'dependencies': {'publish': 'reserve'}, 'deadline': 16}
        spec['public'] = public
        output = {'reserve': {'job_id': public['id'], 'rows': 3}, 'publish': {'job_id': public['id'], 'count': 3, 'sum': 4, 'sum_squares': 38, 'source_sha256': identity([2, -3, 5])}}
        reserve = {'op': 'write', 'intent': 'reserve', 'key': 'r', 'value': '$output:reserve'}
        publish = {'op': 'write', 'intent': 'publish', 'key': 'p', 'value': '$output:publish', 'dependency': '$token:reserve'}
        return spec, public, output, reserve, publish

    def test_k2_requires_acknowledged_causal_token(self):
        spec, public, output, reserve, publish = self.k2_handcrafted()
        artifact = {'steps': [reserve, publish], 'output': output}
        good = ToolSandbox(spec, {}).execute(artifact['steps'], output)
        self.assertTrue(grade_execution(public, artifact, good, good.time)['accepted'])
        for token in (None, 'wrong-token'):
            bad_publish = dict(publish, dependency=token)
            bad = ToolSandbox(spec, {}).execute([reserve, bad_publish], output)
            self.assertFalse(grade_execution(public, artifact, bad, bad.time)['dependency_ok'])

    def test_predicted_token_without_prior_observation_is_rejected(self):
        spec, public, output, reserve, publish = self.k2_handcrafted()
        sandbox = ToolSandbox(spec, {'reserve': 'lost_ack'})
        sandbox.execute([reserve], output)
        guessed_token = sandbox.effects[0]['token']
        sandbox.execute([dict(publish, dependency=guessed_token)], output)
        artifact = {'steps': [reserve, publish], 'output': output}
        self.assertFalse(grade_execution(public, artifact, sandbox, sandbox.time)['dependency_ok'])


if __name__ == '__main__':
    unittest.main()
