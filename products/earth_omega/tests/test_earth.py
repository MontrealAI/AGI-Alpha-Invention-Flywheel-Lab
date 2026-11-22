import copy, hashlib, json, pathlib, tempfile, unittest
from products.earth_omega.earth import *
from products.earth_omega.importers import normalize
from products.earth_omega.agent import run, deterministic_policy, Investigation, HarnessCodexPlanner
EXAMPLE=pathlib.Path(__file__).parents[1]/'examples/mission.json'
class EarthTests(unittest.TestCase):
 def setUp(self): self.m=load(EXAMPLE)
 def test_duplicate_location(self):
  duplicate=copy.deepcopy(self.m['sites'][0]); duplicate.update(id='copy',demand_group='different'); self.m['sites'].append(duplicate)
  with self.assertRaises(Invalid): screen(self.m)
 def test_float_years(self):
  self.m['sites'][0]['economics']['years']=8.0; screen(self.m)
 def test_cost_coverage_required(self):
  for site in self.m['sites']: site['economics'].pop('cost_coverage',None)
  self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],[])
 def test_cost_not_applicable_needs_reason(self):
  for site in self.m['sites']: site['economics']['cost_coverage']['grid']={'status':'not_applicable','basis':''}
  self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],[])
 def test_fixture(self):
  r=screen(self.m); self.assertEqual(r['portfolio']['selected_site_ids'],['B']); self.assertEqual(r['evidence_mode'],'fixture')
 def test_cash_formula_independent(self):
  e=self.m['sites'][0]['economics']; r=economics(e)
  expected=-50000+sum((200*365*.3-6000)/1.1**y for y in range(1,9))
  self.assertAlmostEqual(r['npv_money_range'][0],expected,places=2)
 def test_missing_grid_not_positive(self): self.assertEqual(next(r for r in screen(self.m)['sites'] if r['id']=='C')['status'],'NEEDS_EVIDENCE')
 def test_no_build(self):
  self.m['budget_money']=0; self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],[])
 def test_overlap(self):
  self.m['budget_money']=1e6; self.assertLessEqual(len(screen(self.m)['portfolio']['selected_site_ids']),1)
 def test_positive_does_not_mean_cash(self): self.assertTrue(screen(self.m)['portfolio']['not_authorization_to_invest'])
 def test_duplicate(self):
  self.m['sites'][1]['id']='A'
  with self.assertRaises(Invalid): screen(self.m)
 def test_nan(self):
  self.m['sites'][0]['economics']['capex_money']=float('nan')
  with self.assertRaises(Invalid): screen(self.m)
 def test_bool(self):
  self.m['budget_money']=True
  with self.assertRaises(Invalid): screen(self.m)
 def test_coordinate(self):
  self.m['sites'][0]['coordinates']=[-200,45]
  with self.assertRaises(Invalid): screen(self.m)
 def test_future(self):
  self.m['as_of']='2025-01-01T00:00:00Z'
  with self.assertRaises(Invalid): screen(self.m)
 def test_timezone(self):
  with self.assertRaises(Invalid): stamp('2026-01-01')
 def test_stale(self):
  self.m['max_age_days']=1; self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],[])
 def test_unknown_cost(self):
  self.m['sites'][1]['economics']['unpriced_costs']=['grid upgrade']; self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],['A'])
 def test_negative_margin(self):
  e=self.m['sites'][0]['economics']; e['variable_cost_money_per_kwh']=.9; self.assertIsNone(economics(e)['break_even_daily_kwh'])
 def test_negative_npv(self): self.assertEqual(next(r for r in screen(self.m)['sites'] if r['id']=='D')['status'],'NO_BUILD_IN_SCENARIO')
 def test_observation_not_demand(self):
  a=screen(self.m)['portfolio']; self.m['observations'][0]['daily_kwh']=1e7; self.assertEqual(a,screen(self.m)['portfolio'])
 def test_distance(self): self.assertEqual(distance([0,0],[0,0]),0); self.assertAlmostEqual(distance([0,0],[1,0]),111.195,places=2)
 def test_render_escape(self):
  self.m['sites'][0]['id']='<script>alert(1)</script>'; self.assertNotIn('<script>',render(screen(self.m)))
 def test_trace(self):
  r=run(self.m,deterministic_policy); self.assertEqual(len(r['trace']),6); self.assertEqual(r['report'],screen(self.m))
 def test_tool_injection(self):
  with self.assertRaises(Invalid): Investigation(self.m).step({'tool':'shell','command':'rm -rf /'})
 def test_early_finish(self):
  with self.assertRaises(Invalid): Investigation(self.m).step({'tool':'finish'})
 def test_bound(self):
  with self.assertRaises(Invalid): run(self.m,lambda *_:{'tool':'inspect_site','site_id':'A'},max_steps=3)
 def test_strict_model_json(self):
  class S:
   def generate(self,request): return {'text':'```json\n{}\n```'}
  with self.assertRaises(Invalid): HarnessCodexPlanner(S(),'available-model')('prompt',{})
 def test_model_adapter(self):
  class S:
   def generate(self,request):
    self.request=request; return {'text':'{"tool":"compare"}'}
  s=S(); self.assertEqual(HarnessCodexPlanner(s,'selected-model')('prompt',{})['tool'],'compare'); self.assertEqual(s.request['model'],'selected-model')
 def test_import_snapshot(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d); raw=json.dumps({'results':[{'statut_pdc':'En service','id_pdc_local':'test','coordonneesxy':{'lon':2,'lat':48},'date_maj':'2026-10-06'}]}).encode()
   (p/'source.raw').write_bytes(raw); (p/'receipt.json').write_text(json.dumps({'source':SOURCES['paris'],'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at':'2026-11-16T00:00:00Z'}))
   r=normalize(p,'paris'); self.assertEqual(r['observations'][0]['observed_at'],'2026-10-06T00:00:00Z')
   (p/'source.raw').write_bytes(raw+b' ')
   with self.assertRaises(Invalid): normalize(p,'paris')
 def test_monthly_utilization_contract(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d); raw=b'Numero_borne;Nombre_kwh_total;Annee;Mois;Latitude;Longitude\nT;280;2026;2;45.5;-73.5\n'
   (p/'source.raw').write_bytes(raw); (p/'receipt.json').write_text(json.dumps({'source':SOURCES['utilization'],'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at':'2026-11-16T00:00:00Z'}))
   r=normalize(p,'utilization'); self.assertEqual(r['observations'][0]['daily_kwh'],10)
 def test_montreal_requires_observation_date(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d); raw=b'{"features":[]}'
   (p/'source.raw').write_bytes(raw); (p/'receipt.json').write_text(json.dumps({'source':SOURCES['chargers'],'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at':'2026-11-16T00:00:00Z'}))
   with self.assertRaises(Invalid): normalize(p,'chargers')
 def test_source_redirect(self):
  with self.assertRaises(Invalid): NoRedirect().redirect_request(None,None,None,None,None,None)
 def test_schema(self):
  self.m['schema']='x'
  with self.assertRaises(Invalid): screen(self.m)
 def test_range(self):
  self.m['sites'][0]['economics']['daily_kwh_range']=[100,10]
  with self.assertRaises(Invalid): screen(self.m)
 def test_constraint_rejection(self):
  self.m['sites'][1]['constraints']['site_control']['status']='no'; self.assertEqual(screen(self.m)['portfolio']['selected_site_ids'],['A'])
 def test_hash_changes(self):
  a=screen(self.m)['input_sha256']; self.m['budget_money']=0; self.assertNotEqual(a,screen(self.m)['input_sha256'])
if __name__=='__main__': unittest.main()
