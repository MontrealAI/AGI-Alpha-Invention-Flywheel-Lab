import importlib.util,json,pathlib,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'scripts/release_connected014.py'
spec=importlib.util.spec_from_file_location('compact_release',P);release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
class CompactFailureTests(unittest.TestCase):
 def test_projection_deletes_only_disposable_failure_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);op=root/'operation';op.mkdir();(op/'authority.key').write_text('private');(op/'STATE.json').write_text('active state')
   release.write(op/'FROZEN.json',{'config':{'seed':12}})
   release.write(root/'DOWNLOADED_RELEASE_RUN.json',{'accepted':False,'source_sha256':'b'*64,'active_command':'01-run','failure':{'type':'TimeoutError','message':'SECRET_API_TOKEN'},'resources':{'total_measured_cpu_seconds':3001,'secret':'bad'},'commands':[{'stdout':'01-run.stdout','returncode':1,'command':['secret']}]})
   for name in ('01-run.stdout','01-run.stderr','failed-operation-keyfree.zip','.failed-operation-candidate.zip','downloaded-operation-keyfree.zip','.downloaded-operation-candidate.zip'): (root/name).write_text('bulk')
   for name in ('downloaded-operation-public','published-keyfree'):
    (root/name).mkdir();(root/name/'duplicate.json').write_text('derived')
   r=release.compact_failure(root,'a'*40);encoded=json.dumps(r)
   self.assertNotIn('SECRET_API_TOKEN',encoded);self.assertNotIn('secret',encoded);self.assertNotIn('/private',encoded);self.assertEqual(r['resources']['total_measured_cpu_seconds'],3001)
   self.assertEqual(r['category'],'WALL_TIMEOUT');self.assertEqual(r['active_stage'],'01-run');self.assertFalse(r['accepted'])
   self.assertEqual((op/'authority.key').read_text(),'private');self.assertEqual((op/'STATE.json').read_text(),'active state')
   self.assertEqual({p.name for p in root.iterdir()},{'operation','FAILURE_LESSON.json'})
   self.assertEqual(release.compact_failure(root,'a'*40),r)
 def test_early_setup_failure_truthful_without_fake_resources(self):
  with tempfile.TemporaryDirectory() as d:
   r=release.compact_failure(pathlib.Path(d)/'output','a'*40)
   self.assertFalse(r['accepted']);self.assertFalse(r['actual_release_download']);self.assertEqual(r['resources'],{});self.assertIsNone(r['source_sha256']);self.assertEqual(r['active_stage'],'setup-or-unclassified')
 def test_success_refuses_failure_cleanup(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);release.write(root/'DOWNLOADED_RELEASE_RUN.json',{'accepted':True});z=root/'downloaded-operation-keyfree.zip';z.write_bytes(b'success')
   with self.assertRaisesRegex(ValueError,'SUCCESS_IS_NOT_A_FAILURE'): release.compact_failure(root,'a'*40)
   self.assertEqual(z.read_bytes(),b'success');self.assertTrue((root/'DOWNLOADED_RELEASE_RUN.json').exists())
 def test_foreign_receipt_refused(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);release.write(root/'FAILURE_LESSON.json',{'schema':'agi-alpha/compact-failure/v1','source_commit':'b'*40})
   with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):release.compact_failure(root,'a'*40)
 def test_retry_finishes_disposable_cleanup(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);r=release.compact_failure(root,'a'*40)
   (root/'01-run.stderr').write_text('interrupted cleanup');(root/'.failed-operation-candidate.zip').write_text('bulk')
   self.assertEqual(release.compact_failure(root,'a'*40),r)
   self.assertEqual({p.name for p in root.iterdir()},{'FAILURE_LESSON.json'})
 def test_existing_extra_fields_are_rejected_not_exported(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);r=release.compact_failure(root,'a'*40);r['private']='secret';release.write(root/'FAILURE_LESSON.json',r)
   with self.assertRaisesRegex(ValueError,'SCHEMA_OR_SOURCE'):release.compact_failure(root,'a'*40)
 def test_receipt_symlink_does_not_read_or_modify_private_target(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);private=root/'private.json';private.write_text('private account');out=root/'output';out.mkdir();(out/'FAILURE_LESSON.json').symlink_to(private)
   with self.assertRaisesRegex(ValueError,'UNSYMLINKED_FAILURE_RECEIPT'):release.compact_failure(out,'a'*40)
   self.assertEqual(private.read_text(),'private account')
 def assert_workflow_upload_contract(self, text):
  # Check this workflow's explicit indented steps without optional YAML packages.
  import re
  jobs=re.split(r'(?m)^  (?=[A-Za-z0-9_-]+:)',text)
  operation=[job for job in jobs if job.startswith('operate-published-release:')]
  self.assertEqual(len(operation),1)
  steps=re.split(r'(?m)^      - ',operation[0])
  uploads=[step for step in steps if re.search(r'(?m)^        uses: actions/upload-artifact@',step)]
  self.assertEqual(len(uploads),4)
  failure=[step for step in uploads if re.search(r'(?m)^        if: failure\(\)',step)]
  self.assertEqual(len(failure),1)
  self.assertIn("        if: failure() && steps.operation.outcome != 'success' && steps.compact_failure.outcome == 'success'\n",failure[0])
  self.assertEqual(re.findall(r'(?m)^          path: (.+)$',failure[0]),['${{ runner.temp }}/downloaded-release-operation/FAILURE_LESSON.json'])
  success=[step for step in uploads if 'name: connected014-published-operation-' in step]
  wheel=[step for step in uploads if 'name: connected014-wheel-utility-' in step]
  self.assertEqual(len(wheel),1)
  for step in success+wheel:
   self.assertIn("        if: always() && steps.operation.outcome == 'success'\n",step)
  self.assertEqual(re.findall(r'(?m)^          path: (.+)$',wheel[0]),['${{ runner.temp }}/RELEASED_WHEEL.json'])
  self.assertEqual(len(success),1)
  self.assertEqual(re.findall(r'(?m)^            (.+)$',success[0]),[
   '${{ runner.temp }}/RELEASE_DOWNLOAD.json',
   '${{ runner.temp }}/downloaded-release-operation/DOWNLOADED_RELEASE_RUN.json',
   '${{ runner.temp }}/downloaded-release-operation/downloaded-operation-keyfree.zip'])
  self.assertIn('          path: |\n',success[0])
  flexibility=[step for step in uploads if 'name: transformational063-released-operation-' in step]
  self.assertEqual(len(flexibility),1)
  self.assertIn("        if: always() && steps.released_flexibility.outcome == 'success'\n",flexibility[0])
  self.assertEqual(re.findall(r'(?m)^            (.+)$',flexibility[0]),[
   '${{ runner.temp }}/released-transformational063/REPORT.json',
   '${{ runner.temp }}/released-transformational063/PROTOCOL.json',
   '${{ runner.temp }}/released-transformational063/SOURCE.json',
   '${{ runner.temp }}/released-transformational063/AUDIT.json',
   '${{ runner.temp }}/released-transformational063/source',
   '${{ runner.temp }}/released-transformational063/public'])
  self.assertFalse(any('*.stdout' in step or '*.stderr' in step or 'failed-operation-keyfree' in step for step in uploads))
 def test_workflow_exports_only_compact_failure(self):
  text=(P.parents[1]/'.github/workflows/connected014-release.yml').read_text()
  self.assert_workflow_upload_contract(text)
  for changed in (text.replace(" && steps.compact_failure.outcome == 'success'",''),
                  text.replace('/FAILURE_LESSON.json','/*.stderr'),
                  text.replace('/RELEASED_WHEEL.json','/*.stdout'),
                  text.replace("always() && steps.released_flexibility.outcome == 'success'",'always()'),
                  text.replace('/released-transformational063/public','/released-transformational063/private'),
                  text.replace("always() && steps.operation.outcome == 'success'",'always()'),
                  text.replace('downloaded-operation-keyfree.zip','failed-operation-keyfree.zip')):
   with self.assertRaises(AssertionError): self.assert_workflow_upload_contract(changed)
