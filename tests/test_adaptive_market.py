import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adaptive_enterprise.model import default_policy,validate_policy,world_specs,run_world,MarketActors,aggregate,stable_projection
from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.learning import validate_public
from commercial.ledger import digest

ROOT=Path(__file__).resolve().parents[1]


class AdaptiveMarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(dir=ROOT,prefix='adaptive-market-test-')
        cls.manifest=prepare_services(ROOT,(Path(cls.temporary.name)/'services').relative_to(ROOT),cohort_seed=12001)
        cls.policy=default_policy();cls.policy['max_cycles']=12
        cls.world=world_specs()[0]
        cls.result=run_world(ROOT,cls.manifest,cls.policy,12001,cls.world)

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_strict_current_policy_and_signed_cost_units(self):
        for key,value in [('currency','CAD'),('max_cycles',0),('opening',True),('upfront_cost_multiplier',float('inf'))]:
            policy=copy.deepcopy(self.policy);policy[key]=value
            with self.assertRaises(ValueError):validate_policy(policy)

    def test_decisions_receive_only_exact_copied_public_observations(self):
        for public in self.result['public_observations']:
            self.assertEqual(validate_public(public),public)
            self.assertFalse(any(key in public for key in ['seed','world','regime','private_value','rival_cost','future_shock']))
            self.assertTrue(all(event['observed_cycle']<=public['cycle'] for event in public['feedback']))
            altered=copy.deepcopy(public);altered['supplier']['private_cost']=0
            with self.assertRaises(ValueError):validate_public(altered)
        self.assertTrue(self.result['learning']['used_feedback_event_ids'])

    def test_no_inventory_or_all_cycle_success_gate(self):
        result=self.result
        self.assertFalse(result['economic_completion_requires_all_cycles'])
        self.assertFalse(result['inventory_completion_required'])
        self.assertLess(len(result['service_records']),len(self.manifest['jobs']))
        self.assertEqual(result['operated_cycles'],12)
        self.assertTrue(result['conditional_simulated_go'])
        self.assertGreaterEqual(result['paid_jobs'],12)
        self.assertGreaterEqual(result['profitable_earned_continuations'],2)

    def test_actual_service_acceptance_and_unique_job_revenue(self):
        rows=self.result['service_records'];ids=[row['job_id'] for row in rows]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(row['service_receipt']['accepted'] for row in rows if row['outcome']=='SETTLED'))
        self.assertTrue(all(row['service_receipt']['model_calls']==0 for row in rows))
        settled=sum(row['price'] for row in rows if row['outcome']=='SETTLED')
        self.assertEqual(settled,self.result['summary']['revenue'])
        self.assertEqual(settled,self.result['summary']['collections'])

    def test_complete_cost_receipts_conserve_native_money(self):
        result=self.result;summary=result['summary']
        self.assertEqual(sum(row['amount'] for row in result['cost_receipts']),summary['expenses'])
        self.assertEqual(summary['profit'],summary['revenue']-summary['expenses'])
        self.assertEqual(summary['cash'],self.policy['opening']+summary['collections']-summary['expensePaid'])
        self.assertGreater(summary['equityProtectionBacking'],0)
        self.assertEqual(summary['payables'],0)
        self.assertTrue(result['cash_survival'])
        self.assertEqual(result['actual_collections'],0)
        self.assertGreater(summary['collections'],0)

    def test_fresh_state_planner_reservation_executes_actual_next_delivery(self):
        funded=[row for row in self.result['service_records'] if row['funding']=='PRIOR_UNRESTRICTED_SIMULATED_EARNINGS']
        self.assertTrue(funded)
        plans={row['plan']['plan_id']:row for row in self.result['allocations']}
        for row in funded:
            plan=plans[row['plan_id']]
            self.assertGreaterEqual(plan['before']['unrestrictedEarned'],plan['plan']['reserve_amount'])
            self.assertEqual(row['job_id'],plan['executed_job_id'])
            self.assertTrue(row['service_receipt']['accepted'])
            self.assertIn('obligation_resolution',plan)
        self.assertTrue(any(row['outcome']=='SETTLED' and row['collected']>row['complete_cost'] for row in funded))

    def test_investment_predictions_not_booked_as_collections(self):
        for row in self.result['allocations']:
            self.assertEqual(row['growth_future_receipts_booked'],0)
            self.assertEqual(row['realized_scoped_net_cash'],row['realized_delivery_collections']-row['actual_spend'])
            self.assertGreater(row['plan']['expected_net'],0)
            resolution=row['obligation_resolution']
            self.assertEqual(resolution['upfront_incurred_microUSD']+resolution['later_incurred_microUSD'],row['actual_spend'])
            self.assertEqual(resolution['unused_reserve_microUSD'],row['plan']['reserve_amount']-row['actual_spend'])

    def test_generated_instrument_has_failed_source_and_fresh_executable_mapping(self):
        receipts=self.result['instrument_receipts']
        if not receipts:self.assertEqual(self.result['verdicts']['invention'],'NOT_EXECUTED_IN_THIS_TRAJECTORY')
        for row in receipts:
            self.assertFalse(row['verified_failure_receipt']['accepted'])
            self.assertEqual(row['generated_plan']['status'],'READY')
            self.assertTrue(row['generated_plan']['mapping'])
            compared=row['matched_methods']['methods']
            self.assertTrue(compared['retained']['accepted'])
            self.assertEqual(compared['retained']['useful_outcome_sha256'],compared['ordinary_reuse']['useful_outcome_sha256'])
        if not any(row['offer']['method']=='generated_schema' and row['outcome']=='SETTLED' for row in self.result['service_records']):
            self.assertFalse(any(row['later_settled_job_ids'] for row in self.result['productive_expansion_evidence'] if row['kind']=='instrument'))

    def test_rival_and_supplier_response_has_delayed_actual_history(self):
        events=self.result['private_actor_event_audit']
        rival=[event for event in events if event['kind']=='RIVAL_DELAYED_HISTORY_RESPONSE']
        supplier=[event for event in events if event['kind']=='SUPPLIER_DELAYED_UTILIZATION_RESPONSE']
        self.assertTrue(rival);self.assertTrue(supplier)
        self.assertTrue(all(event['observed_action_ids'] for event in rival))
        self.assertTrue(all(event['source_cycle']<event['cycle'] for event in supplier))
        self.assertTrue(any(event['new_public_price']!=event['previous_public_price'] for event in rival))

    def test_capacity_investment_respects_controller_and_supplier_actual_limits(self):
        self.assertTrue(all(cycle['remaining_capacity']>=0 for cycle in self.result['cycles']))
        for cycle in self.result['cycles']:
            executed=[r for r in self.result['service_records'] if r['cycle']==cycle['cycle']]
            self.assertLessEqual(len(executed),cycle['public_supplier']['available_capacity_units'])
            self.assertLessEqual(len(executed),self.policy['decision_slots'])
        capacity=[a for a in self.result['allocations'] if 'capacity' in a['selected_growth_kinds']]
        self.assertLessEqual(len(capacity),self.policy['decision_slots']-self.policy['supplier_initial_capacity'])

    def test_pending_payments_are_not_early_defaults(self):
        policy=copy.deepcopy(self.policy);policy['max_cycles']=5
        world=copy.deepcopy(self.world);world['payment_delay_days']=23;world['payment_default_probability']=0;world['feedback_delay_cycles']=2
        result=run_world(ROOT,self.manifest,policy,12002,world)
        self.assertTrue(any(obs['account']['pending_payment_count']>0 for obs in result['public_observations']))
        self.assertFalse(any(row['outcome']=='REFUNDED' for row in result['service_records']))
        self.assertTrue(any(event['outcome']=='PENDING' for event in result['delayed_public_feedback']))
        actions=result['ledger']['actions'];days={e['args']['id']:e['day'] for e in actions if e['op']=='offer'}
        releases=[e for e in actions if e['op']=='event' and e['args']['action']=='release']
        self.assertTrue(releases)
        self.assertTrue(all(e['day']-days[e['args']['id']]>=23 for e in releases))

    def test_zero_order_or_cash_retreat_does_not_count_flywheel(self):
        policy=copy.deepcopy(self.policy);policy['max_cycles']=4
        world=copy.deepcopy(self.world);world['arrival']=0
        result=run_world(ROOT,self.manifest,policy,12003,world)
        self.assertEqual(result['paid_jobs'],0)
        self.assertFalse(result['conditional_simulated_go'])
        self.assertLess(result['summary']['profit'],0)
        self.assertEqual(result['profitable_earned_continuations'],0)
        self.assertTrue(result['cash_survival'])

    def test_account_tape_and_policy_trace_deterministic_on_same_inputs(self):
        repeated=run_world(ROOT,self.manifest,self.policy,12001,self.world)
        self.assertEqual(stable_projection(repeated),stable_projection(self.result))

    def test_buyer_pending_commitments_and_outside_purchases_conserve_budget(self):
        actors=MarketActors(self.policy,self.world,12007);buyer=actors.buyers[0]
        buyer.update(initial_budget=100_000_000,budget=100_000_000,value_factor=10,urgency=0,trust=1.)
        offer={'service_id':'reconciliation','human_anchor_microUSD':100_000_000,'scope':'complete_outcome','capacity_units':1,'method':'canonical'}
        actors.rival_remaining_capacity=0
        participates,_=actors.choose(buyer['id'],offer,70_000_000,0,'first',1)
        self.assertTrue(participates)
        actors.commit_buyer(buyer['id'],'order-first',70_000_000)
        participates,_=actors.choose(buyer['id'],offer,70_000_000,0,'second',1)
        self.assertFalse(participates)
        self.assertEqual(sum(buyer['commitments'].values()),70_000_000)
        actors.delivered(buyer['id'],settled=False,price=70_000_000,cycle=1,order_id='order-first')
        self.assertEqual(buyer['budget'],100_000_000)
        actors.commit_buyer(buyer['id'],'order-retry',70_000_000)
        actors.delivered(buyer['id'],settled=True,price=70_000_000,cycle=2,order_id='order-retry')
        self.assertEqual(buyer['budget'],30_000_000)
        self.assertEqual(buyer['our_settled_spend'],70_000_000)
        actors.assert_buyer_budgets()
        another=actors.buyers[1];before=another['budget'];actors.rival_remaining_capacity=2;actors.rival_prices['reconciliation']=1_000_000;another.update(value_factor=10,urgency=0)
        actors.choose(another['id'],offer,900_000_000,0,'outside',1)
        self.assertLess(another['budget'],before)
        self.assertGreater(another['outside_spend'],0)
        actors.assert_buyer_budgets()

    def test_grower_rejects_private_environment_and_ablations_are_exact(self):
        from adaptive_enterprise.model import validate_growth_snapshot
        for allocation in self.result['allocations']:
            public=allocation['public_growth_snapshot'];self.assertEqual(validate_growth_snapshot(public),public)
            with self.assertRaises(ValueError):validate_growth_snapshot(dict(public,private_rival_cost=0))
        policy=copy.deepcopy(self.policy);policy['max_cycles']=6
        result=run_world(ROOT,self.manifest,policy,12008,self.world,arm='no_capital_adaptation')
        self.assertFalse(any(row['selected_growth_kinds'] for row in result['allocations']))
        self.assertFalse(result['instrument_receipts'])

    def test_joint_bundle_consumes_components_and_invokes_retained_joint_pricing(self):
        from enterprise.pricing import optimize_bundle
        from adaptive_enterprise.model import _offers
        from adaptive_enterprise.instruments import load_jobs,execute_offer
        loaded=load_jobs(ROOT,self.manifest);assets={'instrument':True}
        supplier={'quoted_unit_cost_microUSD':250_000,'available_capacity_units':3,'announced_latency_hours':2}
        with patch('enterprise.pricing.optimize_bundle',wraps=optimize_bundle) as joint:
            core,public=_offers(self.policy,loaded,set(),assets,'full_adaptive',[],supplier)
        self.assertGreater(joint.call_count,0)
        offer=next(row for row in core.values() if row['service_id']=='operations_bundle')
        job=loaded[offer['applicable_job_ids'][0]]['job'];receipt=execute_offer(ROOT,self.manifest,offer,job['id'])
        self.assertTrue(receipt['accepted'])
        self.assertEqual(len(job['work_keys']),3)
        self.assertEqual(assets['joint_price_receipts'][offer['id']]['call_path'],'enterprise.pricing.optimize_bundle')
        consumed=[]
        for row in self.result['service_records']:
            self.assertFalse(set(row['work_keys'])&set(consumed));consumed.extend(row['work_keys'])
        _,after=_offers(self.policy,loaded,set(job['work_keys']),assets,'full_adaptive',[],supplier)
        self.assertFalse(any(job['id'] in row['applicable_job_ids'] for row in after))

    def test_controls_share_world_information_but_change_policy(self):
        policy=copy.deepcopy(self.policy);policy['max_cycles']=4
        fixed=run_world(ROOT,self.manifest,policy,12004,self.world,arm='strong_fixed')
        self.assertEqual(fixed['evaluator_world'],self.world)
        self.assertEqual(fixed['seed'],12004)
        self.assertEqual(fixed['arm'],'strong_fixed')
        self.assertFalse(any(d['experiment'] for d in fixed['decisions']))
        result=aggregate([self.result,fixed])
        self.assertEqual(result['runs'],2)
        self.assertIn('downside_cvar20',result)
