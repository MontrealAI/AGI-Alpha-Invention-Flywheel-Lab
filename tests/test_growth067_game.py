"""Finite-game checks; pure proposals only, no economic accounts."""
import time
import unittest
from copy import deepcopy
from growth067.registration import design
from growth067.policy import initial_state,propose
from growth067.planning import expected_net
from growth067.game import _solve

class FiniteGameTests(unittest.TestCase):
    def setUp(self):
        self.reg=design();self.world=deepcopy(self.reg['worlds']['central'])
        self.summary={'available':90_000_000_000,'unrestrictedEarned':0,'profit':-10_000_000_000,'tailReserve':0,'custodyReserve':0,'workingCapital':0}
    def proposal(self,seed=670001,world=None):
        return propose(initial_state(),self.summary,world or self.world,self.reg,seed,10,100_000_000_000,policy_name='finite_game')
    def test_certificate_matches_executed_price_and_objective(self):
        p=self.proposal();c=p['game_certificate']
        self.assertEqual(c['actual_seller_quote_usd'],p['unit_price_usd'])
        self.assertIn(p['unit_price_usd'],[0,c['seller_action']['price_usd']])
        self.assertTrue(c['seller_action']['withdraw_if_nonpositive'])
        self.assertEqual(c['seller_optimality_gap_microUSD'],0)
        self.assertEqual(c['rival_best_response_regret_microUSD'],0)
        self.assertEqual(c['seller_value_microUSD'],max(x['seller_value_microUSD'] for x in c['all_action_values']))
        raw=deepcopy(p);raw.pop('game_certificate')
        self.assertEqual(c['seller_value_microUSD'],expected_net(raw,c['effective_world'],self.reg,10))
    def test_realized_random_draws_do_not_select_action(self):
        a=self.proposal(670001)['game_certificate'];b=self.proposal(670002)['game_certificate']
        for field in ['seller_action','seller_value_microUSD','rival_quote_usd','all_action_values']:
            self.assertEqual(a[field],b[field])
    def test_no_positive_offer_never_certifies_nonexecuted_quote(self):
        p=self.proposal(world=self.reg['worlds']['invalid_quality']);c=p['game_certificate']
        self.assertEqual(c['actual_seller_quote_usd'],p['unit_price_usd'])
        self.assertIn(p['unit_price_usd'],[0,c['seller_action']['price_usd']])
        self.assertTrue(c['seller_action']['withdraw_if_nonpositive'])
        self.assertFalse(c['seller_action']['invest'])
        self.assertEqual(p['lead_attempts'],0)
        self.assertEqual(c['seller_value_microUSD'],-self.reg['planning_horizon_months']*self.reg['fixed_maintenance_monthly_usd']*1_000_000)
    def test_result_copy_and_corruption_cannot_poison_pure_replay(self):
        p=self.proposal();original=deepcopy(p)
        p['game_certificate']['seller_value_microUSD']=10**30
        self.assertEqual(self.proposal(),original)

if __name__=='__main__':unittest.main()
