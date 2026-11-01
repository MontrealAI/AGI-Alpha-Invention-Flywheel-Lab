import copy,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from commercial.ledger import digest
from connected_enterprise.engine import run_world,validate_config
from connected_enterprise.verify import audit
from connected_enterprise.joint_planning import plan_actions
from adaptive_enterprise.instruments import prepare_complete_offer_services
ROOT=Path(__file__).resolve().parents[1]

def config(manifest,composed=True):
 spec=importlib.util.spec_from_file_location('complete_fixture049',ROOT/'tests/test_connected_complete_offer.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 cfg=module.fixture(manifest,'menu');cfg.update(horizon_days=14,customer_pool=8,opening=100000000000,initial_slots=1,maximum_slots=3,setup_cost=3000000,capacity_price=1000000)
 cfg['strategic_policy']['ranking_arithmetic']='exact-rational-v1';cfg['strategic_allocation_policy']['max_customers']=4
 cfg['strategic_allocation_policy']['capacity_menu']={'max_quantity':2,'opportunity_delay_hours':24,'retention_bps':7000}
 cfg['channel_menu_policy']={'schema':'connected-channel-menu/v1','contract_ids':['pilot'],'conversion_bps':4000}
 profile=cfg['complete_offer_policy']['profiles'][0];profile['outside_options']=[]
 profile['price_grids']={s:[30000000] if s!='receivables_packet' else [120000000] for s in profile['services']}
 profile['atoms']=[{'weight_bps':10000,'budget_microUSD':2000000000,'values':{s:45000000 if s!='receivables_packet' else 150000000 for s in profile['services']}}]
 cfg['complete_offer_policy']['requested_jobs']={f'SIM-customer-{i:03d}':[j['id'] for j in manifest['jobs'] if j['service_id'] in profile['services']] for i in range(8)}
 for terms in cfg['channels'].values():terms.update(owned_audience_count=4,price_microUSD=1000000,support_microUSD=0,lead_days=1,duration_days=7,realization_bps=10000,activation_reliability_bps=10000,overlap_bps=0,slots_per_day=2)
 if composed:cfg['strategic_allocation_policy']['sequence']={'schema':'public-sequence-window/v1','composition':'complete-offer-quantity-v1','provenance':'Exposed integration hypotheses; finite public contact seeds, never realized future draws.','window_delay_days':2,'owned_contact_count':4,'owned_available_bps':2500,'service_share_bps':10000,'arrival_bps':10000,'future_rival_price_bps':9000}
 return cfg

class ComposedWindowOperating(unittest.TestCase):
 def test_restricted_composition_rejected_before_account_but_ordinary_path_resumes(self):
  with tempfile.TemporaryDirectory(prefix='.restricted-composed051-',dir=ROOT) as tmp:
   folder=Path(tmp);manifest=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2611010511,packet_jobs=8,packet_rows=12)
   blocked=config(manifest);blocked['complete_offer_policy']['selection']='restricted'
   with patch('connected_enterprise.engine.JournalAccount',side_effect=AssertionError('UNAVAILABLE_MODE_OPENED_ACCOUNT')):
    with self.assertRaisesRegex(ValueError,'RESTRICTED_COMPLETE_SEQUENCE_LIFECYCLE_UNAVAILABLE'):
     run_world(ROOT,manifest,blocked,2611010511,'competitive_growth',folder/'blocked')
   self.assertFalse((folder/'blocked'/'account.sqlite').exists())
   cfg=config(manifest,composed=False);cfg['horizon_days']=4;cfg['complete_offer_policy']['selection']='restricted'
   partial=run_world(ROOT,manifest,cfg,2611010511,'competitive_growth',folder/'world',stop_after_events=2)
   self.assertFalse(partial['complete'])
   result=run_world(ROOT,manifest,cfg,2611010511,'competitive_growth',folder/'world')
   self.assertTrue(audit(ROOT,manifest,result)['accepted']);self.assertTrue(result['orders'])
   self.assertFalse(any(o['offer']['service_id']=='receivables_packet' for o in result['orders']))
   from connected_enterprise.engine import SERVICES
   for wrapper in result['joint_actions'].values():
    for delivery in wrapper['allocation']['deliveries']:
     ident=delivery['customer_id'];job=delivery['selection']['problem']['job_id']
     self.assertIn(job,cfg['complete_offer_policy']['requested_jobs'][ident])
     self.assertIn(delivery['selection']['problem']['offer']['service_id'],SERVICES)
   resumed=run_world(ROOT,manifest,cfg,2611010511,'competitive_growth',folder/'world')
   self.assertEqual(result['owned_account'],resumed['owned_account']);self.assertTrue(audit(ROOT,manifest,resumed)['accepted'])
 def test_native_weighted_sequence_flags_public_information_and_audit(self):
  with tempfile.TemporaryDirectory(prefix='.composed-window049-',dir=ROOT) as tmp:
   folder=Path(tmp);manifest=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=261101049,packet_jobs=24,packet_rows=12)
   cfg=config(manifest);cfg['strategic_allocation_policy']['capacity_menu']['retention_bps']=0
   cfg['strategic_allocation_policy']['strategic_game']={'schema':'connected-finite-follower-regret/v1','public_basis':'Fixed exposed forecast stress only; not actual rival dynamics.','max_response_states':1000000,'scenarios':{sid:{'budget':0,'responses':[{'id':'unchanged','haircut_bps':{},'capture_bps':0,'cost':0},{'id':'compete','haircut_bps':{'delivery':100,'capacity':100,'acquisition':100},'capture_bps':5000,'cost':0}]} for sid in cfg['strategic_allocation_policy']['risk']['scenarios']}}
   calls=[]
   def checked(state,jobs,candidates,*args,**kwargs):
    result=plan_actions(state,jobs,candidates,*args,**kwargs)
    changed=copy.deepcopy(state);changed['seed']=state['seed']+1
    for buyer in changed['buyers']:buyer['remaining_budget']=10**30;buyer['initial_budget']=10**31
    self.assertEqual(result,plan_actions(changed,jobs,copy.deepcopy(candidates),*args,**kwargs))
    calls.append(result);return result
   with patch('connected_enterprise.joint_planning.plan_actions',checked):result=run_world(ROOT,manifest,cfg,261101049,'competitive_growth',folder/'world')
   self.assertTrue(audit(ROOT,manifest,result)['accepted']);self.assertEqual(len(calls),14)
   options=[o for w in calls for o in w['allocation']['investments'] if 'first_investment' in o['execution']]
   self.assertTrue(options);self.assertTrue(any(o['execution']['forecast']['capacity_units']==3 for o in options))
   self.assertTrue(any(o['execution']['forecast']['forecast']['channel_forecast']['invoice_microUSD']>0 for o in options))
   for option in options:
    profile=option['execution']['forecast'];keys=profile['admitted_work_keys']
    self.assertEqual(len(keys),len(set(keys)))
    self.assertTrue(all(r['delivery_capacity_units']==profile['capacity_units'] for r in profile['forecast']['routes']))
    if option['kind']=='capacity':self.assertEqual(option['upfront_cost'],option['execution']['purchased_units']*cfg['capacity_price'])
   selected=[o for w in calls for o in w['allocation']['decision']['selected_options'] if 'first_investment' in o['execution']]
   self.assertTrue(any(o['kind']=='capacity' and o['execution'].get('purchased_units')==2 for o in selected))
   self.assertTrue(any(o['kind']=='acquisition' for o in selected))
   self.assertTrue(all('strategic_game_certificate' in wrapper['allocation']['decision'] for wrapper in calls))
   self.assertTrue(any(o['offer']['service_id']=='receivables_packet' and o['outcome']=='SETTLED' and o.get('capacity_source_plan_ids') for o in result['orders']))
   print('COMPOSED049_DEVELOPMENT',{'profit':result['summary']['profit'],'paid':result['paid_jobs'],'investments':[(i['kind'],i.get('capacity_units'),i['cost']) for i in result['investments']],'sequence_selected':[(o['kind'],o['execution'].get('purchased_units'),o['execution'].get('contingent_capacity_units')) for o in selected]})
   resumed=run_world(ROOT,manifest,cfg,261101049,'competitive_growth',folder/'world');self.assertEqual(result['owned_account'],resumed['owned_account']);self.assertTrue(audit(ROOT,manifest,resumed)['accepted'])
   bad=copy.deepcopy(result);target=next(w for w in bad['joint_actions'].values() if any('first_investment' in o['execution'] for o in w['allocation']['investments']));option=next(o for o in target['allocation']['investments'] if 'first_investment' in o['execution']);option['execution']['forecast']['capacity_units']+=1
   with self.assertRaises(ValueError):audit(ROOT,manifest,bad)
 def test_old_unsupported_combination_and_incoherent_owned_access_stay_closed(self):
  cfg=config({'jobs':[]});bad=copy.deepcopy(cfg);bad['strategic_allocation_policy']['sequence'].pop('composition')
  with self.assertRaisesRegex(ValueError,'COMPLETE_OFFER_REQUIRES_SINGLE_OPPORTUNITY'):validate_config(bad)
  bad=copy.deepcopy(cfg);bad['channels']['pilot']['owned_audience_count']=48
  with self.assertRaisesRegex(ValueError,'COHERENT_FOUR_OWNED'):validate_config(bad)
  bad=copy.deepcopy(cfg);bad['strategic_allocation_policy']['sequence']['owned_contact_count']=0
  with self.assertRaisesRegex(ValueError,'ACTUAL_OWNED_COUNT'):validate_config(bad)
  bad=copy.deepcopy(cfg);bad['strategic_policy'].pop('ranking_arithmetic')
  with self.assertRaisesRegex(ValueError,'COMPLETE_SEQUENCE_REQUIRES_EXACT'):validate_config(bad)

