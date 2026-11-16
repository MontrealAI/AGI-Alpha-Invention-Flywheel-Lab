import copy, unittest
from datetime import datetime, timezone
from products.earth_omega.discovery import discover_records
class DiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,11,16,tzinfo=timezone.utc)
  self.p={'id':'P','nom':'Example','nb_places':200,'nb_voitures_electriques':None,'xlong':2.3,'ylat':48.8,'mis_a_jour':'2026-11-01T00:00:00Z'}
  self.c={'statut_pdc':'En service','id_station_local':'C','id_pdc_local':'C1','coordonneesxy':{'lon':2.3,'lat':48.8},'date_maj':'2026-11-01'}
 def test_discovers_without_operator_candidates(self):
  r=discover_records([self.p],[self.c],self.now); self.assertEqual(len(r['leads']),1); self.assertEqual(r['qualified_commercial_sites'],0)
 def test_unknown_not_zero(self): self.assertIsNone(discover_records([self.p],[],self.now)['leads'][0]['spaces_not_in_reported_non_pmr_ev_category'])
 def test_groups_charging_points_by_station(self):
  r=discover_records([self.p],[self.c,dict(self.c,id_pdc_local='C2')],self.now); self.assertEqual(len(r['leads'][0]['nearby_public_stations']),1); self.assertEqual(r['leads'][0]['nearby_public_stations'][0]['points'],2)
 def test_duplicate_point_rejected(self):
  r=discover_records([self.p],[self.c,self.c],self.now); self.assertEqual(r['input_counts']['invalid_charging_records'],2); self.assertEqual(r['leads'][0]['nearby_public_stations'],[])
 def test_station_geometry_order_independent(self):
  c2=dict(self.c,id_pdc_local='C2',coordonneesxy={'lon':3,'lat':48})
  a=discover_records([self.p],[self.c,c2],self.now); b=discover_records([self.p],[c2,self.c],self.now)
  self.assertEqual(a['leads'],b['leads'])
 def test_exact_freshness_boundary(self):
  from datetime import timedelta
  self.c['date_maj']='2026-08-18'
  now=datetime(2026,11,16,23,tzinfo=timezone.utc)
  r=discover_records([self.p],[self.c],now); self.assertFalse(r['leads'][0]['nearby_public_stations'][0]['fresh'])
 def test_stale(self):
  self.p['mis_a_jour']='2025-01-01T00:00:00Z'; self.assertIn('fresh_parking_inventory',discover_records([self.p],[],self.now)['leads'][0]['evidence_needed'])
 def test_missing_station_id(self):
  self.c['id_station_local']=None; self.assertEqual(discover_records([self.p],[self.c],self.now)['input_counts']['invalid_charging_records'],1)
 def test_capacity_exclusion(self): self.assertEqual(len(discover_records([self.p],[],self.now,300)['leads']),0)
 def test_duplicate(self): self.assertEqual(len(discover_records([self.p,self.p],[],self.now)['leads']),1)
 def test_future_rejected(self):
  self.p['mis_a_jour']='2027-01-01T00:00:00Z'; self.assertEqual(len(discover_records([self.p],[],self.now)['leads']),0)
 def test_bad_charger_not_silent(self): self.assertEqual(discover_records([self.p],[{}],self.now)['input_counts']['invalid_charging_records'],0) # not in service, excluded
 def test_invalid_capacity(self):
  self.p['nb_voitures_electriques']=201; self.assertEqual(len(discover_records([self.p],[],self.now)['leads']),0)
 def test_bounded_inputs(self):
  with self.assertRaises(ValueError): discover_records('bad',[],self.now)
