import copy
import tempfile
from pathlib import Path
import unittest
from adaptive_enterprise.instruments import prepare_complete_offer_services, load_jobs
from connected_enterprise.engine import _buyers, _offer_menu, run_world, validate_config
from connected_enterprise.channels import validate_contracts
from connected_enterprise.startup_acquisition048 import options, preflight, reference, validate_option
from connected_enterprise.verify import audit
from scripts.run_commoncost026 import config

ROOT = Path(__file__).resolve().parents[1]


def fixture(manifest, enabled=True, case='positive'):
    cfg = config('smoke', 'central', 'joint')
    cfg['strategic_policy']['ranking_arithmetic'] = 'exact-rational-v1'
    cfg.update(opening=100000000000, horizon_days=8, customer_pool=8, initial_slots=1, maximum_slots=1,
               arrival_bps=10000, retention_bps=10000, nonpayment_bps=0, clearing_hours=1, monetary_policy='exact-integer-v2')
    for scenario in cfg['strategic_policy']['scenarios']:
        scenario.update(accept_prob=1, collect_prob=1)
    cfg['channel_menu_policy'] = {'schema': 'connected-channel-menu/v1', 'contract_ids': ['pilot'], 'conversion_bps': 5000}
    cfg['channels']['pilot'].update(lead_days=1, duration_days=5, activation_reliability_bps=10000, realization_bps=10000, overlap_bps=0)
    services = ['reconciliation']
    profile = {'id': 'fixed-uncertain-request', 'services': services, 'price_grids': {'reconciliation': [20000000]},
               'atoms': [{'weight_bps': 5000, 'budget_microUSD': 200000000, 'values': {'reconciliation': 100000000}},
                         {'weight_bps': 5000, 'budget_microUSD': 5000000, 'values': {'reconciliation': 10000000}}],
               'outside_options': [{'name': 'human', 'provider': 'human', 'service_id': 'reconciliation', 'price': 30000000, 'quality_bps': 10000, 'delay_cost': 0},
                                   {'name': 'autonomous', 'provider': 'rival', 'service_id': 'reconciliation', 'price': 25000000, 'quality_bps': 10000, 'delay_cost': 0},
                                   {'name': 'self_service', 'provider': 'self_service', 'service_id': 'reconciliation', 'price': 15000000, 'quality_bps': 5000, 'delay_cost': 0}]}
    ids = sorted(j['id'] for j in manifest['jobs'] if j['service_id'] == 'reconciliation')
    requests = {f'SIM-customer-{i:03d}': [] if i < 4 else ids[(i-4)::4] for i in range(8)}
    cfg['complete_offer_policy'] = {'schema': 'connected-complete-offer-market/v1', 'selection': 'menu', 'profiles': [profile], 'requested_jobs': requests}
    if enabled:
        cfg['startup_acquisition_policy'] = {'schema': 'connected-startup-acquisition/v1', 'contract_ids': ['pilot'], 'conversion_bps': 5000, 'planning_cost_microUSD': 50000}
        cfg['setup_cost'] += 5000000
    if case == 'no_demand':
        for atom in profile['atoms']:
            atom['values']['reconciliation'] = 0
    elif case == 'overpriced':
        cfg['channels']['pilot']['price_microUSD'] = 1000000000
    elif case == 'default':
        cfg['nonpayment_bps'] = 10000
        for scenario in cfg['strategic_policy']['scenarios']:
            scenario['collect_prob'] = 0
    elif case == 'support':
        cfg['support_cost'] = 100000000
    elif case == 'timing':
        cfg['channels']['pilot']['lead_days'] = 8
    elif case == 'failed_channel':
        cfg['channels']['pilot']['activation_reliability_bps'] = 0
    cfg['channels'] = validate_contracts(cfg['channels'])
    return cfg


class StartupAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='.startup048-', dir=ROOT)
        cls.folder = Path(cls.temporary.name)
        cls.manifest = prepare_complete_offer_services(ROOT, str(cls.folder.relative_to(ROOT) / 'services'), cohort_seed=2611010481, jobs_per_service=32, packet_jobs=1)
        cls.manifest['native_engine'] = 'exact-permanent-v2'
        cls.jobs = load_jobs(ROOT, cls.manifest)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def opts(self, case='positive', available=100000000000, day=0, prior=False):
        cfg = fixture(self.manifest, case=case)
        snapshot = {'state_digest': 'a'*64, 'summary': {'available': available, 'unrestrictedEarned': 0, 'investmentStopped': False}}
        buyers = {b['id']: b for b in _buyers(cfg, 2611010482)}
        return options(cfg, 'competitive_growth', day*24, snapshot, 0, self.jobs, set(), buyers, cfg['strategic_allocation_policy']['risk']['scenarios'], _offer_menu, prior_investments=prior)

    def test_public_complete_offer_can_bootstrap_without_earned_margin(self):
        rows = self.opts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['execution']['funding'], 'SEED_OR_EARNED')
        self.assertTrue(rows[0]['execution']['startup_contract']['qualified_public_offers'])
        self.assertGreater(rows[0]['future_net_cash']['baseline'], rows[0]['upfront_cost'])
        validate_option(rows[0])

    def test_no_demand_overpriced_default_support_timing_and_channel_hold(self):
        for case in ('no_demand', 'overpriced', 'default', 'support', 'timing', 'failed_channel'):
            with self.subTest(case=case):
                self.assertEqual(self.opts(case), [])

    def test_unavailable_cash_and_day_or_prior_commitment_hold(self):
        self.assertEqual(self.opts(available=0), [])
        self.assertEqual(self.opts(day=1), [])
        self.assertEqual(self.opts(prior=True), [])

    def test_seed_receipt_reference_never_fabricates_earned_plan(self):
        receipt = {'funding': 'SEED', 'plan_id': None, 'id': 'contract', 'source_sha256': 'a'*64, 'work_sha256': 'b'*64}
        self.assertTrue(reference(receipt).startswith('startup-seed-'))
        with self.assertRaisesRegex(ValueError, 'CANNOT_CLAIM_EARNED'):
            reference(dict(receipt, plan_id='forged-earned'))

    def test_startup_and_selective_recourse_share_prepaid_prefix_and_resume(self):
        from unittest.mock import patch
        from connected_enterprise import engine
        cfg=fixture(self.manifest);cfg['horizon_days']=4
        cfg['refusal_recourse_policy']={'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':100000,'daily_evaluation_cost':10000}
        target=self.folder/'combined-startup-selective';original=engine._prepare_plan
        def interrupt(*args,**kwargs):
            if kwargs.get('recourse_preflight'):raise RuntimeError('AFTER_STARTUP_AND_RECOURSE_EVALUATION')
            return original(*args,**kwargs)
        with patch.object(engine,'_prepare_plan',interrupt):
            with self.assertRaisesRegex(RuntimeError,'AFTER_STARTUP_AND_RECOURSE_EVALUATION'):
                run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
        result=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertTrue(any(i['funding_receipt']['funding']=='SEED' for i in result['investments']))
        self.assertEqual(sum(c['id']=='startup-acquisition-evaluation' for c in result['costs']),1)
        self.assertEqual(sum(c['category']=='selective_recourse_public_evaluation' for c in result['costs']),4)
        resumed=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
        self.assertEqual(result['owned_account'],resumed['owned_account'])
        self.assertTrue(audit(ROOT,self.manifest,resumed)['accepted'])

    def test_tampered_certificate_cannot_enable_seed_for_general_expansion(self):
        option = self.opts()[0]
        for key, value in (('kind', 'capacity'), ('id', 'ordinary-channel')):
            altered = copy.deepcopy(option); altered[key] = value
            with self.assertRaises(ValueError):
                validate_option(altered)
        altered = copy.deepcopy(option); altered['execution']['contract_id'] = 'free'
        with self.assertRaises(ValueError):
            validate_option(altered)

    def test_explicit_contract_and_conversion_required(self):
        cfg = fixture(self.manifest)
        for field, value in (('conversion_bps', True), ('conversion_bps', 10001), ('planning_cost_microUSD', 0), ('contract_ids', ['undeclared'])):
            bad = copy.deepcopy(cfg); bad['startup_acquisition_policy'][field] = value
            with self.assertRaises(ValueError):
                validate_config(bad)
        del cfg['strategic_policy']['ranking_arithmetic']
        with self.assertRaisesRegex(ValueError, 'STARTUP_EXACT_PUBLIC_QUOTE_RANKING_REQUIRED'):
            validate_config(cfg)

    def test_private_budget_and_future_state_do_not_change_startup_decision(self):
        cfg = fixture(self.manifest)
        snapshot = {'state_digest': 'a'*64, 'summary': {'available': 100000000000, 'unrestrictedEarned': 0, 'investmentStopped': False}}
        buyers = {b['id']: b for b in _buyers(cfg, 2611010482)}
        args = (cfg, 'competitive_growth', 0, snapshot, 0, self.jobs, set())
        first = options(*args, buyers, cfg['strategic_allocation_policy']['risk']['scenarios'], _offer_menu)
        for buyer in buyers.values():
            buyer.update(remaining_budget=0, initial_budget=0, purchases=999)
        second = options(*args, buyers, cfg['strategic_allocation_policy']['risk']['scenarios'], _offer_menu)
        self.assertEqual(first, second)

    def test_mismatched_or_full_owned_audience_refuses_before_valuation(self):
        cfg = fixture(self.manifest)
        buyers = {b['id']: b for b in _buyers(cfg, 2611010482)}
        for count in (0, 6, 48):
            cfg['channels']['pilot']['owned_audience_count'] = count
            self.assertEqual(preflight(cfg, buyers, self.jobs, _offer_menu), [])
        cfg['channels']['pilot']['owned_audience_count'] = 8
        for buyer in buyers.values():
            buyer['known'] = True
        self.assertEqual(preflight(cfg, buyers, self.jobs, _offer_menu), [])

    def test_empty_deliverable_reach_has_no_evaluation_or_invoice(self):
        cfg = fixture(self.manifest)
        cfg['channels']['pilot']['owned_audience_count'] = 48
        result = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', self.folder / 'empty-reach')
        self.assertTrue(audit(ROOT, self.manifest, result)['accepted'])
        self.assertEqual(result['investments'], [])
        self.assertFalse(any(c['id'] == 'startup-acquisition-evaluation' for c in result['costs']))

    def test_crash_after_seed_invoice_replays_once_with_same_account(self):
        cfg = fixture(self.manifest)
        folder = self.folder / 'crash-operating'
        def crash(stage, state, account):
            if state['current']['event']['kind'] == 'plan' and state['current']['event']['time'] == 0:
                raise RuntimeError('INJECTED_AFTER_STARTUP_INVOICE_BEFORE_CHECKPOINT')
        with self.assertRaisesRegex(RuntimeError, 'INJECTED_AFTER_STARTUP'):
            run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', folder, failpoint=crash)
        result = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', folder)
        self.assertTrue(audit(ROOT, self.manifest, result)['accepted'])
        payments = [e for e in result['owned_account']['connected_journal']['entries'] if e['request']['operation'] == 'spend' and e['request']['id'].startswith('startup-channel-')]
        self.assertEqual(len(payments), 1)
        self.assertEqual(len([i for i in result['investments'] if i['id'].startswith('startup-channel-')]), 1)

    def test_native_purchase_audit_and_same_account_resume(self):
        cfg = fixture(self.manifest)
        folder = self.folder / 'positive-operating'
        paused = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', folder, stop_after_events=2)
        self.assertFalse(paused['complete'])
        result = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', folder)
        self.assertTrue(audit(ROOT, self.manifest, result)['accepted'])
        startup = [i for i in result['investments'] if i['id'].startswith('startup-channel-')]
        self.assertEqual(len(startup), 1)
        self.assertEqual(startup[0]['funding_receipt']['funding'], 'SEED')
        self.assertIsNone(startup[0]['funding_receipt']['plan_id'])
        self.assertTrue(any(b['known'] for b in result['buyers'][4:]))
        self.assertTrue(any(o['acquisition_source_plan_id'] == startup[0]['plan_id'] for o in result['orders']))
        resumed = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', folder)
        self.assertEqual(result['summary'], resumed['summary'])
        self.assertEqual(result['owned_account'], resumed['owned_account'])
        altered = copy.deepcopy(result); altered['investments'][0]['funding_receipt']['funding'] = 'EARNED'
        with self.assertRaises(ValueError):
            audit(ROOT, self.manifest, altered)

    def test_realized_default_refunds_are_costed_and_audited(self):
        cfg = fixture(self.manifest)
        cfg['nonpayment_bps'] = 10000
        result = run_world(ROOT, self.manifest, cfg, 2611010482, 'competitive_growth', self.folder / 'realized-default')
        self.assertTrue(audit(ROOT, self.manifest, result)['accepted'])
        self.assertTrue(result['orders'])
        self.assertTrue(all(o['outcome'] == 'REFUNDED' for o in result['orders']))
        self.assertEqual(result['summary']['collections'], 0)
        self.assertLess(result['summary']['profit'], 0)
        self.assertEqual(result['summary']['payables'], 0)


if __name__ == '__main__':
    unittest.main()
