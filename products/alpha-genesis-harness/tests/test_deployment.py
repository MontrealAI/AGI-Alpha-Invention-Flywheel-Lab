# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bridge.deployment import LocalDeployment, read, digest

def spec(formula='x+1'):
    return {'inputs':['x'],'bindings':{},'outputs':{'y':{'formula':formula}}}
def cases(delta=1):
    return [{'input':{'x':x},'expected':{'y':x+delta}} for x in [0,5,100]]
class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.s=LocalDeployment(self.tmp.name,'operations')
    def test_install_run_reopen_upgrade_rollback(self):
        a=self.s.install(spec(),cases(),approved=True)
        self.assertEqual(self.s.run({'x':8})['output'],{'y':9})
        self.s=LocalDeployment(self.tmp.name,'operations')
        self.assertEqual(self.s.status()['release'],a['release'])
        b=self.s.install(spec('x+2'),cases(2),approved=True)
        self.assertNotEqual(a['release'],b['release'])
        self.assertEqual(self.s.run({'x':8})['output'],{'y':10})
        self.s.rollback(approved=True)
        self.assertEqual(self.s.run({'x':8})['output'],{'y':9})
    def test_failed_acceptance_does_not_replace_current(self):
        a=self.s.install(spec(),cases(),approved=True)
        with self.assertRaises(ValueError):self.s.install(spec('x+2'),cases(),approved=True)
        self.assertEqual(self.s.status()['release'],a['release'])
    def test_approval_required(self):
        with self.assertRaises(ValueError):self.s.install(spec(),cases())
        self.s.install(spec(),cases(),approved=True)
        with self.assertRaises(ValueError):self.s.rollback()
    def test_mutation_blocks_and_records_incident_then_local_recovery(self):
        a=self.s.install(spec(),cases(),approved=True)
        b=self.s.install(spec('x+2'),cases(2),approved=True)
        (self.s.path/(b['release']+'.json')).write_text('{}')
        with self.assertRaises(ValueError):self.s.run({'x':9})
        self.assertEqual(read(self.s.path/'LAST-HEALTH.json')['status'],'blocked')
        self.s.rollback(approved=True)
        self.assertEqual(self.s.status()['release'],a['release'])
    def test_stale_evaluator_refused(self):
        self.s.install(spec(),cases(),approved=True)
        with patch('bridge.deployment.evaluator_identity',return_value='0'*64):
            with self.assertRaises(ValueError):self.s.run({'x':0})
    def test_duplicate_json_refused(self):
        p=Path(self.tmp.name)/'bad.json';p.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):read(p)
    def test_invalid_targets_and_symlinks(self):
        for name in ['../escape','/absolute','a/b','']:
            with self.assertRaises(ValueError):LocalDeployment(self.tmp.name,name)
        link=Path(self.tmp.name)/'link';link.symlink_to(self.s.path,target_is_directory=True)
        with self.assertRaises(ValueError):LocalDeployment(self.tmp.name,'link')
    def test_lock_refuses_overlapping_or_unreconciled_operation(self):
        (self.s.path/'.lock').write_text('')
        with self.assertRaises(ValueError):self.s.install(spec(),cases(),approved=True)
    def test_idempotent_install_keeps_rollback_predecessor(self):
        a=self.s.install(spec(),cases(),approved=True)
        self.s.install(spec('x+2'),cases(2),approved=True)
        self.s.install(spec('x+2'),cases(2),approved=True)
        self.assertEqual(self.s.rollback(approved=True)['release'],a['release'])
    def test_empty_cases_and_wrong_types_refused(self):
        with self.assertRaises(ValueError):self.s.install(spec(),[],approved=True)
        with self.assertRaises(ValueError):self.s.install(spec(),[{'input':{'x':0},'expected':{'y':True}}],approved=True)
    def test_invalid_runtime_input_records_no_raw_data(self):
        self.s.install(spec(),cases(),approved=True)
        with self.assertRaises(ValueError):self.s.run({'x':'private-data'})
        self.assertNotIn('private-data',(self.s.path/'LAST-HEALTH.json').read_text())
    def test_loaded_evaluator_change_refused(self):
        with patch('bridge.deployment.LOADED_SOURCE_SHA256','0'*64):
            with self.assertRaises(ValueError):self.s.install(spec(),cases(),approved=True)

class ReviewRegressions(unittest.TestCase):
    def test_ancestor_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            real=Path(d)/'real';real.mkdir();alias=Path(d)/'alias';alias.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):LocalDeployment(alias/'nested','target')
    def test_private_records_and_no_claim_of_new_input_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            s=LocalDeployment(d,'target');r=s.install(spec('x+1 if x<10 else 999'),[{'input':{'x':1},'expected':{'y':2}}],approved=True)
            out=s.run({'x':20});self.assertEqual(out['output'],{'y':999})
            self.assertEqual(out['receipt']['status'],'executed_local');self.assertFalse(out['receipt']['runtime_acceptance_established'])
            import os
            if os.name=='posix':
                self.assertEqual(s.path.stat().st_mode & 0o777,0o700)
                for f in s.path.iterdir():self.assertEqual(f.stat().st_mode & 0o777,0o600)
    def test_workshop_admission_revocation_and_reopen(self):
        from bridge.workflows import WorkflowService
        from bridge import workshop
        from test_workshop import AuthoredTransport, candidate, authored_request
        with tempfile.TemporaryDirectory() as d:
            service=WorkflowService(AuthoredTransport(candidate('x*2')),Path(d)/'workflow')
            try:
                state=workshop.register(service,authored_request());service.step(state['id'])
                view=workshop.operate(service,'get',{'run_id':state['id']})
                s=LocalDeployment(Path(d)/'deploy','target',service)
                s.install_workshop(state['id'],view['revision'],approved=True)
                self.assertEqual(s.run({'x':8})['output'],{'result':16})
                with self.assertRaises(ValueError):LocalDeployment(Path(d)/'deploy','target').run({'x':8})
                workshop.operate(service,'revoke',{'run_id':state['id'],'revision':view['revision']})
                with self.assertRaises(ValueError):s.run({'x':8})
            finally:service.close()

class OperationBoundRegressions(unittest.TestCase):
    def test_acceptance_and_new_input_use_exact_bound(self):
        instrument={'inputs':['xs'],'outputs':{'total':{'op':'sum','args':[{'field':'xs'}]}}}
        tiny=[{'input':{'xs':[1]},'expected':{'total':1}}]
        with tempfile.TemporaryDirectory() as d:
            s=LocalDeployment(d,'target');s.install(instrument,tiny,approved=True,max_operations=3)
            self.assertEqual(s.run({'xs':[2]})['output'],{'total':2})
            with self.assertRaises(ValueError):s.run({'xs':[1,2]})
            with self.assertRaises(ValueError):s.install(instrument,tiny,approved=True,max_operations=2)
    def test_workshop_snapshot_bound_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            s=LocalDeployment(d,'target')
            with patch.object(s,'_workshop_snapshot',return_value=(spec(),cases(),7)):
                result=s.install_workshop('fixture','revision',approved=True)
                release=read(s.path/(result['release']+'.json'))
                self.assertEqual(release['max_operations'],7)
                with self.assertRaises(ValueError):s.install(spec(),cases(),approved=True,workshop_binding={'run_id':'fixture','revision':'revision'},max_operations=8)

if __name__=='__main__':unittest.main()
