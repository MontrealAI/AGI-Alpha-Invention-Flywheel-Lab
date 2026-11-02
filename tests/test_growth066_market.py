import unittest
from growth066.market import draw_choices,choice_probabilities,outcomes
from growth066.policy import initial_state,propose
from growth066.registration import design
from growth066.money import payment,ceil_share,floor_share

class MarketTests(unittest.TestCase):
    def test_alternatives_conserve_buyers_and_aggregate_mean(self):
        w=design()['worlds']['central'];prob,_=choice_probabilities(40,w,1)
        observed=0
        for seed in range(1000):
            c=draw_choices(100,40,w,1,seed)['counts'];self.assertEqual(sum(c.values()),100);observed+=c['ours']
        self.assertLess(abs(observed-100000*prob['ours']),1000)
        self.assertIn('human_conventional',prob);self.assertIn('self_service',prob);self.assertIn('no_purchase',prob)
    def test_no_demand_never_materializes_orders(self):
        reg=design();w=reg['worlds']['no_demand'];state=initial_state()
        summary={'available':100000000000,'unrestrictedEarned':0,'profit':0,'tailReserve':0,'custodyReserve':0,'workingCapital':0}
        p=propose(state,summary,w,reg,660001,10,100000000000)
        self.assertEqual(p['chosen_orders'],0);self.assertEqual(p['lead_attempts'],0)
    def test_chosen_units_reserve_worst_principal_not_future_collections(self):
        reg=design();w=reg['worlds']['central'];state=initial_state();state.update(month=1,active=10000,capacity=10000)
        summary={'available':1000000000,'unrestrictedEarned':1000000000,'profit':1000000000,'tailReserve':0,'custodyReserve':0,'workingCapital':0}
        p=propose(state,summary,w,reg,660001,10,100000000000)
        prepaid=sum(p['costs_microUSD'].values());price=p['unit_price_usd']*1000000
        self.assertLessEqual(prepaid+p['chosen_orders']*(price+200000+payment(price,w)),summary['available'])
    def test_common_outage_correlates_whole_capacity(self):
        reg=design();w=reg['worlds']['capacity_outage'];state=initial_state();state.update(month=1,active=10000,capacity=10000)
        s={'available':10**12,'unrestrictedEarned':10**12,'profit':10**12,'tailReserve':0,'custodyReserve':0,'workingCapital':0}
        p=propose(state,s,w,reg,660001,10,10**12);self.assertTrue(p['outage']);self.assertEqual(p['chosen_orders'],0)
    def test_100b_money_stress_exact_not_attainment(self):
        amount=100_000_000_000*1_000_000+1
        self.assertEqual(ceil_share(amount,'.029'),2_900_000_000_000_001)
        self.assertEqual(floor_share(amount,'.2'),20_000_000_000_000_000)
