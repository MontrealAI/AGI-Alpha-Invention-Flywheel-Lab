import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from operational075 import broker


def fixture_inputs():
    public={day:{'customers':{0:{'tw_end':50000}},'duration':[[0]]} for day in broker.DAYS}
    rows=[{'service_day_id':day,'dispatch_round':r,'ready_time':r*3600,'order_id':day+'-synthetic-'+str(r),'customer_id':0,'demand':1,'service_time':0,'tw_start':0,'tw_end':50000} for day in broker.DAYS for r in broker.ROUNDS]
    return public,rows


def fixture_resources(hashes):
    return {'wall_seconds':0,'child_cpu_seconds':0,'policy_cpu_seconds':0,'returncode':0,'worker_payload_hashes':hashes,'worker_guard_sha256':hashlib.sha256(broker._WORKER.encode()).hexdigest()}


class BrokerBoundaryTests(unittest.TestCase):
    def test_only_current_cumulative_confirmations_are_released(self):
        public,rows=fixture_inputs()
        first=broker.visible_window(public,rows,0);second=broker.visible_window(public,rows,1)
        self.assertEqual([r['dispatch_round'] for r in first['orders']],[1])
        self.assertEqual([r['dispatch_round'] for r in second['orders']],[1,2])
        self.assertTrue(all(r['service_day_id']=='GD01' for r in second['orders']))

    def test_explicit_bundle_excludes_outcomes_and_binds_retained_json(self):
        with tempfile.TemporaryDirectory() as folder:
            package=Path(folder)
            for name in ('ordinary.py','wave.py','RETAINED.json'):(package/name).write_text('{}' if name.endswith('.json') else '')
            (package/'FUTURE_RESULT.json').write_text('{"future":true}');(package/'future_solver.py').write_text('')
            first=broker.worker_bundle(package);before=broker.worker_payload_hashes(first)
            self.assertNotIn('FUTURE_RESULT.json',first);self.assertNotIn('future_solver.py',first)
            self.assertEqual(first['__init__.py'],b'')
            (package/'RETAINED.json').write_text('{"changed":true}')
            self.assertNotEqual(before,broker.worker_payload_hashes(broker.worker_bundle(package)))

    def test_bundle_drift_rejects_before_policy_invocation(self):
        original={'ordinary.py':b'original','wave.py':b'','RETAINED.json':b'{}','__init__.py':b''}
        changed=dict(original,**{'RETAINED.json':b'{"changed":true}'})
        with patch.object(broker,'worker_bundle',return_value=changed):
            with self.assertRaisesRegex(ValueError,'WORKER_PAYLOAD_CHANGED'):
                broker.run_policy('operational075.ordinary',{},None,expected_payload_hashes=broker.worker_payload_hashes(original))

    def test_locked_envelope_and_bundle_tampering_are_rejected(self):
        public,rows=fixture_inputs();window=broker.visible_window(public,rows,0);raw=b'{"routes":[]}';state={};hashes={'ordinary.py':'a'*64};resources=fixture_resources(hashes)
        with tempfile.TemporaryDirectory() as folder:
            receipt=broker.lock_submission(folder,0,raw,window,state,resources,None)
            broker.check_locked_receipt(receipt,0,raw,window,state,None,hashes)
            for field,value in [('epoch',1),('service_day_id','GD02'),('dispatch_round',2),('submission_bytes',len(raw)+1),('intermediate_score_returned',True)]:
                bad=copy.deepcopy(receipt);bad[field]=value
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'LOCKED_HISTORY_CHANGED'):
                    broker.check_locked_receipt(bad,0,raw,window,state,None,hashes)
            bad=copy.deepcopy(receipt);bad['resources']['worker_payload_hashes']={}
            with self.assertRaisesRegex(ValueError,'LOCKED_WORKER_PAYLOAD_CHANGED'):
                broker.check_locked_receipt(bad,0,raw,window,state,None,hashes)
            with self.assertRaises(FileExistsError):broker.lock_submission(folder,0,b'{}',window,state,resources,None)

    def test_resume_rejects_relabelled_period_before_new_policy_work(self):
        public,rows=fixture_inputs();source_receipt={'source_manifest_sha256':'fixture','upstream_commit':'fixture'};hashes=broker.worker_payload_hashes();calls=[]
        def produce(module,window,state,**kwargs):
            calls.append(window['epoch'])
            if window['epoch']==1:raise ValueError('SYNTHETIC_INTERRUPTION')
            return broker.encoded({'service_day_id':window['service_day_id'],'dispatch_round':window['dispatch_round'],'routes':[]}),{},fixture_resources(hashes)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source';root.mkdir();out=Path(folder)/'episode'
            with patch.object(broker.source,'verify_source',return_value=source_receipt),patch.object(broker,'_load_public',return_value=public),patch.object(broker,'_load_confirmations',return_value=rows),patch.object(broker,'run_policy',side_effect=produce):
                with self.assertRaisesRegex(ValueError,'SYNTHETIC_INTERRUPTION'):broker.run_episode(root,'operational075.ordinary',out)
                path=out/'periods/00/RECEIPT.json';bad=json.loads(path.read_text());bad['epoch']=1;path.write_text(json.dumps(bad));calls.clear()
                with self.assertRaisesRegex(ValueError,'LOCKED_HISTORY_CHANGED'):broker.run_episode(root,'operational075.ordinary',out)
                self.assertEqual(calls,[])

    def test_order_parser_preserves_exact_integer_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/broker.source.GROCERY_PRIVATE;path.parent.mkdir(parents=True)
            path.write_text('service_day_id,dispatch_round,ready_time,order_id,customer_id,demand,service_time,window_start,window_end\nGD01,1,3600,synthetic,9007199254740993,1,0,1.9,40000\n')
            row=broker._load_confirmations(folder)[0]
            self.assertEqual(row['customer_id'],9007199254740993);self.assertEqual(row['tw_start'],1)
            path.write_text(path.read_text().replace(',1,0,1.9',',1.5,0,1.9'))
            with self.assertRaises(ValueError):broker._load_confirmations(folder)


if __name__=='__main__':unittest.main()