class ComposedWindowForecasts(unittest.TestCase):
 def setUp(self):
  self.jobs={f'packet-{i}':{'job':{'id':f'packet-{i}','service_id':'receivables_packet','accepted':True,'work_keys':[f'w{i}-{k}' for k in range(3)]},'artifact':{'method':'receivables_packet','outcome_scope':'complete_outcome'}} for i in range(3)}
  self.cfg=config({'jobs':[x['job'] for x in self.jobs.values()]})
  self.buyers={f'SIM-customer-{i:03d}':{'id':f'SIM-customer-{i:03d}','onboarded':False,'active':True,'pending_commitments':{},'next_need_time':0,'outside_spend':0,'our_settled_spend':0} for i in range(8)}
  self.obs={'scope':'SIMULATED','state_digest':'a'*64,'summary':{'available':1000000000,'unrestrictedEarned':1000000000}}
 def options(self,*,used=(),investments=(),buyers=None,delivery_reserve=0):
  from connected_enterprise.sequence_planning import sequence_options
  from connected_enterprise.channels import ChannelBook
  book=ChannelBook(1,self.cfg['channels']);book.expose(0,list(self.buyers.values()))
  return sequence_options(self.cfg,0,self.obs,0,self.jobs,set(used),list(investments),self.buyers if buyers is None else buyers,{},set(),self.cfg['strategic_allocation_policy']['risk']['scenarios'],current_delivery_reserve=delivery_reserve,channel_state=book.export())
 def test_restricted_packet_only_empty_menu_rejected_before_forecast_valuation(self):
  from connected_enterprise.engine import _offer_menu
  menu=self.options();self.assertTrue(any(o['kind']=='acquisition' for o in menu));self.assertTrue(any(o['kind']=='capacity' and o['execution']['purchased_units']==2 for o in menu))
  self.cfg['complete_offer_policy']['selection']='restricted'
  for index,buyer in enumerate(self.buyers.values()):buyer['service_index']=index%3
  for buyer in self.buyers.values():self.assertEqual(_offer_menu({'used_jobs':[]},self.jobs,buyer,self.cfg),[])
  with self.assertRaisesRegex(ValueError,'RESTRICTED_COMPLETE_SEQUENCE_LIFECYCLE_UNAVAILABLE'):validate_config(self.cfg)
  with patch('connected_enterprise.sequence_planning.select',side_effect=AssertionError('UNAVAILABLE_PROFILE_VALUED')),patch('connected_enterprise.sequence_channels.forecast_contract',side_effect=AssertionError('UNAVAILABLE_REACH_VALUED')):
   with self.assertRaisesRegex(ValueError,'RESTRICTED_COMPLETE_SEQUENCE_LIFECYCLE_UNAVAILABLE'):self.options()
 def test_menu_forecast_golden_parity_after_restricted_unavailable_guard(self):
  self.assertEqual(digest(self.options()),'8d9dffb806f2cda9784a7ba3d9370133638f273aea1c2af238aa490975c1da6d')
 def test_two_unit_complement_and_three_unit_production_cost(self):
  rows=self.options();self.assertTrue(rows);self.assertEqual(len(rows),len({row['id'] for row in rows}))
  packet=next(o for o in rows if o['kind']=='capacity' and o['execution']['purchased_units']==2)
  forecast=packet['execution']['forecast'];routes=forecast['forecast']['routes']
  self.assertEqual(forecast['capacity_units'],3)
  self.assertEqual(next(r for r in routes if not r['channel'] and r['capacity_quantity']==1)['future_delivery_cash_limit'],0)
  self.assertGreater(next(r for r in routes if not r['channel'] and r['capacity_quantity']==2)['future_delivery_cash_limit'],0)
  self.assertEqual(packet['upfront_cost'],2*self.cfg['capacity_price'])
 def test_current_source_work_and_overlapping_packet_never_reused(self):
  self.jobs['primitive']={'job':{'id':'primitive','service_id':'reconciliation','accepted':True,'work_keys':['w0-0']},'artifact':{'method':'canonical','outcome_scope':'complete_outcome'}}
  self.jobs['packet-2']['job']['work_keys']=['w1-0','w2-1','w2-2']
  rows=self.options(used=['primitive'])
  self.assertTrue(rows)
  for row in rows:self.assertEqual(row['execution']['forecast']['admitted_job_ids'],['packet-1'])
 def test_weighted_existing_capacity_and_strict_finish_expiry(self):
  inv={'id':'prior','kind':'capacity','capacity_units':2,'activation_time':1,'expiry_time':100}
  from connected_enterprise.sequence_window import compare_window
  with patch('connected_enterprise.sequence_planning.compare_window',wraps=compare_window) as windows:self.options(investments=[inv])
  self.assertTrue(windows.call_count);self.assertTrue(all(call.kwargs['future_existing_slots']==3 for call in windows.call_args_list))
  inv['expiry_time']=50
  with patch('connected_enterprise.sequence_planning.compare_window',wraps=compare_window) as windows:self.options(investments=[inv])
  self.assertTrue(windows.call_count);self.assertTrue(all(call.kwargs['future_existing_slots']==1 for call in windows.call_args_list))
 def test_outage_crossing_production_blocks_forecast(self):
  self.cfg['production_hours']=30;self.cfg['supplier_outage_start_day']=3;self.cfg['supplier_outage_days']=1
  self.assertEqual(self.options(),[])
 def test_no_demand_no_liquidity_and_late_window_hold(self):
  no=copy.deepcopy(self.cfg)
  for atom in self.cfg['complete_offer_policy']['profiles'][0]['atoms']:atom['values']=dict.fromkeys(atom['values'],0)
  self.assertEqual(self.options(),[]);self.cfg=no
  self.obs['summary']['unrestrictedEarned']=0;self.assertEqual(self.options(),[])
  self.obs['summary']['unrestrictedEarned']=1000000000;self.cfg['horizon_days']=2;self.assertEqual(self.options(),[])
 def test_empty_paid_reach_has_no_acquisition_option(self):
  buyers={ident:buyer for ident,buyer in self.buyers.items() if ident in sorted(self.buyers)[:4]}
  self.assertFalse(any(o['kind']=='acquisition' for o in self.options(buyers=buyers)))
 def test_public_labels_and_hidden_budget_do_not_change_economic_routes(self):
  before=self.options();changed=copy.deepcopy(self.buyers)
  for buyer in changed.values():buyer.update(initial_budget=10**30,remaining_budget=1,private_atom=1)
  self.assertEqual(before,self.options(buyers=changed))
 def test_seed_eligible_current_locks_do_not_erase_earned_invoice_funds(self):
  self.cfg['capacity_price']=3000000;self.cfg['complete_offer_policy']['profiles'][0]['price_grids']['receivables_packet']=[28000000]
  self.cfg['strategic_allocation_policy']['sequence']['owned_available_bps']=10000
  self.obs['summary'].update(available=100000000,unrestrictedEarned=10000000)
  self.assertTrue(any(o['kind']=='capacity' and o['upfront_cost']==6000000 for o in self.options(delivery_reserve=50000000)))
  self.obs['summary']['unrestrictedEarned']=5000000;self.assertEqual(self.options(delivery_reserve=50000000),[])
  self.obs['summary'].update(available=55000000,unrestrictedEarned=10000000);self.assertEqual(self.options(delivery_reserve=50000000),[])
 def test_huge_declared_quantity_is_bounded_by_actual_supplier_room(self):
  before=self.options();self.cfg['strategic_allocation_policy']['capacity_menu']['max_quantity']=10**30
  self.assertEqual(before,self.options())
  self.cfg['production_hours']=30;self.cfg['supplier_outage_start_day']=3;self.cfg['supplier_outage_days']=1
  self.assertEqual(self.options(),[])
 def test_inactive_owned_customer_does_not_create_future_value(self):
  for buyer in self.buyers.values():buyer['active']=False
  self.assertEqual(self.options(),[])
 def test_each_context_requires_common_admitted_work(self):
  first=sorted(self.buyers)[0];self.cfg['complete_offer_policy']['requested_jobs'][first]=[]
  self.assertEqual(self.options(),[])

