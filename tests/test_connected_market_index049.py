"""Exact lookup/validation parity and native acceptance, not market calibration."""
import copy
import dataclasses
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connected_enterprise import complete_offer_market as market
from connected_enterprise.engine import _buyers, _offer_menu, default_config, fresh_account_config, run_world
from connected_enterprise.verify import _check_buyer_origins, audit

ROOT=Path(__file__).resolve().parents[1]
MICRO=1_000_000


def policy(n=4):
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet']
    profiles=[]
    for index in range(3):
        values=dict.fromkeys(services,40*MICRO);values['receivables_packet']=100*MICRO
        profiles.append({'id':'profile-'+str(index),'services':services,
            'price_grids':{s:[20*MICRO,25*MICRO] if s!='receivables_packet' else [50*MICRO] for s in services},
            'atoms':[{'weight_bps':7000,'budget_microUSD':600*MICRO,'values':values},
                     {'weight_bps':3000,'budget_microUSD':300*MICRO,'values':{s:v//2 for s,v in values.items()}}],
            'outside_options':[{'name':'rival-packet','provider':'rival','service_id':'receivables_packet',
                                'price':65*MICRO,'quality_bps':10000,'delay_cost':0}]})
    return {'schema':market.SCHEMA,'selection':'menu','profiles':profiles,
            'requested_jobs':{f'SIM-customer-{i:03d}':[f'job-{i}-{j}' for j in range(4)] for i in range(n)}}


def native_config(manifest,n=4,days=4):
    from portfolio25.pricing import SCENARIOS
    cfg,manifest=fresh_account_config(manifest,root=ROOT)
    p=policy(n)
    for profile in p['profiles']:profile['atoms']=[{**profile['atoms'][0],'weight_bps':10000}]
    by_service={}
    for job in manifest['jobs']:by_service.setdefault(job['service_id'],[]).append(job['id'])
    p['requested_jobs']={f'SIM-customer-{i:03d}':[] for i in range(n)}
    for ids in by_service.values():
        for i,ident in enumerate(sorted(ids)):p['requested_jobs'][f'SIM-customer-{i%n:03d}'].append(ident)
    scenarios=copy.deepcopy(list(SCENARIOS))
    for scenario in scenarios:scenario.update(repeat_horizon=0,cost_shock=1)
    cfg.update(horizon_days=days,customer_pool=n,opening=100000*MICRO,initial_slots=3,maximum_slots=3,
               arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=24)
    cfg['complete_offer_policy']=p
    cfg['strategic_policy']={'schema':'connected-strategic-commerce/v1','public_basis':'Explicit synthetic correctness fixture, no market calibration.',
        'price_bps':[5500,7000,9000,10000],'rival_price_bps':[5500,7000,9000,10000],
        'rival_cost_bps':3000,'rival_response':'observed_quote','scenarios':scenarios,'demand_model':'connected_range',
        'connected_beliefs':{s['id']:{'min_value_bps':7000,'max_value_bps':21000,'min_budget_microUSD':0,
            'max_budget_microUSD':600*MICRO,'rival_available_bps':8000} for s in scenarios}}
    cfg['strategic_allocation_policy']={'max_customers':4,'risk':{
        'scenarios':{'baseline':5000,'ai_parity_price_war':3000,'differentiated_verified_service':2000},
        'worst_loss_limit':cfg['opening'],'downside_penalty_bps':2500,'max_states':262144,
        'authorized_allocation':cfg['opening'],'interactions':[]}}
    return cfg,manifest


def jobs_fixture(n=100):
    services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet'];jobs={}
    for i in range(n):
        service=services[i%4];ident=f'job-{i:06d}'
        jobs[ident]={'job':{'id':ident,'service_id':service,'accepted':True,'work_keys':['work-'+str(i)]},
                     'artifact':{'method':'receivables_packet' if service=='receivables_packet' else 'canonical',
                                 'outcome_scope':'complete_outcome'}}
    return jobs


def original_menu(state,jobs,buyer,cfg):
    from adaptive_enterprise.strategies import offer_catalog
    from connected_enterprise.engine import SERVICES
    profile=market.request_profile(cfg['complete_offer_policy'],buyer['id']);services=profile['services']
    if cfg['complete_offer_policy']['selection']=='restricted':
        service=SERVICES[buyer['service_index']%3];services=[service] if service in services else []
    used={k for ident in state['used_jobs'] for k in jobs[ident]['job']['work_keys']};options=[]
    for service in services:
        entries=[entry for entry in jobs.values() if entry['job']['id'] in cfg['complete_offer_policy']['requested_jobs'][buyer['id']]
                 and entry['job']['accepted'] and entry['job']['service_id']==service and entry['artifact'].get('outcome_scope')=='complete_outcome'
                 and not used.intersection(entry['job']['work_keys'])]
        if not entries:continue
        entry=min(entries,key=lambda x:x['job']['id']);offer=copy.deepcopy(next(o for o in offer_catalog(include_packet=True)
            if o['service_id']==service and o['method']==entry['artifact']['method']))
        grid=profile['price_grids'][service];offer['price_microUSD']=grid[0];options.append((entry,offer,max(grid)))
    return options


class MarketIndexTests(unittest.TestCase):
    def test_profiles_context_and_private_atom_match_stateless_queries(self):
        p=policy(64);prepared=market.compile_market(p)
        for buyer in p['requested_jobs']:
            self.assertEqual(prepared.profile(buyer),market.request_profile(p,buyer))
            for seed in (0,1,261101049):self.assertEqual(prepared.atom(buyer,seed),market.private_atom(p,buyer,seed))
            for spent in (0,12,450*MICRO):
                for rival in (True,False):self.assertEqual(prepared.context(buyer,spent,rival),market.market_context(p,buyer,spent,rival))
    def test_input_mutation_cannot_change_existing_snapshot(self):
        p=policy();prepared=market.compile_market(p);before=prepared.profile('a')
        for profile in p['profiles']:profile['atoms'][0]['budget_microUSD']=0
        self.assertEqual(prepared.profile('a'),before)
        self.assertNotEqual(market.compile_market(p).policy_sha256,prepared.policy_sha256)
    def test_return_mutation_cannot_change_later_queries(self):
        prepared=market.compile_market(policy());r=prepared.profile('a');r['atoms'].clear()
        self.assertTrue(prepared.profile('a')['atoms'])
    def test_snapshot_fields_are_frozen(self):
        prepared=market.compile_market(policy())
        with self.assertRaises(dataclasses.FrozenInstanceError):prepared.encoded_profiles=()
    def test_invalid_unselected_profile_refused(self):
        p=policy();p['profiles'][-1]['atoms'][0]['weight_bps']=0
        with self.assertRaises(ValueError):market.compile_market(p)
    def test_invalid_unselected_customer_request_refused(self):
        p=policy(100);p['requested_jobs']['SIM-customer-099']=['same','same']
        with self.assertRaises(ValueError):market.compile_market(p)
    def test_boolean_and_noninteger_spend_refused(self):
        prepared=market.compile_market(policy())
        for value in (True,False,0.1,-1,'1'):
            with self.assertRaises(ValueError):prepared.context('a',value)
    def test_nonboolean_rival_refused(self):
        with self.assertRaises(ValueError):market.compile_market(policy()).context('a',0,1)
    def test_recompile_does_not_reuse_stale_request_validation(self):
        p=policy();market.compile_market(p);p['requested_jobs']['new']=['x','x']
        with self.assertRaises(ValueError):market.compile_market(p)
    def test_only_public_profile_data_is_returned(self):
        prepared=market.compile_market(policy())
        self.assertEqual(set(prepared.context('a',0)),{'profile','observed_spend','rival_available'})
        self.assertNotIn('seed',dataclasses.asdict(prepared))
    def test_no_process_wide_cache(self):
        p=policy();a=market.compile_market(p);b=market.compile_market(p)
        self.assertIsNot(a,b);self.assertEqual(a,b)
    def test_buyer_initialization_validates_once_and_preserves_draws(self):
        cfg=default_config();cfg['customer_pool']=128;cfg['complete_offer_policy']=policy(128)
        with patch.object(market,'validate_policy',wraps=market.validate_policy) as validate:
            buyers=_buyers(cfg,261101049)
        self.assertEqual(validate.call_count,1)
        for buyer in buyers:
            p=market.request_profile(cfg['complete_offer_policy'],buyer['id'])
            a=market.private_atom(cfg['complete_offer_policy'],buyer['id'],261101049)
            self.assertEqual(buyer['initial_budget'],p['atoms'][a]['budget_microUSD'])
        self.assertEqual(sum(b['known'] for b in buyers),4)
    def test_independent_origin_audit_validates_once(self):
        cfg=default_config();cfg['customer_pool']=128;cfg['complete_offer_policy']=policy(128);buyers=_buyers(cfg,5)
        with patch.object(market,'validate_policy',wraps=market.validate_policy) as validate:_check_buyer_origins(cfg,5,buyers)
        self.assertEqual(validate.call_count,1)
    def test_tampered_buyer_budget_rejected(self):
        cfg=default_config();cfg['complete_offer_policy']=policy(cfg['customer_pool']);buyers=_buyers(cfg,5);buyers[0]['initial_budget']+=1
        with self.assertRaisesRegex(ValueError,'INITIAL_BUYER_BUDGET_CHANGED'):_check_buyer_origins(cfg,5,buyers)
    def test_large_population_has_no_new_business_ceiling(self):
        cfg=default_config();cfg['customer_pool']=2049;cfg['complete_offer_policy']=policy(2049)
        self.assertEqual(len(_buyers(cfg,5)),2049)


class RequestedJobLookupTests(unittest.TestCase):
    def setUp(self):
        self.jobs=jobs_fixture();self.buyer={'id':'SIM-customer-000','service_index':0};self.state={'used_jobs':[]}
        self.cfg=default_config();p=policy();p['requested_jobs'][self.buyer['id']]=['job-000007','job-000006','job-000005','job-000004','job-000003','job-000002','job-000001','job-000000'];self.cfg['complete_offer_policy']=p
    def assert_parity(self):self.assertEqual(_offer_menu(self.state,self.jobs,self.buyer,self.cfg),original_menu(self.state,self.jobs,self.buyer,self.cfg))
    def test_exact_selected_work_and_quotes_match_full_scan(self):self.assert_parity()
    def test_request_order_and_catalog_order_do_not_change_choice(self):
        first=_offer_menu(self.state,self.jobs,self.buyer,self.cfg)
        self.jobs=dict(reversed(list(self.jobs.items())));self.cfg['complete_offer_policy']['requested_jobs'][self.buyer['id']].reverse()
        self.assertEqual(first,_offer_menu(self.state,self.jobs,self.buyer,self.cfg))
    def test_unrelated_inventory_is_not_scanned(self):
        class NoScan(dict):
            def values(self):raise AssertionError('full inventory scan')
        self.assertTrue(_offer_menu(self.state,NoScan(self.jobs),self.buyer,self.cfg))
    def test_work_overlap_still_excluded(self):self.state['used_jobs']=['job-000000','job-000001'];self.assert_parity()
    def test_unaccepted_and_partial_scope_still_excluded(self):
        self.jobs['job-000000']['job']['accepted']=False;self.jobs['job-000001']['artifact']['outcome_scope']='readiness';self.assert_parity()
    def test_restricted_service_unchanged(self):self.cfg['complete_offer_policy']['selection']='restricted';self.assert_parity()
    def test_unknown_request_keeps_public_helper_behavior(self):self.cfg['complete_offer_policy']['requested_jobs'][self.buyer['id']].append('missing');self.assert_parity()
    def test_wrong_index_identity_refused(self):
        self.jobs['job-000000']['job']['id']='somebody-else'
        with self.assertRaisesRegex(ValueError,'INDEX_IDENTITY'):_offer_menu(self.state,self.jobs,self.buyer,self.cfg)
    def test_compiled_profile_keeps_same_menu(self):
        self.assertEqual(_offer_menu(self.state,self.jobs,self.buyer,self.cfg),_offer_menu(self.state,self.jobs,self.buyer,self.cfg,_market=market.compile_market(self.cfg['complete_offer_policy'])))
    def test_offer_mutation_does_not_change_future_quote(self):
        first=_offer_menu(self.state,self.jobs,self.buyer,self.cfg);expected=copy.deepcopy(first);first[0][1]['price_microUSD']=1
        self.assertEqual(expected,_offer_menu(self.state,self.jobs,self.buyer,self.cfg))


class NativeMarketIndexTests(unittest.TestCase):
    def test_native_complete_outcome_and_independent_tamper_checks(self):
        from adaptive_enterprise.instruments import prepare_complete_offer_services
        with tempfile.TemporaryDirectory(prefix='.market049-',dir=ROOT) as directory:
            folder=Path(directory);manifest=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=261101049,jobs_per_service=32,packet_jobs=4,packet_rows=8)
            cfg,manifest=native_config(manifest)
            result=run_world(ROOT,manifest,cfg,261101049,'competitive_growth',folder/'account')
            self.assertTrue(audit(ROOT,manifest,result)['accepted']);self.assertGreater(result['paid_jobs'],0)
            for change in ('budget','choice','context','order'):
                forged=copy.deepcopy(result)
                if change=='budget':forged['buyers'][0]['initial_budget']+=1
                elif change=='choice':next(d for d in forged['decisions'] if d['kind']=='offer')['chosen']=False
                elif change=='context':next(d for d in forged['decisions'] if d['kind']=='offer')['market_context']['profile']['atoms'][0]['values']['reconciliation']+=1
                else:forged['orders'][0]['complete_cost']-=1
                with self.assertRaises(ValueError):audit(ROOT,manifest,forged)

if __name__=='__main__':unittest.main()
