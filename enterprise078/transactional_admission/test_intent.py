import copy
import unittest
from .offer import COSTS
from .intent import evaluate


def row(ident='a'):
    return dict(id=ident,buyer='buyer',price=200,value=500,outside=100,
                costs={k: (50 if k=='production' else 0) for k in COSTS},
                collected=200,response='consented',accepted=True)


class IntentTests(unittest.TestCase):
    def run_case(self, rows=None, bundles=None, **kw):
        args=dict(wallets={'buyer':300},available=1000,earned=1000,sunk_acquisition=30)
        args.update(kw)
        return evaluate(rows or [row()], bundles or [['a']], **args)

    def test_uncontacted_not_demand(self):
        r=row();r['response']='uncontacted'
        v=self.run_case([r]);self.assertEqual(v['selected_bundle'],[])
        self.assertEqual(v['selected_scenario_net_microUSD'],-30)

    def test_shared_wallet_not_two_customers(self):
        v=self.run_case([row('a'),row('b')],[['a'],['a','b']])
        self.assertEqual(v['selected_bundle'],['a'])
        self.assertIn('SHARED_BUYER_WALLET_EXCEEDED',v['outcomes'][2]['reasons'])

    def test_whole_bundle_cash(self):
        v=self.run_case([row('a'),row('b')],[['a'],['a','b']],wallets={'buyer':1000},earned=80)
        self.assertIn('BUNDLE_NOT_EARNED_FUNDED',v['outcomes'][2]['reasons'])
        self.assertEqual(v['selected_bundle'],['a'])

    def test_outside_option_tie(self):
        r=row();r['outside']=300
        self.assertEqual(self.run_case([r])['selected_bundle'],[])

    def test_unknown_cost(self):
        r=row();r['costs']['host_model']=None
        v=self.run_case([r]);self.assertIsNone(v['outcomes'][1]['scenario_net_microUSD'])
        self.assertEqual(v['selected_bundle'],[])

    def test_nonpayment_loss_preserved(self):
        r=row();r['collected']=0
        v=self.run_case([r]);self.assertEqual(v['outcomes'][1]['scenario_net_microUSD'],-80)
        self.assertEqual(v['selected_scenario_net_microUSD'],-30)

    def test_positive_is_conditional_only(self):
        v=self.run_case();self.assertEqual(v['selected_scenario_net_microUSD'],120)
        self.assertFalse(v['native_catalog_admitted']);self.assertIsNone(v['forecast_expected_net'])

    def test_duplicate_budget_consumption_refused(self):
        with self.assertRaises(ValueError): self.run_case(bundles=[['a','a']])

    def test_input_not_mutated(self):
        r=row();before=copy.deepcopy(r);self.run_case([r]);self.assertEqual(r,before)

if __name__=='__main__':unittest.main()
