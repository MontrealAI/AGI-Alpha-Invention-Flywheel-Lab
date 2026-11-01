import copy
import tempfile
from pathlib import Path
import unittest
from adaptive_enterprise.instruments import prepare_complete_offer_services, load_jobs
from connected_enterprise.engine import _buyers, _offer_menu, run_world, validate_config
from connected_enterprise.channels import validate_contracts
from connected_enterprise import joint_planning # Keep native aliases outside startup-only valuation mocks.
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


def owned_operating_fixture(manifest, wide=False):
    """Fixed public cost counterexamples, not a demand or discovery result."""
    cfg = fixture(manifest)
    cfg.update(customer_pool=5, horizon_days=6, exposure_cost=200000)
    cfg['strategic_allocation_policy']['max_customers'] = 5
    cfg['startup_acquisition_policy']['conversion_bps'] = 10000
    cfg['channels']['pilot'].update(price_microUSD=1, support_microUSD=0)
    profile = cfg['complete_offer_policy']['profiles'][0]
    profile['outside_options'] = []
    cfg['complete_offer_policy']['requested_jobs'] = {f'SIM-customer-{i:03d}':
        [] if i < 4 else [j['id'] for j in manifest['jobs'] if j['service_id'] == 'reconciliation'] for i in range(5)}
    if wide:
        # Public profile hashing assigns narrow to 002/003/004 and wide to
        # 000/001. No private atom, future response or seed search selects this.
        services = ['reconciliation', 'kpi_variance', 'evidence_matrix', 'receivables_packet']
        profile['id'] = 'fixed-narrow-prospect'
        wide_profile = {'id': 'fixed-wide-owned', 'services': services,
            'price_grids': {s: [20000000] for s in services},
            'atoms': [{'weight_bps': 10000, 'budget_microUSD': 200000000, 'values': dict.fromkeys(services, 0)}],
            'outside_options': []}
        cfg['complete_offer_policy']['profiles'] = [profile, wide_profile]
        for i in (0, 1):
            cfg['complete_offer_policy']['requested_jobs'][f'SIM-customer-{i:03d}'] = [
                sorted(j['id'] for j in manifest['jobs'] if j['service_id']==service and j['accepted'])[i if service!='receivables_packet' else 0] for service in services]
        cfg['complete_offer_policy']['requested_jobs']['SIM-customer-004'] = sorted(
            j['id'] for j in manifest['jobs'] if j['service_id']=='reconciliation' and j['accepted'])[2:]
        cfg.update(exposure_cost=0, qualification_cost=200000, maintenance_daily=1)
    return cfg


