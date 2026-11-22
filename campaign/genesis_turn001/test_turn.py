"""Executable confirmation, independent checker, fraud and negative controls."""
import copy
import unittest
from . import power,independent

class PowerTests(unittest.TestCase):
    def test_complete_successor(self):
        d=power.scenario(); result=power.solve(d)
        self.assertTrue(independent.accept_power(d,result))
        self.assertEqual(result['status'],'FEASIBLE_IN_MODEL')
        self.assertEqual(result['cost_cents'],3700)
        self.assertEqual(len(result['assignments']),3)

    def test_reject_unqualified_superpack(self):
        d=power.scenario();result=power.solve(d)
        self.assertNotIn('SPARKY-UNVERIFIED',[x['module'] for x in result['assignments']])
        forged=copy.deepcopy(result);forged['assignments'][0]['module']='SPARKY-UNVERIFIED'
        with self.assertRaises(ValueError):independent.accept_power(d,forged)

    def test_double_spend_battery_rejected(self):
        d=power.scenario(); result=power.solve(d)
        forged=copy.deepcopy(result);forged['assignments'].append(dict(result['assignments'][0]))
        with self.assertRaises(ValueError):independent.accept_power(d,forged)

    def test_missing_required_load_rejected(self):
        d=power.scenario(); result=power.solve(d)
        forged=copy.deepcopy(result);forged['assignments'].pop()
        with self.assertRaises(ValueError):independent.accept_power(d,forged)

    def test_no_valid_capacity_stop(self):
        d=power.scenario()
        for p in d['modules']:p['research_only_qualified']=False
        self.assertTrue(independent.accept_power(d,power.solve(d)))
        self.assertEqual(power.solve(d)['status'],'NOT_FEASIBLE_IN_MODEL')

    def test_unsourced_extra_battery_rejected(self):
        d=power.scenario(); result=power.solve(d)
        forged=copy.deepcopy(result);forged['assignments'][0]['module']='MADE-UP'
        with self.assertRaises(ValueError):independent.accept_power(d,forged)

    def test_changed_source_rejected(self):
        d=power.scenario();result=power.solve(d)
        d['loads'][0]['required_wh']=8000
        with self.assertRaises(ValueError):independent.accept_power(d,result)

    def test_conservation_of_modeled_money(self):
        x={'price_cents':6500,'pre_successor_costs_cents':[1200,900,200,500,400],
           'tax_rate_basis_points':2000,'tax_cents':660,
           'earned_before_successor_cents':2640,'successor_cost_cents':1800,
           'net_after_successor_cents':840,'actual_customer_receipts_cents':0}
        self.assertTrue(independent.accept_cents(x))
        x['net_after_successor_cents']+=100
        with self.assertRaises(ValueError):independent.accept_cents(x)

if __name__=='__main__':unittest.main()
