"""Abrupt startup interruption must preserve authenticated native identity.

All processes operate only on fresh disposable synthetic accounts. A lost
checkpoint after any native operation remains a refusal, not a restart.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from campaign.genesis_commitment001 import service
from connected_enterprise.finance import source_paths_for_manifest

ROOT = Path(service.__file__).resolve().parents[2]
OPENING = 100_000_000_000
FAULT_EXIT = 83

FAULT = r'''
import hashlib,json,os,sys
from pathlib import Path
from campaign.genesis_commitment001 import runner
out,marker,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
if mode=='registration_only':
    runner._register(out,'central','retained')
    marker.write_text(json.dumps({'boundary':'registration_before_account'}))
    os._exit(83)
original=runner.BusinessAccount
class StopBeforeFirstCheckpoint(original):
    def __enter__(self):
        entered=super().__enter__()
        def stop(audit=True):
            record=self.account.export()
            path=out/'private'/'account.sqlite'
            key=path.with_name(path.name+'.adaptive-simulation-key')
            tape=path.with_name(path.name+'.actions.jsonl')
            observation={
                'boundary':'authenticated_account_before_first_operating_checkpoint',
                'mode':mode,'audit_accepted':self.account.audit()['accepted'] if audit else None,
                'config':record['ledger']['config'],'summary':record['ledger']['summary'],
                'native_actions':len(record['ledger']['actions']),
                'connected_entries':len(record['connected_journal']['entries']),
                'connected_statuses':[e['status'] for e in record['connected_journal']['entries']],
                'signer_sha256':hashlib.sha256(key.read_bytes()).hexdigest(),
                'tape_sha256':hashlib.sha256(tape.read_bytes()).hexdigest(),
                'tape_inode':tape.stat().st_ino,
                'checkpoint_exists':(out/'private'/'STATE.json').exists(),
            }
            marker.write_text(json.dumps(observation))
            # Real abrupt process exit: context managers and normal account
            # close do not run; the OS releases the single-writer lease.
            os._exit(83)
        if mode=='expense':
            runner._spend(self.account,'setup-research','research',200_000_000,0,allow_seed=True)
        elif mode=='wallet':
            self.account.execute('wallet',{'buyer':'startup-probe','amount':1_000_000},0)
        elif mode=='pending_expense':
            # The real JournalAccount persists its signed PENDING intent before
            # invoking the native cost. Stop at that seam without performing it.
            self.account._account.cost=lambda *args,**kwargs:stop(audit=False)
            runner._spend(self.account,'setup-research','research',200_000_000,0,allow_seed=True)
            raise RuntimeError('PENDING_FAULT_NOT_REACHED')
        elif mode!='pristine':
            raise ValueError('UNKNOWN_FAULT_CASE')
        stop()
runner.BusinessAccount=StopBeforeFirstCheckpoint
runner.run(out,scenario='central',arm='retained')
raise SystemExit('FAULT_BOUNDARY_NOT_REACHED')
'''


class CommitmentStartupRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='commitment-startup-source-')
        cls.source=Path(cls.temporary.name)/'source'
        for name in source_paths_for_manifest({'schema':service.SCHEMA}):
            target=cls.source/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='commitment-startup-case-')
        self.home=Path(self.case.name);self.output=self.home/'operating'
        self.marker=self.home/'fault-observation.json'

    def tearDown(self):
        self.case.cleanup()

    def crash(self,mode='pristine'):
        result=subprocess.run([sys.executable,'-c',FAULT,str(self.output),str(self.marker),mode],
                              cwd=self.source,capture_output=True,text=True)
        self.assertEqual(result.returncode,FAULT_EXIT,result.stdout+result.stderr)
        self.assertTrue(self.marker.is_file())
        self.assertFalse((self.output/'private'/'STATE.json').exists())
        return json.loads(self.marker.read_text())

    def resume(self,*,max_steps=None):
        command=[sys.executable,'-m','campaign.genesis_commitment001.runner','resume',
                 '--output',str(self.output),'--scenario','central','--arm','retained']
        if max_steps is not None:command+=['--max-steps',str(max_steps)]
        return subprocess.run(command,cwd=self.source,capture_output=True,text=True)

    def authority_bytes(self):
        private=self.output/'private'
        suffixes=('.adaptive-simulation-key','.actions.jsonl','.connected-journal.json',
                  '.adaptive-account.json','.adaptive-proofs.json','.adaptive-resolutions.json')
        return {suffix:(private/('account.sqlite'+suffix)).read_bytes()
                for suffix in suffixes if (private/('account.sqlite'+suffix)).is_file()}

    def assert_refused_without_new_state_or_authority(self):
        before=self.authority_bytes()
        result=self.resume()
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse((self.output/'private'/'STATE.json').exists())
        self.assertFalse((self.output/'REPORT.json').exists())
        self.assertEqual(self.authority_bytes(),before)
        return result

    def test_pristine_initialized_account_resumes_same_signer_without_reseeding(self):
        original=self.crash()
        self.assertTrue(original['audit_accepted'])
        self.assertEqual(original['native_actions'],0)
        self.assertEqual(original['connected_entries'],0)
        self.assertEqual(original['config']['opening'],OPENING)
        self.assertEqual(original['summary']['cash'],OPENING)
        before=self.authority_bytes()
        result=self.resume(max_steps=0)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.authority_bytes(),before)
        tape=self.output/'private'/'account.sqlite.actions.jsonl'
        self.assertEqual(tape.stat().st_ino,original['tape_inode'])
        record=json.loads((self.output/'NATIVE_EXPORT.json').read_text())
        self.assertEqual(record['ledger']['config'],original['config'])
        self.assertEqual(record['ledger']['actions'],[])
        self.assertEqual(record['connected_journal']['entries'],[])
        state=json.loads((self.output/'private'/'STATE.json').read_text())
        self.assertEqual(state['body']['native_sequence'],0)
        self.assertEqual(state['body']['state']['phase'],'setup')
        # Complete that same account and retry. Exactly the original $100,000
        # less the registered central-case costs remains; no extra seed appears.
        result=self.resume()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads((self.output/'REPORT.json').read_text())
        self.assertEqual(report['opening_microUSD'],OPENING)
        self.assertEqual(report['native_summary']['cash'],98_920_000_000)
        self.assertEqual(report['native_summary']['expenses'],1_080_000_000)
        key=self.output/'private'/'account.sqlite.adaptive-simulation-key'
        self.assertEqual(hashlib.sha256(key.read_bytes()).hexdigest(),original['signer_sha256'])
        exported=(self.output/'NATIVE_EXPORT.json').read_bytes()
        result=self.resume()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.output/'NATIVE_EXPORT.json').read_bytes(),exported)

    def test_missing_checkpoint_after_first_expense_remains_rejected(self):
        original=self.crash('expense')
        self.assertTrue(original['audit_accepted'])
        self.assertEqual(original['native_actions'],1)
        self.assertEqual(original['connected_entries'],1)
        self.assertEqual(original['summary']['expenses'],200_000_000)
        result=self.assert_refused_without_new_state_or_authority()
        self.assertIn('SIGNED_CHECKPOINT_REQUIRED',result.stderr)

    def test_missing_checkpoint_after_nonfinancial_operation_remains_rejected(self):
        original=self.crash('wallet')
        self.assertTrue(original['audit_accepted'])
        self.assertEqual(original['native_actions'],1)
        self.assertEqual(original['summary']['expenses'],0)
        self.assertEqual(original['summary']['cash'],OPENING)
        result=self.assert_refused_without_new_state_or_authority()
        self.assertIn('SIGNED_CHECKPOINT_REQUIRED',result.stderr)

    def test_missing_checkpoint_with_pending_intent_does_not_execute_recovery(self):
        original=self.crash('pending_expense')
        self.assertEqual(original['native_actions'],0)
        self.assertEqual(original['connected_entries'],1)
        self.assertEqual(original['connected_statuses'],['PENDING'])
        self.assertEqual(original['summary']['cash'],OPENING)
        result=self.assert_refused_without_new_state_or_authority()
        self.assertIn('SIGNED_CHECKPOINT_REQUIRED',result.stderr)

    def test_missing_signer_is_not_recreated_for_pristine_existing_account(self):
        self.crash()
        key=self.output/'private'/'account.sqlite.adaptive-simulation-key';key.unlink()
        result=self.assert_refused_without_new_state_or_authority()
        self.assertIn('EXISTING_ACCOUNT_AUTHORITY_REQUIRED',result.stderr)
        self.assertFalse(key.exists())

    def test_corrupt_connected_journal_is_not_used_to_authorize_new_checkpoint(self):
        self.crash()
        path=self.output/'private'/'account.sqlite.connected-journal.json'
        envelope=json.loads(path.read_text())
        envelope['signature']='0'*64
        path.write_text(json.dumps(envelope))
        self.assert_refused_without_new_state_or_authority()

    def test_completed_registration_without_account_can_initialize_once(self):
        self.crash('registration_only')
        self.assertFalse((self.output/'private').exists())
        result=self.resume(max_steps=0)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        record=json.loads((self.output/'NATIVE_EXPORT.json').read_text())
        self.assertEqual(record['ledger']['config']['opening'],OPENING)
        self.assertEqual(record['ledger']['summary']['cash'],OPENING)
        self.assertEqual(record['ledger']['actions'],[])
        before=self.authority_bytes()
        result=self.resume(max_steps=0)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.authority_bytes(),before)


if __name__=='__main__':
    unittest.main()