def priority_fixture(manifest, jobs, maximum=4):
    """Critic's fixed public admission counterexample; no economic seed search."""
    cfg=fixture(manifest)
    cfg.update(customer_pool=5,horizon_days=4,arrival_bps=10000,exposure_cost=1,qualification_cost=1,
        maintenance_daily=1,production_cost=1,supplier_unit_cost=1,support_cost=1,onboarding_cost=1,
        payment_bps=0,payment_fixed=1,profit_tax_bps=0)
    cfg['strategic_allocation_policy']['max_customers']=maximum
    cfg['mechanism_policy']['cost_contract']['production_envelope_microUSD']=1
    cfg['startup_acquisition_policy'].update(conversion_bps=10000,planning_cost_microUSD=1)
    cfg['channels']['pilot'].update(price_microUSD=100,support_microUSD=0)
    base=cfg['complete_offer_policy']['profiles'][0]
    profiles=[]
    for i in range(16):
        profile=copy.deepcopy(base);profile['id']='fixed-priority-profile-'+str(i);profile['outside_options']=[]
        profile['atoms']=[{'weight_bps':10000,'budget_microUSD':200000000,'values':{'reconciliation':100000000 if i==8 else 0}}]
        profiles.append(profile)
    cfg['complete_offer_policy']['profiles']=profiles
    ids=sorted(ident for ident,entry in jobs.items() if entry['job']['service_id']=='reconciliation'
        and entry['job']['accepted'] and entry['artifact'].get('outcome_scope')=='complete_outcome')
    cfg['complete_offer_policy']['requested_jobs']={f'SIM-customer-{i:03d}':[ids[i]] for i in range(5)}
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

    def test_full_multiservice_qualification_cost_changes_buy_to_hold(self):
        from fractions import Fraction
        cfg=fixture(self.manifest)
        profile=cfg['complete_offer_policy']['profiles'][0]
        services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
        profile['services']=services
        profile['price_grids']={service:[20000000] for service in services}
        for atom in profile['atoms']:
            atom['values']={service:atom['values']['reconciliation'] for service in services}
        for i in range(4,8):
            cfg['complete_offer_policy']['requested_jobs'][f'SIM-customer-{i:03d}']=[
                job['id'] for service in services for n,job in enumerate(j for j in self.manifest['jobs'] if j['service_id']==service) if n%4==i-4]
        cfg['channels']['pilot'].update(price_microUSD=1,support_microUSD=0)
        cfg['qualification_cost']=0
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        witness=options(*args())[0]['execution']['startup_contract']
        cfg['qualification_cost']=100000
        margin=min(Fraction(p['conservative_net_fraction']) for p in witness['qualified_public_offers'])
        prospects=Fraction(witness['prospect_fraction']);contacts=Fraction(witness['contact_fraction'])
        envelope=witness['future_cost_envelope']
        days=min(cfg['channels']['pilot']['duration_days'],cfg['horizon_days']-cfg['channels']['pilot']['lead_days'])
        single_menu_count=days*min(4,cfg['strategic_allocation_policy']['max_customers'])
        self.assertEqual(envelope['qualification_evaluations'],single_menu_count*4)
        old_benefit=prospects*margin-envelope['outreach_microUSD']-envelope['maintenance_microUSD']-single_menu_count*cfg['qualification_cost']
        invoice=old_benefit.numerator//old_benefit.denominator-1
        self.assertGreater(invoice,0)
        cfg['channels']['pilot']['price_microUSD']=invoice
        self.assertGreater(old_benefit-invoice,0)
        original_benefit=prospects*margin-envelope['attempt_slots']*cfg['exposure_cost']-contacts*cfg['qualification_cost']
        self.assertGreater(original_benefit-invoice,0)
        self.assertEqual(envelope['maximum_menu_size'],4)
        self.assertEqual(options(*args()),[])

    def test_future_operating_cash_is_locked_without_projected_receipts(self):
        cfg=fixture(self.manifest)
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        option=options(*args())[0];certificate=option['execution']['startup_contract']
        current=max(p['current_cash_lock'] for p in certificate['qualified_public_offers'])*cfg['initial_slots']
        self.assertGreater(certificate['future_operating_cash_lock'],0)
        self.assertEqual(option['execution']['cash_lock'],current+certificate['future_operating_cash_lock'])
        snapshot['summary']['available']=option['upfront_cost']+current
        self.assertEqual(options(*args()),[])

    def test_owned_empty_requests_change_outreach_value_and_current_cash_to_hold(self):
        from fractions import Fraction
        cfg=owned_operating_fixture(self.manifest);cfg['exposure_cost']=0
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        certificate=options(*args())[0]['execution']['startup_contract'];envelope=certificate['future_cost_envelope']
        self.assertEqual(envelope['future_planning_days'],5)
        self.assertEqual(envelope['continuing_owned_outreach_units'],20)
        self.assertEqual(envelope['continuing_prospect_outreach_units'],5)
        self.assertEqual(envelope['attempt_slots'],10)
        self.assertEqual(envelope['qualification_evaluations'],5)
        self.assertEqual(envelope['maintenance_days'],5)
        gross=Fraction(certificate['prospect_fraction'])*min(Fraction(p['conservative_net_fraction']) for p in certificate['qualified_public_offers'])
        cfg['exposure_cost']=200000
        old_outreach=(10+5)*cfg['exposure_cost']
        old_maintenance=6*cfg['maintenance_daily']
        old_net=gross-old_outreach-envelope['qualification_microUSD']-old_maintenance-1
        self.assertGreater(old_net,0,'The omitted owned fee must be decisive, not a losing old case')
        self.assertLess(gross-35*cfg['exposure_cost']-envelope['qualification_microUSD']-envelope['maintenance_microUSD']-1,0)
        self.assertEqual(options(*args()),[])
        cfg['exposure_cost']=50000
        option=options(*args())[0];certificate=option['execution']['startup_contract'];envelope=certificate['future_cost_envelope']
        current=max(p['current_cash_lock'] for p in certificate['qualified_public_offers'])*cfg['initial_slots']
        old_operating=15*cfg['exposure_cost']+envelope['qualification_microUSD']+old_maintenance
        snapshot['summary']['available']=option['upfront_cost']+current+old_operating
        self.assertLess(snapshot['summary']['available'],option['upfront_cost']+option['execution']['cash_lock'])
        self.assertEqual(options(*args()),[])
        snapshot['summary']['profit']=10**18
        self.assertEqual(options(*args()),[],'Forecast or accounting profit cannot fund owned operating bills')

    def test_wider_owned_menus_change_future_qualification_buy_to_hold(self):
        from fractions import Fraction
        from connected_enterprise.complete_offer_market import compile_market
        cfg=owned_operating_fixture(self.manifest,wide=True);fee=cfg['qualification_cost'];cfg['qualification_cost']=0
        market=compile_market(cfg['complete_offer_policy'])
        self.assertEqual(market.profile('SIM-customer-004')['services'],['reconciliation'])
        self.assertEqual(len(market.profile('SIM-customer-000')['services']),4)
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        certificate=options(*args())[0]['execution']['startup_contract'];envelope=certificate['future_cost_envelope']
        self.assertEqual(envelope['maximum_menu_size'],4)
        self.assertEqual(envelope['daily_qualification_bound'],9)
        self.assertEqual(envelope['qualification_evaluations'],45)
        gross=Fraction(certificate['prospect_fraction'])*min(Fraction(p['conservative_net_fraction']) for p in certificate['qualified_public_offers'])
        old_evaluations=5 # One newly reachable narrow-menu buyer on each live day.
        self.assertGreater(gross-old_evaluations*fee-envelope['maintenance_microUSD']-1,0)
        self.assertLess(gross-envelope['qualification_evaluations']*fee-envelope['maintenance_microUSD']-1,0)
        cfg['qualification_cost']=fee
        self.assertEqual(options(*args()),[])

    def test_native_owned_operating_cost_windows_hold_and_resume_without_invoice(self):
        import json
        for wide in (False,True):
            with self.subTest(wide_owned_menu=wide):
                cfg=owned_operating_fixture(self.manifest,wide=wide)
                target=self.folder/('owned-operating-hold-'+str(wide))
                paused=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target,stop_after_events=2)
                prefix=copy.deepcopy(paused['owned_account']['ledger']['actions'])
                result=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
                self.assertTrue(audit(ROOT,self.manifest,json.loads(json.dumps(result,sort_keys=True)))['accepted'])
                self.assertEqual(result['investments'],[]);self.assertEqual(result['orders'],[])
                self.assertEqual(result['owned_account']['ledger']['actions'][:len(prefix)],prefix)
                self.assertEqual(sum(c['id']=='startup-acquisition-evaluation' for c in result['costs']),1)
                self.assertEqual(result['summary']['expenses'],sum(c['amount'] for c in result['costs']))
                future=[w for w in result['joint_actions'].values() if 24<=w['time']<6*24]
                self.assertEqual(len(future),5)
                for wrapper in future:
                    self.assertTrue({f'SIM-customer-{i:03d}' for i in range(4)}<=set(wrapper['candidate_ids']))
                if wide:
                    evaluations=sum(len(w['allocation']['deliveries']) for w in future)
                    self.assertEqual(evaluations,35) # A shared packet is evaluated once per native shortlist.
                    actual=sum(c['amount'] for c in result['costs'] if c['id'] in {f'qualification-{d}' for d in range(1,6)})
                    self.assertEqual(actual,evaluations*cfg['qualification_cost'])
                    self.assertGreater(actual,5*cfg['qualification_cost'])
                    self.assertLessEqual(evaluations,45)
                else:
                    actual=sum(c['amount'] for c in result['costs'] if c['id'] in {f'outreach-{d}' for d in range(1,6)})
                    self.assertEqual(actual,20*cfg['exposure_cost'])
                    self.assertGreater(actual,15*cfg['exposure_cost'],'Owned activity alone exceeds the old complete outreach budget')
                    self.assertLessEqual(actual,35*cfg['exposure_cost'])
                again=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
                self.assertEqual(again['owned_account'],result['owned_account'])

    def test_initial_priority_frontier_matches_actual_planner_and_five_place_control(self):
        from unittest.mock import patch
        from connected_enterprise.engine import _initial,_prepare_plan
        from connected_enterprise.channels import ChannelBook
        from connected_enterprise.complete_offer_market import compile_market
        cfg=priority_fixture(self.manifest,self.jobs)
        buyers={b['id']:b for b in _buyers(cfg,2611010521)}
        market=compile_market(cfg['complete_offer_policy'])
        self.assertTrue(all(market.profile(f'SIM-customer-{i:03d}')['atoms'][0]['values']['reconciliation']==0 for i in range(4)))
        self.assertGreater(market.profile('SIM-customer-004')['atoms'][0]['values']['reconciliation'],0)
        snapshot={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        with patch('connected_enterprise.strategic_commerce.select',side_effect=AssertionError('UNADMITTED_STARTUP_VALUATION')):
            self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),[])
            self.assertEqual(options(*args()),[])
        # This is a bounded pure planner control with hypothetical paid access,
        # not a native payment, production receipt or economic experiment.
        def prepared():
            state=_initial(cfg,2611010521,'competitive_growth',{})
            book=ChannelBook(2611010521,cfg['channels']);book.expose(0,state['buyers'])
            book.purchase('pilot',0,'HYPOTHETICAL-PAID-ACCESS')
            state['channel_state']=book.export();state['queue']=[{'kind':'plan','id':'plan-0001','time':24}]
            return _prepare_plan(state,None,self.jobs,snapshot_override=snapshot)
        blocked=prepared()
        self.assertEqual([x['customer_id'] for x in blocked['exposures']],['SIM-customer-004'])
        self.assertEqual({d['customer_id'] for d in blocked['joint_action']['allocation']['deliveries']},{f'SIM-customer-{i:03d}' for i in range(4)})
        self.assertEqual(blocked['orders'],[])
        choices=[d for d in blocked['declines'] if d.get('buyer_choice')]
        self.assertEqual(len(choices),5)
        self.assertTrue(all(d['buyer_choice']=='decline' and not d.get('outside_spend') for d in choices))
        cfg['strategic_allocation_policy']['max_customers']=5
        self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),['pilot'])
        row=options(*args())[0]['execution']['startup_contract']
        self.assertEqual([p['customer_id'] for p in row['qualified_public_offers']],['SIM-customer-004'])
        self.assertEqual(row['qualified_public_offers'][0]['preceding_possible_menus'],4)
        allowed=prepared()
        self.assertEqual([o['customer_id'] for o in allowed['orders']],['SIM-customer-004'])

    def test_unadmitted_native_startup_holds_free_but_pays_normal_owned_operation(self):
        cfg=priority_fixture(self.manifest,self.jobs)
        target=self.folder/'priority-blocked-native'
        paused=run_world(ROOT,self.manifest,cfg,2611010521,'competitive_growth',target,stop_after_events=2)
        prefix=copy.deepcopy(paused['owned_account']['ledger']['actions'])
        result=run_world(ROOT,self.manifest,cfg,2611010521,'competitive_growth',target)
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertEqual(result['orders'],[]);self.assertEqual(result['investments'],[])
        self.assertFalse(any(c['id']=='startup-acquisition-evaluation' or c['category']=='acquisition_contract' for c in result['costs']))
        self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='development_integration_qualification_and_failed_search'),cfg['setup_cost'])
        self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='maintenance'),4)
        self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='outreach_including_failed_and_unused_slots'),16)
        self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='qualification_including_lost_offers'),16)
        self.assertEqual(result['summary']['expenses'],sum(c['amount'] for c in result['costs']))
        self.assertEqual(result['owned_account']['ledger']['actions'][:len(prefix)],prefix)
        again=run_world(ROOT,self.manifest,cfg,2611010521,'competitive_growth',target)
        self.assertEqual(again['owned_account'],result['owned_account'])

    def test_frontier_excludes_all_earlier_requested_work_not_only_first_menu(self):
        from unittest.mock import patch
        cfg=priority_fixture(self.manifest,self.jobs,maximum=5)
        ids=sorted(ident for ident,entry in self.jobs.items() if entry['job']['service_id']=='reconciliation'
            and entry['job']['accepted'] and entry['artifact'].get('outcome_scope')=='complete_outcome')
        requests=cfg['complete_offer_policy']['requested_jobs']
        requests['SIM-customer-000']=[ids[0],ids[5]]
        requests['SIM-customer-004']=[ids[5]]
        buyers={b['id']:b for b in _buyers(cfg,2611010521)}
        first=_offer_menu({'used_jobs':[]},self.jobs,buyers['SIM-customer-000'],cfg)[0][0]['job']
        self.assertEqual(first['id'],ids[0])
        self.assertFalse(set(first['work_keys'])&set(self.jobs[ids[5]]['job']['work_keys']))
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
        with patch('connected_enterprise.strategic_commerce.select',side_effect=AssertionError('SHARED_WORK_STARTUP_VALUATION')):
            self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),[])
            self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu,used_jobs=[ids[0]]),[])
            self.assertEqual(options(*args()),[])
        requests['SIM-customer-004']=[ids[6]]
        self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),['pilot'])
        self.assertEqual(options(*args())[0]['execution']['startup_contract']['qualified_public_offers'][0]['job_id'],ids[6])

    def test_possible_blockers_are_standalone_and_count_before_capacity_or_value(self):
        from unittest.mock import patch
        cfg=priority_fixture(self.manifest,self.jobs)
        buyers={b['id']:b for b in _buyers(cfg,2611010521)}
        def oversized_owned(state,jobs,buyer,configuration):
            menu=_offer_menu(state,jobs,buyer,configuration)
            if buyer['known']:
                menu=copy.deepcopy(menu)
                for entry,offer,anchor in menu:offer['capacity_units']=16
            return menu
        self.assertTrue(all(_offer_menu({'used_jobs':[]},self.jobs,buyers[f'SIM-customer-{i:03d}'],cfg) for i in range(4)))
        # Even a caller's tentative work exclusions must not erase possible
        # predecessors: their earlier refusal/absence can leave that work live.
        tentative=[j for i in range(4) for j in cfg['complete_offer_policy']['requested_jobs'][f'SIM-customer-{i:03d}']]
        with patch('connected_enterprise.strategic_commerce.select',side_effect=AssertionError('BLOCKER_VALUATION_STARTED')):
            self.assertEqual(preflight(cfg,buyers,self.jobs,oversized_owned,used_jobs=tentative),[])
            shared=cfg['complete_offer_policy']['requested_jobs']['SIM-customer-000']
            for i in range(1,4):
                cfg['complete_offer_policy']['requested_jobs'][f'SIM-customer-{i:03d}']=shared[:]
            self.assertEqual(preflight(cfg,buyers,self.jobs,oversized_owned),[],
                'Standalone blocker identities must not disappear through tentative shared-work deduplication')

    def test_recurring_recourse_fees_change_startup_value_and_cash_feasibility(self):
        from commercial.ledger import digest
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        policies=({'schema':'connected-refusal-recourse/v1','daily_planning_cost':1000},
                  {'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':1000,'daily_evaluation_cost':2000})
        for policy in policies:
            with self.subTest(policy=policy['schema']):
                cfg=fixture(self.manifest);cfg['channels']['pilot'].update(lead_days=3,duration_days=2)
                buyers={b['id']:b for b in _buyers(cfg,2611010482)}
                args=lambda:(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
                no_recourse=options(*args())[0]
                cfg['refusal_recourse_policy']=copy.deepcopy(policy)
                costed=options(*args())[0];certificate=costed['execution']['startup_contract'];envelope=certificate['future_cost_envelope']
                future_days=4
                fees=future_days*(policy['daily_planning_cost']+policy.get('daily_evaluation_cost',0))
                self.assertEqual(envelope['recourse_planning_days'],future_days)
                self.assertEqual(envelope['recourse_policy_sha256'],digest(policy))
                self.assertEqual(envelope['recourse_evaluation_microUSD'],future_days*policy.get('daily_evaluation_cost',0))
                self.assertEqual(envelope['recourse_allowance_microUSD'],future_days*policy['daily_planning_cost'])
                self.assertEqual(no_recourse['future_net_cash']['baseline']-costed['future_net_cash']['baseline'],fees)
                self.assertEqual(costed['execution']['cash_lock']-no_recourse['execution']['cash_lock'],fees)
                snapshot['summary']['available']=costed['upfront_cost']+costed['execution']['cash_lock']-fees
                self.assertTrue(no_recourse['upfront_cost']+no_recourse['execution']['cash_lock']<=snapshot['summary']['available'])
                self.assertEqual(options(*args()),[])
                snapshot['summary']['available']=100000000000
                if policy['schema']=='connected-selective-refusal-recourse/v2':
                    cfg['refusal_recourse_policy']['daily_evaluation_cost']=1000000000
                else:cfg['refusal_recourse_policy']['daily_planning_cost']=1000000000
                self.assertEqual(options(*args()),[])
                snapshot['summary']['profit']=10**18
                self.assertEqual(options(*args()),[])
                snapshot['summary'].pop('profit')

    def test_recourse_fee_window_excludes_day_zero_and_clips_to_operating_horizon(self):
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        for lead,duration,horizon,expected in ((1,1,8,1),(2,1,8,2),(3,20,4,3)):
            with self.subTest(lead=lead,duration=duration,horizon=horizon):
                cfg=fixture(self.manifest);cfg['horizon_days']=horizon
                cfg['channels']['pilot'].update(lead_days=lead,duration_days=duration,price_microUSD=1,support_microUSD=0)
                cfg['refusal_recourse_policy']={'schema':'connected-refusal-recourse/v1','daily_planning_cost':1}
                buyers={b['id']:b for b in _buyers(cfg,2611010482)}
                rows=options(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'],_offer_menu)
                envelope=rows[0]['execution']['startup_contract']['future_cost_envelope']
                self.assertEqual(envelope['recourse_planning_days'],expected)
                self.assertEqual(envelope['recourse_allowance_microUSD'],expected)
                self.assertEqual(envelope['future_planning_days'],expected)
                self.assertEqual(envelope['maintenance_days'],expected)
                self.assertEqual(envelope['continuing_owned_outreach_units'],4*expected)
                self.assertEqual(envelope['continuing_prospect_outreach_units'],4*expected)
                self.assertEqual(envelope['qualification_evaluations'],4*expected)

    def test_zero_lead_startup_channel_holds_without_evaluation_or_native_invoice(self):
        cfg=fixture(self.manifest);cfg['horizon_days']=4
        cfg['channel_menu_policy']['contract_ids']=['extended','pilot']
        cfg['startup_acquisition_policy']['contract_ids']=['extended']
        cfg['channels']['extended'].update(lead_days=0,duration_days=1)
        self.assertEqual(validate_config(cfg)['channels']['extended']['lead_days'],0)
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),[])
        cfg['channels']['extended']['duration_days']=5
        self.assertEqual(preflight(cfg,buyers,self.jobs,_offer_menu),[])
        cfg['channels']['extended']['duration_days']=1
        result=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',self.folder/'unsupported-zero-lead')
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertEqual(result['investments'],[])
        self.assertFalse(any(c['id']=='startup-acquisition-evaluation' for c in result['costs']))

    def test_native_recurring_fee_contract_holds_startup_and_resumes_without_forced_allowance(self):
        import json
        policies=({'schema':'connected-refusal-recourse/v1','daily_planning_cost':1000000000},
                  {'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':100000,'daily_evaluation_cost':1000000000})
        for number,policy in enumerate(policies):
            with self.subTest(policy=policy['schema']):
                cfg=fixture(self.manifest);cfg['horizon_days']=4;cfg['refusal_recourse_policy']=copy.deepcopy(policy)
                target=self.folder/('recurring-fee-hold-'+str(number))
                paused=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target,stop_after_events=2)
                self.assertFalse(paused['complete']);prefix=copy.deepcopy(paused['owned_account']['ledger']['actions'])
                result=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
                self.assertTrue(audit(ROOT,self.manifest,json.loads(json.dumps(result,sort_keys=True)))['accepted'])
                self.assertEqual(result['investments'],[]);self.assertEqual(result['orders'],[])
                self.assertEqual(result['summary']['collections'],0);self.assertEqual(result['summary']['payables'],0)
                self.assertLess(result['summary']['profit'],0)
                self.assertEqual(result['owned_account']['ledger']['actions'][:len(prefix)],prefix)
                self.assertEqual(sum(c['id']=='startup-acquisition-evaluation' for c in result['costs']),1)
                evaluation=sum(c['amount'] for c in result['costs'] if c['category']=='selective_recourse_public_evaluation')
                allowance=sum(c['amount'] for c in result['costs'] if c['category']=='prepaid_finite_refusal_recourse')
                self.assertEqual(evaluation,4*policy.get('daily_evaluation_cost',0))
                self.assertEqual(allowance,0 if 'daily_evaluation_cost' in policy else 4*policy['daily_planning_cost'])
                self.assertEqual(result['summary']['expenses'],sum(c['amount'] for c in result['costs']))
                again=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
                self.assertEqual(again['owned_account'],result['owned_account'])
                self.assertTrue(audit(ROOT,self.manifest,again)['accepted'])

    def test_startup_profile_preparation_validates_once_and_preserves_callback(self):
        from unittest.mock import patch
        from connected_enterprise import complete_offer_market as market
        cfg=fixture(self.manifest)
        snapshot={'state_digest':'a'*64,'summary':{'available':100000000000,'unrestrictedEarned':0,'investmentStopped':False}}
        buyers={b['id']:b for b in _buyers(cfg,2611010482)}
        args=(cfg,'competitive_growth',0,snapshot,0,self.jobs,set(),buyers,cfg['strategic_allocation_policy']['risk']['scenarios'])
        with patch.object(market,'validate_policy',wraps=market.validate_policy) as validate:
            expected=options(*args,_offer_menu)
        self.assertEqual(sum('requested_jobs' in call.args[0] for call in validate.call_args_list),1)
        with patch.object(market,'validate_policy',wraps=market.validate_policy) as validate:
            preflight(cfg,buyers,self.jobs,_offer_menu)
        self.assertEqual(validate.call_count,1)
        calls=[]
        def callback(state,jobs,buyer,configuration):
            calls.append(buyer['id'])
            return _offer_menu(state,jobs,buyer,configuration)
        self.assertEqual(options(*args,callback),expected)
        self.assertTrue(calls)

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

    def test_exact_startup_selective_category_caps_hold_with_paid_prefix_and_resume(self):
        import json
        cfg=fixture(self.manifest);cfg['horizon_days']=4
        cfg['refusal_recourse_policy']={'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':100000,'daily_evaluation_cost':10000}
        cfg['strategic_allocation_policy']['category_budgets_bps']={'acquisition':5000,'capacity':5000}
        target=self.folder/'startup-selective-category-exact'
        paused=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target,stop_after_events=2)
        self.assertFalse(paused['complete'])
        prefix=copy.deepcopy(paused['owned_account']['ledger']['actions'])
        result=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertTrue(audit(ROOT,self.manifest,json.loads(json.dumps(result,sort_keys=True)))['accepted'])
        self.assertEqual(result['config']['monetary_policy'],'exact-integer-v2')
        self.assertEqual(result['config']['strategic_policy']['ranking_arithmetic'],'exact-rational-v1')
        self.assertEqual(self.manifest['native_engine'],'exact-permanent-v2')
        from commercial.ledger import digest
        self.assertEqual(result['owned_account']['ledger']['config']['manifest_sha256'],digest(self.manifest))
        self.assertEqual(result['investments'],[])
        self.assertEqual(result['orders'],[])
        self.assertEqual(result['summary']['collections'],0)
        self.assertEqual(result['summary']['payables'],0)
        tape=result['owned_account']['ledger']['actions']
        self.assertEqual(tape[:len(prefix)],prefix)
        fees={a['args']['id']:a for a in tape if a['op']=='cost'}
        names=('maintenance-0','startup-acquisition-evaluation','recourse-evaluation-0')
        self.assertEqual([fees[name]['seq'] for name in names],list(range(fees[names[0]]['seq'],fees[names[0]]['seq']+3)))
        self.assertEqual(sum(c['id']=='startup-acquisition-evaluation' for c in result['costs']),1)
        self.assertEqual(sum(c['category']=='selective_recourse_public_evaluation' for c in result['costs']),4)
        self.assertFalse(any(c['category'] in ('acquisition_contract','prepaid_finite_refusal_recourse') for c in result['costs']))
        day_zero=next(w for w in result['joint_actions'].values() if w['time']==0)
        self.assertTrue(any(o['execution'].get('startup_contract') for o in day_zero['allocation']['investments']))
        for wrapper in result['joint_actions'].values():
            allocation=wrapper['allocation']
            self.assertEqual(allocation['category_upfront_caps'],{'acquisition':0,'capacity':0})
            self.assertEqual(allocation['decision']['category_upfront_caps'],allocation['category_upfront_caps'])
            self.assertEqual(allocation['decision']['selected_options'],[])
            self.assertFalse(wrapper['selective_recourse_decision']['purchase'])
        again=run_world(ROOT,self.manifest,cfg,2611010482,'competitive_growth',target)
        self.assertEqual(again['owned_account'],result['owned_account'])
        self.assertTrue(audit(ROOT,self.manifest,again)['accepted'])

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
