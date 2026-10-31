"""Incremental pre-entry audit must equal full replay; public audits stay full."""
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from commercial.ledger import _NativePrefixReplay, _audit_native_and_jobs, TapeExchange, digest
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services
from adaptive_enterprise.instruments import SOURCE_PATHS as ADAPTIVE_PATHS, prepare_services as prepare_adaptive
ROOT=Path(__file__).resolve().parents[1]

class PrefixReplayTests(unittest.TestCase):
    prepare = staticmethod(prepare_services)
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='prefix037-fixture-');cls.root=Path(cls.temp.name)
        for name in sorted(set(SOURCE_PATHS)|set(SERVICE_PATHS)|set(ADAPTIVE_PATHS)):
            p=cls.root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
        cls.manifest=cls.prepare(cls.root,'services')
        cls.records=[]
        with JournalAccount(cls.root,cls.manifest,cls.root/'fixture.sqlite',opening=1000000000,working=0,contract='prefix037') as a:
            cls.records.append(a.export())
            for i in range(12):
                a.cost('cost-'+str(i),1000+i,i)
                cls.records.append(a.export())

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.identity={'writer':'one','source':'fixed','key':'one'}
        self.session=_NativePrefixReplay(lambda:copy.deepcopy(self.identity))
    def tearDown(self):self.session.close()
    def check(self,record,session=None):
        return _audit_native_and_jobs(record['ledger'],root=self.root,manifest=self.manifest,_session=session)
    def error(self,record,session=None):
        try:self.check(record,session)
        except Exception as e:return type(e).__name__,str(e)
        self.fail('Corruption accepted')

    def test_every_prefix_matches_full_and_only_suffix_executes(self):
        calls=[];original=TapeExchange.execute
        def execute(this,*a,**kw):calls.append(a[0]);return original(this,*a,**kw)
        for record in self.records:
            full=self.check(record)
            with patch.object(TapeExchange,'execute',execute):got=self.check(record,self.session)
            self.assertEqual(got,full)
        self.assertEqual(len(calls),12)
        self.assertEqual(self.session._length,12)

    def test_same_head_and_size_old_prefix_tamper_has_same_error(self):
        self.check(self.records[-1],self.session)
        changed=copy.deepcopy(self.records[-1]);changed['ledger']['actions'][0]['args']['amount']+=1
        # Same supplied head and list length cannot authorize stale prefix reuse.
        self.assertEqual(self.error(changed),self.error(changed,self.session))
        self.assertIsNone(self.session._replay)
        self.check(self.records[-1],self.session)
        changed['ledger']['actions_sha256']=digest(changed['ledger']['actions'])
        self.assertEqual(self.error(changed),self.error(changed,self.session))
        self.assertIsNone(self.session._replay)

    def test_changed_derived_state_still_checked_when_no_new_actions(self):
        for field in ['summary','journal','orders','investments','investment_witnesses','invoices']:
            self.check(self.records[-1],self.session)
            changed=copy.deepcopy(self.records[-1])
            if field=='summary':changed['ledger'][field]['cash']+=1
            elif field=='journal':changed['ledger'][field][0]['amount']=str(int(changed['ledger'][field][0]['amount'])+1)
            else:changed['ledger'][field].append({'tampered':True})
            self.assertEqual(self.error(changed),self.error(changed,self.session))
            self.assertIsNone(self.session._replay)

    def test_rewind_and_owner_key_source_changes_replay_from_zero(self):
        self.check(self.records[-1],self.session)
        old=self.session._replay
        self.assertEqual(self.check(self.records[3],self.session),self.check(self.records[3]))
        self.assertIsNot(old,self.session._replay)
        for key in ['writer','source','key']:
            old=self.session._replay;self.identity[key]+='changed'
            self.assertEqual(self.check(self.records[5],self.session),self.check(self.records[5]))
            self.assertIsNot(old,self.session._replay)

    @unittest.skipUnless(hasattr(os,'fork'),'POSIX fork ownership test')
    def test_inherited_child_close_does_not_remove_parent_verifier(self):
        self.check(self.records[-1],self.session)
        directory=self.session._tmp
        pid=os.fork()
        if pid==0:
            try:self.session.close()
            finally:os._exit(0)
        _,status=os.waitpid(pid,0)
        self.assertEqual(status,0)
        self.assertTrue(directory.exists())
        self.assertEqual(self.check(self.records[-1],self.session),self.check(self.records[-1]))

    def test_manifest_mismatch_drops_cached_authority(self):
        self.check(self.records[-1],self.session)
        changed=copy.deepcopy(self.records[-1]);changed['ledger']['config']['manifest_sha256']='0'*64
        self.assertEqual(self.error(changed),self.error(changed,self.session))
        self.assertIsNone(self.session._replay)

    def test_public_final_audit_never_uses_cache(self):
        with patch.object(_NativePrefixReplay,'begin',side_effect=AssertionError('public cache used')):
            self.assertTrue(audit_journal(self.records[-1],root=self.root,manifest=self.manifest)['accepted'])

    def test_live_toy_writer_reopen_and_source_error_invalidate(self):
        if self.manifest.get('schema') != 'agi-alpha/adaptive012-services/v1':
            with tempfile.TemporaryDirectory(prefix='prefix037-legacy-') as temp:
                with patch.object(_NativePrefixReplay, 'begin', side_effect=AssertionError('legacy cache used')):
                    with JournalAccount(self.root,self.manifest,Path(temp)/'account.sqlite',opening=1000000000,working=0,contract='prefix037-legacy') as a:
                        a.cost('legacy-cost',1000,0)
                        self.assertIsNone(a._native_prefix)
                        self.assertTrue(a.audit()['accepted'])
            return
        with tempfile.TemporaryDirectory(prefix='prefix037-owner-') as temp:
            path=Path(temp)/'account.sqlite'
            a=JournalAccount(self.root,self.manifest,path,opening=1000000000,working=0,contract='prefix037-live')
            try:
                a.cost('first',1000,0);a.cost('second',1000,1)
                self.assertIsNotNone(a._native_prefix._replay)
                with self.assertRaisesRegex(ValueError,'TAPE_ALREADY_OWNED'):
                    JournalAccount(self.root,self.manifest,path,opening=1000000000,working=0,contract='prefix037-live')
                with patch.object(a,'_assert_current',side_effect=ValueError('CONNECTED_FINANCE_SOURCE_CHANGED')):
                    with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):a._audit_incremental()
                self.assertIsNone(a._native_prefix._replay)
                self.assertEqual(a._audit_incremental(),a.audit())
                with patch.object(a,'_assert_current',side_effect=ValueError('CONNECTED_FINANCE_SOURCE_CHANGED')):
                    with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):a.audit()
                self.assertIsNone(a._native_prefix._replay)
            finally:a.close()
            self.assertIsNone(a._native_prefix._replay)
            with JournalAccount(self.root,self.manifest,path,opening=1000000000,working=0,contract='prefix037-live') as reopened:
                self.assertIsNone(reopened._native_prefix)
                reopened.cost('third',1000,2)
                self.assertEqual(reopened._audit_incremental(),reopened.audit())

