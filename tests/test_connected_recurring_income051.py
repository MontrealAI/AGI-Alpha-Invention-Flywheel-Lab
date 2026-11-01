"""Current-source recurring commerce, with no enterprise cash from buyer income."""
import copy
from pathlib import Path
import tempfile
import unittest

from connected_enterprise.buyer_income import SCHEMA, EVIDENCE, validate_policy, public_accrued, public_context, audit_income
from connected_enterprise.engine import default_config, fresh_account_config, validate_config, run_world, _initial
from connected_enterprise.verify import audit
from connected_enterprise.runner import identity
from adaptive_enterprise.instruments import prepare_complete_offer_services

ROOT = Path(__file__).resolve().parents[1]
M = 1_000_000


def income(**changes):
    p = {'schema': SCHEMA, 'first_day': 3, 'period_days': 4, 'income_microUSD': 50*M, 'receipt_bps': 10000}
    p.update(changes)
    return p


def configuration(manifest, *, days=12, funded=True, demand=True):
    from portfolio25.pricing import SCENARIOS
    cfg, manifest = fresh_account_config(manifest, root=ROOT)
    cfg.update(horizon_days=days, customer_pool=4, opening=100000*M,
        initial_slots=3, maximum_slots=3, arrival_bps=10000, retention_bps=10000,
        nonpayment_bps=0, clearing_hours=24)
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
    values={s:(100*M if s=='receivables_packet' else 40*M) if demand else 0 for s in services}
    profile={'id':'recurring-test','services':services,
        'price_grids':{s:[50*M] if s=='receivables_packet' else [20*M,25*M] for s in services},
        'atoms':[{'weight_bps':10000,'budget_microUSD':50*M,'values':values}],
        'outside_options':[{'name':'outside-complete','provider':'rival','service_id':'receivables_packet','price':65*M,'quality_bps':10000,'delay_cost':0}]}
    groups={}
    for j in manifest['jobs']:groups.setdefault(j['service_id'],[]).append(j['id'])
    requested={f'SIM-customer-{i:03d}':[] for i in range(4)}
    for ids in groups.values():
        for i,j in enumerate(sorted(ids)):requested[f'SIM-customer-{i%4:03d}'].append(j)
    cfg['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':'menu','profiles':[profile],'requested_jobs':requested}
    scenarios=copy.deepcopy(list(SCENARIOS))
    for s in scenarios:s.update(repeat_horizon=0,cost_shock=1)
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1','public_basis':'Authored recurring-income integration fixture; not observed demand.',
        'price_bps':[5500,7000,9000,10000],'rival_price_bps':[5500,7000,9000,10000],
        'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
        'connected_beliefs':{s['id']:{'min_value_bps':7000,'max_value_bps':21000,'min_budget_microUSD':0,'max_budget_microUSD':600*M,'rival_available_bps':8000} for s in scenarios}}
    cfg['strategic_allocation_policy']={'max_customers':4,'risk':{
        'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
        'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,
        'authorized_allocation':cfg['opening'],'interactions':[]}}
    if funded:cfg['buyer_income_policy']=income()
    return validate_config(cfg),manifest


class IncomeContractTests(unittest.TestCase):
    def test_default_unchanged(self):
        self.assertNotIn('buyer_income_policy',default_config())
        self.assertEqual(default_config(),validate_config(default_config()))
    def test_invalid_contracts_reject(self):
        for change in ({'income_microUSD':0},{'income_microUSD':True},{'period_days':0},{'first_day':12},{'receipt_bps':True},{'receipt_bps':10001},{'schema':'wrong'}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_policy(income(**change),12)
    def test_only_accrued_not_future_or_drain_income(self):
        cfg={'horizon_days':12,'buyer_income_policy':income()}
        for hour,amount in [(0,0),(71,0),(72,50*M),(167,50*M),(168,100*M),(264,150*M),(999999,150*M)]:
            self.assertEqual(public_accrued(cfg,hour),amount)
    def test_invalid_observation_clock(self):
        for t in (True,-1,0.5,'1'):
            with self.assertRaises(ValueError):public_accrued({},t)
    def test_stochastic_income_not_exposed_as_known_cash(self):
        cfg={'horizon_days':12,'buyer_income_policy':income(receipt_bps=5000)}
        with self.assertRaisesRegex(ValueError,'POSTERIOR_UNAVAILABLE'):public_accrued(cfg,168)
    def test_zero_receipts_add_zero_budget(self):
        self.assertEqual(public_accrued({'horizon_days':12,'buyer_income_policy':income(receipt_bps=0)},168),0)
    def test_income_precedes_same_time_plan(self):
        cfg=default_config();cfg.update(horizon_days=12,buyer_income_policy=income())
        state=_initial(cfg,51,'baseline',{'sha256':'fixture'})
        self.assertEqual([e['kind'] for e in state['queue'] if e['time']==72],['buyer_income','plan'])
        self.assertTrue(all(b['external_income_total']==0 for b in state['buyers']))
    def test_unregistered_balance_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):
            audit_income({'config':{},'seed':1,'buyers':[{'external_income_total':0}],'events':[]})


class NativeRecurringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='.recurring051-',dir=ROOT)
        cls.folder=Path(cls.temp.name)
        cls.manifest=prepare_complete_offer_services(ROOT,str(cls.folder.relative_to(ROOT)/'inputs'),cohort_seed=261101051,jobs_per_service=32,packet_jobs=16,packet_rows=8)
        cls.cfg,cls.manifest=configuration(cls.manifest)
        cls.source=identity(ROOT)
        cls.paused=run_world(ROOT,cls.manifest,cls.cfg,261101051,'competitive_growth',cls.folder/'live',source=cls.source,stop_after_events=7)
        cls.result=run_world(ROOT,cls.manifest,cls.cfg,261101051,'competitive_growth',cls.folder/'live',source=cls.source)
        cls.checked=audit(ROOT,cls.manifest,cls.result)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_real_delivery_audit_and_recurrence(self):
        self.assertTrue(self.checked['accepted']);self.assertFalse(self.paused['complete']);self.assertTrue(self.result['complete'])
        self.assertGreater(self.result['paid_jobs'],4)
        self.assertGreater(self.result['summary']['collections'],200*M)
        self.assertEqual(self.result['config']['opening'],100000*M)
    def test_income_never_credits_native_enterprise(self):
        self.assertEqual(self.checked['external_buyer_income_microUSD_recomputed'],600*M)
        self.assertEqual(self.result['summary']['collections'],sum(o['price'] for o in self.result['orders'] if o['outcome']=='SETTLED'))
        self.assertFalse(self.checked['income_is_enterprise_collection'])
    def test_completed_resume_idempotent(self):
        again=run_world(ROOT,self.manifest,self.cfg,261101051,'competitive_growth',self.folder/'live',source=self.source)
        self.assertEqual(again['buyers'],self.result['buyers']);self.assertEqual(again['summary'],self.result['summary'])
        self.assertEqual(again['owned_account']['ledger'],self.result['owned_account']['ledger'])
    def test_changed_schedule_cannot_resume(self):
        cfg=copy.deepcopy(self.cfg);cfg['buyer_income_policy']['income_microUSD']+=1
        with self.assertRaises(ValueError):run_world(ROOT,self.manifest,cfg,261101051,'competitive_growth',self.folder/'live',source=self.source)
    def test_income_mutations_rejected(self):
        for kind in ('missing','amount','time','total','role','boolean'):
            r=copy.deepcopy(self.result);i=next(i for i,e in enumerate(r['events']) if e['kind']=='EXTERNAL_BUYER_INCOME')
            if kind=='missing':r['events'].pop(i)
            elif kind=='total':r['buyers'][0]['external_income_total']+=1
            elif kind=='boolean':r['buyers'][0]['external_income_total']=True
            else:r['events'][i][{'amount':'amount_microUSD','time':'time','role':'evidence_role'}[kind]]=0
            with self.subTest(kind=kind),self.assertRaises(ValueError):audit_income(r)
    def test_receipt_cannot_follow_same_day_decision(self):
        r=copy.deepcopy(self.result)
        e=r['events'].pop(max(i for i,e in enumerate(r['events']) if e['kind']=='EXTERNAL_BUYER_INCOME' and e['time']==72))
        i=next(i for i,e in enumerate(r['events']) if e['kind']=='BUSINESS_DECISION' and e['time']==72)
        r['events'].insert(i+1,e)
        with self.assertRaisesRegex(ValueError,'AFTER_SAME_DAY'):audit_income(r)
    def test_forecast_cannot_spend_future_month(self):
        r=copy.deepcopy(self.result)
        w=next(w for w in r['joint_actions'].values() if w['time']==0)
        w['allocation']['deliveries'][0]['selection']['problem']['market_context']['profile']['atoms'][0]['budget_microUSD']+=50*M
        with self.assertRaises(ValueError):audit(ROOT,self.manifest,r)
    def test_complete_context_does_not_mutate_input(self):
        ctx=next(d['market_context'] for d in self.result['decisions'] if d['kind']=='offer' and d['time']==0)
        before=copy.deepcopy(ctx);after=public_context(ctx,self.cfg,72)
        self.assertEqual(ctx,before);self.assertEqual(after['profile']['atoms'][0]['budget_microUSD'],100*M)
        self.assertEqual(set(after),{'profile','observed_spend','rival_available'})
    def test_no_demand_stays_no_commerce(self):
        cfg,m=configuration(self.manifest,days=4,demand=False)
        r=run_world(ROOT,m,cfg,261101052,'competitive_growth',self.folder/'no-demand',source=self.source)
        self.assertTrue(audit(ROOT,m,r)['accepted']);self.assertEqual(r['paid_jobs'],0)
        self.assertEqual(r['summary']['collections'],0);self.assertLess(r['summary']['profit'],0)
        self.assertGreater(sum(b['external_income_total'] for b in r['buyers']),0)
    def test_stochastic_complete_market_fails_before_account(self):
        cfg=copy.deepcopy(self.cfg);cfg['buyer_income_policy']['receipt_bps']=5000
        with self.assertRaisesRegex(ValueError,'POSTERIOR_UNAVAILABLE'):validate_config(cfg)


