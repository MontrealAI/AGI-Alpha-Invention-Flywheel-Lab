"""Exposed causal wiring/recovery fixtures, not market or profit confirmation."""
import copy, json, tempfile, unittest
from pathlib import Path
from tests.test_connected_complete_offer import fixture
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import run_world, validate_config
from connected_enterprise.verify import audit
from connected_enterprise.complete_offer_market import private_atom
ROOT=Path(__file__).resolve().parents[1]

def config(manifest,enabled=True):
 cfg=fixture(manifest,'menu');cfg.update(horizon_days=1)
 p=cfg['complete_offer_policy']['profiles'][0]
 p['outside_options']=[]
 values={s:0 for s in p['services']};values['receivables_packet']=100_000_000
 p['atoms']=[{'weight_bps':5000,'budget_microUSD':300_000_000,'values':dict.fromkeys(p['services'],0)}, {'weight_bps':5000,'budget_microUSD':300_000_000,'values':values}]
 if enabled:cfg['refusal_recourse_policy']={'schema':'connected-refusal-recourse/v1','daily_planning_cost':100_000}
 return cfg

class RefusalRecourseOperating(unittest.TestCase):
 def test_refusal_reassignment_prepaid_audit_and_recovery(self):
  with tempfile.TemporaryDirectory(prefix='.recourse-',dir=ROOT) as folder:
   folder=Path(folder)
   m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2611010338,packet_jobs=8,packet_rows=40)
   cfg=config(m)
   # Choose exposed private-response test data, not an economic confirmation seed.
   seed=next(s for s in range(100) if private_atom(cfg['complete_offer_policy'],'SIM-customer-000',s)==1 and private_atom(cfg['complete_offer_policy'],'SIM-customer-001',s)==0)
   result=run_world(ROOT,m,cfg,seed,'competitive_growth',folder/'full')
   self.assertTrue(audit(ROOT,m,result)['accepted'])
   trace=next(iter(result['joint_actions'].values()))['refusal_recourse']
   self.assertGreaterEqual(len(trace['attempts']),2)
   self.assertFalse(trace['attempts'][0]['accepted']);self.assertTrue(trace['attempts'][1]['accepted'])
   self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='prepaid_finite_refusal_recourse'),100_000)
   self.assertTrue(any(o['joint_recourse_round']>0 for o in result['orders']))
   for mutate in (lambda x:next(iter(x['joint_actions'].values()))['refusal_recourse']['attempts'][0].update(accepted=True),lambda x:x['orders'][0].update(joint_recourse_round=0)):
    bad=copy.deepcopy(result);mutate(bad)
    with self.assertRaises(ValueError):audit(ROOT,m,bad)
   def fail(stage,state,account):
    if state['current']['event']['kind']=='plan':raise RuntimeError('EXPOSED_RECOVERY_FAILPOINT')
   with self.assertRaisesRegex(RuntimeError,'EXPOSED_RECOVERY_FAILPOINT'):
    run_world(ROOT,m,cfg,seed,'competitive_growth',folder/'resume',failpoint=fail)
   recovered=run_world(ROOT,m,cfg,seed,'competitive_growth',folder/'resume')
   self.assertTrue(audit(ROOT,m,recovered)['accepted'])
   trajectory=lambda r:[(a['op'],a['day'],a['before'],a['after']) for a in r['owned_account']['ledger']['actions']]
   self.assertEqual(trajectory(result),trajectory(recovered));self.assertEqual(result['summary'],recovered['summary'])
   self.assertEqual(result['decisions'],recovered['decisions'])
   # A crash after the second prepaid debit but before the sealed plan must replay
   # both named costs idempotently, without charging or contacting twice.
   from unittest.mock import patch
   from connected_enterprise import engine
   original_prepare=engine._prepare_plan
   def interrupted_prepare(state,account,jobs):
    if state['queue'][0]['kind']=='plan':raise RuntimeError('AFTER_PREPAID_BEFORE_PLAN')
    return original_prepare(state,account,jobs)
   with patch.object(engine,'_prepare_plan',interrupted_prepare):
    with self.assertRaisesRegex(RuntimeError,'AFTER_PREPAID_BEFORE_PLAN'):
     run_world(ROOT,m,cfg,seed,'competitive_growth',folder/'prepaid-interruption')
   prepaid_recovered=run_world(ROOT,m,cfg,seed,'competitive_growth',folder/'prepaid-interruption')
   self.assertTrue(audit(ROOT,m,prepaid_recovered)['accepted'])
   self.assertEqual(trajectory(result),trajectory(prepaid_recovered))
   self.assertEqual(result['decisions'],prepaid_recovered['decisions'])
   baseline=run_world(ROOT,m,config(m,False),seed,'competitive_growth',folder/'baseline')
   self.assertTrue(audit(ROOT,m,baseline)['accepted'])
   self.assertFalse(any('refusal_recourse' in w for w in baseline['joint_actions'].values()))
   self.assertLess(len(baseline['orders']),len(result['orders']))
   refusal_seed=next(s for s in range(100) if all(private_atom(cfg['complete_offer_policy'],f'SIM-customer-{i:03d}',s)==0 for i in (0,1)))
   refused=run_world(ROOT,m,cfg,refusal_seed,'competitive_growth',folder/'all-refused')
   self.assertTrue(audit(ROOT,m,refused)['accepted']);self.assertEqual(refused['orders'],[])
   refused_trace=next(iter(refused['joint_actions'].values()))['refusal_recourse']
   self.assertEqual(len(refused_trace['attempts']),2);self.assertTrue(all(not a['accepted'] for a in refused_trace['attempts']))
   self.assertEqual(sum(c['amount'] for c in refused['costs'] if c['category']=='prepaid_finite_refusal_recourse'),100_000)
   tight=copy.deepcopy(cfg);tight.update(opening=100_000_000,working=1_000_000)
   unfunded=run_world(ROOT,m,tight,seed,'competitive_growth',folder/'cash-tight')
   self.assertTrue(audit(ROOT,m,unfunded)['accepted']);self.assertEqual(unfunded['orders'],[])
   self.assertEqual(next(iter(unfunded['joint_actions'].values()))['refusal_recourse']['attempts'],[])
   print('EXPOSED_NATIVE_RECEIPT '+json.dumps({name:{'orders':len(world['orders']),'expenses':world['summary']['expenses'],'profit':world['summary']['profit'],'planning_fee':sum(c['amount'] for c in world['costs'] if c['category']=='prepaid_finite_refusal_recourse')} for name,world in [('baseline',baseline),('recourse',result),('all_refused',refused),('cash_tight',unfunded)]},sort_keys=True),flush=True)
   insolvent=copy.deepcopy(cfg);insolvent.update(opening=50_000_000,working=1_000_000)
   from connected_enterprise import engine
   with patch('connected_enterprise.joint_planning.plan_actions',side_effect=AssertionError('UNFUNDED_SOLVER_CALLED')):
    with self.assertRaisesRegex(ValueError,'RECOURSE_PLANNING_NOT_FUNDED'):
     run_world(ROOT,m,insolvent,seed,'competitive_growth',folder/'unfunded-planning')
   from connected_enterprise.engine import fresh_account_config
   exactcfg,exactm=fresh_account_config(m,root=ROOT)
   exact=copy.deepcopy(cfg);exact['monetary_policy']=exactcfg['monetary_policy']
   exactresult=run_world(ROOT,exactm,exact,seed,'competitive_growth',folder/'exact')
   self.assertTrue(audit(ROOT,exactm,exactresult)['accepted']);self.assertEqual(exactresult['summary'],result['summary'])
   badcfg=copy.deepcopy(cfg);badcfg['strategic_allocation_policy']['risk']['interactions']=[{'unsupported':True}]
   with self.assertRaises(ValueError):validate_config(badcfg)

