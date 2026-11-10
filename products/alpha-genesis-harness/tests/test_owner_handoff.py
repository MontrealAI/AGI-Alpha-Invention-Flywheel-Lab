import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('owner_handoff',HERE.parent/'scripts'/'owner_handoff.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
SOURCE='a'*40

class OwnerHandoffTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.assets=self.root/'assets';self.assets.mkdir()
  self.op=self.root/'operation';self.op.mkdir()
  self.archive=self.assets/'ALPHA_GENESIS_HARNESS_0.3.0_source-bound_aaaaaaaaaaaa.zip'
  matrix={'criteria':[{'id':'B3','requirement':'Live Pro <script>alert(1)</script>','status':'BLOCKED','actual_test_or_required_procedure':'Real consent','remaining_dependency_or_scope':'Eligible consent is missing','evidence_location':'fixture'}, {'id':'D1','requirement':'Synthetic artifact fixture','status':'PASS','actual_test_or_required_procedure':'Fixture','remaining_dependency_or_scope':'Test only'}]}
  self.content={
   'START-HERE.html':b'<html>synthetic fixture</html>',
   'VERSION.json':b'{"version":"0.3.0"}',
   'LICENSE':b'synthetic license fixture',
   'THIRD-PARTY.json':b'{}',
   'SECURITY.md':b'fixture',
   'README.md':b'Synthetic source and build fixture',
   'app/index.html':b'<html>Synthetic application fixture</html>',
   'scripts/package_release.py':b'# Synthetic packager fixture; not executed\n',
   'bridge/config.example.json':b'{}',
   'bridge/config.local-only.example.json':b'{}',
   'bridge/genesis_next.py':b'# Synthetic GENESIS fixture; not executed\n',
   'bridge/upgrade_foundry.py':b'# Synthetic foundry fixture; not executed\n',
   'scripts/qualify_genesis_successor.py':b'# Synthetic successor fixture; not executed\n',
   'evidence/OMEGA-PROTOCOL.md':b'Synthetic bounded construction protocol',
   'evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md':b'Synthetic fresh-instance protocol',
   'examples/example.json':b'{}',
   'evidence/QUALIFICATION-MATRIX.json':json.dumps(matrix).encode(),
   'commercial/listing.md':'# Synthetic listing\n## English\nFixture only\n## Français\nExemple seulement'.encode(),
   'commercial/listing.json':b'{}',
   'commercial/storefront-checklist.md':b'Owner only',
  }
  for name in ['INSTALLATION','MODEL-CONNECTIONS','QUICKSTART','OPERATOR','TROUBLESHOOTING','PRIVACY','RELEASE-NOTES','FAQ','EDITION','CHATGPT-COMMERCIAL-APPLICATION','CHATGPT-PLAN','PROVIDER-PROTOCOLS','OMEGA-GENESIS-NEXT','RELEASE','UPGRADE-FOUNDRY','FRONTIER-MONITOR']:
   self.content['docs/'+name+'.md']=b'synthetic documentation fixture'
  self.manifest={'schema':'alpha-genesis-harness-release/v1','version':'0.3.0','source_revision':SOURCE,'source_product_tree':'b'*40,'build_mode':'source-bound','source_matches_commit':True,'release_status':'release-candidate'}
  self.write_archive()
  self.args=argparse.Namespace(source_sha=SOURCE,release_url=module.REPOSITORY+'/releases/tag/alpha-genesis-harness-v0.3.0-rc-aaaaaaaaaaaa',asset_dir=self.assets,operation_receipt=self.op/'QUALIFICATION.json',output=self.root/'out',customer_zip=None,expected_sha256=None,matrix=None,screenshots_dir=None,pull_request_url=None)
  self.write_operation()
  (self.assets/'HARNESS-fixture.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-not-rendered')
  (self.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps({'source_revision':SOURCE,'status':'PASS','scope':'Synthetic assembler fixture only','screenshots':['HARNESS-fixture.png']}))
 def tearDown(self):self.temp.cleanup()
 def write_archive(self,extra=None):
  self.manifest['files']=[{'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in self.content.items()]
  with zipfile.ZipFile(self.archive,'w') as z:
   for name,data in self.content.items():z.writestr('ALPHA_GENESIS_HARNESS_0.3.0/'+name,data)
   z.writestr('ALPHA_GENESIS_HARNESS_0.3.0/RELEASE-MANIFEST.json',json.dumps(self.manifest))
   if extra:z.writestr(extra,b'bad')
 def write_operation(self):
  value={'schema':'alpha-genesis-harness-downloaded-operation/v1','source_revision':SOURCE,'archive_sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest(),'verdict':'PASSED IN SCOPE','operations':[{'command':['python','unittest'],'returncode':0},{'command':['node','--test'],'returncode':0}],'scope':'SYNTHETIC UNIT TEST ONLY','dom_qualification':'SYNTHETIC'}
  (self.op/'QUALIFICATION.json').write_text(json.dumps(value))
  (self.op/'operation-1.stderr.txt').write_text('Ran 987 tests in 0.1s\nOK (skipped=2)\n')
  (self.op/'operation-2.stdout.txt').write_text('ℹ tests 654\n')
  for name in ['WORKFLOW-DEMONSTRATION.json','STRATEGY-DEMONSTRATION.json','OMEGA-DEMONSTRATION.json','OMEGA-FRESH-SOURCE-FREEZE.json','OMEGA-FRESH-SUCCESSOR.json']:
   (self.op/name).write_text(json.dumps({'scope':'SYNTHETIC ASSEMBLER FIXTURE ONLY','file':name})+'\n',encoding='utf-8')
 def test_complete_candidate_preserves_exact_bytes_and_derives_actual_counts(self):
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  self.assertEqual((folder/'01-CUSTOMER-DOWNLOAD'/self.archive.name).read_bytes(),self.archive.read_bytes())
  self.assertEqual(result['included_deliverable_types'],22)
  self.assertFalse(result['commercially_ready'])
  report=json.loads((folder/'OWNER-HANDOFF.json').read_text())
  self.assertEqual(report['published_archive_operation']['operations'][0]['reported_python_tests'],987)
  self.assertEqual(report['published_archive_operation']['operations'][1]['reported_node_tests'],654)
  self.assertEqual(report['matrix_status_counts']['BLOCKED'],1)
  self.assertTrue(report['screenshots_source_bound'])
  self.assertEqual((folder/'05-VERIFICATION/operation-logs/operation-1.stderr.txt').read_bytes(),(self.op/'operation-1.stderr.txt').read_bytes())
  page=(folder/'00-OWNER-START.html').read_text()
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>alert(1)</script>',page)
  self.assertIn('not a declaration that the full commercial mandate is complete',page)
 def test_browser_exports_and_extension_probes_are_preserved_without_new_categories(self):
  data=b'{"experiments":["synthetic-owner-export"]}'
  file=self.assets/'GENESIS-NEXT-browser-export.json';file.write_bytes(data)
  receipt_path=self.assets/'BROWSER-VERIFICATION.json';receipt=json.loads(receipt_path.read_text())
  receipt['exports']=[{'file':file.name,'bytes':len(data),'sha256':module.digest(data)}];receipt_path.write_text(json.dumps(receipt))
  probe={'source_revision':SOURCE,'archive_sha256':module.digest(self.archive.read_bytes()),'status':'BLOCKED','scope':'Synthetic receipt only'}
  probe_path=self.assets/'FRONTIER-MONITOR-VERIFICATION.json';probe_path.write_text(json.dumps(probe))
  mac_path=self.assets/'Darwin-UPGRADE-FOUNDRY-HOST-VERIFICATION.json';mac_path.write_text(json.dumps(probe))
  result=module.assemble(self.args);folder=Path(result['owner_directory']);identity=json.loads((folder/'OWNER-HANDOFF.json').read_text())
  expected_name='ALPHA_GENESIS_HARNESS_OWNER_HANDOFF_0.3.0_'+SOURCE[:12]
  expected_zip=self.args.output/(expected_name+'.zip')
  self.assertEqual(folder.name,expected_name)
  self.assertEqual(Path(result['owner_zip']),expected_zip)
  self.assertEqual(expected_zip.with_suffix('.zip.sha256').read_text(),
                   module.digest(expected_zip.read_bytes())+'  '+expected_zip.name+'\n')
  self.assertEqual(json.loads((self.args.output/(expected_name+'.receipt.json')).read_text()),result)
  with zipfile.ZipFile(expected_zip) as archive:
   self.assertEqual({name.split('/')[0] for name in archive.namelist()},{expected_name})
   self.assertEqual(json.loads(archive.read(expected_name+'/OWNER-HANDOFF.json')),identity)
   self.assertEqual(json.loads(archive.read(expected_name+'/OWNER-FILE-MANIFEST.json')),
                    json.loads((folder/'OWNER-FILE-MANIFEST.json').read_text()))
  self.assertEqual(result['included_deliverable_types'],22)
  self.assertEqual((folder/'05-VERIFICATION/browser-exports'/file.name).read_bytes(),data)
  self.assertEqual((folder/'05-VERIFICATION'/probe_path.name).read_bytes(),probe_path.read_bytes())
  self.assertEqual((folder/'05-VERIFICATION'/mac_path.name).read_bytes(),mac_path.read_bytes())
  self.assertEqual(len(identity['source_probe_receipts']),2)
  self.assertEqual(identity['source_probe_receipts'][0]['status'],'BLOCKED')
  self.assertEqual(identity['browser_exports'][0]['sha256'],module.digest(data))
  foundry=next(row for row in identity['required_deliverables'] if row['id']=='11')
  self.assertIn('02-EXPLORE-THE-EDITION/docs/UPGRADE-FOUNDRY.md',foundry['paths'])
  self.assertFalse(identity['commercially_ready'])
 def test_browser_export_substitution_is_refused(self):
  file=self.assets/'export.json';file.write_bytes(b'{}')
  receipt_path=self.assets/'BROWSER-VERIFICATION.json';receipt=json.loads(receipt_path.read_text())
  receipt['exports']=[{'file':file.name,'bytes':2,'sha256':'0'*64}];receipt_path.write_text(json.dumps(receipt))
  with self.assertRaisesRegex(ValueError,'Browser export bytes'):module.assemble(self.args)
 def test_foreign_extension_probe_is_refused(self):
  (self.assets/'Darwin-UPGRADE-FOUNDRY-HOST-VERIFICATION.json').write_text(json.dumps({'source_revision':'c'*40,'archive_sha256':module.digest(self.archive.read_bytes()),'status':'PASS'}))
  with self.assertRaisesRegex(ValueError,'Extension probe'):module.assemble(self.args)
 def test_22_categories_include_genesis_source_and_untouched_fresh_successor_evidence(self):
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text(encoding='utf-8'))
  rows={row['id']:row for row in identity['required_deliverables']}
  self.assertEqual(identity['version'],'0.3.0')
  self.assertEqual(set(rows),{str(i) for i in range(1,23)})
  self.assertEqual(result['expected_deliverable_types'],22)
  self.assertTrue(rows['11']['included'])
  self.assertTrue(rows['11']['path'].endswith('/docs/OMEGA-GENESIS-NEXT.md'))
  self.assertIn('02-EXPLORE-THE-EDITION/bridge/genesis_next.py',rows['11']['paths'])
  self.assertTrue(rows['13']['included'])
  for name in ['OMEGA-DEMONSTRATION.json','OMEGA-FRESH-SOURCE-FREEZE.json','OMEGA-FRESH-SUCCESSOR.json','STRATEGY-DEMONSTRATION.json','WORKFLOW-DEMONSTRATION.json']:
   target='05-VERIFICATION/'+name
   self.assertEqual((folder/target).read_bytes(),(self.op/name).read_bytes())
   self.assertIn({'path':target,'sha256':module.digest((self.op/name).read_bytes())},identity['published_operation_evidence'])
  page=(folder/'00-OWNER-START.html').read_text(encoding='utf-8')
  self.assertIn('All 22 delivery categories',page)
  self.assertIn('href="05-VERIFICATION/OMEGA-FRESH-SUCCESSOR.json"',page)
 def test_quote_and_historical_evidence_cannot_replace_missing_actual_genesis_receipt(self):
  self.content['evidence/OMEGA-FRESH-RESULTS.json']=b'{"status":"PASS","scope":"HISTORICAL SYNTHETIC FIXTURE"}'
  self.write_archive();self.write_operation();self.model_fixture(status='PASS')
  (self.op/'OMEGA-FRESH-SUCCESSOR.json').unlink()
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text(encoding='utf-8'))
  scientific=next(row for row in identity['required_deliverables'] if row['id']=='13')
  self.assertFalse(scientific['included'])
  self.assertEqual(result['included_deliverable_types'],21)
  self.assertFalse(identity['commercially_ready'])
 def test_genesis_guide_does_not_hide_missing_genesis_implementation(self):
  self.content.pop('bridge/genesis_next.py');self.write_archive();self.write_operation()
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text(encoding='utf-8'))
  genesis=next(row for row in identity['required_deliverables'] if row['id']=='11')
  self.assertFalse(genesis['included'])
 def test_hash_mismatch_refused_before_output(self):
  self.args.expected_sha256='f'*64
  with self.assertRaisesRegex(ValueError,'digest'):module.assemble(self.args)
  self.assertFalse(self.args.output.exists())
 def test_manifest_source_mismatch_refused(self):
  self.args.source_sha='c'*40
  with self.assertRaisesRegex(ValueError,'source revision'):module.assemble(self.args)
 def test_candidate_archive_cannot_be_labeled_source_bound_handoff(self):
  self.manifest['build_mode']='candidate';self.manifest['source_matches_commit']=False;self.write_archive();self.write_operation()
  with self.assertRaisesRegex(ValueError,'source-bound'):module.assemble(self.args)
 def test_operation_receipt_cannot_belong_to_another_archive(self):
  value=json.loads(self.args.operation_receipt.read_text());value['archive_sha256']='0'*64;self.args.operation_receipt.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'digest'):module.assemble(self.args)
 def test_latest_matrix_requires_exact_commit_binding(self):
  self.args.matrix=self.root/'matrix.json';self.args.matrix.write_text(json.dumps({'source_revision':'c'*40,'criteria':[]}))
  with self.assertRaisesRegex(ValueError,'latest matrix'):module.assemble(self.args)
 def test_traversal_refused_without_extracting_outside(self):
  self.write_archive('ALPHA_GENESIS_HARNESS_0.3.0/../../escape.txt');self.write_operation()
  with self.assertRaisesRegex(ValueError,'Unsafe'):module.assemble(self.args)
  self.assertFalse((self.root/'escape.txt').exists())
 def test_corrupt_file_cannot_pass_correct_whole_zip_receipt(self):
  target='ALPHA_GENESIS_HARNESS_0.3.0/START-HERE.html'
  old=self.archive.read_bytes()
  # Rebuild with a changed member while preserving the old per-file manifest.
  with zipfile.ZipFile(io.BytesIO(old)) as source,zipfile.ZipFile(self.archive,'w') as targetzip:
   for info in source.infolist():targetzip.writestr(info,source.read(info.filename)+(b'changed' if info.filename==target else b''))
  self.write_operation()
  with self.assertRaisesRegex(ValueError,'hash mismatch'):module.assemble(self.args)
 def test_foreign_source_screenshots_are_rejected(self):
  (self.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps({'source_revision':'d'*40,'status':'PASS'}))
  with self.assertRaisesRegex(ValueError,'Screenshot receipt'):module.assemble(self.args)
 def test_failed_operation_does_not_become_pass(self):
  value=json.loads(self.args.operation_receipt.read_text());value['operations'][0]['returncode']=1;value['verdict']='INVALID';self.args.operation_receipt.write_text(json.dumps(value))
  result=module.assemble(self.args)
  self.assertEqual(result['published_operation_status'],'FAIL');self.assertFalse(result['commercially_ready'])
 def test_extra_unassociated_gallery_cannot_inherit_other_receipt(self):
  self.args.screenshots_dir=self.root/'extra';self.args.screenshots_dir.mkdir()
  (self.args.screenshots_dir/'HARNESS-extra.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-not-rendered')
  result=module.assemble(self.args)
  identity=json.loads((Path(result['owner_directory'])/'OWNER-HANDOFF.json').read_text())
  self.assertFalse(identity['screenshots_source_bound'])
 def test_image_not_named_in_receipt_is_unassociated(self):
  (self.assets/'HARNESS-unlisted.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-not-rendered')
  result=module.assemble(self.args)
  identity=json.loads((Path(result['owner_directory'])/'OWNER-HANDOFF.json').read_text())
  self.assertFalse(identity['screenshots_source_bound'])
 def test_release_tag_for_different_source_refused(self):
  self.args.release_url=module.REPOSITORY+'/releases/tag/alpha-genesis-harness-v0.3.0-rc-cccccccccccc'
  with self.assertRaisesRegex(ValueError,'Release tag'):module.assemble(self.args)
 def test_release_tag_in_query_refused(self):
  self.args.release_url=module.REPOSITORY+'/?x=/releases/tag/alpha-genesis-harness-v0.3.0-rc-aaaaaaaaaaaa'
  with self.assertRaisesRegex(ValueError,'publication URL'):module.assemble(self.args)
 def test_boolean_exit_code_cannot_pass(self):
  value=json.loads(self.args.operation_receipt.read_text());value['operations'][0]['returncode']=False;self.args.operation_receipt.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'returncode'):module.assemble(self.args)
 def test_missing_command_cannot_pass(self):
  value=json.loads(self.args.operation_receipt.read_text());value['operations'][0]['command']=None;self.args.operation_receipt.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'command'):module.assemble(self.args)
 def platform_fixture(self):
  browser={'source_revision':SOURCE,'status':'PASS','screenshots':['HARNESS-platform.png']}
  value={'source_revision':SOURCE,'archive_sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest(),'status':'PASS','host':'Synthetic Windows test fixture','scope':'SYNTHETIC ONLY; no real OS assertion','operations':[{'command':['node','--test'],'returncode':0}],'browser_report':browser}
  file=self.assets/'PLATFORM-Windows-VERIFICATION.json';file.write_text(json.dumps(value))
  (self.assets/'Windows-HARNESS-platform.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-not-rendered')
  (self.assets/'Windows-operation-1.stdout.txt').write_text('ℹ tests 432\n')
  return file
 def test_platform_receipt_and_prefixed_screenshot_preserved_in_scope(self):
  platform=self.platform_fixture();result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text())
  self.assertTrue(identity['screenshots_source_bound'])
  self.assertEqual(identity['platform_qualifications'][0]['operations'][0]['reported_node_tests'],432)
  self.assertEqual((folder/'05-VERIFICATION'/platform.name).read_bytes(),platform.read_bytes())
  self.assertTrue((folder/'04-SCREENSHOTS/Windows-HARNESS-platform.png').exists())
  self.assertIn('432 Node tests executed on this platform',(folder/'00-OWNER-START.html').read_text())
 def test_failed_native_startup_diagnostic_and_logs_preserved_as_failed_evidence(self):
  file=self.platform_fixture();record=json.loads(file.read_text());record['status']='FAIL';file.write_text(json.dumps(record))
  diagnostic={'status':'FAIL','stage':'workflow_initialization','errno':13,'traceback':'synthetic diagnostic traceback'}
  source=self.assets/'Windows-GENESIS-STARTUP-DIAGNOSTIC.json';source.write_text(json.dumps(diagnostic))
  log=self.assets/'Windows-genesis-startup.stdout.txt';log.write_text(json.dumps(diagnostic)+'\n')
  result=module.assemble(self.args);folder=Path(result['owner_directory']);identity=json.loads((folder/'OWNER-HANDOFF.json').read_text())
  self.assertEqual((folder/'05-VERIFICATION'/source.name).read_bytes(),source.read_bytes())
  self.assertEqual((folder/'05-VERIFICATION/operation-logs'/log.name).read_bytes(),log.read_bytes())
  self.assertEqual(identity['platform_startup_diagnostics'][0]['status'],'FAIL')
  self.assertEqual(identity['platform_qualifications'][0]['status'],'FAIL')
  self.assertFalse(identity['commercially_ready'])
 def test_native_startup_diagnostic_substitution_is_refused(self):
  file=self.platform_fixture();record=json.loads(file.read_text())
  record['checks']={'genesis_startup_diagnostic':{'status':'PASS','interpreter':'selected-python'}};file.write_text(json.dumps(record))
  (self.assets/'Windows-GENESIS-STARTUP-DIAGNOSTIC.json').write_text(json.dumps({'status':'PASS','interpreter':'other-python'}))
  with self.assertRaisesRegex(ValueError,'Startup diagnostic differs'):module.assemble(self.args)
 def test_platform_receipt_other_archive_refused(self):
  file=self.platform_fixture();value=json.loads(file.read_text());value['archive_sha256']='f'*64;file.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'Platform receipt'):module.assemble(self.args)
 def test_platform_pass_with_failed_operation_refused(self):
  file=self.platform_fixture();value=json.loads(file.read_text());value['operations'][0]['returncode']=1;file.write_text(json.dumps(value))
  with self.assertRaisesRegex(ValueError,'Platform PASS'):module.assemble(self.args)

 def test_all_native_codex_receipts_and_diagnostics_preserved_without_promoting_blocked(self):
  archive_hash=hashlib.sha256(self.archive.read_bytes()).hexdigest()
  for prefix in ['', 'Darwin-', 'Windows-']:
   value={'status':'BLOCKED','inference_calls':0,'real_credentials_used':False}
   if prefix:value.update(source_revision=SOURCE,archive_sha256=archive_hash)
   name=prefix+'CODEX-HOST-VERIFICATION.json'
   (self.assets/name).write_text(json.dumps(value),encoding='utf-8')
   (self.assets/(prefix+'CODEX-HOST-VERIFICATION.stderr.txt')).write_text('Synthetic diagnostic only',encoding='utf-8')
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text(encoding='utf-8'))
  receipts=identity['native_codex_probe_receipts']
  self.assertEqual(len(receipts),3)
  self.assertTrue(all(row['status']=='BLOCKED' for row in receipts))
  self.assertEqual(sum(row['source_archive_bound'] for row in receipts),2)
  for prefix in ['', 'Darwin-', 'Windows-']:
   name=prefix+'CODEX-HOST-VERIFICATION.json'
   self.assertEqual((folder/'05-VERIFICATION'/name).read_bytes(),(self.assets/name).read_bytes())
   self.assertTrue((folder/'05-VERIFICATION'/(prefix+'CODEX-HOST-VERIFICATION.stderr.txt')).is_file())
  self.assertFalse(identity['commercially_ready'])
 def test_foreign_source_or_archive_native_codex_receipt_refused(self):
  for field,value in [('source_revision','f'*40),('archive_sha256','f'*64)]:
   with self.subTest(field=field):
    record={'status':'BLOCKED',field:value}
    (self.assets/'Windows-CODEX-HOST-VERIFICATION.json').write_text(json.dumps(record),encoding='utf-8')
    self.args.output=self.root/('out-'+field)
    with self.assertRaisesRegex(ValueError,'Native Codex receipt'):module.assemble(self.args)
 def test_conflicting_native_codex_receipts_are_not_silently_overwritten(self):
  self.args.screenshots_dir=self.root/'native-extra';self.args.screenshots_dir.mkdir()
  for directory,status in [(self.assets,'BLOCKED'),(self.args.screenshots_dir,'PASS')]:
   (directory/'Darwin-CODEX-HOST-VERIFICATION.json').write_text(json.dumps({'status':status}),encoding='utf-8')
  with self.assertRaisesRegex(ValueError,'Conflicting native Codex receipt'):module.assemble(self.args)

 def model_fixture(self, status='FAIL'):
  self.args.model_evidence_archive=self.assets/'LOCAL-MODEL-EVIDENCE-fixture.zip'
  self.model_files={'quote/manufacturing_construct/quote.json':b'{"fixture":"not executed"}',
                    'LOCAL-QUOTE-PROTOCOL-005.json':b'{"fixture":true}'}
  self.model_manifest={'schema':'alpha-harness/hosted-local-qualification/v1','status':status,
                       'source_revision':SOURCE,'source_product_tree':self.manifest['source_product_tree'],
                       'source_unchanged':True,'qualifications':{'local_inference':'FAIL'},
                       'published_sha256':{name:module.digest(data) for name,data in self.model_files.items()}}
  self.write_model_archive()
 def write_model_archive(self, extra=(), manifest_bytes=None):
  with zipfile.ZipFile(self.args.model_evidence_archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
   bundle.writestr('HOSTED-LOCAL-QUALIFICATION.json',manifest_bytes if manifest_bytes is not None else json.dumps(self.model_manifest))
   for name,data in self.model_files.items():bundle.writestr(name,data)
   for name,data in extra:bundle.writestr(name,data)
 def test_model_evidence_copies_exact_archive_and_manifest_without_promoting_failures(self):
  self.model_fixture();original=self.args.model_evidence_archive.read_bytes()
  result=module.assemble(self.args);folder=Path(result['owner_directory'])
  identity=json.loads((folder/'OWNER-HANDOFF.json').read_text(encoding='utf-8'))
  evidence=identity['model_evidence_archive']
  self.assertEqual((folder/evidence['archive']).read_bytes(),original)
  self.assertEqual(evidence['archive_sha256'],module.digest(original))
  self.assertEqual(evidence['recorded_status'],'FAIL')
  self.assertEqual(json.loads((folder/evidence['manifest']).read_text()),self.model_manifest)
  self.assertEqual(identity['matrix_status_counts']['BLOCKED'],1)
  self.assertFalse(identity['commercially_ready'])
  page=(folder/'00-OWNER-START.html').read_text(encoding='utf-8')
  self.assertIn('href="'+evidence['archive']+'"',page)
  self.assertIn('Recorded outcome: FAIL',page)
  self.assertFalse((folder/'05-VERIFICATION/quote').exists())
 def test_model_evidence_requires_current_unchanged_source_tree_and_final_status(self):
  for field,value in [('source_revision','f'*40),('source_product_tree','f'*40),('source_unchanged',False),('status','RUNNING')]:
   with self.subTest(field=field):
    self.model_fixture();self.model_manifest[field]=value;self.write_model_archive()
    with self.assertRaisesRegex(ValueError,'Model evidence'):module.assemble(self.args)
    self.assertFalse(self.args.output.exists())
 def test_model_evidence_refuses_extra_missing_and_changed_members(self):
  for mutation in ['extra','missing','changed']:
   with self.subTest(mutation=mutation):
    self.model_fixture()
    if mutation=='extra':self.model_files['unlisted.txt']=b'unlisted'
    elif mutation=='missing':self.model_files.pop('LOCAL-QUOTE-PROTOCOL-005.json')
    else:self.model_files['LOCAL-QUOTE-PROTOCOL-005.json']=b'changed'
    self.write_model_archive()
    with self.assertRaisesRegex(ValueError,'Model evidence (inventory|file hash)'):module.assemble(self.args)
    self.assertFalse(self.args.output.exists())
 def test_model_evidence_rejects_unsafe_and_ambiguous_paths_without_extraction(self):
  for name in ['../escape.txt','/absolute.txt','C:/drive.txt','bad\\name.txt','bad:name.txt','quote/NUL.txt','quote/end.','quote/bad?.txt','hosted-local-qualification.json']:
   with self.subTest(name=name):
    self.model_fixture();self.model_files[name]=b'invalid';self.model_manifest['published_sha256'][name]=module.digest(b'invalid');self.write_model_archive()
    with self.assertRaisesRegex(ValueError,'Unsafe'):module.assemble(self.args)
    self.assertFalse((self.root/'escape.txt').exists())
 def test_model_evidence_rejects_links_special_files_and_directories(self):
  for mode in [0o120777,0o010644,0o020644,0o040755]:
   with self.subTest(mode=mode):
    self.model_fixture();info=zipfile.ZipInfo('special.txt');info.create_system=3;info.external_attr=mode<<16
    self.model_manifest['published_sha256']['special.txt']=module.digest(b'payload');self.write_model_archive(extra=[(info,b'payload')])
    with self.assertRaisesRegex(ValueError,'regular files'):module.assemble(self.args)
 def test_model_evidence_enforces_compressed_and_expanded_size_bounds(self):
  self.model_fixture()
  with patch.object(module,'MAX_BYTES',self.args.model_evidence_archive.stat().st_size):
   with self.assertRaisesRegex(ValueError,'safety envelope'):module.model_evidence_snapshot(self.args.model_evidence_archive,SOURCE,'b'*40)
  self.model_files['large.txt']=b'x'*20_000;self.model_manifest['published_sha256']['large.txt']=module.digest(self.model_files['large.txt']);self.write_model_archive()
  with patch.object(module,'MAX_BYTES',10_000):
   with self.assertRaisesRegex(ValueError,'Expanded model evidence'):module.model_evidence_snapshot(self.args.model_evidence_archive,SOURCE,'b'*40)
 def test_model_evidence_rejects_duplicate_json_fields_and_self_hash_listing(self):
  self.model_fixture();raw=json.dumps(self.model_manifest).replace('"status": "FAIL"','"status": "PASS", "status": "FAIL"')
  self.write_model_archive(manifest_bytes=raw)
  with self.assertRaisesRegex(ValueError,'Duplicate JSON'):module.assemble(self.args)
  self.model_fixture();self.model_manifest['published_sha256']['HOSTED-LOCAL-QUALIFICATION.json']='f'*64;self.write_model_archive()
  with self.assertRaisesRegex(ValueError,'hash inventory'):module.assemble(self.args)

if __name__=='__main__':unittest.main()
