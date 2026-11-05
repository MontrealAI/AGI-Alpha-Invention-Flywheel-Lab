import copy
import unittest
from enterprise078_review.test_joint_choice import offer,case_for
from .joint_cost import evaluate


def run(rows, cases):
    return evaluate(rows,[[r['id'] for r in rows]],wallets={'buyer':500},available=1000,
                    earned=1000,sunk_acquisition=30,scenarios=cases)


def scenario(rows):
    return {'choice':case_for(rows),'costs':{r['id']:copy.deepcopy(r['costs']) for r in rows}}


class JointCostTests(unittest.TestCase):
    def test_joint_substitutes(self):
        rows=[offer('a'),offer('b')]
        self.assertEqual(run(rows,{'base':scenario(rows)})['selected_bundle'],[])

    def test_rival_response(self):
        rows=[offer('a')];s=scenario(rows);s['choice']=case_for(rows,single_ai=310)
        self.assertEqual(run(rows,{'rival':s})['selected_bundle'],[])

    def test_production_shock_reverses(self):
        rows=[offer('a')];base=scenario(rows);shock=copy.deepcopy(base)
        shock['costs']['a']['production']=250
        result=run(rows,{'base':base,'shock':shock})
        self.assertEqual(result['selected_bundle'],[])
        self.assertEqual(result['outcomes'][1]['cases']['base']['robust_net_microUSD'],120)
        self.assertEqual(result['outcomes'][1]['cases']['shock']['robust_net_microUSD'],-80)
        self.assertEqual(result['conditional_worst_net_microUSD'],-30)

    def test_unknown_cost_never_zero(self):
        rows=[offer('a')];s=scenario(rows);s['costs']['a']['support']=None
        r=run(rows,{'unknown':s});self.assertEqual(r['selected_bundle'],[])
        self.assertIsNone(r['outcomes'][1]['worst_net_microUSD'])

    def test_missing_cost_vector_refused(self):
        rows=[offer('a')];s=scenario(rows);s['costs']={}
        with self.assertRaisesRegex(ValueError,'COMPLETE_SCENARIO_OFFER_COSTS_REQUIRED'):run(rows,{'missing':s})

    def test_nonpayment_loss(self):
        rows=[offer('a')];s=scenario(rows);s['choice']=case_for(rows,paid=False)
        r=run(rows,{'nonpayment':s});self.assertEqual(r['outcomes'][1]['worst_net_microUSD'],-80)
        self.assertFalse(r['native_catalog_admitted']);self.assertIsNone(r['forecast_expected_net'])

if __name__=='__main__':unittest.main()
