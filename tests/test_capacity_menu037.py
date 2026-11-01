import copy,json,unittest
from portfolio25.pricing import SCENARIOS
from adaptive_enterprise.strategies import offer_catalog
from connected_enterprise.strategic_commerce import select
from connected_enterprise.capacity_menu import evaluate,rederive
from adaptive_enterprise.allocation import allocate


def fixture(units=(3,3)):
    obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':100000,'unrestrictedEarned':100000}}
    sc=copy.deepcopy(SCENARIOS[0]);sc.update(id='case',weight=1,repeat_horizon=0,cost_shock=1,accept_prob=1,collect_prob=1)
    policy={'schema':'connected-strategic-commerce/v1','public_basis':'Engineering public deterministic opportunity, not measured demand','price_bps':[5000],'rival_price_bps':[10000],'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':[sc],'demand_model':'connected_range','connected_beliefs':{'case':{'min_value_bps':20000,'max_value_bps':20000,'min_budget_microUSD':10000,'max_budget_microUSD':10000,'rival_available_bps':0}}}
    pub={'anchor':2000,'public_rival_price':2000,'base_cost':100,'payment_bps':0,'payment_fixed':0,'available':100000,'reserve_buffer':0,'quote_cost':0,'native_state_digest':'a'*64,'profit_tax_bps':0}
    offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
    ds=[]
    for i,u in enumerate(units):
        r=select(policy,None,'job'+str(i),offer,None,pub)
        ds.append({'id':'d'+str(i),'customer_id':'c'+str(i),'onboarding':0,'exclusive_group':'c'+str(i),'selection':r,'requires':[],'capacity_units':u,'work_keys':['w'+str(i)]})
    risk={'scenarios':{'case':10000},'worst_loss_limit':100000,'downside_penalty_bps':0,'max_states':4096,'authorized_allocation':100000,'interactions':[]}
    return dict(observation=obs,deliveries=ds,riskpolicy=risk,now=0,opportunity_time=24,finish_time=25,calendar=[{'id':'base','units':3,'active_at':0,'expires_at':100}],contract={'id':'unit','unit_invoice':10,'lead_hours':24,'duration_hours':48},max_quantity=3,current_commitment_lock=0,future_evaluation_cost=20,earned_deduction=0,retention_bps=10000,shared_benefit_id='expansion-same-backlog')

