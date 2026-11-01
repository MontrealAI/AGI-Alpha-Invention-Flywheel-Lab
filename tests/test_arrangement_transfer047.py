"""Scoped inherited recipes never grant proof, cash or promotion authority."""
import copy
import unittest
from commercial.ledger import digest
from experiments.arrangement_transfer047 import (protocol, lesson_record, retained_policy,
    configure, select_from_results, covered)


def capsule():
    return {'schema':'agi-alpha/applicability-capsule046/v1','current_proof':None,
        'execution_authority':False,'authority':[],
        'observed_regions':{'positive':{'choice':'COMPLEMENTARY_CAPACITY_SEARCH','observed_profit_delta_microUSD':25},
                            'negative':{'choice':'NO_SUPPORTED_PROFITABLE_EXPANSION','observed_profit_delta_microUSD':0}}}


def select(c=None, **kw):
    c=capsule() if c is None else c
    return retained_policy(c,digest(c),**dict(required_units=3,initial_slots=1,max_slots=9,max_customers=2,**kw))


def world(profit):
    return {'audit_accepted':True,'summary':{'profit':profit,'cash':100000,'payables':0,
        'investmentStopped':False,'custodyReserve':100,'tailReserve':100,'workingCapital':100}}


def outcomes():
    return {case['id']+'-'+arm:world(100) for case in protocol()['cases'] for arm in protocol()['arms']}


class RetainedArrangement047Tests(unittest.TestCase):
    def test_imported_capsule_is_known_method_not_new_authority(self):
        r=lesson_record();self.assertEqual(digest(r['capsule']),r['capsule_sha256'])
        self.assertTrue(r['capsule']['known_method_not_new_invention'])
        self.assertIn('strong_outside',r['capsule']['observed_regions'])
        self.assertFalse(r['capsule']['execution_authority'])

    def test_joint_resource_recipe_not_single_unit_trap(self):
        r=select();self.assertEqual(r['max_quantity'],5)
        self.assertEqual(r['choice'],'COMPLEMENTARY_CAPACITY_SEARCH')
        self.assertIsNone(r['current_proof']);self.assertEqual(r['authority'],[])
        self.assertIs(r['execution_authority'],False)

    def test_no_positive_prior_retains_simple(self):
        c=capsule();c['observed_regions']['positive']['observed_profit_delta_microUSD']=0
        self.assertEqual(select(c)['max_quantity'],1)

    def test_current_contract_limits_remain(self):
        c=capsule()
        r=retained_policy(c,digest(c),required_units=3,initial_slots=1,max_slots=3,max_customers=2)
        self.assertEqual(r['max_quantity'],2)

    def test_changed_source_capsule_pin_fails(self):
        c=capsule();pin=digest(c);c['observed_regions']['positive']['observed_profit_delta_microUSD']+=1
        with self.assertRaisesRegex(ValueError,'PINNED_CAPSULE'):
            retained_policy(c,pin,required_units=3,initial_slots=1,max_slots=9,max_customers=2)

    def test_no_inherited_permission_or_approval(self):
        for key,value in [('authority',['spend']),('current_proof',{'passed':True}),('execution_authority',True)]:
            c=capsule();c[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'NO_INHERITED'):select(c)

    def test_false_is_not_zero_for_authority(self):
        c=capsule();c['execution_authority']=0
        with self.assertRaises(ValueError):select(c)

    def test_boolean_profit_or_capacity_is_not_evidence(self):
        c=capsule();c['observed_regions']['positive']['observed_profit_delta_microUSD']=True
        with self.assertRaisesRegex(ValueError,'EXACT_OBSERVED'):select(c)
        c=capsule()
        with self.assertRaises(ValueError):retained_policy(c,digest(c),required_units=True,initial_slots=1,max_slots=9,max_customers=2)

    def test_no_capsule_or_inconsistent_physical_envelope(self):
        c=capsule();c['observed_regions']={}
        with self.assertRaises(ValueError):select(c)
        c=capsule()
        with self.assertRaises(ValueError):retained_policy(c,digest(c),required_units=3,initial_slots=10,max_slots=9,max_customers=2)

    def test_three_arms_and_all_negative_regions_fixed(self):
        p=protocol();self.assertEqual(len(p['arms']),3);self.assertEqual(len(p['cases']),3)
        self.assertEqual(p['cases'][1]['seed'],p['cases'][2]['seed'])
        self.assertEqual(p['opening_microUSD'],100_000_000_000)
        self.assertEqual(p['reuse_adaptation_cost_microUSD'],5_000_000)
        self.assertEqual(p['external_funding_microUSD'],0)

    def test_one_unit_wins_exact_three_way_tie(self):
        r=select_from_results(outcomes())
        self.assertTrue(all(x['selected']=='one_unit' for x in r.values()))

    def test_strong_ordinary_beats_costlier_reuse(self):
        rows=outcomes()
        for case in protocol()['cases']:
            rows[case['id']+'-ordinary_complement']['summary']['profit']=250
            rows[case['id']+'-retained_complement']['summary']['profit']=245
        r=select_from_results(rows)
        self.assertTrue(all(x['selected']=='ordinary_complement' for x in r.values()))
        self.assertTrue(all(x['retained_vs_ordinary_profit_microUSD']==-5 for x in r.values()))

    def test_actual_reuse_gain_can_win_without_forcing_it(self):
        rows=outcomes()
        for case in protocol()['cases']:rows[case['id']+'-retained_complement']['summary']['profit']=150
        self.assertTrue(all(x['selected']=='retained_complement' for x in select_from_results(rows).values()))

    def test_losing_case_has_no_promoted_policy(self):
        rows=outcomes()
        for r in rows.values():r['summary']['profit']=-1
        self.assertTrue(all(x['selected'] is None for x in select_from_results(rows).values()))

    def test_positive_profit_does_not_override_obligations(self):
        r=world(999999);r['summary']['cash']=1
        self.assertFalse(covered(r))
        rows=outcomes();rows['fresh_transfer-retained_complement']=r
        self.assertNotEqual(select_from_results(rows)['fresh_transfer']['selected'],'retained_complement')

    def test_native_stop_and_payables_fail_adoption(self):
        for k,v in [('investmentStopped',True),('payables',1)]:
            r=world(999999);r['summary'][k]=v;self.assertFalse(covered(r))

    def test_unaudited_result_cannot_select_anything(self):
        rows=outcomes();rows['larger_workload-ordinary_complement']['audit_accepted']=False
        with self.assertRaisesRegex(ValueError,'AUDITED'):select_from_results(rows)

    def test_selector_does_not_mutate_evidence(self):
        rows=outcomes();before=copy.deepcopy(rows);select_from_results(rows);self.assertEqual(rows,before)


if __name__=='__main__':unittest.main()
