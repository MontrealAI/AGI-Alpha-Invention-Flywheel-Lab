import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import resurrect as r


@unittest.skipUnless(shutil.which('cc') or shutil.which('gcc'), 'C compiler required')
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name)
        self.example=r.demo(self.work, unsafe_local=True)
        self.manifest=self.work/'manifest.json'
        self.obs=self.work/'observations.json'
        self.candidate=self.work/'replacement.py'

    def test_full_domain_native_binary_to_replacement(self):
        v=self.example['verification']
        self.assertEqual(v['status'],'PASS_FINITE_DOMAIN')
        self.assertEqual(v['cases_checked'],24)
        self.assertEqual(v['binary_sha256'],r.file_sha(self.work/'legacy_pricing'))
    def test_generated_candidate_is_standalone(self):
        result=r.process(self.candidate,'candidate',[{'region':'EU','seats':4,'tier':'PRO'}],True)
        self.assertEqual(result[0]['total_cents'],r.process(self.work/'legacy_pricing','reference',[{'region':'EU','seats':4,'tier':'PRO'}],True)[0]['total_cents'])
    def test_corrupt_observations_refused(self):
        d=r.load(self.obs)
        d['cases'].pop()
        r.save(self.obs,d)
        with self.assertRaises(r.Hold): r.synthesize(self.manifest,self.obs,self.work/'bad.py')
    def test_forged_manifest_hash_refused(self):
        d=r.load(self.obs)
        d['manifest_sha256']='0'*64
        r.save(self.obs,d)
        with self.assertRaises(r.Hold): r.synthesize(self.manifest,self.obs,self.work/'bad.py')
    def test_wrong_candidate_detected_by_independent_replay(self):
        wrong=self.work/'wrong.py'
        wrong.write_text('import sys\nfor line in sys.stdin: print("{}")\n')
        v=r.verify(self.manifest,wrong,unsafe_local=True)
        self.assertEqual(v['status'],'FAIL_MISMATCH')
    def test_outside_domain_refuses_execution(self):
        import subprocess
        p=subprocess.run([sys.executable,str(self.candidate)],input='{"region":"NA","seats":99,"tier":"PRO"}\n',text=True,capture_output=True)
        self.assertEqual(p.returncode,2)
        self.assertIn('HOLD',p.stderr)
    def test_rights_attestation_required(self):
        d=r.load(self.manifest)
        d['authorization']='NO'
        r.save(self.manifest,d)
        with self.assertRaises(r.Hold):r.read_manifest(self.manifest)
    def test_case_limit_fails_closed(self):
        d=r.load(self.manifest)
        d['axes']['seats']=list(range(r.MAX_CASES))
        r.save(self.manifest,d)
        with self.assertRaises(r.Hold):r.read_manifest(self.manifest)
    def test_docker_absence_fails_closed(self):
        from unittest.mock import patch
        with patch.object(r.shutil,'which',return_value=None):
            with self.assertRaises(r.Hold): r.process(self.candidate,'candidate',[{'region':'NA','seats':1,'tier':'PRO'}],False)

if __name__=='__main__': unittest.main()

class TestAgentSafety(unittest.TestCase):
    def test_external_disclosure_requires_opt_in(self):
        from agentic import develop_with_codex
        with self.assertRaises(r.Hold):
            develop_with_codex('none','none','none',authorize_disclosure=False)

    def test_missing_codex_fails_closed(self):
        from agentic import develop_with_codex
        from unittest.mock import patch
        import agentic
        with patch.object(agentic.shutil,'which',return_value=None):
            with self.assertRaises(r.Hold):
                develop_with_codex('none','none','none',authorize_disclosure=True)

    def test_agent_saw_only_subset(self):
        from agentic import selected_examples
        cases=[{'input':{'x':i},'output':i} for i in range(60)]
        samples=selected_examples(cases)
        self.assertLess(len(samples),len(cases))
        self.assertTrue(samples)
