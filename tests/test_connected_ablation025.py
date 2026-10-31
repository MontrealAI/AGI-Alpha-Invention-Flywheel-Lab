"""Small declaration checks for exposed, cost-matched diagnostic paths."""
import copy
import unittest
from connected_enterprise.engine import validate_config
from scripts.run_strategic025_ablation import config,PROTOCOL

class ExposedAblation(unittest.TestCase):
    def test_fixed_exposed_protocol(self):
        self.assertEqual(PROTOCOL['seed'],2610311602)
        self.assertEqual(PROTOCOL['horizon_days'],28)
        self.assertIn('NOT_FRESH_CONFIRMATION',PROTOCOL['status'])
    def test_modes_are_explicit_and_disjoint(self):
        sequential=config('quote_only');self.assertEqual(validate_config(sequential),sequential)
        self.assertNotIn('strategic_allocation_policy',sequential)
        bad=copy.deepcopy(sequential);bad['strategic_allocation_policy']={}
        with self.assertRaises(ValueError):validate_config(bad)
        bad=copy.deepcopy(sequential);bad['strategic_execution']='magic'
        with self.assertRaises(ValueError):validate_config(bad)
    def test_three_component_arms_match_declared_costs(self):
        arms=[config(a) for a in ('matched_incumbent','quote_only','full_joint')]
        for key in ('setup_cost','qualification_cost','mechanism_policy'):
            self.assertTrue(all(a[key]==arms[0][key] for a in arms))
        normalized=[]
        for arm in arms:
            c=copy.deepcopy(arm)
            for key in ('strategic_policy','strategic_execution','strategic_allocation_policy'):c.pop(key,None)
            normalized.append(c)
        self.assertEqual(normalized[0],normalized[1]);self.assertEqual(normalized[1],normalized[2])
class SequentialCoverage(unittest.TestCase):
    def fixture(self):
        cfg=config('quote_only');cfg['arrival_bps']=10000
        result={'config':cfg,'seed':1,'investments':[],'orders':[],
                'decisions':[{'kind':'outside_choice','time':0,'customer_id':'c','chosen':False,
                              'strategic_selection':{'problem':{'job_id':'j'}}}]}
        manifest={'jobs':[{'id':'j','accepted':True,'service_id':'reconciliation','artifact':'x','artifact_sha256':'h'}]}
        lifecycle={'daily_candidate_ids_recomputed':{0:['c']},'daily_public_buyers':{0:{'c':{'service_index':0}}}}
        return manifest,result,lifecycle
    def test_no_bid_evaluation_must_have_receipt(self):
        from unittest.mock import patch
        from connected_enterprise.sequential_audit import expected_evaluations
        m,r,l=self.fixture()
        with patch('connected_enterprise.sequential_audit.read_bound',return_value={'outcome_scope':'complete_outcome'}):
            self.assertEqual(expected_evaluations('.',m,r,l),{(0,'c'):'j'})
            r['decisions'][0].pop('strategic_selection')
            with self.assertRaisesRegex(ValueError,'COVERAGE'):expected_evaluations('.',m,r,l)
    def test_missing_need_and_zero_slots(self):
        from unittest.mock import patch
        from connected_enterprise.sequential_audit import expected_evaluations
        m,r,l=self.fixture()
        with patch('connected_enterprise.sequential_audit.read_bound',return_value={'outcome_scope':'complete_outcome'}):
            r['decisions']=[]
            with self.assertRaisesRegex(ValueError,'NEED_COVERAGE'):expected_evaluations('.',m,r,l)
            m,r,l=self.fixture();r['config']['initial_slots']=0
            with self.assertRaisesRegex(ValueError,'RECEIPT_COVERAGE'):expected_evaluations('.',m,r,l)
            r['decisions'][0].pop('strategic_selection')
            self.assertEqual(expected_evaluations('.',m,r,l),{(0,'c'):None})

if __name__=='__main__':unittest.main()
