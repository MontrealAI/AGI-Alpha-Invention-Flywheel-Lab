import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from enterprise.runner import RunLock, audit_run, canonical, freeze_run, protocol, tasks_for, write_json

ROOT = Path(__file__).resolve().parents[1]


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='enterprise011-runner-tests-')
        cls.output = Path(cls.temp.name)/'executed'
        subprocess.run([sys.executable, '-m', 'enterprise', 'run', '--output', str(cls.output), '--smoke'], cwd=ROOT, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_snapshot_command_and_native_audit(self):
        self.assertFalse((self.output/'source/.git').exists())
        self.assertTrue(audit_run(self.output)['accepted'])
        report = json.loads((self.output/'REPORT.json').read_text())
        self.assertEqual(report['service_count'], 3)
        self.assertEqual(report['actual_artifacts'], 96)
        self.assertEqual(report['verdicts']['actual_commercial_operation'], 'NOT_EXECUTED')

    def test_no_output_overwrite(self):
        with self.assertRaises(FileExistsError):
            freeze_run(self.output, True)

    def test_confirmation_fixed_coverage_is_not_smoke(self):
        p = protocol()
        self.assertFalse(set(p['seeds']) & set(p['development_seeds']))
        tasks = tasks_for({'protocol': p})
        self.assertEqual(len(tasks), len(set(tasks)))
        self.assertEqual(sum(not t[-1] for t in tasks), 128)
        self.assertEqual(len(tasks), 188)

    def test_concurrent_owner_cannot_resume_same_output(self):
        with tempfile.TemporaryDirectory() as directory:
            with RunLock(directory):
                with self.assertRaisesRegex(ValueError, 'ANOTHER_CURRENT_RUN'):
                    with RunLock(directory):
                        pass

    def test_dropped_or_duplicate_world_refused(self):
        path = self.output/'INDEX.json'; original = path.read_bytes()
        try:
            index = json.loads(original); index['worlds'][-1] = index['worlds'][0]
            write_json(path, index)
            with self.assertRaisesRegex(ValueError, 'COVERAGE'):
                audit_run(self.output)
        finally:
            path.write_bytes(original)

    def test_jointly_rehashed_false_report_refused(self):
        path, complete = self.output/'REPORT.json', self.output/'COMPLETE.json'
        original, completion = path.read_bytes(), complete.read_bytes()
        try:
            report = json.loads(original); report['central_region']['paid_jobs_total'] += 1
            write_json(path, report)
            ending = json.loads(completion); ending['report_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest(); write_json(complete, ending)
            with self.assertRaisesRegex(ValueError, 'REPORT_DERIVATION'):
                audit_run(self.output)
        finally:
            path.write_bytes(original); complete.write_bytes(completion)

    def test_wrong_seed_cannot_fill_checkpoint(self):
        index_path = self.output/'INDEX.json'; original_index = index_path.read_bytes()
        index = json.loads(original_index); item = index['worlds'][0]; path = self.output/item['path']; original = path.read_bytes()
        try:
            result = json.loads(gzip.decompress(original)); result['seed'] += 1
            path.write_bytes(gzip.compress(canonical(result), mtime=0)); item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest(); item['bytes'] = path.stat().st_size; write_json(index_path, index)
            with self.assertRaisesRegex(ValueError, 'TASK_OR_MANIFEST'):
                audit_run(self.output)
        finally:
            path.write_bytes(original); index_path.write_bytes(original_index)

    def test_false_operating_counts_rejected_after_native_audit(self):
        index_path = self.output/'INDEX.json'; original_index = index_path.read_bytes()
        index = json.loads(original_index); item = index['worlds'][0]; path = self.output/item['path']; original = path.read_bytes()
        try:
            result = json.loads(gzip.decompress(original)); result['repeat_buyers'] += 1
            path.write_bytes(gzip.compress(canonical(result), mtime=0)); item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest(); item['bytes'] = path.stat().st_size; write_json(index_path, index)
            with self.assertRaisesRegex(ValueError, 'OPERATIONAL_REPLAY'):
                audit_run(self.output)
        finally:
            path.write_bytes(original); index_path.write_bytes(original_index)

    def test_completed_worlds_resume_without_duplicate_settlement(self):
        index = json.loads((self.output/'INDEX.json').read_text())
        hashes = {x['path']: x['sha256'] for x in index['worlds']}
        subprocess.run([sys.executable, '-m', 'enterprise', 'resume', '--output', str(self.output)], cwd=ROOT, check=True, capture_output=True)
        resumed = json.loads((self.output/'INDEX.json').read_text())
        self.assertEqual(hashes, {x['path']: x['sha256'] for x in resumed['worlds']})

    def test_torn_world_preserved_then_recomputed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'recover'; shutil.copytree(self.output, output)
            index = json.loads((output/'INDEX.json').read_text()); item = index['worlds'][-1]; path = output/item['path']
            path.write_bytes(path.read_bytes()[:20])
            subprocess.run([sys.executable, '-m', 'enterprise', 'resume', '--output', str(output)], cwd=ROOT, check=True, capture_output=True)
            self.assertTrue(list(path.parent.glob(path.name + '.interrupted-*')))
            self.assertTrue(audit_run(output)['accepted'])
