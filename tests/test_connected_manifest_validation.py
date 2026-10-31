from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from adaptive_enterprise import instruments
from adaptive_enterprise.account import Account, audit_account
from commercial import ledger
import copy


class CurrentManifestBatchChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='current-manifest-batch-')
        cls.root = Path(cls.fixture.name)
        root = Path(__file__).resolve().parents[1]
        for name in instruments.SOURCE_PATHS:
            target = cls.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
        cls.manifest = instruments.prepare_services(cls.root, 'services', cohort_seed=9915017)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def test_batch_and_standalone_checks_match_every_artifact(self):
        batched = instruments.load_jobs(self.root, self.manifest)
        expected = {job['id']: instruments.check_job(self.root, self.manifest, job)
                    for job in self.manifest['jobs'] if job['accepted']}
        self.assertEqual(batched, expected)

    def test_manifest_source_changed_during_batch_is_rejected_before_return(self):
        path = self.root / 'adaptive_enterprise/checkers.py'
        original = path.read_bytes()
        check = instruments._check_job
        changed = False
        def mutation(*args, **kwargs):
            nonlocal changed
            result = check(*args, **kwargs)
            if not changed:
                path.write_bytes(original + b'\n'); changed = True
            return result
        try:
            with patch.object(instruments, '_check_job', mutation), self.assertRaisesRegex(ValueError, 'ADAPTIVE_EXECUTING_SOURCE_CHANGED'):
                instruments.load_jobs(self.root, self.manifest)
            with self.assertRaisesRegex(ValueError, 'ADAPTIVE_EXECUTING_SOURCE_CHANGED'):
                instruments.check_job(self.root, self.manifest, self.manifest['jobs'][0])
        finally:
            path.write_bytes(original)

    def test_last_artifact_tampering_is_checked_and_not_cached(self):
        instruments.load_jobs(self.root, self.manifest)
        job = self.manifest['jobs'][-1]
        path = self.root / job['artifact']
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_OR_ARTIFACT_CHANGED'):
                instruments.load_jobs(self.root, self.manifest)
        finally:
            path.write_bytes(original)


class NativeAuditJobAuthorityChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CurrentManifestBatchChecks.setUpClass()
        cls.root, cls.manifest = CurrentManifestBatchChecks.root, CurrentManifestBatchChecks.manifest

    @classmethod
    def tearDownClass(cls):
        CurrentManifestBatchChecks.tearDownClass()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='audit-job-authority-')
        self.current_manifest = copy.deepcopy(self.manifest)
        self.account = Account(self.root, self.current_manifest, Path(self.temporary.name) / 'account.sqlite',
                               opening=1_000_000_000, working=0, contract='audit-job-authority')
        self.account.cost('probe', 7, 0)
        self.record = copy.deepcopy(self.account.export())

    def tearDown(self):
        self.account.close(); self.temporary.cleanup()

    def mutate_during_replay(self, mutation):
        execute = ledger.TapeExchange.execute
        changed = False
        def replay(exchange, *args, **kwargs):
            nonlocal changed
            result = execute(exchange, *args, **kwargs)
            if exchange.persistence is None and not changed:
                changed = True; mutation(exchange)
            return result
        return patch.object(ledger.TapeExchange, 'execute', replay)

    def file_change_is_rejected(self, path):
        original = path.read_bytes()
        try:
            with self.mutate_during_replay(lambda _: path.write_bytes(original + b'\n')):
                with self.assertRaises(ValueError):
                    audit_account(self.record, root=self.root, manifest=self.current_manifest)
        finally:
            path.write_bytes(original)

    def test_each_audit_qualifies_cohort_once_and_returns_detached_job_authority(self):
        with patch.object(ledger, 'load_jobs', wraps=ledger.load_jobs) as loads:
            checked = audit_account(self.record, root=self.root, manifest=self.current_manifest)
            self.assertTrue(checked['accepted']); self.assertEqual(loads.call_count, 1)
        receipt, jobs = ledger._audit_native_and_jobs(self.record['ledger'], root=self.root, manifest=self.current_manifest)
        self.assertEqual(set(receipt), {'accepted', 'scope', 'actions_sha256', 'summary', 'orders', 'investments'})
        ident = next(iter(jobs)); jobs[ident]['job']['work_keys'].append('changed-return')
        jobs[ident]['artifact']['changed-return'] = True; jobs[ident]['receipt']['changed-return'] = True
        original_job = next(job for job in self.current_manifest['jobs'] if job['id'] == ident)
        self.assertNotIn('changed-return', original_job['work_keys'])
        with patch.object(ledger, 'load_jobs', wraps=ledger.load_jobs) as loads:
            self.assertTrue(audit_account(self.record, root=self.root, manifest=self.current_manifest)['accepted'])
            self.assertEqual(loads.call_count, 1)

    def test_unused_input_changed_during_replay_is_rejected(self):
        self.file_change_is_rejected(self.root / self.current_manifest['jobs'][-1]['input'])

    def test_unused_artifact_changed_during_replay_is_rejected(self):
        self.file_change_is_rejected(self.root / self.current_manifest['jobs'][-1]['artifact'])

    def test_unused_receipt_changed_during_replay_is_rejected(self):
        self.file_change_is_rejected(self.root / self.current_manifest['jobs'][-1]['receipt'])

    def test_checker_source_changed_during_replay_is_rejected(self):
        self.file_change_is_rejected(self.root / 'adaptive_enterprise/checkers.py')

    def test_manifest_changed_during_replay_is_rejected(self):
        def mutate(_):
            self.current_manifest['resource_receipt']['process_cpu_seconds'] += 1
        with self.mutate_during_replay(mutate), self.assertRaisesRegex(ValueError, 'SOURCE_COHORT_MISMATCH'):
            audit_account(self.record, root=self.root, manifest=self.current_manifest)

    def test_manifest_and_caller_config_cannot_move_post_replay_authority_together(self):
        read = ledger.read_bound
        replayed = False
        def mark_replay(_):
            nonlocal replayed
            replayed = True
        def move_authority(*args, **kwargs):
            current = read(*args, **kwargs)
            if replayed and args[1] == self.current_manifest['jobs'][-1]['receipt']:
                self.current_manifest['resource_receipt']['process_cpu_seconds'] += 1
                self.record['ledger']['config']['manifest_sha256'] = ledger.digest(self.current_manifest)
            return current
        with self.mutate_during_replay(mark_replay), patch.object(ledger, 'read_bound', move_authority):
            with self.assertRaisesRegex(ValueError, 'SOURCE_COHORT_MISMATCH'):
                audit_account(self.record, root=self.root, manifest=self.current_manifest)

    def test_cached_artifact_mutation_and_extra_authority_are_rejected(self):
        def artifact(exchange):
            exchange.jobs[next(iter(exchange.jobs))]['artifact']['unbound'] = True
        def extra(exchange):
            exchange.jobs['unbound-job'] = copy.deepcopy(next(iter(exchange.jobs.values())))
        for mutation in [artifact, extra]:
            with self.subTest(mutation=mutation), self.mutate_during_replay(mutation):
                with self.assertRaisesRegex(ValueError, 'AUDITED_JOB_AUTHORITY'):
                    audit_account(self.record, root=self.root, manifest=self.current_manifest)


if __name__ == '__main__':
    unittest.main()
