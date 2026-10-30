from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from adaptive_enterprise import instruments


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


if __name__ == '__main__':
    unittest.main()