class AdaptivePrefixReplayTests(PrefixReplayTests):
    prepare = staticmethod(lambda root,path: prepare_adaptive(root,path,jobs_per_service=32))

    def test_bound_service_bytes_rechecked_with_warm_prefix(self):
        job=next(j for j in self.manifest['jobs'] if j['accepted'])
        names=[job[field] for field in ['input','artifact','receipt']]
        names.append(next(iter(self.manifest['source_hashes'])))
        for name in names:
            self.check(self.records[-1],self.session)
            path=self.root/name;original=path.read_bytes()
            try:
                path.write_bytes(original+b' ')
                self.assertEqual(self.error(self.records[-1]),self.error(self.records[-1],self.session))
                self.assertIsNone(self.session._replay)
            finally:path.write_bytes(original)

    def test_complete_journal_failure_after_native_acceptance_closes_cache(self):
        with tempfile.TemporaryDirectory(prefix='prefix037-journal-') as temp:
            with JournalAccount(self.root,self.manifest,Path(temp)/'account.sqlite',opening=1000000000,working=0,contract='prefix037-journal') as a:
                a.cost('first',1000,0);a.cost('second',1000,1)
                a._audit_incremental()
                original=copy.deepcopy(a._journal)
                a._journal['entries'][0]['receipt']['summary']['cash']+=1
                try:
                    with self.assertRaises(ValueError):a._audit_incremental()
                    self.assertIsNone(a._native_prefix._replay)
                finally:a._journal=original
                self.assertEqual(a._audit_incremental(),a.audit())

if __name__=='__main__':unittest.main()
