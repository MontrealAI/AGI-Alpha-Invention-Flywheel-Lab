import copy,csv,pathlib,tempfile,unittest
from datetime import datetime,timezone
from products.earth_omega.national import inspect_csv,FIELDS,hash_file
from products.earth_omega.earth import Invalid
class NationalTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.p=pathlib.Path(self.t.name)/'x.csv';self.now=datetime(2026,11,16,tzinfo=timezone.utc)
  self.leads=[{'id':'L','coordinates':[2.3,48.8],'nearby_public_stations':[{'station_id':'B'}]}]
  self.row=dict(id_pdc_itinerance='P1',id_station_itinerance='S1',consolidated_longitude='2.3',consolidated_latitude='48.8',consolidated_is_lon_lat_correct='true',date_maj='2026-11-01',datagouv_dataset_id='dataset',datagouv_resource_id='resource',datagouv_last_modified='2026-11-15',date_mise_en_service='2025-01-01',condition_acces='Accès libre',horaires='24/7')
 def write(self,rows):
  with self.p.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=sorted(FIELDS));w.writeheader();w.writerows(rows)
 def run_rows(self,rows):self.write(rows);return inspect_csv(self.p,self.leads,self.now)
 def test_count(self):self.assertEqual(self.run_rows([self.row])['comparisons'][0]['national_point_count'],1)
 def test_no_sum(self):
  c=self.run_rows([self.row])['comparisons'][0];self.assertEqual(c['belib_station_count_from_prior_snapshot'],1);self.assertNotIn('combined_count',c)
 def test_duplicate_quarantines_all(self):self.assertEqual(self.run_rows([self.row,self.row])['comparisons'][0]['national_point_count'],0)
 def test_duplicate_outside_bbox_quarantines_inside(self):
  other=dict(self.row,consolidated_latitude='44');self.assertEqual(self.run_rows([self.row,other])['comparisons'][0]['national_point_count'],0)
 def test_false_coordinates_excluded(self):
  self.row['consolidated_is_lon_lat_correct']='false';self.assertEqual(self.run_rows([self.row])['spatially_retained_unique_points'],0)
 def test_nan_excluded(self):
  self.row['consolidated_longitude']='nan';self.assertEqual(self.run_rows([self.row])['spatially_retained_unique_points'],0)
 def test_stale_not_retrieval(self):
  self.row['date_maj']='2025-01-01';self.assertEqual(self.run_rows([self.row])['comparisons'][0]['fresh_national_point_count'],0)
 def test_future_excluded(self):
  self.row['date_maj']='2027-01-01';self.assertEqual(self.run_rows([self.row])['spatially_retained_unique_points'],0)
 def test_future_commissioning_separate(self):
  self.row['date_mise_en_service']='2027-01-01';r=self.run_rows([self.row]);self.assertEqual(r['comparisons'][0]['national_point_count'],0);self.assertEqual(r['comparisons'][0]['future_commissioning_points_excluded'],['P1'])
 def test_restricted_access_retained_not_called_public(self):
  self.row['condition_acces']='Restricted';r=self.run_rows([self.row]);self.assertEqual(r['observation_table']['P1']['condition_acces'],'Restricted');self.assertIn('not confirmed operating',r['comparisons'][0]['count_scope'])
 def test_bad_schema(self):
  self.p.write_text('x\n1\n')
  with self.assertRaises(Invalid):inspect_csv(self.p,self.leads,self.now)
 def test_mainland_bound(self):
  self.write([self.row]);self.leads[0]['coordinates']=[-73,45]
  with self.assertRaises(Invalid):inspect_csv(self.p,self.leads,self.now)
 def test_radius(self):
  self.row['consolidated_longitude']='2.31';self.assertEqual(self.run_rows([self.row])['comparisons'][0]['national_point_count'],0)
 def test_missing_station(self):
  self.row['id_station_itinerance']='';self.assertEqual(self.run_rows([self.row])['spatially_retained_unique_points'],0)
 def test_hash_changes(self):
  self.write([self.row]);a=hash_file(self.p);self.p.write_text('tamper');self.assertNotEqual(a[0],hash_file(self.p)[0])
