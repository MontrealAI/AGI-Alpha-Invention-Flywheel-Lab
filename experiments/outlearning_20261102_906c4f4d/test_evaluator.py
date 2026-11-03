import copy
import unittest

from .evaluate import evaluate, execute_program, validate_program
from .world import Provider, ProbeSession, make_world, provider_config, public_task


def graph(spec, actions, finish='delivered', obligations=None):
    nodes = {'end': {'finish': finish, 'obligations': obligations or []}}
    for i, (provider, op) in enumerate(actions):
        nodes[str(i)] = {'provider': provider, 'op': op, 'token': 'order',
                         'next': {'*': str(i+1) if i+1 < len(actions) else 'end'}}
    return {'entry': '0' if actions else 'end', 'nodes': nodes}


class IndependentAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.spec = make_world('acceptance-development', 'K1', 1)
        self.ident = self.spec['providers'][0]['id']

    def test_empty_completion_is_not_delivery(self):
        result = evaluate(self.spec, graph(self.spec, []))
        self.assertFalse(result['accepted'])
        self.assertFalse(result['all_safe'])

    def test_clean_refusal_is_safe_without_income(self):
        result = evaluate(self.spec, graph(self.spec, [], 'aborted'))
        self.assertTrue(result['all_safe'])
        self.assertFalse(result['accepted'])
        self.assertEqual(result['delivered_count'], 0)

    def test_duplicate_effects_fail_even_with_done_response(self):
        result = execute_program(self.spec, graph(self.spec, [(self.ident, 'execute')]*2), 'healthy')
        self.assertEqual(result['effect_counts'][self.ident], 2)
        self.assertFalse(result['delivered'])
        self.assertTrue(result['harm'])
        self.assertGreater(result['residual_exposure_microUSD'], 0)

    def test_false_abort_does_not_hide_effect(self):
        result = execute_program(self.spec, graph(self.spec, [(self.ident, 'execute')], 'aborted'), 'healthy')
        self.assertTrue(result['harm'])
        self.assertFalse(result['truthful_obligations'])

    def test_truthful_unresolved_still_has_cost_and_no_acceptance(self):
        result = execute_program(self.spec, graph(self.spec, [(self.ident, 'execute')], 'unresolved', [self.ident]), 'healthy')
        self.assertTrue(result['truthful_obligations'])
        self.assertFalse(result['safe'])
        self.assertFalse(result['delivered'])
        self.assertGreater(result['residual_exposure_microUSD'], 0)

    def test_compensation_cannot_undo_irreversible_effect(self):
        spec = make_world('irreversible-development', 'K1', 6)
        ident = spec['providers'][0]['id']
        result = execute_program(spec, graph(spec, [(ident, 'execute'), (ident, 'cancel')], 'aborted'), 'healthy')
        self.assertTrue(result['harm'])
        self.assertEqual(result['effect_counts'][ident], 1)

    def test_missing_request_and_ack_have_different_effects(self):
        program = graph(self.spec, [(self.ident, 'execute')])
        lost = execute_program(self.spec, program, 'lost_request')
        ack = execute_program(self.spec, program, 'lost_ack')
        self.assertEqual(lost['effect_counts'][self.ident], 0)
        self.assertEqual(ack['effect_counts'][self.ident], 1)
        self.assertEqual(lost['trace'][0]['response'], ack['trace'][0]['response'])

    def test_stale_status_needs_more_than_h1_h2(self):
        engine = Provider(provider_config('stale'))
        self.assertEqual(engine.call('execute', fault='ack_lost'), 'TIMEOUT')
        self.assertEqual(engine.call('status'), 'ABSENT')
        self.assertEqual(engine.call('fence'), 'DONE')
        self.assertEqual(len(engine.effects), 1)

    def test_key_expiry_can_duplicate_even_stable_token(self):
        engine = Provider(provider_config('expiring'))
        engine.call('execute', fault='ack_lost')
        engine.call('wait', ticks=8)
        engine.call('execute')
        self.assertEqual(len(engine.effects), 2)

    def test_probe_budget_not_bypassed(self):
        probe = ProbeSession(self.spec)
        probe._spec['probe_budget_microUSD'] = 1
        result = probe(self.ident, [{'op': 'status'}])
        self.assertEqual(result['error'], 'BUDGET_EXHAUSTED')
        self.assertEqual(probe.spent_microUSD, 0)

    def test_program_fault_override_is_rejected(self):
        program = graph(self.spec, [(self.ident, 'execute')])
        program['nodes']['0']['fault'] = 'none'
        self.assertFalse(evaluate(self.spec, program)['valid_program'])

    def test_unsupported_commit_cannot_drain_a_productive_fault(self):
        program = graph(self.spec, [(self.ident, 'commit'), (self.ident, 'execute')])
        result = execute_program(self.spec, program, 'lost_request')
        self.assertEqual(result['trace'][0]['response'], 'UNSUPPORTED')
        self.assertEqual(result['trace'][1]['response'], 'TIMEOUT')
        self.assertEqual(result['effect_counts'][self.ident], 0)

    def test_local_policy_cannot_receive_hidden_fields(self):
        task = public_task(self.spec)
        self.assertNotIn('seed', task)
        self.assertNotIn('stratum', task)
        self.assertNotIn('refusal_provider', task)
        self.assertNotIn('config', task['providers'][0])

    def test_refused_provider_not_fixed_by_public_list_order(self):
        spec = copy.deepcopy(self.spec)
        other = copy.deepcopy(spec['providers'][0])
        other['id'] = 'other'
        spec['providers'].append(other)
        program = graph(spec, [('other', 'execute'), (self.ident, 'execute')])
        spec['refusal_provider'] = self.ident
        result = execute_program(spec, program, 'provider_refusal')
        self.assertTrue(result['harm'])
        self.assertEqual(result['effect_counts']['other'], 1)
        self.assertEqual(result['effect_counts'][self.ident], 0)

    def test_prepared_hold_expires_with_other_provider_operations(self):
        spec = copy.deepcopy(self.spec)
        spec['providers'][0]['config'] = provider_config('fragile_hold')
        other = copy.deepcopy(spec['providers'][0])
        other['id'] = 'other'
        spec['providers'].append(other)
        program = graph(spec, [(self.ident, 'reserve'), ('other', 'status'), ('other', 'status'), (self.ident, 'commit')])
        result = execute_program(spec, program, 'healthy')
        self.assertEqual(result['effect_counts'][self.ident], 0)
        self.assertEqual(result['trace'][-1]['response'], 'REFUSED')


if __name__ == '__main__':
    unittest.main()
