from pathlib import Path
import unittest,json,os
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parents[1]
class Browser(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def setUp(self):
  self.page=self.browser.new_page(viewport={'width':1440,'height':1000});self.errors=[];self.page.on('pageerror',lambda e:self.errors.append(str(e)));self.page.set_content((BASE/'index.html').read_text(),wait_until='load')
 def tearDown(self):
  errors=list(self.errors);self.page.close();self.assertEqual(errors,[])
 def test_01_branding_and_research_map(self):
  self.assertIn('Capturing the Exponential',self.page.title());self.assertEqual(self.page.locator('.paper-link').count(),11);self.assertIn('BUILT IN MONTRÉAL',self.page.locator('.heritage').inner_text());self.assertEqual(self.page.locator('.story .year').count(),2)
 def test_02_construct_and_change_scope(self):
  self.page.locator('#mm-challenge').click();self.assertIn('[60, 100]',self.page.locator('#mm-witness').inner_text());self.page.locator('#mm-build').click();self.assertEqual(self.page.locator('#mm-labels').inner_text(),'3');self.page.locator('#mm-successor').click();self.assertEqual(self.page.locator('#mm-next-labels').inner_text(),'6');self.assertEqual(self.page.locator('#mm-checks').inner_text(),'90');self.page.locator('#mm-tamper').click();self.assertIn('REJECTED',self.page.locator('#mm-export-status').inner_text())
 def test_03_custom_domain_and_invalidation(self):
  self.page.locator('#mm-domain').fill('0, 1, 2, 3');self.page.locator('#mm-build').click();self.assertEqual(self.page.locator('#mm-labels').inner_text(),'4');self.page.locator('#mm-successor').click();self.assertEqual(self.page.locator('#mm-next-labels').inner_text(),'10');self.page.locator('#mm-domain').fill('0, 1, 2');self.assertTrue(self.page.locator('#mm-export').is_disabled());self.page.locator('#mm-domain').fill('0, , 2');self.page.locator('#mm-build').click();self.assertIn('no empty fields',self.page.locator('#mm-parent').inner_text())
 def test_04_generated_instrument_executes_and_rejects(self):
  self.page.locator('#mm-successor').click();html=self.page.evaluate('FRONTIER_STUDIO.instrumentHTML(FRONTIER_STUDIO.state.child)');child=self.browser.new_page();errors=[];child.on('pageerror',lambda e:errors.append(str(e)));child.set_content(html);child.locator('#a').fill('60');child.locator('#b').fill('100');child.locator('#run').click();self.assertIn('raw-input check agrees',child.locator('#check').inner_text());child.locator('#a').fill('61');child.locator('#run').click();self.assertIn('REFUSED',child.locator('#answer').inner_text());child.locator('#a').fill('');child.locator('#run').click();self.assertIn('REFUSED',child.locator('#answer').inner_text());self.assertEqual(errors,[]);child.close()
 def test_05_exact_observation_and_stress(self):
  self.page.locator('#studio-tab-measure').click();self.page.locator('#learn-run').click();self.assertEqual(self.page.locator('#learn-candidates').inner_text(),'448');self.assertEqual(self.page.locator('#learn-cost').inner_text(),'13');self.assertEqual(self.page.locator('#learn-radius').inner_text(),'3/1003');self.page.locator('#learn-break').click();self.assertEqual(self.page.locator('#learn-radius').inner_text(),'INVALID');self.assertIn('false',self.page.locator('#learn-log').inner_text())
 def test_06_reuse_horizon_and_export(self):
  self.page.locator('#studio-tab-measure').click();self.page.locator('#learn-uses').fill('20');self.page.locator('#learn-run').click();self.assertEqual(self.page.locator('#learn-cost').inner_text(),'136.3');self.assertEqual(self.page.locator('#learn-radius').inner_text(),'1/334');self.page.locator('#learn-uses').fill('30');self.assertTrue(self.page.locator('#learn-export').is_disabled())
 def test_07_original_journey_preserved(self):
  self.page.locator('[data-sample="industrial"]').click();self.page.locator('#investigate').click();self.assertEqual(self.page.locator('#signals button').count(),5);self.page.locator('#signals button').nth(2).click();self.page.locator('#toward-mechanisms').click();self.assertEqual(self.page.locator('#mechanisms button').count(),8);self.page.locator('#toward-build').click();self.assertIn('Construction Witness',self.page.locator('#brief-title').inner_text())
 def test_08_original_three_experiments(self):
  self.page.locator('#run-causal').click();self.assertEqual(self.page.evaluate('FRONTIER_WORLD_LAB.S.causal.correct'),8191);self.page.locator('[data-lab="market"]').click();self.page.locator('#run-market').click();self.assertAlmostEqual(self.page.evaluate('FRONTIER_WORLD_LAB.S.market.expected_contribution'),120);self.page.locator('[data-lab="builder"]').click();self.page.locator('#run-builder').click();self.assertEqual(self.page.evaluate('FRONTIER_WORLD_LAB.S.builder.passed'),4000)
 def test_09_mobile_no_overflow(self):
  for width in [390,360]:
   self.page.set_viewport_size({'width':width,'height':844});self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width);self.page.locator('#mm-successor').click();self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width);self.page.locator('#studio-tab-measure').click();self.page.locator('#learn-run').click();self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),width);self.page.locator('#studio-tab-missing').click()
 def test_10_downloaded_evidence_is_executed_not_placeholder(self):
  self.page.locator('#mm-successor').click()
  with self.page.expect_download() as info:self.page.locator('#mm-evidence').click()
  d=info.value;p=BASE/'evidence'/'browser-export.json';d.save_as(p);x=json.loads(p.read_text());self.assertEqual(x['current_parent_check']['checks'],36);self.assertEqual(x['current_successor_check']['checks'],54);self.assertFalse(x['commercial_acceptance'])
 def test_11_complete_session_export_contains_new_constructions(self):
  self.page.locator('#mm-successor').click();self.page.locator('#studio-tab-measure').click();self.page.locator('#learn-run').click()
  with self.page.expect_download() as info:self.page.locator('#download-session').click()
  p=BASE/'evidence'/'complete-session.json';info.value.save_as(p);x=json.loads(p.read_text());c=x['construction_studio'];self.assertEqual(len(c['parent']['decoders']),3);self.assertEqual(len(c['successor']['decoders']),6);self.assertEqual(c['measurement']['best']['radius'],'3/1003');self.assertIn('No live model inference',x['limits'])
if __name__=='__main__':unittest.main(verbosity=2)