class PublicBudgetGateTests(unittest.TestCase):
    def setUp(self):
        self.cfg={'horizon_days':36,'buyer_income_policy':income(first_day=30,period_days=30),
            'public_budget_gate':{'schema':'connected-public-budget-gate051/v1','daily_cost_microUSD':10000}}
        self.profile={'atoms':[{'budget_microUSD':20*M},{'budget_microUSD':50*M}], 'price_grids':{'p':[50*M]}}
    def test_conservative_upper_support_and_exact_boundary(self):
        from connected_enterprise.public_budget_gate051 import admits
        self.assertTrue(admits(self.profile,'p',0,self.cfg,0))
        self.assertFalse(admits(self.profile,'p',1,self.cfg,0))
    def test_wait_then_reenter_only_after_income_is_due(self):
        from connected_enterprise.public_budget_gate051 import admits
        self.assertFalse(admits(self.profile,'p',50*M,self.cfg,719))
        self.assertTrue(admits(self.profile,'p',50*M,self.cfg,720))
    def test_no_private_budget_or_false_free_gate(self):
        from connected_enterprise.public_budget_gate051 import validate
        cfg=default_config();cfg['public_budget_gate']={'schema':'connected-public-budget-gate051/v1','daily_cost_microUSD':0}
        with self.assertRaisesRegex(ValueError,'POSITIVE_COSTED'):validate(cfg)
    def test_disable_is_exact_no_filter(self):
        from connected_enterprise.public_budget_gate051 import admits
        self.assertTrue(admits(self.profile,'p',999999999,{},0))


class NativeBudgetGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='.budget051-',dir=ROOT);cls.folder=Path(cls.temp.name)
        manifest=prepare_complete_offer_services(ROOT,str(cls.folder.relative_to(ROOT)/'jobs'),cohort_seed=261101054,jobs_per_service=32,packet_jobs=16,packet_rows=8)
        cls.cfg,cls.manifest=configuration(manifest,days=36)
        cls.cfg['buyer_income_policy']=income(first_day=30,period_days=30)
        cls.gated=copy.deepcopy(cls.cfg);cls.gated['public_budget_gate']={'schema':'connected-public-budget-gate051/v1','daily_cost_microUSD':10000}
        cls.source=identity(ROOT)
        cls.control=run_world(ROOT,cls.manifest,cls.cfg,261101054,'competitive_growth',cls.folder/'control',source=cls.source)
        cls.candidate=run_world(ROOT,cls.manifest,cls.gated,261101054,'competitive_growth',cls.folder/'candidate',source=cls.source)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_both_complete_native_audits_pass(self):
        self.assertTrue(audit(ROOT,self.manifest,self.control)['accepted'])
        self.assertTrue(audit(ROOT,self.manifest,self.candidate)['accepted'])
    def test_same_accepted_work_and_collections_not_fabricated_demand(self):
        project=lambda r:[(o['job_id'],o['customer_id'],o['price'],o['collection_time'],o['outcome']) for o in r['orders']]
        self.assertEqual(project(self.control),project(self.candidate))
        self.assertEqual(self.control['summary']['collections'],self.candidate['summary']['collections'])
    def test_gate_fee_charged_every_day_including_wait_days(self):
        costs=[c for c in self.candidate['costs'] if c['category']=='public_affordability_preflight']
        self.assertEqual(len(costs),36);self.assertEqual(sum(c['amount'] for c in costs),360000)
    def test_saved_qualification_is_separate_from_fee(self):
        qualifications=lambda r:sum(c['amount'] for c in r['costs'] if c['category']=='qualification_including_lost_offers')
        self.assertLess(qualifications(self.candidate),qualifications(self.control))
    def test_forged_fee_or_future_budget_rejected(self):
        r=copy.deepcopy(self.candidate);next(c for c in r['costs'] if c['category']=='public_affordability_preflight')['amount']=0
        with self.assertRaises(ValueError):audit(ROOT,self.manifest,r)


