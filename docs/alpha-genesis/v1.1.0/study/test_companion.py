import unittest
from fractions import Fraction as F
from itertools import product
import companion as c

class ExactStudies(unittest.TestCase):
    def test_inverse_identity(self):
        for a,b,d,e in product(range(-2,3),repeat=4):
            m=((F(a),F(b)),(F(d),F(e)))
            if a*e==b*d: continue
            inv=c.inverse2(m)
            for x in ((F(1),F(0)),(F(0),F(1))): self.assertEqual(c.apply(inv,c.apply(m,x)),x)
    def test_singular_refused(self):
        with self.assertRaises(ValueError): c.inverse2(((F(1),F(1)),(F(2),F(2))))
    def test_noise_enumeration(self):
        r=c.instrument_study(); self.assertEqual(r['worst_error'],'1/10');self.assertEqual(r['enumerated_state_noise_cases'],225)
    def test_candidate_counts(self):
        r=c.instrument_study();self.assertEqual(r['candidate_count'],8);self.assertEqual(r['full_rank_candidates'],6)
    def test_ordinary_solver_ties(self): self.assertTrue(c.instrument_study()['conventional_control_matches'])
    def test_third_mechanism_invalidates_bound(self): self.assertGreater(F(c.instrument_study()['third_mechanism_error']),F(1,10))
    def test_successor_algebra(self): self.assertEqual(c.instrument_study()['successor_algebra_cases'],1764)
    def test_replay_results(self):
        r=c.replay_study();self.assertEqual(r['blanket']['evaluations'],25);self.assertEqual(r['selective']['evaluations'],5)
    def test_ordinary_dependency_ties(self):
        r=c.replay_study()
        for key in ('evaluations','completed','trace'):
            self.assertEqual(r['selective'][key],r['conventional_dependency_control'][key])
    def test_irrelevant_release(self): self.assertEqual(c.replay('dependency')['trace'][2]['evaluated'],[])
    def test_unknown_blocker_is_not_proven_impossible(self):
        r=c.replay('dependency',{'X':{'unknown'}},[{'geometry'}]);self.assertEqual(r['completed'],[])
    def test_cashflows_equal_profit(self):
        a,b=c.paths();self.assertEqual(sum(a),sum(b));self.assertEqual(sum(a),40)
    def test_liquidity_depends_on_timing(self):
        a,b=c.paths();self.assertEqual(c.funding_need(a),44);self.assertEqual(c.funding_need(b),80)
    def test_protected_reserve(self):
        a,_=c.paths();self.assertEqual(c.funding_need(a,[F(10)]*(len(a)+1)),54)
    def test_cash_exhaustive(self):self.assertEqual(c.economic_study()['exhaustive_schedule_checks'],1440)
    def test_price_and_demand(self):
        r=c.economic_study();self.assertEqual(r['low_demand_profit'],'-16');self.assertEqual(r['imitated_price_profit'],'0')
    def test_earned_funded_successor(self):
        r=c.economic_study();self.assertEqual(r['successor_minimum_cash'],'34');self.assertEqual(r['earned_cash_after_successor'],'50')
    def test_invalid_reserve(self):
        with self.assertRaises(ValueError):c.funding_need([F(-1)],[F(0)])
    def test_lag_monotonicity(self):
        r=c.lag_study()['points'];self.assertEqual(r[0]['fraction'],1);self.assertEqual(r[-1]['fraction'],.25)
        self.assertTrue(all(a['fraction']>b['fraction'] for a,b in zip(r,r[1:])))
    def test_negative_noise(self):
        with self.assertRaises(ValueError):c.bound(((F(1),F(0)),(F(0),F(1))),F(-1))

if __name__=='__main__':unittest.main()
