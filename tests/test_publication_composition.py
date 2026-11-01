"""Synthetic release-binding tests, never economic or clean-operation qualification."""
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
from scripts import release_connected014 as release
from connected_enterprise.runner import identity

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'evidence/strategic024-publication'

class ComposedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.binding = json.loads((BASE/'COMPOSED_SOURCE_BINDING.json').read_text())
        self.publication = json.loads((ROOT/'docs/completion015/PUBLICATION.json').read_text())
        self.current = identity(ROOT)['files']
        # The retained registration describes its historical source tree. Build
        # a fresh synthetic registration for this test's current bytes instead
        # of modifying that evidence whenever the optional source set grows.
        prior = self.binding['historical_files']
        self.binding.update(current_files=self.current,
            current_source_sha256=release.canonical_digest(self.current),
            source_delta={p:{'before_sha256':prior.get(p),'after_sha256':self.current.get(p)}
                          for p in sorted(set(prior)|set(self.current))
                          if prior.get(p)!=self.current.get(p)})
        self.registration = copy.deepcopy(self.binding)
        self.receipt = {'accepted':True, 'no_git_execution':True,
                        'completed_resume_financially_unchanged':True,
                        'source_sha256':release.canonical_digest(self.current), 'source_files':self.current,
                        'source_archive':{'sha256':'a'*64}, 'public_archive':{'sha256':'b'*64}}
        self.receipt.update(schema='agi-alpha/connected014-clean-qualification/v1',
            commands=[{'command':['python','-m','connected_enterprise',a], 'returncode':0,
                       'stdout':str(i)+'.stdout','stderr':str(i)+'.stderr'}
                      for i,a in enumerate(['run','resume','audit','package','audit'])],
            logs={str(i)+'.'+stream:'d'*64 for i in range(5) for stream in ['stdout','stderr']},
            native_and_operating_audit={'accepted':True,'source_sha256':release.canonical_digest(self.current)},
            keyfree_public_audit={'accepted':True,'source_sha256':release.canonical_digest(self.current)})
        self.receipt_hash = release.canonical_digest(self.receipt)
        self.binding.update(qualification_sha256=self.receipt_hash,
                            source_archive_sha256='a'*64, public_archive_sha256='b'*64)
        self.archive = ROOT

    def verify(self):
        return release.verify_composed_binding(self.binding,self.current,self.publication,
                                               self.receipt,self.receipt_hash,self.archive)

    def test_actual_current_map_and_declared_delta_are_exact(self):
        self.verify()
        self.assertNotEqual(release.canonical_digest(self.current), release.HISTORICAL_SOURCE)

    def test_current_distribution_reconstructs_history_without_separate_archive(self):
        import tempfile
        from scripts import qualify_connected014 as qualifier
        # The exact producer's source-member selection includes plain snapshots;
        # no operation or accepted qualification is fabricated by this test.
        names=set(qualifier.source_paths(ROOT))|{'AGENTS.md','requirements-commercial010.txt','scripts/qualify_connected014.py','docs/connected014/OPERATOR.md'}
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/release.HISTORICAL_SNAPSHOTS).rglob('*.txt') if p.is_file())
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'current-source.zip'
            with zipfile.ZipFile(path,'w') as z:
                for name in sorted(names):z.writestr(name,(ROOT/name).read_bytes())
            self.assertEqual(release.historical_source(path,self.binding['historical_files']),self.binding['historical_files'])

    def test_registration_alone_is_not_qualification(self):
        self.binding = copy.deepcopy(self.registration)
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_unaccepted_qualification_fails(self):
        self.receipt['accepted']=False
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_stale_qualification_fails(self):
        self.receipt['source_sha256']=release.HISTORICAL_SOURCE
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_rebound_qualification_bytes_fail(self):
        self.receipt_hash='c'*64
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_rebound_source_archive_fails(self):
        self.receipt['source_archive']['sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_rebound_public_archive_fails(self):
        self.receipt['public_archive']['sha256']='c'*64
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()

    def test_resume_and_clean_execution_required(self):
        for key in ['no_git_execution','completed_resume_financially_unchanged']:
            with self.subTest(key=key):
                self.receipt[key]=False
                with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):self.verify()
                self.receipt[key]=True

    def test_forged_current_map_cannot_hide_changed_source(self):
        self.binding['current_files']=dict(self.current, **{'unexpected.py':'e'*64})
        with self.assertRaisesRegex(ValueError,'SOURCE_DELTA'):self.verify()

    def test_omitted_delta_fails(self):
        self.binding['source_delta']={}
        with self.assertRaisesRegex(ValueError,'SOURCE_DELTA'):self.verify()

    def test_historical_paper_tamper_even_with_rehashed_binding_fails(self):
        self.publication['invented_new_claim']='qualified'
        self.binding['historical_publication_sha256']=release.canonical_digest(self.publication)
        with self.assertRaisesRegex(ValueError,'HISTORICAL_PUBLICATION'):self.verify()

    def test_historical_source_bytes_tamper_fails(self):
        from unittest.mock import patch
        original=Path.read_bytes
        def changed(path):
            raw=original(path)
            return raw+b'changed' if path.as_posix().endswith('connected_enterprise/engine.py.txt') else raw
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_CHANGED'):self.verify()

    def test_historical_map_tamper_fails(self):
        self.binding['historical_files']['adaptive_enterprise/account.py']='0'*64
        with self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_CHANGED'):self.verify()

    def test_fresh_economics_claim_cannot_replace_scope(self):
        self.binding['scope']='FRESH_COMMERCIAL_SUCCESS'
        with self.assertRaisesRegex(ValueError,'HISTORICAL_PUBLICATION'):self.verify()

    def test_status_and_hashes_without_commands_are_not_execution(self):
        self.receipt['commands']=[]
        with self.assertRaisesRegex(ValueError,'EXECUTED_COMMAND'):self.verify()

    def test_failed_command_and_unbound_audit_fail(self):
        self.receipt['commands'][0]['returncode']=1
        with self.assertRaisesRegex(ValueError,'EXECUTED_COMMAND'):self.verify()
        self.receipt['commands'][0]['returncode']=0
        self.receipt['keyfree_public_audit']['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SOURCE_BOUND_AUDITS'):self.verify()
