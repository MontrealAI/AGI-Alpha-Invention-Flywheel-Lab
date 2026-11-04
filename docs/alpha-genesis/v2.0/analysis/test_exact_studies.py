import unittest
from fractions import Fraction as F
from dataclasses import replace
from decision_model import Config,Planner
from exact_studies import oracle,calculations

class PaperStudies(unittest.TestCase):
    def test_independent_default(self): self.assertEqual(oracle(Config()),F(3441,100))
    def test_strong_no_probe(self): self.assertEqual(oracle(Config(),False),F(313,10))
    def test_incremental_information(self): self.assertEqual(oracle(Config())-oracle(Config(),False),F(311,100))
    def test_perfect_information(self):
        c=Config();p=c.initial_p_good
        v=p*oracle(replace(c,initial_p_good=F(1)),False)+(1-p)*oracle(replace(c,initial_p_good=F(0)),False)
        self.assertEqual(v,F(391,10))
    def test_external_tool_adopted(self):self.assertEqual(oracle(replace(Config(),frontier_net_delivery=(28,30))),58)
    def test_upkeep_blocks_build(self):self.assertEqual(oracle(replace(Config(),maintenance_per_delivery=25)),30)
    def test_zero_horizon_value(self):
        c=replace(Config(),horizon=1);self.assertEqual(oracle(c),16)
    def test_no_market_stops(self):
        c=replace(Config(),frontier_net_delivery=(-5,-5),specialist_net_delivery=(-6,-6),constructed_net_delivery=(-4,-4))
        self.assertEqual(oracle(c),0)
    def test_uninformative_probe_not_valuable(self):
        c=replace(Config(),signal_sensitivity=F(1,2),signal_false_positive=F(1,2))
        self.assertEqual(oracle(c),oracle(c,False))
    def test_inaccessible_frontier_excluded(self):
        c=replace(Config(),frontier_access=False,horizon=1);self.assertEqual(oracle(c),12)
    def test_expensive_probe_ignored(self):
        c=replace(Config(),probe_cost=100);self.assertEqual(oracle(c),oracle(c,False))
    def test_complementary_net(self):
        r=calculations()['complementary_means'];self.assertEqual(r['joint_benefit']+r['instrument_only']+r['interface_only'],r['together'])
    def test_competition_inverts_private_margin(self):
        r=calculations()['competitive_diffusion'];self.assertLess(r['after']['cost'],r['before']['cost']);self.assertLess(r['after']['margin'],r['before']['margin'])
    def test_independent_grid(self):self.assertEqual(calculations()['independently_reimplemented_sensitivity_cases'],54)
    def test_archival_sunk_cost_not_retention_cost(self):
        r=calculations()['retention'];self.assertEqual(r['prospective_uses']*r['saving_per_use']-r['remaining_integration']-r['carrying_cost'],r['net_avoidance_value'])

if __name__=='__main__':unittest.main()
