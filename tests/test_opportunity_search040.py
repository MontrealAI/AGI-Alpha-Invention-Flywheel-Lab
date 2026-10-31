"""Adversarial tests for the opt-in native opportunity/means search."""
import copy
import hashlib
import unittest
from connected_enterprise.engine import default_config,validate_config,MICRO
from connected_enterprise.opportunity_search040 import SCHEMA,validate_policy,search,audit_history,connected_sequence
from commercial.ledger import digest

POLICY={'schema':SCHEMA,'conversion_bps':9000,'max_new_deliveries':12,'buffer_microUSD':1*MICRO,
        'minimum_settlements':1,'min_expected_surplus_microUSD':100_000}

def fixture():
    cfg=default_config();cfg['opportunity_policy']=copy.deepcopy(POLICY)
    cfg['channels']['pilot'].update(price_microUSD=MICRO,support_microUSD=100000,activation_reliability_bps=10000,
          realization_bps=10000,overlap_bps=0,slots_per_day=4,lead_days=1)
    state={'arm':'growth','config':cfg,'orders':[],'investments':[],'decisions':[],
           'buyers':[{'id':f'SIM-customer-{i:03d}','onboarded':False,'known':i<4,'active':True} for i in range(24)]}
    candidate={'id':'SIM-customer-001','known':True,'active':True,'remaining_budget':100*MICRO,'onboarded':False}
    prepared={'event':{'kind':'plan','time':24*5},'before':{'summary':{'available':200*MICRO,'unrestrictedEarned':200*MICRO,'investmentStopped':False},'state_digest':'a'*64},
              'channel_after':{'instances':{},'contacts':{}}}
    jobs={s:{'job':{'id':s,'service_id':s,'accepted':True},'artifact':{'outcome_scope':'complete_outcome'}} for s in ('reconciliation','kpi_variance','evidence_matrix')}
    def offer(jobs,state,buyer,cfg):
        return jobs['evidence_matrix'],{'price_microUSD':50*MICRO},45*MICRO
    return state,prepared,jobs,[candidate],offer

