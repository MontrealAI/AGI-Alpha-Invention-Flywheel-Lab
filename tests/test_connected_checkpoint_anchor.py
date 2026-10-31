import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from commercial.ledger import operating_state_digest
from connected_enterprise import finance


class CheckpointAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_connected_finance import ConnectedFinanceTests
        cls.fixture_class=ConnectedFinanceTests;cls.fixture_class.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.fixture_class.tearDownClass()

    def setUp(self):
        self.f=self.fixture_class();self.f.setUp();self.path=self.f.path.parent/'STATE.json'
        self.state={'queue':[{'id':'first','time':1}],'current':None,'last_time':0,'processed_events':0,'costs':[]}

    def tearDown(self):
        self.f.tearDown()

    def test_replayed_signed_checkpoint_is_rejected_after_committed_successor(self):
        first=self.f.account.save_checkpoint(self.path,self.state)
        self.f.account.cost('new-version-event',7,1)
        second={**self.state,'queue':[],'last_time':1,'processed_events':1}
        self.f.account.save_checkpoint(self.path,second);before=self.f.account.export()
        with self.assertRaisesRegex(ValueError,'REWIND_FORBIDDEN'):self.f.account.verify_checkpoint(first)
        with self.assertRaisesRegex(ValueError,'REWIND_FORBIDDEN'):self.f.account.save_checkpoint(self.path,self.state)
        self.assertEqual(self.f.account.export(),before)
        self.assertTrue(self.f.account.audit()['accepted'])

    def test_crash_before_anchor_commit_recovers_authenticated_intent(self):
        execute=self.f.account.execute
        def crash(op,args,day):
            if op=='operating_checkpoint':raise InterruptedError('before anchor')
            return execute(op,args,day)
        with patch.object(self.f.account,'execute',side_effect=crash),self.assertRaises(InterruptedError):
            self.f.account.save_checkpoint(self.path,self.state)
        self.f.reopen();checkpoint=json.loads(self.path.read_text())
        self.assertEqual(self.f.account.verify_checkpoint(checkpoint),self.state)
        self.assertEqual(sum(e['op']=='operating_checkpoint' for e in self.f.account.export()['ledger']['actions']),1)

    def test_crash_after_anchor_before_state_write_recovers_exact_state_once(self):
        original=finance.atomic_bytes
        def crash(path,data):
            if Path(path)==self.path:raise InterruptedError('after anchor before STATE')
            return original(path,data)
        with patch.object(finance,'atomic_bytes',side_effect=crash),self.assertRaises(InterruptedError):
            self.f.account.save_checkpoint(self.path,self.state)
        intent=self.f.path.with_name(self.f.path.name+'.operating-checkpoint-intent.json')
        self.assertTrue(intent.exists());self.f.reopen()
        self.assertFalse(intent.exists());checkpoint=json.loads(self.path.read_text())
        self.assertEqual(self.f.account.verify_checkpoint(checkpoint),self.state)
        before=self.f.account.export();self.f.reopen();self.assertEqual(self.f.account.export(),before)

    def test_signed_old_intent_cannot_replace_later_native_history(self):
        original=finance.atomic_bytes
        def crash(path,data):
            if Path(path)==self.path:raise InterruptedError('capture intent')
            return original(path,data)
        with patch.object(finance,'atomic_bytes',side_effect=crash),self.assertRaises(InterruptedError):
            self.f.account.save_checkpoint(self.path,self.state)
        intent=self.f.path.with_name(self.f.path.name+'.operating-checkpoint-intent.json');saved=intent.read_bytes()
        self.f.reopen();self.f.account.cost('after-recovery',9,1)
        self.f.account.save_checkpoint(self.path,{**self.state,'processed_events':1,'last_time':1})
        before=self.path.read_bytes();self.f.account.close();intent.write_bytes(saved)
        self.f.account=self.f.open()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(intent.exists())
        archive=self.f.path.with_name(self.f.path.name+'.rejected-operating-intents')
        self.assertEqual([p.read_bytes() for p in archive.glob('*.json')],[saved])
        self.assertTrue(self.f.account.audit()['accepted'])

    def test_obsolete_intent_cannot_hide_replayed_signed_state(self):
        first=self.f.account.save_checkpoint(self.path,self.state)
        original=finance.atomic_bytes
        def crash(path,data):
            if Path(path)==self.path:raise InterruptedError('capture intent')
            return original(path,data)
        with patch.object(finance,'atomic_bytes',side_effect=crash),self.assertRaises(InterruptedError):
            self.f.account.save_checkpoint(self.path,{**self.state,'processed_events':1,'last_time':1})
        intent=self.f.path.with_name(self.f.path.name+'.operating-checkpoint-intent.json');saved=intent.read_bytes()
        self.f.reopen();self.f.account.cost('later',1,2)
        self.f.account.save_checkpoint(self.path,{**self.state,'processed_events':2,'last_time':2})
        self.f.account.close();intent.write_bytes(saved)
        self.path.write_text(json.dumps(first))
        with self.assertRaisesRegex(ValueError,'REWIND_FORBIDDEN'):self.f.open()
        self.assertEqual(intent.read_bytes(),saved)
        intent.unlink()

    def test_unsigned_obsolete_intent_is_rejected_without_changing_current_state(self):
        self.f.account.save_checkpoint(self.path,self.state);before=self.path.read_bytes()
        self.f.account.close()
        intent=self.f.path.with_name(self.f.path.name+'.operating-checkpoint-intent.json')
        intent.write_text(json.dumps({'body':{},'signature':'0'*64}))
        with self.assertRaisesRegex(ValueError,'AUTHORITY_CHANGED'):self.f.open()
        self.assertEqual(self.path.read_bytes(),before);self.assertTrue(intent.exists())
        intent.unlink()

    def test_anchor_excludes_only_diagnostic_timing_and_keeps_money_and_obligations(self):
        state={'costs':[{'amount':7,'process_cpu_seconds':1.0}],'tailReserve':20,'queue':[{'time':4,'kind':'clear'}]}
        changed=copy.deepcopy(state);changed['costs'][0]['process_cpu_seconds']=99.0
        self.assertEqual(operating_state_digest(state),operating_state_digest(changed))
        for key in ['tailReserve','queue','costs']:
            changed=copy.deepcopy(state);changed[key]=[] if isinstance(changed[key],list) else 21
            self.assertNotEqual(operating_state_digest(state),operating_state_digest(changed))


if __name__=='__main__':unittest.main()