class CapacityMenu(unittest.TestCase):
    def test_outer_split_lock_and_work_overlap(self):
        args=fixture();args['observation']['summary']['unrestrictedEarned']=30
        option=evaluate(**args)['options'][0]
        chosen=allocate(args['observation'],[option],args['riskpolicy'],allow_seed=True)
        self.assertEqual(chosen['selected'],[option['id']]);self.assertEqual(chosen['reserve_amount'],2250)
        args['observation']['summary']['available']=2200
        self.assertFalse(allocate(args['observation'],[option],args['riskpolicy'],allow_seed=True)['selected'])
        for value in (-1,2221,True):
            bad=copy.deepcopy(option);bad['execution']['earned_cash_lock']=value
            with self.assertRaises(ValueError):allocate(args['observation'],[bad],args['riskpolicy'],allow_seed=True)
        bad=copy.deepcopy(option);bad['execution'].pop('capacity_recourse_schema')
        with self.assertRaises(ValueError):allocate(args['observation'],[bad],args['riskpolicy'],allow_seed=True)
        args=fixture();one=evaluate(**args)['options'][0];two=copy.deepcopy(one)
        two['id']='other';two['exclusive_group']=None;one['exclusive_group']=None
        two['benefit_ids']=['different-benefit']
        both=allocate(args['observation'],[one,two],args['riskpolicy'],allow_seed=True)
        self.assertEqual(len(both['selected']),1)

    def test_known_supplier_outage_disables_future_quantity(self):
        from connected_enterprise.engine import default_config
        from connected_enterprise.joint_planning import capacity_recourse
        args=fixture((3,3,3));cfg=default_config()
        cfg.update(initial_slots=3,maximum_slots=6,capacity_price=10,production_hours=1,horizon_days=10,exposure_cost=1,qualification_cost=1)
        cfg['strategic_allocation_policy']={'capacity_menu':{'max_quantity':3,'opportunity_delay_hours':24,'retention_bps':10000}}
        common=(cfg,0,args['observation'],0,args['deliveries'],[],3,args['riskpolicy'])
        active=capacity_recourse(*common)
        self.assertTrue(active['options'])
        cfg.update(supplier_outage_start_day=1,supplier_outage_days=1)
        blocked=capacity_recourse(*common)
        self.assertEqual(blocked['options'],[])
        self.assertEqual(blocked['recourse'][0]['slots'],0)
        rederive(blocked)

    def test_selected_quantity_binds_actual_invoice_and_timing(self):
        from connected_enterprise.strategic_audit import check_capacity_effect
        args=fixture();option=evaluate(**args)['options'][0]
        cfg={'capacity_price':10,'capacity_lead_hours':24,'capacity_duration_hours':48}
        row={'id':option['id'],'kind':'capacity','capacity_units':3,'cost':30,'purchased_time':0,'activation_time':24,'expiry_time':72,'predicted_net':870}
        check_capacity_effect(option,row,cfg,0,args['riskpolicy'])
        for key in ('capacity_units','cost','purchased_time','activation_time','expiry_time','predicted_net'):
            bad=copy.deepcopy(row);bad[key]+=1
            with self.assertRaisesRegex(ValueError,'SELECTED_CAPACITY_QUANTITY'):
                check_capacity_effect(option,bad,cfg,0,args['riskpolicy'])
        bad=copy.deepcopy(row);bad.update(capacity_units=2,cost=20,predicted_net=880)
        with self.assertRaisesRegex(ValueError,'SELECTED_CAPACITY_QUANTITY'):
            check_capacity_effect(option,bad,cfg,0,args['riskpolicy'])

    def test_three_unit_complement_and_replay_no_authority(self):
        a=fixture();before=copy.deepcopy(a);r=evaluate(**a)
        self.assertEqual([len(x['selected_work']) for x in r['recourse']],[1,1,1,2])
        self.assertEqual([x['execution']['purchased_units'] for x in r['options']],[3])
        o=r['options'][0];self.assertEqual(o['upfront_cost'],30)
        self.assertEqual(o['future_net_cash'],{'case':900})
        self.assertEqual(o['execution']['cash_lock'],2220)
        self.assertEqual(o['execution']['recourse_work_keys'],['w0','w1'])
        self.assertEqual(o['benefit_ids'],['expansion-same-backlog','delivery-job0','delivery-job1'])
        self.assertEqual(a,before);self.assertIsNone(r['authorized_digest'])
        self.assertNotIn('authorized_digest',json.dumps(r['recourse']))
        rederive(json.loads(json.dumps(r)))
        r['options'][0]['upfront_cost']=0
        with self.assertRaises(ValueError):rederive(r)

    def test_mixed_units_not_delivery_count(self):
        r=evaluate(**fixture((2,3)))
        self.assertEqual([len(x['selected_work']) for x in r['recourse']],[1,1,2,2])
        self.assertEqual([o['execution']['purchased_units'] for o in r['options']],[2,3])

    def test_one_request_no_invented_demand(self):
        self.assertEqual(evaluate(**fixture((3,)))['options'],[])

    def test_finish_must_precede_expiry_and_current_calendar_expires(self):
        a=fixture();a['contract']['duration_hours']=1
        self.assertEqual(evaluate(**a)['options'],[])
        a=fixture();a['calendar'][0]['expires_at']=25
        r=evaluate(**a)
        self.assertEqual(r['recourse'][0]['slots'],0)
        self.assertEqual(r['recourse'][3]['slots'],3)
        self.assertEqual(len(r['recourse'][3]['selected_work']),1)

    def test_cash_earned_and_current_commitment_locks(self):
        a=fixture();a['current_commitment_lock']=99000
        self.assertEqual(evaluate(**a)['options'],[])
        a=fixture();a['earned_deduction']=99980
        self.assertEqual(evaluate(**a)['options'],[])
        a=fixture();a['observation']['summary']['unrestrictedEarned']=0
        self.assertEqual(evaluate(**a)['options'],[])

    def test_invoice_earned_future_production_may_use_present_seed(self):
        a=fixture();a['observation']['summary']['unrestrictedEarned']=30
        r=evaluate(**a);self.assertEqual(len(r['options']),1)
        o=r['options'][0];self.assertEqual(o['upfront_cost'],30)
        self.assertEqual(o['execution']['earned_cash_lock'],0)
        self.assertEqual(o['execution']['cash_lock'],2220)
        self.assertEqual(o['execution']['capacity_recourse_schema'],'connected-capacity-recourse/v1')
        a['observation']['summary']['available']=2200
        self.assertEqual(evaluate(**a)['options'],[])

    def test_retention_and_common_cost_once(self):
        a=fixture();a['retention_bps']=5000;r=evaluate(**a)
        self.assertEqual(r['options'][0]['future_net_cash'],{'case':450})
        self.assertEqual(r['recourse'][0]['scenario_net'],{'case':'880'})
        self.assertEqual(r['recourse'][3]['scenario_net'],{'case':'1780'})
        a['future_evaluation_cost']=0
        with self.assertRaises(ValueError):evaluate(**a)
        a=fixture();a['deliveries'][0]['selection']['problem']['public']['quote_cost']=1
        with self.assertRaisesRegex(ValueError,'CHARGED_TWICE'):evaluate(**a)

    def test_work_overlap_and_customer_exclusivity(self):
        a=fixture();a['deliveries'][1]['work_keys']=['w0']
        self.assertEqual(evaluate(**a)['options'],[])
        a=fixture();a['deliveries'][1]['exclusive_group']='c0'
        self.assertEqual(evaluate(**a)['options'],[])

    def test_unresolved_bound_and_empty_backlog(self):
        a=fixture((3,3,3));a['riskpolicy']['max_states']=4
        r=evaluate(**a)
        self.assertEqual(r['options'],[]) # four alternatives+empty exceed cap
        a=fixture(());self.assertEqual(evaluate(**a)['options'],[])

if __name__=='__main__':unittest.main()