class IncomeBoundaryTests(unittest.TestCase):
    def test_old_fixed_market_bound_does_not_misstate_replenishing_market(self):
        from connected_enterprise.billion036 import registered_design, preflight
        spec=registered_design()
        spec['configs']['central']['buyer_income_policy']=income(first_day=30,period_days=30)
        with self.assertRaisesRegex(ValueError,'FIXED_BUYER_BOUND_UNAVAILABLE'):preflight(spec)
    def test_original_fixed_market_diagnostic_is_still_available(self):
        from connected_enterprise.billion036 import registered_design, preflight
        result=preflight(registered_design())
        self.assertTrue(all(c['finite_buyer_budget_barrier'] for c in result['cases']))
    def test_source_helpers_cannot_be_omitted_from_income_world(self):
        import inspect
        from connected_enterprise.verify import audit
        from commercial.ledger import digest
        source=inspect.getsource(audit)
        self.assertIn("required.add('connected_enterprise/buyer_income.py')",source)
        self.assertIn("required.add('connected_enterprise/public_budget_gate051.py')",source)
    def test_unsupported_startup_and_sequence_are_explicit(self):
        from connected_enterprise.public_budget_gate051 import validate
        cfg={'public_budget_gate':{'schema':'connected-public-budget-gate051/v1','daily_cost_microUSD':1},'complete_offer_policy':{},'strategic_policy':{}}
        for extra in ({'startup_acquisition_policy':{}},{'strategic_allocation_policy':{'sequence':{}}}):
            with self.assertRaisesRegex(ValueError,'COMPOSITION_UNAVAILABLE'):validate(cfg|extra)



class RecurringRegistrationTests(unittest.TestCase):
    def test_wrong_inventory_geometry_rejected_before_operating(self):
        from connected_enterprise.recurring_business051 import validate_inventory
        with self.assertRaisesRegex(ValueError,'GEOMETRY'):validate_inventory(ROOT,{'native_engine':'exact-permanent-v2'})
    def test_matching_geometry_does_not_certify_wrong_seed(self):
        from connected_enterprise.recurring_business051 import validate_inventory, PROTOCOL
        g={'primitive_jobs_per_service':32,'packet_jobs':64,'packet_rows_per_kind':8,'chunk_size':64}
        m={'native_engine':'exact-permanent-v2','cohort_provenance':{'finite_admission':g,'cohort_seed_sha256':'0'*64}}
        with self.assertRaisesRegex(ValueError,'COHORT_SEED'):validate_inventory(ROOT,m)
    def test_boolean_receipt_is_not_one_microdollar(self):
        p=income(first_day=1,period_days=1,income_microUSD=1)
        r={'config':{'horizon_days':2,'buyer_income_policy':p},'seed':1,'buyers':[{'id':'SIM-customer-000','external_income_total':1}],
            'events':[{'id':'external-income-000001-SIM-customer-000','time':24,'kind':'EXTERNAL_BUYER_INCOME','customer_id':'SIM-customer-000','amount_microUSD':True,'evidence_role':EVIDENCE}]}
        with self.assertRaisesRegex(ValueError,'TYPED_EXTERNAL'):audit_income(r)

if __name__=='__main__':unittest.main()