class SelectiveRecourseOperating(unittest.TestCase):
 def test_purchase_hold_exact_quote_public_audit_and_charge_recovery(self):
  from unittest.mock import patch
  from connected_enterprise import engine
  with tempfile.TemporaryDirectory(prefix='.selective-recourse-',dir=ROOT) as folder:
   folder=Path(folder)
   m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2611010481,packet_jobs=8,packet_rows=40)
   cfg=config(m);cfg['refusal_recourse_policy']={'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':100_000,'daily_evaluation_cost':10_000}
   cfg['strategic_policy']['ranking_arithmetic']='exact-rational-v1'
   result=run_world(ROOT,m,cfg,2,'competitive_growth',folder/'purchase')
   self.assertTrue(audit(ROOT,m,result)['accepted'])
   wrapper=next(iter(result['joint_actions'].values()))
   self.assertTrue(wrapper['selective_recourse_decision']['purchase'])
   self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='prepaid_finite_refusal_recourse'),100_000)
   self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='selective_recourse_public_evaluation'),10_000)
   for mutate in (lambda x:next(iter(x['joint_actions'].values()))['selective_recourse_decision'].update(purchase=False),lambda x:next(iter(x['joint_actions'].values()))['selective_recourse_decision']['expected_increment_microUSD'].update(numerator=1)):
    bad=copy.deepcopy(result);mutate(bad)
    with self.assertRaises(ValueError):audit(ROOT,m,bad)
   holdcfg=copy.deepcopy(cfg);holdcfg['strategic_allocation_policy']['max_customers']=1
   hold=run_world(ROOT,m,holdcfg,2,'competitive_growth',folder/'hold')
   self.assertTrue(audit(ROOT,m,hold)['accepted'])
   holdwrapper=next(iter(hold['joint_actions'].values()))
   self.assertFalse(holdwrapper['selective_recourse_decision']['purchase'])
   self.assertNotIn('refusal_recourse',holdwrapper)
   self.assertFalse(any(c['category']=='prepaid_finite_refusal_recourse' for c in hold['costs']))
   self.assertEqual(sum(c['amount'] for c in hold['costs'] if c['category']=='selective_recourse_public_evaluation'),10_000)
   trajectory=lambda r:[(a['op'],a['day'],a['before'],a['after']) for a in r['owned_account']['ledger']['actions']]
   original_prepare=engine._prepare_plan
   def fail_after_allowance(*args,**kwargs):
    if kwargs.get('selective_purchase') is True:raise RuntimeError('AFTER_SELECTIVE_ALLOWANCE_BEFORE_PLAN')
    return original_prepare(*args,**kwargs)
   with patch.object(engine,'_prepare_plan',fail_after_allowance):
    with self.assertRaisesRegex(RuntimeError,'AFTER_SELECTIVE_ALLOWANCE_BEFORE_PLAN'):
     run_world(ROOT,m,cfg,2,'competitive_growth',folder/'recover')
   recovered=run_world(ROOT,m,cfg,2,'competitive_growth',folder/'recover')
   self.assertTrue(audit(ROOT,m,recovered)['accepted']);self.assertEqual(trajectory(result),trajectory(recovered));self.assertEqual(result['decisions'],recovered['decisions'])

if __name__=='__main__':unittest.main()
