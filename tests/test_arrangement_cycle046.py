"""Accounting and applicability tests. Native execution remains separately required."""
import copy
import unittest
from commercial.ledger import digest
from experiments.arrangement_cycle046 import protocol,validate,witness,retain_mechanism


def fixture():
    actions=[{'op':'example'}];summary={'profit':150,'expenses':40,'collections':190}
    first={'id':'first','outcome':'SETTLED','offer':{'service_id':'reconciliation'},'price':30,'complete_cost':5,'collection_time':10,'qualified_time':1}
    later={'id':'next','outcome':'SETTLED','offer':{'service_id':'receivables_packet'},'price':160,'complete_cost':10,
           'collection_time':40,'qualified_time':30,'capacity_units':3,'capacity_source_plan_ids':['capacity']}
    plan={'plan_id':'capacity','kind':'capacity','purchased_time':20,'activation_time':25,'expiry_time':60,
          'cost':16,'capacity_units':2,'funding_receipt':{'funding':'EARNED'}}
    return {'complete':True,'summary':summary,'owned_account':{'ledger':{'summary':copy.deepcopy(summary),'actions':actions,'actions_sha256':digest(actions)}},
            'orders':[first,later],'investments':[plan]}


class NativeArrangementTests(unittest.TestCase):
    def test_protocol_is_fixed_before_running(self):
        p=protocol();self.assertEqual(validate(p),p)
        p['seed']+=1
        with self.assertRaises(ValueError):validate(p)
    def test_no_topup_and_independent_initial_capital(self):
        p=protocol();self.assertEqual(p['opening_microUSD'],100_000_000_000)
        self.assertEqual(p['external_funding_microUSD'],0)
        self.assertEqual(len(p['cases'])*len(p['arms']),6)
    def test_same_account_earned_successor(self):
        r=witness(fixture());self.assertEqual(r['status'],'NATIVE_FUNDED_COMPLEMENTARY_SUCCESSOR')
        self.assertEqual(r['chains'][0]['cohort_cost_and_enabler_invoice_microUSD'],26)
        self.assertEqual(r['chains'][0]['conservative_after_all_enterprise_expenses_microUSD'],120)
        self.assertFalse(r['new_invention']);self.assertEqual(r['authority'],[])
    def test_seed_funded_capacity_is_not_earned_successor(self):
        r=fixture();r['investments'][0]['funding_receipt']['funding']='SEED'
        self.assertEqual(witness(r)['status'],'NOT_ESTABLISHED')
    def test_missing_plan_refused(self):
        r=fixture();r['investments']=[]
        with self.assertRaisesRegex(ValueError,'MISSING_REQUIRED'):witness(r)
    def test_duplicate_plans_refused(self):
        r=fixture();r['investments'].append(copy.deepcopy(r['investments'][0]))
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):witness(r)
    def test_future_prior_collection_cannot_bootstrap(self):
        r=fixture();r['orders'][0]['collection_time']=21
        self.assertEqual(witness(r)['status'],'NOT_ESTABLISHED')
    def test_pending_successor_is_not_cash(self):
        r=fixture();r['orders'][1]['outcome']='PENDING'
        self.assertEqual(witness(r)['status'],'NOT_ESTABLISHED')
    def test_wrong_capacity_cannot_satisfy_packet(self):
        r=fixture();r['orders'][1]['capacity_units']=1
        self.assertEqual(witness(r)['status'],'NOT_ESTABLISHED')
    def test_expired_capacity_refused(self):
        r=fixture();r['investments'][0]['expiry_time']=30
        with self.assertRaisesRegex(ValueError,'LIFETIME'):witness(r)
    def test_all_linked_losing_and_refunded_work_costs_count(self):
        r=fixture();bad=copy.deepcopy(r['orders'][1]);bad.update(id='bad',outcome='REFUNDED',price=999,complete_cost=170)
        r['orders'].append(bad)
        r['summary']['expenses']=210;r['summary']['profit']=-20
        r['owned_account']['ledger']['summary']=copy.deepcopy(r['summary'])
        w=witness(r);self.assertEqual(w['status'],'NOT_ESTABLISHED')
        self.assertEqual(w['chains'][0]['cohort_collections_microUSD'],160)
        self.assertEqual(w['chains'][0]['cohort_contribution_before_shared_overhead_microUSD'],-36)
    def test_other_indispensable_invoice_counted_once(self):
        r=fixture();p=copy.deepcopy(r['investments'][0]);p.update(plan_id='access',kind='acquisition',cost=11,capacity_units=0)
        r['investments'].append(p);r['orders'][1]['acquisition_source_plan_id']='access'
        w=witness(r);self.assertEqual(w['chains'][0]['cohort_cost_and_enabler_invoice_microUSD'],37)
        self.assertEqual(len(w['chains'][0]['enablers']),2)
    def test_shared_plan_cost_not_charged_twice(self):
        r=fixture();o=copy.deepcopy(r['orders'][1]);o.update(id='third',collection_time=45)
        r['orders'].append(o)
        self.assertEqual(witness(r)['chains'][0]['cohort_cost_and_enabler_invoice_microUSD'],36)
    def test_all_enterprise_expenses_can_refute_local_margin(self):
        r=fixture();r['summary']['expenses']=170;r['summary']['profit']=20
        r['owned_account']['ledger']['summary']=copy.deepcopy(r['summary'])
        self.assertEqual(witness(r)['status'],'NOT_ESTABLISHED')
    def test_changed_financial_receipt_rejected(self):
        r=fixture();r['summary']['profit']+=1
        with self.assertRaisesRegex(ValueError,'SUMMARY'):witness(r)
    def test_incomplete_operation_rejected(self):
        r=fixture();r['complete']=False
        with self.assertRaises(ValueError):witness(r)


