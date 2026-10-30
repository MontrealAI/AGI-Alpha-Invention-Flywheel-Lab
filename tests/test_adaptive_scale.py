import copy
import unittest
from adaptive_enterprise.scale import CONTROLLERS, _controller_actions, default_config, evaluate_scale, simulate_scale, validate_config


class AdaptiveScaleTests(unittest.TestCase):
    def cfg(self):
        c=default_config();c['months']=18;c['targets_annual_collected_cents']=[1_000_000,10**18]
        return c

    def test_matched_controls_replay_and_cash_conservation(self):
        c=self.cfg()
        for controller in CONTROLLERS:
            r=simulate_scale(c,17,controller)
            self.assertEqual(r,simulate_scale(c,17,controller))
            for index,row in enumerate(r['monthly']):
                self.assertEqual(row['cash_cents'],c['opening_cash_cents']+row['cumulative_collected_revenue_cents']-row['cumulative_cost_cents'])
                self.assertGreaterEqual(row['cash_cents'],row['restricted_cash_cents'])
                self.assertEqual(row['annualized_collected_run_rate_cents'],12*row['collected_revenue_cents'])
                self.assertEqual(row['trailing_12_collected_revenue_cents'],sum(x['collected_revenue_cents'] for x in r['monthly'][max(0,index-11):index+1]))
                self.assertLessEqual(row['exposed_unique_opportunities'],c['reachable_market_customers']-c['initial_customers'])

    def test_costed_delayed_channels_and_capacity_execute(self):
        c=self.cfg();r=simulate_scale(c,7)
        self.assertTrue(r['cash_survival'])
        self.assertGreater(r['monthly'][-1]['capacity_jobs'],c['initial_capacity_jobs'])
        self.assertGreater(r['monthly'][-1]['channels_ready'],1)
        self.assertEqual(r['monthly'][0]['channels_ready'],1)
        entries=[a for row in r['monthly'] for a in row['action_traces'] if a.get('channel_entries',0)]
        self.assertTrue(entries)
        for action in entries:
            self.assertGreaterEqual(action['cost'],action['channel_entries']*c['channel_entry_cost_cents'])
            self.assertEqual(action['cash_before']-action['cash_after'],action['cost'])

    def test_adaptive_gain_is_controller_conditional_not_impossibility(self):
        c=self.cfg();r=evaluate_scale(c,[7,8])
        self.assertEqual(set(r['controllers']),set(CONTROLLERS))
        self.assertTrue(any(p['adaptive_minus_fixed_collected_cents']>0 for p in r['paired_comparisons']))
        self.assertIn('not impossibility',r['conclusion'])
        for controller in r['controllers'].values():
            target=controller['milestones'][str(10**18)]
            self.assertEqual(target['not_reached'],2)
            self.assertIsNone(target['unconditional_censored_quantiles_months']['p50'])

    def test_no_demand_cannot_create_free_customers(self):
        c=self.cfg();c.update(initial_customers=0,choice_probability=0.)
        for controller in CONTROLLERS:
            r=simulate_scale(c,9,controller)
            self.assertEqual(r['cumulative_collected_revenue_cents'],0)
            self.assertTrue(all(row['active_customers']==0 for row in r['monthly']))
            self.assertTrue(all(row['activated_future_customers']==0 for row in r['monthly']))

    def test_zero_supplier_or_capacity_respects_actual_limits(self):
        c=self.cfg();c['supplier_capacity_jobs']=0
        r=simulate_scale(c,10)
        self.assertEqual(r['cumulative_collected_revenue_cents'],0)
        self.assertTrue(all(row['attempted_projection_work_products']==0 for row in r['monthly']))

    def test_initial_cash_cannot_be_refilled_by_future_prediction(self):
        c=self.cfg();c.update(opening_cash_cents=1,setup_cost_cents=10_000)
        r=simulate_scale(c,11)
        self.assertFalse(r['cash_survival'])
        self.assertEqual(r['ending_cash_cents'],1)
        self.assertEqual(r['monthly'],[])

    def test_cash_retention_and_nonmarketing_investment_choices(self):
        c=self.cfg()
        state={'active':0,'cash':1_000_000,'restricted':0,'capacity':200,'pending_capacity':[],
            'channels':[],'retention':False,'supplier_diversity':False,'instrument':False,
            'new_services':0,'additional_expected_products':0.,'pipeline':[],
            'price':40_000,'unit_cost':4_000,'estimated_conversion':0.,'exposed':0,'previous_desired':0}
        self.assertEqual(_controller_actions(c,state,'adaptive',1)['kind'],'retain_cash')
        state.update(active=1000,cash=1_000_000_000,capacity=10000)
        chosen=_controller_actions(c,state,'adaptive',1)
        self.assertIn(chosen['kind'],{'retention','instrument','new_service','supplier_diversity'})
        self.assertGreater(chosen['cost'],0)

    def test_prudential_buffer_is_testable_policy_not_liability(self):
        c=self.cfg();a=simulate_scale(c,12)
        c['prudential_buffer_months']=4.
        b=simulate_scale(c,12)
        self.assertNotEqual([row['action_traces'] for row in a['monthly']],[row['action_traces'] for row in b['monthly']])
        self.assertIn('Revisable',a['prudential_buffer_policy']['scope'])

    def test_same_shocks_unchanged_policy_match_independent_replay(self):
        c=self.cfg()
        a=simulate_scale(c,15,'ordinary_adaptive')
        b=simulate_scale(copy.deepcopy(c),15,'ordinary_adaptive')
        self.assertEqual(a,b)
        self.assertIn('keyed monthly',a['matching_scope'])

    def test_invalid_or_unknown_inputs_rejected(self):
        for key,value in [('currency','CAD'),('prudential_buffer_months',float('nan')),('months',True),('targets_annual_collected_cents',[{}]),('collection_probability',1.1)]:
            c=self.cfg();c[key]=value
            with self.assertRaises(ValueError):validate_config(c)
        with self.assertRaises(ValueError):evaluate_scale(self.cfg(),[{}])
        with self.assertRaises(ValueError):simulate_scale(self.cfg(),1,'omniscient')

    def test_arbitrary_revenue_target_and_tax_passthrough(self):
        c=self.cfg();c['targets_annual_collected_cents']=[10**30]
        a=simulate_scale(c,14)
        self.assertIsNone(a['milestones'][str(10**30)])
        c['sales_tax_bps']=2000;b=simulate_scale(c,14)
        self.assertEqual(a['ending_cash_cents'],b['ending_cash_cents'])
        self.assertGreater(sum(x['tax_collected_and_remitted_cents'] for x in b['monthly']),0)

    def test_ordinary_control_has_same_paid_actions_rounds_and_delays(self):
        c=default_config()
        for controller in ('ordinary_adaptive','adaptive'):
            result=simulate_scale(c,1,controller)
            actions=[a for row in result['monthly'] for a in row['action_traces']]
            self.assertTrue({'growth_bundle','instrument','new_service','retention','supplier_diversity'} <= {a['kind'] for a in actions})
            self.assertTrue(any(a.get('channel_entries',0)>0 for a in actions))
            self.assertTrue(any(a.get('capacity_blocks',0)>0 for a in actions))
            self.assertEqual(result['monthly'][0]['channels_ready'],1)
            for row in result['monthly']:
                self.assertLessEqual(row['planning_rounds_used'],c['planning_rounds_per_month'])
                self.assertEqual(row['planning_cost_cents'],row['planning_rounds_used']*c['planner_round_cost_cents'])
                self.assertLessEqual(row['contacts'],row['channels_ready']*c['channel_contacts_per_month'])
