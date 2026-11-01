"""Exposed operating wiring, not a calibrated market or profit confirmation."""
import copy,json,importlib.util,tempfile,unittest
from pathlib import Path
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import run_world
from connected_enterprise.verify import audit
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('common_runner',ROOT/'scripts/run_commoncost026.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def fixture(manifest,selection):
 m=manifest
 services=['reconciliation','kpi_variance','evidence_matrix','receivables_packet'];values=dict.fromkeys(services,30_000_000);values['receivables_packet']=100_000_000
 profile={'id':'exposed-arithmetic-request','services':services,'price_grids':{s:[20_000_000] if s!='receivables_packet' else [50_000_000] for s in services},'atoms':[{'weight_bps':5000,'budget_microUSD':300_000_000,'values':values},{'weight_bps':5000,'budget_microUSD':120_000_000,'values':{s:v//2 for s,v in values.items()}}],'outside_options':[{'name':'competent-human-packet','provider':'human','service_id':'receivables_packet','price':80_000_000,'quality_bps':10000,'delay_cost':0},{'name':'autonomous-packet','provider':'rival','service_id':'receivables_packet','price':65_000_000,'quality_bps':10000,'delay_cost':0},{'name':'self-service-packet','provider':'self_service','service_id':'receivables_packet','price':15_000_000,'quality_bps':6000,'delay_cost':5_000_000}]}
 # Exposed wiring fixture: deterministic high-value atom exercises actual packet production, not an economic confirmation.
 profile['atoms']=[{'weight_bps':10000,'budget_microUSD':300_000_000,'values':values}]
 requested={f'SIM-customer-{i:03d}':[j['id'] for j in m['jobs'] if j['service_id'] in services and int(sorted(jj['id'] for jj in m['jobs'] if jj['service_id']==j['service_id']).index(j['id']))%4==i] for i in range(4)}
 base=r.config('smoke','central','joint');base.update(horizon_days=4,customer_pool=4,initial_slots=3,maximum_slots=3,arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,clearing_hours=1);base['strategic_allocation_policy']['max_customers']=2
 base['complete_offer_policy']={'schema':'connected-complete-offer-market/v1','selection':selection,'profiles':[profile],'requested_jobs':requested}
 return base

class CompleteOfferOperating(unittest.TestCase):
 def test_packet_native_cost_capacity_request_and_audit(self):
  with tempfile.TemporaryDirectory(prefix='.complete-offer-',dir=ROOT) as folder:
   folder=Path(folder)
   m=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312145,packet_jobs=8,packet_rows=40)
   results={}
   for arm in ('restricted','menu'):
    result=run_world(ROOT,m,fixture(m,arm),2610312145,'competitive_growth',folder/arm)
    self.assertTrue(audit(ROOT,m,result)['accepted']);results[arm]=result
   result=results['menu'];self.assertTrue(result['orders'])
   packets=[o for o in result['orders'] if o['offer']['service_id']=='receivables_packet'];self.assertTrue(packets)
   cfg=result['config']
   for o in packets:
    self.assertEqual(o['capacity_units'],3)
    self.assertEqual(o['production_cost'],3*(cfg['production_cost']+cfg['supplier_unit_cost']))
    self.assertEqual(o['support_cost'],3*cfg['support_cost'])
    self.assertEqual(len(o['work_keys']),3)
    self.assertIn(o['job_id'],cfg['complete_offer_policy']['requested_jobs'][o['customer_id']])
    self.assertTrue(o['service_receipt']['accepted'])
   # Native and operating tampering must fail, not silently become changed assumptions.
   for mutate in (lambda x:x['orders'][0].update(capacity_units=1),lambda x:x['orders'][0].update(production_cost=1),lambda x:next(d for d in x['decisions'] if d.get('kind')=='outside_choice').update(outside_spend=999),lambda x:next(iter(x['joint_actions'].values()))['evaluation_cost'].update(fixed_evaluation_cost=0)):
    bad=copy.deepcopy(result);mutate(bad)
    with self.assertRaises(ValueError):audit(ROOT,m,bad)
   badcfg=fixture(m,'menu');badcfg['complete_offer_policy']['requested_jobs']['SIM-customer-000']=['not-admitted']
   with self.assertRaisesRegex(ValueError,'PREDECLARED_ADMITTED_CUSTOMER_REQUESTS_REQUIRED'):
    run_world(ROOT,m,badcfg,1,'competitive_growth',folder/'invalid')
   self.assertFalse((folder/'invalid'/'account.sqlite').exists())
if __name__=='__main__':unittest.main()
