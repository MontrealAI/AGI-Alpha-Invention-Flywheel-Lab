import unittest
from math import isclose
from engine import Channel, World, TARGET, ORIGINAL, posterior, find_plan, simulate, world_examples

class TestOmegaDirection(unittest.TestCase):
    def test_exact_information_no_go(self):
        sensor=Channel('same',ORIGINAL,0,1,'installed')
        for n in (0,1,10,100,1000):
            loss,_=posterior((n,), (sensor,), 0.2)
            self.assertAlmostEqual(loss,1,places=10)
    def test_new_instrument_changes_feasibility(self):
        w=world_examples()[0]; p=find_plan(w)
        self.assertTrue(p['model_acceptance'])
        self.assertTrue(p['proposed_instrument_used'])
        self.assertEqual(p['cost_units'],4)
        self.assertLess(p['posterior_target_variance'],0.05)
        self.assertEqual(p['net_utility_units'],5)
    def test_complete_incumbent_wins(self):
        p=find_plan(world_examples()[1]); self.assertTrue(p['incumbent_used'])
        self.assertFalse(p['proposed_instrument_used'])
        self.assertEqual(p['cost_units'],3)
        self.assertEqual(p['net_utility_units'],6)
    def test_budget_not_imagined(self):
        p=find_plan(world_examples()[2]); self.assertFalse(p['model_acceptance']); self.assertEqual(p['cost_units'],0)
    def test_low_value_refusal(self):
        p=find_plan(world_examples()[3]);self.assertEqual(p['cost_units'],0);self.assertEqual(p['net_utility_units'],0)
    def test_no_false_epistemic_invention(self):
        p=find_plan(world_examples()[4]);self.assertFalse(p['model_acceptance']);self.assertEqual(p['cost_units'],0)
    def test_monte_carlo_independent(self):
        w=world_examples()[0];p=find_plan(w)
        mse=simulate(w,p,seed=777,trials=5000)
        self.assertAlmostEqual(mse,p['posterior_target_variance'],delta=.007)
    def test_reject_invalid_costs(self):
        with self.assertRaises(ValueError):Channel('bad',TARGET,0,0,'proposed')

if __name__=='__main__':unittest.main()
