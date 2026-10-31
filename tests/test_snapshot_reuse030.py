"""Reuse adjacent native snapshots, never a previous operation's state."""
import unittest
from unittest.mock import Mock
from commercial.ledger import TapeExchange


def state(**changes):
    return dict(cash=100,collections=0,recoveryIncome=0,expensePaid=0,
                profit=0,revenue=0,expenses=0,unrestrictedEarned=0,available=100,payables=0,**changes)

class SnapshotReuseTests(unittest.TestCase):
    def owner(self, snapshots):
        obj=TapeExchange.__new__(TapeExchange)
        obj._adaptive_writer=Mock(spec=['assert_owner']);obj.persistence=None;obj.last_day=0;obj.actions=[]
        obj.ex=Mock();obj.ex.opening=100;obj.ex.snapshot.side_effect=snapshots
        return obj

    def test_opening_and_after_each_read_once_with_all_checks(self):
        before=state();after=state();obj=self.owner([before,after])
        result=obj.execute('wallet',{'buyer':'a','amount':1},0,_expected_before=before)
        self.assertEqual(result,after);self.assertEqual(obj.ex.snapshot.call_count,2)
        self.assertEqual(obj.actions[0]['before'],before);self.assertEqual(obj.actions[0]['after'],after)
        obj._adaptive_writer.assert_owner.assert_called_once()

    def test_bad_opening_rejected_before_native_mutation(self):
        for expected in (None,{},dict(state(),cash=99)):
            with self.subTest(expected=expected):
                obj=self.owner([state()])
                with self.assertRaisesRegex(ValueError,'OPENING_STATE_MISMATCH'):
                    obj.execute('wallet',{'buyer':'a','amount':1},0,_expected_before=expected)
                obj.ex.wallet.assert_not_called();self.assertEqual(obj.actions,[])

    def test_no_cross_operation_snapshot_cache(self):
        first=state();second=dict(state(),cash=101,collections=1,available=101)
        obj=self.owner([first,first,second,second])
        obj.execute('wallet',{'buyer':'a','amount':1},0)
        obj.execute('wallet',{'buyer':'b','amount':1},1)
        self.assertEqual(obj.actions[1]['before'],second)
        self.assertEqual(obj.ex.snapshot.call_count,4)

    def test_every_conservation_guard_still_rejects(self):
        variants=[({'cash':99},'CASH_CONSERVATION'),({'profit':1},'PROFIT_CONSERVATION'),
                  ({'unrestrictedEarned':-1},'EARNED_OR_RESTRICTED'),
                  ({'unrestrictedEarned':101},'EARNED_OR_RESTRICTED'),
                  ({'cash':-1,'expensePaid':101},'NEGATIVE_BALANCE'),({'payables':-1},'NEGATIVE_BALANCE')]
        for change,message in variants:
            with self.subTest(change=change):
                obj=self.owner([state(),dict(state(),**change)])
                with self.assertRaisesRegex(ValueError,message):obj.execute('wallet',{'buyer':'a','amount':1},0)
                self.assertEqual(obj.actions,[])

    def test_public_conservation_check_always_reads_current_native_state(self):
        obj=self.owner([state(),dict(state(),payables=-1)])
        obj.assert_conservation()
        with self.assertRaisesRegex(ValueError,'NEGATIVE_BALANCE'):obj.assert_conservation()
        self.assertEqual(obj.ex.snapshot.call_count,2)

    def test_lost_writer_ownership_prevents_even_snapshot(self):
        obj=self.owner([state()]);obj._adaptive_writer.assert_owner.side_effect=ValueError('LOST_OWNER')
        with self.assertRaisesRegex(ValueError,'LOST_OWNER'):obj.execute('wallet',{'buyer':'a','amount':1},0)
        obj.ex.snapshot.assert_not_called();obj.ex.wallet.assert_not_called()

class RealNativeReplayTests(unittest.TestCase):
    def test_real_memory_ledger_replay_and_stale_opening_rejection(self):
        from pathlib import Path
        import copy
        import tempfile
        from unittest.mock import patch
        from commercial.ledger import _audit_native_and_jobs, digest
        with tempfile.TemporaryDirectory() as tmp, patch('commercial.ledger.load_jobs',return_value={}):
            owner=TapeExchange(Path(tmp)/'native.sqlite',root=Path(__file__).resolve().parents[1],
                               manifest={'jobs':[]},opening=100,working=0,contract='snapshot-test',durable=False)
            try:
                owner.execute('wallet',{'buyer':'test','amount':5},0)
                owner.execute('cost',{'id':'test-cost','amount':3},1)
                tape=copy.deepcopy(owner.export())
                checked,_=_audit_native_and_jobs(tape,root=owner.root,manifest=owner.manifest)
                self.assertTrue(checked['accepted']);self.assertEqual(checked['summary'],tape['summary'])
                bad=copy.deepcopy(tape);bad['actions'][0]['before']['cash']+=1;bad['actions_sha256']=digest(bad['actions'])
                with self.assertRaisesRegex(ValueError,'OPENING_STATE_MISMATCH'):
                    _audit_native_and_jobs(bad,root=owner.root,manifest=owner.manifest)
            finally:owner.close()

    def test_competing_native_owner_is_still_rejected(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from commercial.single_writer import SingleWriterExchange
        with tempfile.TemporaryDirectory() as tmp, patch('commercial.ledger.load_jobs',return_value={}):
            path=Path(tmp)/'native.sqlite';kwargs=dict(root=Path(__file__).resolve().parents[1],manifest={'jobs':[]},opening=100,working=0,contract='ownership-test',durable=False)
            owner=SingleWriterExchange(path,**kwargs)
            try:
                with self.assertRaises(ValueError):SingleWriterExchange(path,**kwargs)
                owner.execute('cost',{'id':'cost','amount':1},0)
                self.assertEqual(owner.snapshot()['cash'],99)
            finally:owner.close()