class ComposedInventoryOrigin(unittest.TestCase):
 def test_fixed_source_cohort_rejects_other_valid_seed_and_packet_count(self):
  import shutil
  from adaptive_enterprise.instruments import SOURCE_PATHS
  from connected_enterprise.composed_window049 import PROTOCOL,validate_inventory
  with tempfile.TemporaryDirectory(prefix='composed049-cohort-check-') as temporary:
   root=Path(temporary)
   for name in SOURCE_PATHS:
    target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
   def generate(seed,packets):
    if (root/'workloads').exists():shutil.rmtree(root/'workloads')
    m=prepare_complete_offer_services(root,'workloads/composed049',cohort_seed=seed,jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=packets,packet_rows=PROTOCOL['packet_rows']);m['native_engine']='exact-permanent-v2';return m
   original=generate(PROTOCOL['cohort_seed'],PROTOCOL['packet_jobs']);self.assertEqual(validate_inventory(original,root)['registered_jobs_rederived'],len(original['jobs']))
   for seed,packets in ((PROTOCOL['cohort_seed']+1,PROTOCOL['packet_jobs']),(PROTOCOL['cohort_seed'],PROTOCOL['packet_jobs']-1)):
    changed=generate(seed,packets)
    with self.assertRaisesRegex(ValueError,'REGISTERED_COMPOSED_COHORT_CHANGED'):validate_inventory(changed,root)

if __name__=='__main__':unittest.main()
