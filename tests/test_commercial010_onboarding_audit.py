import copy
import json
from pathlib import Path
import tempfile
import unittest

from commercial.market import default_policy, keyed_draw, onboarding_quote, run_world, usd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'campaign/commercial-010/service/executed-002/manifest.json'


class OnboardingPolicyAuditTests(unittest.TestCase):
    def test_agent_expense_customer_friction_and_external_fee_stay_separate(self):
        policy = default_policy()
        policy['external_onboarding_fee'] = usd(2)
        world = copy.deepcopy(policy['worlds'][0])
        state = {'onboarded': False}
        arm = next(a for a in policy['arms'] if a['corrected_onboarding'])
        quote = onboarding_quote(arm, world, state, policy)
        self.assertEqual(quote['agent_expense'], policy['agent_onboarding_autonomous'])
        self.assertEqual(quote['external_fee'], usd(2))
        self.assertEqual(quote['customer_friction_usd'], world['switching'])
        world['switching'] += 100
        changed = onboarding_quote(arm, world, state, policy)
        self.assertEqual(changed['agent_expense'], quote['agent_expense'])
        self.assertEqual(changed['external_fee'], quote['external_fee'])
        self.assertEqual(changed['customer_friction_usd'], quote['customer_friction_usd'] + 100)

    def test_repeat_has_no_second_onboarding_but_new_buyer_has_its_own(self):
        policy = default_policy()
        policy['external_onboarding_fee'] = usd(2)
        arm, world = policy['arms'][1], policy['worlds'][0]
        first = onboarding_quote(arm, world, {'onboarded': False}, policy)
        repeat = onboarding_quote(arm, world, {'onboarded': True}, policy)
        newcomer = onboarding_quote(arm, world, {'onboarded': False}, policy)
        for field in ['agent_expense', 'external_fee', 'customer_friction_usd']:
            self.assertEqual(repeat[field], 0)
            self.assertEqual(newcomer[field], first[field])
        with self.assertRaises(ValueError):
            onboarding_quote(arm, world, {'onboarded': 'unknown'}, policy)

    def test_common_random_draws_do_not_depend_on_arm_or_consumption_order(self):
        keys = [(1, c, f'buyer-{b}', channel) for c in range(3) for b in range(2)
                for channel in ['arrival', 'revision', 'dispute', 'rival_information']]
        forward = {k: keyed_draw(*k) for k in keys}
        for _ in range(10):
            keyed_draw(99, 9, 'unrelated', 'extra')
        backward = {k: keyed_draw(*k) for k in reversed(keys)}
        self.assertEqual(forward, backward)
        self.assertTrue(all(0 <= value < 1 for value in forward.values()))
        self.assertGreater(len(set(forward.values())), len(forward) // 2)


class OnboardingMarketExecutionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='onboarding010-independent-')
        cls.work = Path(cls.tmp.name)
        cls.manifest = json.loads(MANIFEST.read_text())
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_case(self, *, arm_index=1, seed=1, price=9500, dispute=0, variable_values=False):
        policy = default_policy()
        policy['cycles'] = 2
        policy['external_onboarding_fee'] = usd(2)
        world = policy['worlds'][0]
        world.update(value_low=0 if variable_values else 3000, value_high=4000 if variable_values else 3000,
                     arrival=1., revision_probability=0., dispute_probability=dispute,
                     switching=5., self_service_trust=.5)
        type(self).counter += 1
        return run_world(root=ROOT, manifest=self.manifest, policy=policy, world=world, seed=seed,
                         multiplier=price, arm=policy['arms'][arm_index],
                         directory=self.work / str(type(self).counter))

    def test_actual_ledger_charges_each_buyer_once_and_keeps_fee_distinct(self):
        result = self.run_case()
        actions = result['ledger']['actions']
        agent = [x for x in actions if x['op'] == 'cost' and x['args']['id'].endswith('-agent-onboarding')]
        external = [x for x in actions if x['op'] == 'cost' and x['args']['id'].endswith('-external-onboarding-fee')]
        self.assertEqual(len(agent), 2)
        self.assertEqual(len(external), 2)
        self.assertEqual(sum(x['args']['amount'] for x in agent), 2 * default_policy()['agent_onboarding_autonomous'])
        self.assertEqual(sum(x['args']['amount'] for x in external), usd(4))
        first, repeat = result['cycles']
        self.assertTrue(all(d['participates'] for d in first['decisions']))
        self.assertTrue(all(d['participates'] for d in repeat['decisions']))
        self.assertTrue(all(d['onboarding']['customer_friction_usd'] == 5 for d in first['decisions']))
        for decision in repeat['decisions']:
            self.assertEqual(decision['onboarding']['agent_expense'], 0)
            self.assertEqual(decision['onboarding']['external_fee'], 0)
            self.assertEqual(decision['onboarding']['customer_friction_usd'], 0)

    def test_refund_does_not_erase_completed_onboarding(self):
        result = self.run_case(dispute=1.)
        self.assertEqual(result['cycles'][0]['collected'], 0)
        self.assertTrue(all(d['participates'] for d in result['cycles'][0]['decisions']))
        for decision in result['cycles'][1]['decisions']:
            self.assertEqual(decision['onboarding']['agent_expense'], 0)
            self.assertEqual(decision['onboarding']['external_fee'], 0)
            self.assertEqual(decision['onboarding']['customer_friction_usd'], 0)

    def test_initial_seller_forecast_is_identical_under_different_private_values(self):
        first = self.run_case(seed=1, variable_values=True)
        second = self.run_case(seed=2, variable_values=True)
        a, b = first['cycles'][0], second['cycles'][0]
        self.assertEqual(a['seller_public_observation'], b['seller_public_observation'])
        self.assertEqual(a['forecast_expected_net_value'], b['forecast_expected_net_value'])
        self.assertNotEqual([x['own_utility'] for x in a['decisions']], [x['own_utility'] for x in b['decisions']])

    def test_four_arms_share_cohort_allocations_and_exogenous_shocks(self):
        runs = [self.run_case(arm_index=i, price=9500 if i < 2 else 12000, variable_values=True)
                for i in range(4)]
        reference = runs[0]
        def shocks(result):
            return {(c['cycle'], d['buyer']): (d['arrival_draw'], d['revision_draw'], d['dispute_draw'])
                    for c in result['cycles'] for d in c['decisions']}
        for run in runs[1:]:
            self.assertEqual(run['cohort_sha256'], reference['cohort_sha256'])
            self.assertEqual([c['jobs'] for c in run['cycles']], [c['jobs'] for c in reference['cycles']])
            self.assertEqual(shocks(run), shocks(reference))


if __name__ == '__main__':
    unittest.main()
