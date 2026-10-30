import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from adaptive_enterprise.model import stable_projection
from adaptive_enterprise.runner import MAX_WORKERS,_parallel,assemble_report,audit,canonical,freeze,package,protocol,tasks,write_json

ROOT=Path(__file__).resolve().parents[1]


def _observe_parallel(payload):
    identity,delay=payload
    time.sleep(delay)
    return {'identity':identity,'pid':os.getpid()}


class AdaptiveRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='adaptive012-runner-tests-')
        cls.output=Path(cls.temp.name)/'run'
        subprocess.run([sys.executable,'-m','adaptive_enterprise','run','--output',str(cls.output),'--smoke'],cwd=ROOT,check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_current_command_no_git_snapshot_and_independent_audit(self):
        self.assertFalse((self.output/'source/.git').exists())
        checked=audit(self.output)
        self.assertTrue(checked['accepted'])
        self.assertEqual(checked['native_and_operating_worlds_replayed'],1)
        self.assertFalse(checked['private_signing_keys_required'])

    def test_financial_only_snapshot_dispatch_reports_no_operating_replay(self):
        checked=audit(self.output,reexecute=False)
        self.assertTrue(checked['accepted'])
        self.assertEqual(checked['qualification_scope'],'NATIVE_FINANCIAL_ONLY')
        self.assertEqual(checked['native_worlds_replayed'],1)
        self.assertEqual(checked['operating_replayed'],0)
        self.assertEqual(checked['native_and_operating_worlds_replayed'],0)

    def test_parallel_workers_preserve_task_order_and_worker_bound(self):
        self.assertEqual(MAX_WORKERS,4)
        rows=list(_parallel(_observe_parallel,[(0,.4),(1,.05),(2,.05),(3,.05),(4,.05)]))
        self.assertEqual([row['identity'] for row in rows],list(range(5)))
        self.assertGreater(len({row['pid'] for row in rows}),1)
        self.assertLessEqual(len({row['pid'] for row in rows}),MAX_WORKERS)

    def test_protocol_is_fresh_complete_and_preserves_hard_requirements(self):
        p=protocol();planned=tasks({'protocol':p})
        self.assertFalse(set(p['seeds'])&set(p['exposed_development_seeds']))
        self.assertEqual(len({t['id'] for t in planned}),len(planned))
        primary=[t for t in planned if t['kind']=='primary']
        self.assertEqual(len(primary),len(p['seeds'])*len(p['worlds'])*len(p['primary_arms']))
        self.assertFalse(p['economic_criteria']['all_cycles_required'])
        self.assertFalse(p['economic_criteria']['inventory_completion_required'])
        self.assertIn('No protected-fund spending',p['hard_requirements'])

    def test_existing_output_refused(self):
        with self.assertRaises(FileExistsError):freeze(self.output,True)

    def test_source_and_completion_identity_tampering_refused(self):
        frozen=json.loads((self.output/'FROZEN012.json').read_text())
        name=next(iter(frozen['source']['files']));path=self.output/'source'/name;original=path.read_bytes()
        try:
            path.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'FROZEN_SOURCE'):audit(self.output)
        finally:path.write_bytes(original)
        path=self.output/'COMPLETE.json';original=path.read_bytes()
        try:
            changed=json.loads(original);changed['source_sha256']='0'*64;write_json(path,changed)
            with self.assertRaisesRegex(ValueError,'COMPLETE_SOURCE'):audit(self.output)
        finally:path.write_bytes(original)

    def test_dropped_registered_world_and_changed_cohort_refused(self):
        path=self.output/'INDEX.json';original=path.read_bytes()
        try:
            changed=json.loads(original);changed['worlds']=[];write_json(path,changed)
            with self.assertRaisesRegex(ValueError,'COVERAGE'):audit(self.output)
        finally:path.write_bytes(original)
        path=self.output/'SERVICES.json';original=path.read_bytes()
        try:
            changed=json.loads(original);changed['jobs'].pop();write_json(path,changed)
            with self.assertRaisesRegex(ValueError,'REGISTERED_SERVICE_COHORT'):audit(self.output)
        finally:path.write_bytes(original)

    def _jointly_rehash(self,mutator):
        index_path=self.output/'INDEX.json';report_path=self.output/'REPORT.json';complete_path=self.output/'COMPLETE.json'
        index=json.loads(index_path.read_text());item=index['worlds'][0];world_path=self.output/item['path']
        paths=[index_path,report_path,complete_path,world_path];original={p:p.read_bytes() for p in paths}
        try:
            result=json.loads(gzip.decompress(original[world_path]));mutator(result)
            world_path.write_bytes(gzip.compress(canonical(result),mtime=0));item['sha256']=hashlib.sha256(world_path.read_bytes()).hexdigest();item['bytes']=world_path.stat().st_size;write_json(index_path,index)
            frozen=json.loads((self.output/'FROZEN012.json').read_text());manifest=json.loads((self.output/'SERVICES.json').read_text())
            report=assemble_report(frozen,[(item['task'],result)],manifest);report['resource_receipt']=json.loads(original[report_path])['resource_receipt'];write_json(report_path,report)
            complete=json.loads(original[complete_path]);complete['report_sha256']=hashlib.sha256(report_path.read_bytes()).hexdigest();write_json(complete_path,complete)
            with self.assertRaisesRegex(ValueError,'OPERATING_REPLAY'):audit(self.output)
        finally:
            for path,raw in original.items():path.write_bytes(raw)

    def test_rehashed_false_operating_counts_refused(self):
        self._jointly_rehash(lambda r:r.__setitem__('accepted_jobs',r['accepted_jobs']+1))

    def test_rehashed_fabricated_instrument_trace_refused(self):
        self._jointly_rehash(lambda r:r['instrument_receipts'].append({'fabricated_source_claim':True}))

    def test_scale_sensitivity_file_is_part_of_qualification(self):
        path=self.output/'SCALE_SENSITIVITIES.json';original=path.read_bytes()
        try:
            write_json(path,[{'fabricated_sensitivity':True}])
            with self.assertRaisesRegex(ValueError,'SCALE_SENSITIVITY'):audit(self.output)
        finally:path.write_bytes(original)

    def test_semantic_projection_preserves_claims_and_ignores_only_execution_entropy(self):
        first={'accepted_jobs':3,'resource_receipt':{'process_cpu_seconds':1,'paid_model_calls':0},'owned_account':{'snapshot':{'filesystem':'overlay'},'action_proofs':{'plan':{'signature':'first','body':{'amount':10}}}},'instrument_receipts':[{'source_sha256':'a'*64}]}
        second=copy.deepcopy(first);second['resource_receipt']['process_cpu_seconds']=9;second['owned_account']['snapshot']['filesystem']='ext4';second['owned_account']['action_proofs']['plan']['signature']='second'
        self.assertEqual(stable_projection(first),stable_projection(second))
        second['resource_receipt']['paid_model_calls']=1
        self.assertNotEqual(stable_projection(first),stable_projection(second))
        second=copy.deepcopy(first);second['instrument_receipts'][0]['source_sha256']='b'*64
        self.assertNotEqual(stable_projection(first),stable_projection(second))

    def test_completed_world_resume_is_idempotent_and_package_omits_private_key(self):
        before=json.loads((self.output/'INDEX.json').read_text())
        subprocess.run([sys.executable,'-m','adaptive_enterprise','resume','--output',str(self.output)],cwd=ROOT,check=True,capture_output=True)
        self.assertEqual(before,json.loads((self.output/'INDEX.json').read_text()))
        key=self.output/'must-not-publish.adaptive-simulation-key';key.write_bytes(b'simulation-private-material')
        archive=Path(self.temp.name)/'qualified.zip'
        try:
            checked=package(self.output,archive)
            self.assertTrue(checked['qualification']['accepted'])
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                self.assertFalse(any(name.endswith('.adaptive-simulation-key') for name in z.namelist()))
                self.assertIn('REPORT.json',z.namelist())
        finally:key.unlink()


if __name__=='__main__':unittest.main()
