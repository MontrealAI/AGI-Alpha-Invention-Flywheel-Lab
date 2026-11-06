import copy,unittest
from dataclasses import replace
from model import Case,Strategy,construct,recourse,financial_path
from oracle import check_witness,source_check,classify_criticism,oracle
from run_study import run

class SourceTests(unittest.TestCase):
    def test_missing_required_item(self):self.assertFalse(source_check(['a','b'],['a'],['a'])['accepted'])
    def test_permitted_omission(self):self.assertTrue(source_check(['a'],['a'],['a'])['accepted'])
    def test_wrong_outcome(self):self.assertFalse(source_check(['a'],['a'],[])['accepted'])
    def test_irrelevant_criticism(self):self.assertEqual(classify_criticism(['a'],['a','b'],['a'],{'source_id':'b','present':False}),'IMMATERIAL_TO_THIS_CHARTER')
    def test_fabricated_criticism(self):self.assertEqual(classify_criticism(['a'],['a'],['a'],{'source_id':'b','present':False}),'UNSUPPORTED')
    def test_false_criticism(self):self.assertEqual(classify_criticism(['a'],['a'],['a'],{'source_id':'a','present':False}),'FALSE_CRITICISM')
    def test_material_criticism(self):self.assertEqual(classify_criticism(['a'],['a'],[],{'source_id':'a','present':False}),'MATERIAL_OMISSION')

    def test_critic_cannot_invent_missing_item(self):self.assertEqual(classify_criticism(['a'],['a'],['a'],{'source_id':'a','present':False}),'FALSE_CRITICISM')
    def test_critic_cannot_hide_actual_omission(self):self.assertEqual(classify_criticism(['a'],['a'],[],{'source_id':'a','present':True}),'MATERIAL_OMISSION')

class ConstructionTests(unittest.TestCase):
    def test_central(self):
        r=construct(Case());self.assertEqual((r['cost'],r['surplus']),(13,3));self.assertTrue(check_witness(Case(),r))
    def test_refinement(self):
        r=construct(Case());self.assertEqual(len(r['history']),2);self.assertEqual(r['history'][0]['cost'],8)
    def test_pre_frontier(self):self.assertEqual(construct(Case(adapter_cost=6,cash=30))['decision'],'DECLINE')
    def test_technical_only(self):self.assertEqual(construct(Case(pooling_available=False,cash=30))['decision'],'DECLINE')
    def test_arrangement_only(self):self.assertEqual(construct(Case(adapter_available=False,cash=30))['decision'],'DECLINE')
    def test_cash_prefix(self):self.assertEqual(construct(Case(cash=12))['decision'],'DECLINE')
    def test_no_supplier_agreement(self):self.assertEqual(construct(Case(supplier_q_accepted=False,cash=30))['decision'],'DECLINE')
    def test_break_even(self):self.assertEqual(construct(Case(pooled_q_cost=5,cash=30))['decision'],'DECLINE')
    def test_redundancy(self):
        c=Case(include_q_failure=True,cash=30,price_per_buyer=12);r=construct(c);self.assertTrue(check_witness(c,r));self.assertEqual(r['cost'],17)
    def test_unpriced_supplier_failure(self):self.assertEqual(construct(Case(include_q_failure=True,cash=30))['decision'],'DECLINE')
    def test_local_not_global(self):
        s=Strategy(False,False,('P',));self.assertTrue(recourse(s,{'active':('A',),'failed':()})['feasible']);self.assertFalse(recourse(s,{'active':('A','B'),'failed':()})['feasible'])
    def test_cash_identity(self):
        c=Case();f=financial_path(c,construct(c));self.assertEqual((f['before_receipts'],f['terminal'],f['actual_receipts']),(0,16,0))
    def test_no_fake_receipts_on_decline(self):
        c=Case(cash=0);self.assertIsNone(financial_path(c,construct(c)))
    def test_all_grid(self):self.assertEqual(run()['grid']['cases'],192)
    def test_invalid_negative(self):
        with self.assertRaises(ValueError):construct(Case(adapter_cost=-1))
    def test_invalid_bool_cost(self):
        with self.assertRaises(ValueError):construct(Case(adapter_cost=True))
    def test_invalid_permission(self):
        with self.assertRaises(ValueError):construct(Case(adapter_available=1))

class AdversarialTests(unittest.TestCase):
    def reject(self,change):
        c=Case();r=construct(c);change(r)
        with self.assertRaises(ValueError):check_witness(c,r)
    def test_wrong_cost(self):self.reject(lambda r:r.update(cost=12))
    def test_wrong_surplus(self):self.reject(lambda r:r.update(surplus=4))
    def test_fake_decline(self):self.reject(lambda r:r.update(decision='DECLINE'))
    def test_missing_world(self):self.reject(lambda r:r['witnesses'].pop())
    def test_wrong_units(self):self.reject(lambda r:r['witnesses'][3]['allocation'][0].update(units=5))
    def test_duplicate_edge(self):self.reject(lambda r:r['witnesses'][3]['allocation'].append(dict(r['witnesses'][3]['allocation'][0])))
    def test_wrong_capacity(self):self.reject(lambda r:r['strategy'].update(reserved=('P',)))
    def test_wrong_interface(self):self.reject(lambda r:r['strategy'].update(adapter=False))
    def test_wrong_world(self):self.reject(lambda r:r['witnesses'][3]['world'].update(active=('A',)))
    def test_fake_feasible_flag(self):self.reject(lambda r:r['witnesses'][3].update(feasible=False))
    def test_fake_declined_value(self):
        c=Case(cash=0);r=construct(c);r['surplus']=100
        with self.assertRaises(ValueError):check_witness(c,r)
    def test_determinism(self):self.assertEqual(run(),run())

if __name__=='__main__':unittest.main()