class RetainedApplicabilityTests(unittest.TestCase):
    def sample(self):
        summary={'source_sha256':'a'*64,'experiment_sha256':'d'*64,'protocol_sha256':'b'*64,'worlds':{}}
        for c in protocol()['cases']:
            for arm in protocol()['arms']:
                summary['worlds'][c['id']+'-'+arm]={'audit_accepted':True,'summary':{'profit':10},
                    'mechanism':{'status':'NOT_ESTABLISHED'},'result_sha256':'c'*64}
        return summary
    def test_ties_retain_simpler_policy(self):
        s=self.sample();c=retain_mechanism(s)
        self.assertTrue(all(v['choice']=='RETAIN_SIMPLER_ONE_UNIT_POLICY' for v in c['observed_regions'].values()))
        self.assertIs(c['execution_authority'],False);self.assertIsNone(c['current_proof'])
    def test_gain_without_enabling_witness_does_not_promote(self):
        s=self.sample();s['worlds']['larger-complementary']['summary']['profit']=99
        self.assertEqual(retain_mechanism(s)['observed_regions']['larger']['choice'],'RETAIN_SIMPLER_ONE_UNIT_POLICY')
    def test_observed_gain_and_witness_record_applicability(self):
        s=self.sample();r=s['worlds']['larger-complementary'];r['summary']['profit']=99
        r['mechanism']['status']='NATIVE_FUNDED_COMPLEMENTARY_SUCCESSOR'
        self.assertEqual(retain_mechanism(s)['observed_regions']['larger']['choice'],'COMPLEMENTARY_CAPACITY_SEARCH')
    def test_losses_do_not_create_success_capsule(self):
        s=self.sample()
        for arm in protocol()['arms']:s['worlds']['strong_outside-'+arm]['summary']['profit']=-5
        self.assertEqual(retain_mechanism(s)['observed_regions']['strong_outside']['choice'],'NO_SUPPORTED_PROFITABLE_EXPANSION')
    def test_failed_audit_refuses_learning(self):
        s=self.sample();s['worlds']['central-one_unit']['audit_accepted']=False
        with self.assertRaises(ValueError):retain_mechanism(s)


class PublicScopeTests(unittest.TestCase):
    def test_completed_synthetic_header_is_admissible(self):
        from experiments.arrangement_cycle046 import protocol,validate_result_header,SCHEMA
        p=protocol();f={'source':{'sha256':'a'*64},'driver_files':{'driver':'c'*64}}
        r={'schema':SCHEMA,'scope':p['scope'],'complete':True,'source_sha256':'a'*64,
           'protocol_sha256':digest(p),'experiment_sha256':digest(f['driver_files']),'opening_per_world_microUSD':p['opening_microUSD'],
           'external_funding_microUSD':0,'actual_customers':0,'actual_profit_microUSD':None,'limits':p['limits']}
        validate_result_header(r,f,p)
        for change in ({'scope':'REAL_COMMERCE'},{'actual_customers':1},{'actual_customers':False},
                       {'external_funding_microUSD':False},{'actual_profit_microUSD':123},
                       {'opening_per_world_microUSD':1},{'limits':[]} ,{'complete':1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_result_header(dict(r,**change),f,p)


if __name__=='__main__':unittest.main()
