"""Directed I/O-race and native accounting checks for current 009 qualification."""
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CAPSULE = ROOT / 'campaign/consequential-009/qualification_v2'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load('qualification009_monitor_test', CAPSULE / 'resource_guard.py')
runner = load('qualification009_runner_test', CAPSULE / 'run.py')


class JournalRaceTests(unittest.TestCase):
    def fixture(self, base):
        journal = base / 'artifacts/outage_delay/exchange.sqlite-journal'
        journal.parent.mkdir(parents=True)
        database = journal.with_name('exchange.sqlite')
        database.write_bytes(b'durable database')
        journal.write_bytes(b'transient journal')
        scanner = guard.StorageScan(base, ['artifacts/outage_delay/exchange.sqlite-journal'])
        return scanner, journal, database

    def test_enumerated_native_journal_disappears_before_single_stat(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scanner, journal, database = self.fixture(base)
            original = Path.lstat
            calls = []

            def disappear(path, *args, **kwargs):
                calls.append(path)
                if path == journal:
                    path.unlink()
                return original(path, *args, **kwargs)

            with patch.object(Path, 'rglob', return_value=iter([journal, database])), patch.object(Path, 'lstat', disappear):
                self.assertEqual(scanner.sizes(base), [len(b'durable database')])
            self.assertEqual(calls.count(journal), 1)
            self.assertEqual(scanner.vanished_count, 1)
            self.assertEqual(scanner.vanished_examples, ['artifacts/outage_delay/exchange.sqlite-journal'])

    def test_missing_nonjournal_and_unauthorized_world_are_not_suppressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scanner, _, _ = self.fixture(base)
            for name in ['artifacts/outage_delay/REPORT.json', 'artifacts/unknown/exchange.sqlite-journal']:
                with self.subTest(name=name), patch.object(Path, 'rglob', return_value=iter([base / name])):
                    with self.assertRaises(FileNotFoundError):
                        scanner.sizes(base)
            self.assertEqual(scanner.vanished_count, 0)

    def test_missing_database_does_not_license_missing_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scanner, journal, database = self.fixture(base)
            journal.unlink()
            database.unlink()
            with patch.object(Path, 'rglob', return_value=iter([journal])):
                with self.assertRaises(FileNotFoundError):
                    scanner.sizes(base)
            self.assertEqual(scanner.vanished_count, 0)

    def test_permission_and_nontransient_io_errors_propagate(self):
        for error in [PermissionError(errno.EACCES, 'permission denied'), OSError(errno.EIO, 'I/O failure')]:
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                scanner, journal, _ = self.fixture(base)
                with patch.object(Path, 'rglob', return_value=iter([journal])), patch.object(Path, 'lstat', side_effect=error):
                    with self.assertRaises(type(error)) as caught:
                        scanner.sizes(base)
                self.assertIs(caught.exception, error)
                self.assertEqual(scanner.vanished_count, 0)

    def test_live_file_sizes_and_symlink_bytes_are_charged(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scanner, journal, database = self.fixture(base)
            link = base / 'link'
            link.symlink_to('artifacts/outage_delay/exchange.sqlite')
            expected = sum(p.lstat().st_size for p in [journal, database, link])
            self.assertEqual(sum(scanner.sizes(base)), expected)
            self.assertEqual(scanner.vanished_count, 0)


class NativeBoundaryTests(unittest.TestCase):
    def test_original_freezes_guard_runner_packager_and_workflow_snapshot_stay_exact(self):
        self.assertEqual(guard.sha((ROOT / 'experiments/resource006_v3.py').read_bytes()), guard.INHERITED_GUARD)
        freeze_raw = (ROOT / runner.FREEZE).read_bytes()
        self.assertEqual(guard.sha(freeze_raw), runner.FREEZE_SHA256)
        pins = json.loads(freeze_raw)['files']
        for name in ['run_consequential009.py', 'scripts/package_consequential009.py']:
            self.assertEqual(guard.sha((ROOT / name).read_bytes()), pins[name])
        self.assertEqual(guard.sha((ROOT / runner.SNAPSHOT).read_bytes()), pins[runner.WORKFLOW])

    def test_materialized_original_closure_and_current_workflow_have_separate_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'frozen'
            report = runner.materialize(ROOT, destination)
            self.assertEqual(report['frozen_files_verified'], 31)
            self.assertEqual(report['historical_workflow_sha256'], guard.sha((ROOT / runner.SNAPSHOT).read_bytes()))
            self.assertEqual(report['current_workflow_sha256'], guard.sha((ROOT / runner.WORKFLOW).read_bytes()))
            self.assertNotEqual(report['historical_workflow_sha256'], report['current_workflow_sha256'])
            for name, expected in json.loads((ROOT / runner.FREEZE).read_text())['files'].items():
                self.assertEqual(guard.sha((destination / name).read_bytes()), expected)
            self.assertFalse((destination / '.git').exists())
            with self.assertRaises(FileExistsError):
                runner.materialize(ROOT, destination)

    def native(self, base, *, payload=0, storage=131072):
        output = base / 'run'
        worker = 'from pathlib import Path;Path(%r).write_bytes(b"x"*%d)' % (str(output / 'payload.bin'), payload)
        result = guard.run([sys.executable, '-c', worker], output, base / 'ledger.json', 'directed-test',
            {'wall_seconds': 3, 'cpu_seconds': 2, 'memory_bytes': 134217728,
             'output_bytes': storage, 'storage_bytes': storage}, ROOT)
        return output, result

    def test_native_receipt_own_bytes_hash_and_settlement_include_actual_adapter(self):
        from experiments import resource006_v3 as historical
        original_usage, original_file = historical._usage, historical.__file__
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output, result = self.native(base, payload=17)
            receipt = result['receipt']
            self.assertEqual(receipt['state'], 'complete')
            self.assertEqual(receipt['wrapper_sha256'], guard.sha((CAPSULE / 'resource_guard.py').read_bytes()))
            self.assertEqual(receipt['qualification_boundary']['inherited_guard_sha256'], guard.INHERITED_GUARD)
            self.assertEqual(receipt['output_bytes'], sum(p.lstat().st_size for p in output.rglob('*') if p.is_file() or p.is_symlink()))
            self.assertEqual(result['receipt_sha256'], historical.digest(receipt))
            ledger = json.loads((base / 'ledger.json').read_text())
            self.assertEqual(ledger['runs']['directed-test']['receipt_sha256'], result['receipt_sha256'])
            self.assertEqual(ledger['runs']['directed-test']['budget_cpu_seconds'], 2)
            self.assertFalse(receipt['descendant_survivors'])
        self.assertIs(historical._usage, original_usage)
        self.assertEqual(historical.__file__, original_file)

    def test_actual_aggregate_storage_crossing_still_blocks_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output, result = self.native(base, payload=15000, storage=16384)
            receipt = result['receipt']
            self.assertEqual(receipt['state'], 'overrun')
            self.assertGreater(receipt['output_bytes'], 16384)
            self.assertEqual(json.loads((base / 'ledger.json').read_text())['state'], 'blocked-overrun')
            self.assertFalse(receipt['descendant_survivors'])


if __name__ == '__main__':
    unittest.main()
