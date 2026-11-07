import unittest
import numpy as np
from . import model as m

class StrategicTests(unittest.TestCase):
 def test_budget_and_refusal(self):
  c=m.Conditions()
  a,b=m.buyer_shares(1000,1000,c)
  self.assertEqual(float(a.sum()+b.sum()),0)
 def test_outside_ties_refuse(self):
  c=m.Conditions(value_multiplier=0)
  a,b=m.buyer_shares(0,0,c)
  self.assertEqual(float(a.sum()+b.sum()),0)
 def test_all_price_responses_independently(self):
  c=m.conditions('central');contacts=np.array([100.,10.,1.])
  g=m.stage_game(contacts,c)
  aa=np.array(g['leader_payoffs']);bb=np.array(g['rival_payoffs'])
  for i,j in enumerate(g['rival_response_indices']):
   self.assertGreaterEqual(0. if j<0 else bb[i,j],max(0.,max(bb[i]))-1e-7)
   if j>=0:
    candidates=[aa[i,k] for k in range(len(m.PRICES)) if abs(bb[i,k]-bb[i,j])<=m.PRICE_GAME_TOL]
    self.assertLessEqual(aa[i,j],min(candidates)+1e-7)
  self.assertEqual(g['finite_grid_gap'],0)
  self.assertAlmostEqual(g['leader_value'],max(g['leader_commitment_values']))
 def test_unfunded_action_rejected(self):
  c=m.Conditions();p=m.plan(100,100,[10,2,1],c,'adaptive')
  self.assertEqual(p['spend'],0)
  self.assertEqual(p['reserve_bound'],0)
 def test_exact_replay(self):
  a=m.simulate(100000,'central','adaptive',94001,12)
  b=m.simulate(100000,'central','adaptive',94001,12)
  self.assertEqual(a,b)
 def test_zero_demand_no_income(self):
  r=m.simulate(100000,'zero_demand','adaptive',94001,12)
  self.assertEqual(r['accepted_orders'],0)
  self.assertLess(r['cumulative_profit'],0)
  self.assertFalse(r['three_billion_year'])
 def test_equity_is_not_income(self):
  r=m.simulate(1000000000,'zero_demand','organic',94001,12)
  self.assertLess(r['cumulative_profit'],0)
  self.assertFalse(r['investor_hurdle_met'])
 def test_cash_reconciliation_all_scenarios(self):
  for sc in m.SCENARIOS:
   r=m.simulate(1000000,sc,'adaptive',94002,12)
   self.assertAlmostEqual(r['cash_reconciliation_error'],0,places=5)
   self.assertGreaterEqual(r['min_available'],-1e-6)
 def test_delayed_pipeline_not_recognized(self):
  r=m.simulate(1000000,'slow_payment','adaptive',94003,12,True)
  for row in r['trace'][:3]:self.assertEqual(row['recognized_net_revenue'],0)
  for row in r['trace'][:7]:self.assertEqual(row['collected'],0)
 def test_same_game_strong_controls(self):
  c=m.Conditions();a=m.plan(1e6,0,[100,10,1],c,'adaptive')
  b=m.plan(1e6,0,[100,10,1],c,'staged')
  d=m.plan(1e6,0,[100,10,1],c,'organic')
  self.assertGreaterEqual(a['expected_contribution'],b['expected_contribution'])
  self.assertGreaterEqual(b['expected_contribution'],d['expected_contribution'])
 def test_no_forced_negative_entry(self):
  c=m.Conditions(cost_multiplier=1000)
  p=m.plan(1e6,0,[100,10,1],c,'adaptive')
  self.assertEqual(p['spend'],0)
  self.assertEqual(float(p['contacts'].sum()),0)
 def test_price_floor_has_no_false_monopoly(self):
  g=m.stage_game([100,10,1],m.Conditions())
  self.assertLess(m.PRICES[g['price_index']],.45)
  self.assertGreaterEqual(g['rival_index'],0)
if __name__=='__main__':unittest.main()