class PolicyTests(unittest.TestCase):
    def test_valid_optin_does_not_modify_default(self):
        self.assertNotIn('opportunity_policy',default_config())
        st,*_=fixture();self.assertEqual(validate_config(st['config'])['opportunity_policy'],POLICY)
    def test_reject_float_bool_unknown_fields(self):
        for key,value in [('conversion_bps',True),('conversion_bps',0.5),('conversion_bps',10001),('minimum_settlements',0),('max_new_deliveries',49)]:
            x=copy.deepcopy(POLICY);x[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):validate_policy(x)
        x=copy.deepcopy(POLICY);x['permission']='spend'
        with self.assertRaises(ValueError):validate_policy(x)
    def test_unknown_buyer_cannot_be_treated_as_observed_direct_demand(self):
        st,p,j,bs,fn=fixture();bs.append({'id':'SIM-customer-023','known':False,'active':True,'remaining_budget':100*MICRO,'onboarded':False})
        d=search(st,p,j,bs,1,0,fn)
        self.assertEqual(len(d['direct_outcomes']),1)
        self.assertEqual(d['selected'],'continue_direct')
        self.assertEqual(d['unseen_buyer_outcomes'],'UNKNOWN')
    def test_profit_without_collection_cannot_finance_reach(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'PENDING','price':50*MICRO,'complete_cost':5*MICRO,'collection_time':None}]
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_no_spendable_earnings_blocks_acquisition(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':50*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        p['before']['summary']['unrestrictedEarned']=0
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_profit_without_available_cash_blocks_acquisition(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':50*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        p['before']['summary']['available']=0
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_negative_observed_contribution_refuses_expansion(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':5*MICRO,'complete_cost':10*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_positive_collected_evidence_selects_costed_partner(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':50*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        decision=search(st,p,j,bs,2,0,fn)
        self.assertEqual(decision['selected'],'partner_access')
        self.assertIn(decision['target_service_id'],('reconciliation','kpi_variance','evidence_matrix'))
        self.assertEqual(decision['observed']['reconciliation']['settlements'],1)
        self.assertGreater(next(x['net_microUSD'] for x in decision['alternatives'] if x['id']=='partner_access'),0)
        self.assertEqual(decision['id'],digest({k:v for k,v in decision.items() if k!='id'}))
    def test_discovery_can_select_a_better_unsold_service_from_declared_priors(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':6*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        d=search(st,p,j,bs,1,0,fn)
        self.assertEqual(d['target_service_id'],'evidence_matrix')
        self.assertEqual(d['observed']['reconciliation']['settlements'],1)
        self.assertNotIn('evidence_matrix',d['observed'])

    def test_prospective_buyer_declines_are_not_paid_work(self):
        st,p,j,bs,fn=fixture();st['decisions']=[{'kind':'offer','time':24,'chosen':False}]
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_native_stop_state_blocks_even_high_margins(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':50*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        p['before']['summary']['investmentStopped']=True
        self.assertEqual(search(st,p,j,bs,1,0,fn)['selected'],'continue_direct')
    def test_unearned_future_gain_does_not_increase_budget(self):
        st,p,j,bs,fn=fixture();st['orders']=[{'outcome':'SETTLED','price':50*MICRO,'complete_cost':5*MICRO,
                  'collection_time':24,'offer':{'service_id':'reconciliation'}}]
        p['before']['summary']['unrestrictedEarned']=500000
        d=search(st,p,j,bs,1,0,fn)
        self.assertEqual(d['selected'],'continue_direct')
    def test_source_scope_not_automatically_authority(self):
        st,p,j,bs,fn=fixture();d=search(st,p,j,bs,1,0,fn)
        self.assertNotIn('authority',d)
        self.assertNotIn('native_receipt',d)
        self.assertIn('NOT_OBSERVED_CAUSAL_BENEFIT',d['decision_scope'])

class AuditTests(unittest.TestCase):
    def fixture_trace(self):
        st,p,j,bs,fn=fixture();st['config']['horizon_days']=2
        records=[];events=[]
        for day in range(2):
            p['event']['time']=24*day
            d=search(st,p,j,bs,1,0,fn);records.append(d)
            events.append({'kind':'OPPORTUNITY_SELECTION','time':24*day,'decision_sha256':d['id'],
                           'selected':d['selected'],'target_service_id':d['target_service_id']})
        return {'arm':'growth','config':st['config'],'decisions':records,'events':events,'orders':[],
                'investments':[], 'summary':{'profit':0}}, {'jobs':[{'service_id':s,'accepted':True} for s in j]}
    def test_empty_prior_native_observation_is_rederived(self):
        result,manifest=self.fixture_trace()
        self.assertEqual(audit_history(result,manifest)['opportunity_search_decisions_checked'],2)
        self.assertEqual(connected_sequence(result,manifest)['status'],'NOT_ESTABLISHED')
    def test_forged_observation_fails(self):
        result,manifest=self.fixture_trace();result['decisions'][0]['observed']={'reconciliation':{'settlements':99,'mean_contribution_microUSD':10}}
        with self.assertRaises(ValueError):audit_history(result,manifest)
    def test_proposal_change_without_event_fails(self):
        result,manifest=self.fixture_trace();result['decisions'][0]['selected']='partner_access'
        with self.assertRaises(ValueError):audit_history(result,manifest)
    def test_unregistered_extra_opportunity_fails(self):
        result,manifest=self.fixture_trace();result['decisions'].append(copy.deepcopy(result['decisions'][0]))
        with self.assertRaises(ValueError):audit_history(result,manifest)
    def test_no_invented_asset_for_hold(self):
        result,manifest=self.fixture_trace();result['investments'].append({'purchased_time':0,'kind':'acquisition','funding_receipt':{'funding':'EARNED'}})
        with self.assertRaises(ValueError):audit_history(result,manifest)
    def test_baseline_cannot_self_report_opportunity_discovery(self):
        result,manifest=self.fixture_trace();result['arm']='baseline'
        with self.assertRaises(ValueError):audit_history(result,manifest)

if __name__=='__main__':unittest.main()
