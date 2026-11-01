import unittest
from adaptive_enterprise.allocation import allocate,default_riskpolicy

def option(ident,units,work,net=100):
    return {'id':ident,'kind':'delivery','upfront_cost':10,'later_liabilities':{'central':0,'adverse':0},'future_net_cash':{'central':net+10,'adverse':net+10},'benefit_ids':[ident],'requires':[],'exclusive_group':None,'authorized':True,'evidence':'fixture','execution':{'job_id':ident,'customer_id':'buyer-'+ident,'payment_bps':0,'payment_fixed_microUSD':0,'onboarding_microUSD':0,'capacity_units':units,'work_keys':work}}

class CompleteOfferAllocationTests(unittest.TestCase):
    def run_plan(self,opts,slots):
        return allocate({'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':10000,'unrestrictedEarned':10000}},opts,default_riskpolicy(),max_delivery_slots=slots)
    def test_three_component_packet_needs_three_slots(self):
        p=option('packet',3,['a','b','c'])
        self.assertEqual(self.run_plan([p],2)['selected'],[])
        self.assertEqual(self.run_plan([p],3)['selected'],['packet'])
    def test_packet_and_primitive_cannot_reuse_work(self):
        self.assertEqual(self.run_plan([option('packet',3,['a','b','c'],500),option('primitive',1,['a'])],4)['selected'],['packet'])
    def test_disjoint_work_with_capacity_can_combine(self):
        self.assertEqual(self.run_plan([option('packet',3,['a','b','c']),option('primitive',1,['d'])],4)['selected'],['packet','primitive'])
    def test_invalid_unit_count_or_empty_work_rejected(self):
        for p in (option('bad',0,['a']),option('bad',True,['a']),option('bad',3,[]),option('bad',3,['a','a'])):
            with self.assertRaises(ValueError):self.run_plan([p],4)
