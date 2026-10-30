import copy
import unittest
from unittest.mock import patch
from connected_enterprise.channels import ChannelBook
from connected_enterprise.engine import MICRO,_initial,_prepare_plan,_record_exposure,default_config


class AccountView:
    def snapshot(self):return {'summary':{'available':5000*MICRO,'unrestrictedEarned':0}}


class ConnectedLifecycleTests(unittest.TestCase):
    def state(self,day=0):
        cfg=default_config();cfg.update(arrival_bps=10000)
        state=_initial(cfg,13,'channel',{})
        state['queue']=[{'id':'plan-test','time':day*24,'kind':'plan'}]
        return state

    def offer(self,jobs,state,buyer,cfg):
        ident='job-'+buyer['id']
        return {'job':{'id':ident,'work_keys':[ident]}},{'service_id':'reconciliation','price_microUSD':5*MICRO},25*MICRO

    def test_paid_prospect_has_no_uncontracted_free_followup(self):
        state=self.state(day=2)
        for b in state['buyers'][:4]:b['active']=False
        terms=state['config']['channels']['pilot'];terms.update(activation_reliability_bps=10000,realization_bps=10000,slots_per_day=1)
        book=ChannelBook(state['seed'],state['config']['channels']);book.purchase('pilot',0,'paid-plan');state['channel_state']=book.export()
        with patch('connected_enterprise.engine._offer',side_effect=self.offer):first=_prepare_plan(state,AccountView(),{})
        self.assertEqual(len(first['exposures']),1)
        customer=first['exposures'][0]['customer_id']
        self.assertTrue(any(d.get('customer_id')==customer and d['kind']=='offer' for d in first['declines']))
        state['channel_state']=first['channel_after'];next(b for b in state['buyers'] if b['id']==customer)['known']=True
        state['queue'][0]['time']=3*24
        with patch('connected_enterprise.engine._offer',side_effect=self.offer):second=_prepare_plan(state,AccountView(),{})
        self.assertFalse(any(d.get('customer_id')==customer and d['kind'] in {'offer','outside_choice'} for d in second['declines']))
        self.assertFalse(any(o['customer_id']==customer for o in second['orders']))

    def test_capacity_decline_preserves_finite_outside_choices_and_budget(self):
        state=self.state();state['config'].update(supplier_outage_start_day=0,supplier_outage_days=5)
        with patch('connected_enterprise.engine._offer',side_effect=self.offer):plan=_prepare_plan(state,AccountView(),{})
        constraints=[d for d in plan['declines'] if d['kind']=='capacity_decline'];outside=[d for d in plan['declines'] if d['kind']=='outside_choice']
        self.assertEqual(len(constraints),4);self.assertEqual(len(outside),4);self.assertFalse(plan['orders'])
        self.assertEqual(sum(d['buyer_choice']=='rival' for d in outside),2)
        self.assertTrue(all(d['outside_spend']>0 for d in outside))
        buyers={b['id']:b for b in state['buyers']}
        self.assertTrue(all(d['outside_spend']<=buyers[d['customer_id']]['remaining_budget'] for d in outside))

    def test_churned_exposure_needs_private_reactivation_response(self):
        state=self.state(day=2)
        for b in state['buyers']:b['active']=False
        state['config']['channels']['pilot'].update(activation_reliability_bps=10000,realization_bps=10000,slots_per_day=2)
        book=ChannelBook(state['seed'],state['config']['channels']);book.purchase('pilot',0,'paid-plan');state['channel_state']=book.export()
        with patch('connected_enterprise.engine._offer',side_effect=self.offer):
            first=_prepare_plan(state,AccountView(),{});second=_prepare_plan(copy.deepcopy(state),AccountView(),{})
        self.assertTrue(first['reactivations']);self.assertEqual(first['reactivations'],second['reactivations'])
        refused={r['customer_id'] for r in first['reactivations'] if not r['responded']}
        self.assertTrue(refused)
        self.assertTrue(all(r['response_probability_bps']==3500 for r in first['reactivations']))
        self.assertFalse(any(o['customer_id'] in refused for o in first['orders']))
        self.assertFalse(any(d.get('customer_id') in refused and d['kind']=='offer' for d in first['declines']))

    def test_inventory_and_liquidity_constraints_leave_outside_options(self):
        state=self.state()
        inventory=_prepare_plan(state,AccountView(),{})
        self.assertEqual(sum(d['kind']=='inventory_decline' for d in inventory['declines']),4)
        self.assertEqual(sum(d['kind']=='outside_choice' for d in inventory['declines']),4)
        class PoorAccount:
            def snapshot(self):return {'summary':{'available':MICRO,'unrestrictedEarned':0}}
        with patch('connected_enterprise.engine._offer',side_effect=self.offer):liquidity=_prepare_plan(state,PoorAccount(),{})
        self.assertEqual(sum(d['kind']=='liquidity_decline' for d in liquidity['declines']),4)
        self.assertEqual(sum(d['kind']=='outside_choice' for d in liquidity['declines']),4)
        self.assertGreater(liquidity['operating_cost_envelope'],state['config']['maintenance_daily'])

    def test_public_reactivation_trace_follows_its_paid_exposure(self):
        state={'events':[]}
        exposure={'customer_id':'SIM-customer-010','exposure_id':'paid-exposure','source_plan_id':'earned-plan'}
        response={'customer_id':'SIM-customer-010','time':1512,'source_plan_id':'earned-plan','responded':False,'response_probability_bps':3500}
        _record_exposure(state,1512,exposure,response)
        self.assertEqual([row['kind'] for row in state['events']],['EXPOSURE','REACTIVATION_RESPONSE'])
        first,second=state['events']
        self.assertEqual(second['id'],first['id']+'-reactivation')
        self.assertEqual((first['time'],first['customer_id'],first['source_plan_id']),(second['time'],second['customer_id'],second['source_plan_id']))
        self.assertFalse(second['responded'])


if __name__=='__main__':unittest.main()
