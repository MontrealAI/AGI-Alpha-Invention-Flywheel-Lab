from pathlib import Path
import json, os, unittest
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[1]

class Ignition(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls): cls.browser.close();cls.p.stop()
 def setUp(self):
  self.page=self.browser.new_page(viewport={'width':1440,'height':1000});self.errors=[];self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.set_content((BASE/'index.html').read_text(),wait_until='load')
 def tearDown(self):
  self.page.close();self.assertEqual(self.errors,[])
 def build(self): self.page.locator('#ignition-run').click()
 def child(self):
  self.build();h=self.page.evaluate('FRONTIER_IGNITION.instrumentHTML(FRONTIER_IGNITION.current())');p=self.browser.new_page();p.on('pageerror',lambda e:self.errors.append(str(e)));p.set_content(h);return p,h
 def test_01_guided_construction_and_negative_control(self):
  self.build();r=self.page.evaluate('FRONTIER_IGNITION.current()');self.assertEqual(r['check']['checks'],54);self.assertTrue(r['negative_control']['rejected']);self.assertEqual(r['model_calls'],0);self.assertEqual(r['authority'],[]);self.assertFalse(r['commercial_acceptance']);self.assertIn('6',self.page.locator('#ignition-result').inner_text())
 def test_02_changed_purpose_revokes_current_export(self):
  self.build();self.page.locator('#ignition-purpose').fill('Changed objective');self.assertTrue(self.page.locator('#ignition-export').is_disabled());self.assertIsNone(self.page.evaluate('FRONTIER_IGNITION.state.current'));self.assertEqual(self.page.evaluate('FRONTIER_IGNITION.state.historical.length'),1)
 def test_03_changed_actual_contract_changes_construction(self):
  self.page.locator('#ignition-domain').fill('0, 1, 2, 3');self.build();self.assertEqual(self.page.evaluate('FRONTIER_IGNITION.current().check.labels'),10);self.page.locator('#ignition-scope').select_option('upper');self.assertTrue(self.page.locator('#ignition-export').is_disabled());self.build();self.assertEqual(self.page.evaluate('FRONTIER_IGNITION.current().check.labels'),4)
 def test_04_complete_ambition_handoff(self):
  mission='MONTREAL.AI — retain evidence for our next valuable construction.';self.page.locator('#ambition').fill(mission);self.page.locator('#investigate').click();self.page.locator('#toward-mechanisms').click();self.page.locator('#toward-build').click();self.page.locator('#ignition-carry').click();self.assertEqual(self.page.locator('#ignition-purpose').input_value(),mission);self.build();self.assertIsNotNone(self.page.evaluate('FRONTIER_IGNITION.current().selected_research_lead'))
 def test_05_portable_batch_and_fail_closed(self):
  p,h=self.child()
  try:
   p.locator('#query').select_option('1');p.locator('#batch-run').click();self.assertIn('2 records checked',p.locator('#batch-result').inner_text());p.locator('#batch-rows').fill('60,60\n61,80');p.locator('#batch-run').click();self.assertIn('BATCH REFUSED',p.locator('#batch-result').inner_text());self.assertIn('No partial',p.locator('#batch-detail').inner_text());p.locator('#batch-rows').fill('60,60');p.locator('#batch-run').click();self.assertIn('1 records checked',p.locator('#batch-result').inner_text());p.locator('#query').select_option('2');self.assertIn('No current',p.locator('#batch-detail').inner_text())
  finally:p.close()
 def test_06_hostile_text_remains_data_in_export(self):
  payload='</script><script>window.HACKED=1</script><img src=x onerror="window.HACKED=1">'
  self.page.locator('#ignition-purpose').fill(payload);self.page.locator('#ignition-name').fill(payload[:100]);p,h=self.child()
  try:self.assertIsNone(p.evaluate('window.HACKED'));self.assertIn(payload,p.locator('#purpose').inner_text());self.assertIsNone(self.page.evaluate('window.HACKED'))
  finally:p.close()
 def test_07_invalid_contract_refuses(self):
  self.page.locator('#ignition-domain').fill('0,,1');self.build();self.assertTrue(self.page.locator('#ignition-export').is_disabled());self.assertIn('NOT CONSTRUCTED',self.page.locator('#ignition-status').inner_text());self.assertIsNone(self.page.evaluate('FRONTIER_IGNITION.state.current'))
 def test_08_session_export_contains_current_contract(self):
  self.build()
  with self.page.expect_download() as d:self.page.locator('#download-session').click()
  p=BASE/'evidence'/'ignition-session.json';d.value.save_as(p);r=json.loads(p.read_text());self.assertEqual(r['ignition']['check']['checks'],54);self.assertEqual(r['model_calls'],0)
 def test_09_mobile_contract_and_export(self):
  for width in (360,390):
   self.page.set_viewport_size({'width':width,'height':844});self.build();self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width);self.assertTrue(self.page.locator('#ignition-export').is_enabled())
 def test_10_no_network_during_construction(self):
  requests=[];self.page.on('request',lambda r:requests.append(r.url));self.build();self.assertEqual(requests,[])
 def test_11_edited_ambition_invalidates_dossier(self):
  self.page.locator('#ambition').fill('A software migration');self.page.locator('#investigate').click();self.page.locator('#step-1').click();self.page.locator('#ambition').fill('Another objective');self.assertIsNone(self.page.evaluate('FRONTIER_WORLD_LAB.S.selected'))
