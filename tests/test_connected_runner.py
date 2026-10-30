import contextlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from commercial.ledger import digest
from connected_enterprise.runner import source_paths

ROOT=Path(__file__).resolve().parents[1]


class ConnectedRunnerAuthenticityTests(unittest.TestCase):
    @classmethod
    def invoke(cls,*arguments,cwd=None):
        cwd=Path(cwd or cls.output/'source')
        return subprocess.run([sys.executable,'-m','connected_enterprise',*arguments],cwd=cwd,
                              env={**os.environ,'PYTHONPATH':str(cwd),'PYTHONDONTWRITEBYTECODE':'1'},
                              capture_output=True,text=True,timeout=180)

    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory(prefix='connected014-runner-')
        cls.directory=Path(cls.fixture.name);cls.source=cls.directory/'input-source'
        try:
            for name in source_paths(ROOT):
                target=cls.source/name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/name,target)
            cls.output=cls.directory/'operation'
            run=cls.invoke('run','--smoke','--output','../unused/../operation',cwd=cls.source)
            if run.returncode:raise AssertionError('CURRENT_SOURCE_SMOKE_FAILED:'+run.stderr)
            cls.baseline=cls.invoke('audit','--output',str(cls.output))
            if cls.baseline.returncode:raise AssertionError('VALID_BASELINE_AUDIT_FAILED:'+cls.baseline.stderr)
            cls.report=json.loads((cls.output/'REPORT.json').read_text())
        except BaseException:
            failure=ROOT.parent/('connected014-runner-failure-'+str(time.time_ns()))
            shutil.copytree(cls.directory,failure)
            print('Runner failure evidence preserved at '+str(failure),file=sys.stderr)
            cls.fixture.cleanup();raise

    @classmethod
    def tearDownClass(cls):cls.fixture.cleanup()

    @contextlib.contextmanager
    def changed_json(self,path,mutate):
        path=Path(path);original=path.read_bytes();value=json.loads(original)
        mutate(value);path.write_text(json.dumps(value))
        try:yield
        finally:path.write_bytes(original)

    def rejects(self,marker,*arguments):
        result=self.invoke(*(arguments or ('audit','--output',str(self.output))))
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn(marker,result.stderr)

    def test_normalized_smoke_and_keyfree_public_package_audit(self):
        frozen=json.loads((self.output/'FROZEN.json').read_text())
        self.assertIsNone(frozen['git_commit'])
        self.assertEqual(self.report['worlds'],2)
        self.assertEqual(len(list((self.output/'worlds').glob('*/RESULT.json'))),2)
        receipt=json.loads((self.output/'PACKAGE_AUDIT.json').read_text())
        self.assertTrue(receipt['accepted']);self.assertEqual(receipt['worlds'],2)
        self.assertEqual(receipt['source_sha256'],frozen['source']['sha256'])
        archive=self.directory/'public-evidence.zip'
        packaged=self.invoke('package','--output',str(self.output),'--archive',str(archive))
        self.assertEqual(packaged.returncode,0,packaged.stderr)
        extracted=self.directory/'public-copy'
        with zipfile.ZipFile(archive) as z:
            self.assertIsNone(z.testzip())
            self.assertFalse(any(name.endswith('.adaptive-simulation-key') or '.sqlite' in name for name in z.namelist()))
            z.extractall(extracted)
        public=self.invoke('audit','--output',str(extracted),cwd=extracted/'source')
        self.assertEqual(public.returncode,0,public.stderr)
        self.assertTrue(json.loads((extracted/'PACKAGE_AUDIT.json').read_text())['accepted'])

    def test_top_level_index_growth_and_completion_tampering_refused(self):
        report=self.output/'REPORT.json'
        with self.changed_json(report,lambda row:row['outcomes'].__setitem__('commercial_result','FABRICATED_SUCCESS')):
            self.rejects('TOP_LEVEL_COMMERCIAL_REPORT_CHANGED')
            refused=self.directory/'refused-tampered-package.zip'
            self.rejects('TOP_LEVEL_COMMERCIAL_REPORT_CHANGED','package','--output',str(self.output),'--archive',str(refused))
            self.assertFalse(refused.exists())
        with self.changed_json(report,lambda row:row['worlds_index'][0].__setitem__('result_sha256','0'*64)):
            self.rejects('WORLD_RESULT_INDEX_BINDING_CHANGED')
        task=self.report['worlds_index'][0]['task']['id']
        with self.changed_json(self.output/'worlds'/task/'GROWTH.json',lambda row:row.__setitem__('fabricated_incremental_profit',1_000_000)):
            self.rejects('GROWTH_REPORT_NOT_REDERIVED_FROM_NATIVE_RECORDS')
        with self.changed_json(self.output/'worlds'/task/'AUDIT.json',lambda row:row['daily_outreach_units_recomputed'].__setitem__('0',999999)):
            self.rejects('WORLD_AUDIT_RECEIPT_CHANGED')
        with self.changed_json(self.output/'COMPLETE.json',lambda row:row.__setitem__('report_sha256','0'*64)):
            self.rejects('COMPLETION_RECEIPT_CHANGED')

    def test_self_rehashed_registration_and_wrong_cohort_origin_refused(self):
        def change_registration(row):
            row['protocol']['service_cohort_seed']+=1
            row.pop('sha256');row['sha256']=digest(row)
        with self.changed_json(self.output/'FROZEN.json',change_registration):
            self.rejects('FROZEN_REGISTRATION_NOT_REDERIVED_FROM_SOURCE')
        with self.changed_json(self.output/'SERVICES.json',lambda row:row['cohort_provenance'].__setitem__('cohort_seed_sha256','0'*64)):
            self.rejects('REGISTERED_SERVICE_COHORT_CHANGED')

    def test_executing_source_mutation_and_output_symlink_refused(self):
        path=self.output/'source/connected_enterprise/engine.py';original=path.read_bytes()
        try:
            path.write_bytes(original+b'\n')
            self.rejects('FROZEN_SOURCE_OR_CONFIGURATION_CHANGED')
        finally:path.write_bytes(original)
        link=self.directory/'linked-output';link.symlink_to(self.output,target_is_directory=True)
        self.rejects('OUTPUT_SYMLINK_REFUSED','audit','--output',str(link))
        child=self.directory/'linked-parent';child.symlink_to(self.directory,target_is_directory=True)
        self.rejects('OUTPUT_SYMLINK_REFUSED','run','--smoke','--output',str(child/'new-output'))
        self.assertFalse((self.directory/'new-output').exists())
