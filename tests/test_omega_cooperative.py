import copy
import unittest
from mechanism_harness import cooperative_construction as c


class CooperativeContractTests(unittest.TestCase):
    def test_naive_overfunding_has_free_rider_deviation(self):
        result=c.construct_arrangement(c.fixture())
        self.assertTrue(any(e['kind']=='PROFITABLE_WITHDRAWAL' for q in result['criticisms'] for e in q['verification']['errors']))
        self.assertTrue(result['verification']['accepted'])
        self.assertEqual(result['cash_received_cents'],0)

    def test_full_ordinary_control_matches(self):
        for stress in ('central','weak','no_demand','copycat','withdrawal','overrun'):
            spec=c.fixture(stress)
            self.assertEqual(c.construct_arrangement(spec)['proposal'],c.ordinary_shared_commission(spec))

    def test_strong_incumbent_erases_new_frontier_claim(self):
        spec=c.fixture();proposal=c.construct_arrangement(spec)['proposal']
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal,c.ordinary_shared_commission(spec))
        for p in spec['participants']:
            self.assertIsNone(c.construct_arrangement({**spec,'participants':[p]})['proposal'])

    def test_no_demand_copycat_and_overrun_decline(self):
        for stress in ('weak','no_demand','copycat','overrun'):
            self.assertEqual(c.construct_arrangement(c.fixture(stress))['decision'],'NONENTRY')

    def test_bad_fields_and_bool_money_rejected(self):
        spec=c.fixture();spec['participants'][0]['budget_cents']=True
        with self.assertRaises(ValueError):c.construct_arrangement(spec)
        with self.assertRaises(ValueError):c.construct_arrangement({**c.fixture(),'shell':'echo unsafe'})

    def test_underfunding_and_budget_rejected(self):
        spec=c.fixture();proposal=c.construct_arrangement(spec)['proposal']
        broken=copy.deepcopy(proposal)
        for k in broken['contributions_cents']:broken['contributions_cents'][k]=0
        self.assertFalse(c.verify_arrangement(spec,broken)['accepted'])
        broken['contributions_cents']['beneficiary-0']=960
        self.assertFalse(c.verify_arrangement(spec,broken)['accepted'])

    def test_zero_cost_no_demand_has_no_phantom_commission(self):
        spec=c.fixture('no_demand');spec['costs']={k:0 for k in spec['costs']};spec['margin_cents']=0
        for person in spec['participants']:person['budget_cents']=0
        self.assertIsNone(c.construct_arrangement(spec)['proposal'])
        self.assertIsNone(c.ordinary_shared_commission(spec))

    def test_output_tampering_rejected(self):
        raw=c.substrate.synthetic_raw('reconciliation',8,61011)
        result=c._measured(raw,c.inventor.policy())
        artifact=copy.deepcopy(result['artifact']);artifact['useful_outcome']={'counterfeit':True}
        self.assertFalse(c.audit_delivery('reconciliation',raw,artifact)['accepted'])

    def test_actual_fresh_productive_successor_and_reuse(self):
        result=c.execute_production()
        self.assertTrue(result['all_accepted_complete'])
        self.assertTrue(result['equal_content_reuse_ties'])
        self.assertTrue(result['strong_conventional_outcome_ties'])
        self.assertEqual(result['candidate_count'],32)
        self.assertTrue(all(not x['direct_predecessor_mapping_accepted'] for x in result['successors']))
        self.assertGreater(result['total_retained_work_including_acquisition'],result['successor_retained_work'])

    def test_delayed_funding_failed_acceptance_are_not_sales(self):
        result=c.execute()
        for case in result['arrangements']:
            self.assertFalse(case['financial_execution'])
            if case['stress'] in ('delayed_commitment','failed_verification'):
                self.assertFalse(case['conditionally_feasible'])
            if case['stress']=='failed_verification':self.assertFalse(case['injected_delivery_check']['accepted'])
        self.assertFalse(result['newly_attainable_vs_strong_incumbent'])
        self.assertFalse(result['discovery_superiority_established'])

if __name__=='__main__':unittest.main()
