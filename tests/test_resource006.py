import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from experiments.resource006 import run, reserve, settle, CAP_CPU


class ResourceTests(unittest.TestCase):
    def limits(self, **changed):
        return {'wall_seconds': 3, 'cpu_seconds': 2, 'memory_bytes': 128*1024**2,
                'output_bytes': 1024**2, 'storage_bytes': 2*1024**2, **changed}

    def test_success_failure_and_idempotent_settlement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root/'ledger.json'
            first = run([sys.executable, '-c', 'print("accepted")'], root/'first', ledger, 'first', self.limits())
            self.assertEqual(first['receipt']['state'], 'complete')
            self.assertEqual(first['receipt']['exit_code'], 0)
            self.assertEqual((root/'first/stdout.log').read_text(), 'accepted\n')
            self.assertEqual(settle(ledger, 'first', first['receipt']), first['settlement'])
            second = run([sys.executable, '-c', 'raise SystemExit(7)'], root/'second', ledger, 'second', self.limits())
            self.assertEqual(second['receipt']['state'], 'failed')
            self.assertEqual(second['receipt']['exit_code'], 7)
            self.assertFalse(second['receipt']['aggregate_cpu_complete'])
            with self.assertRaisesRegex(ValueError, 'RESOURCE_RUN_ID_REUSED'):
                run([sys.executable, '-c', 'pass'], root/'duplicate', ledger, 'first', self.limits())
            self.assertFalse((root/'duplicate').exists())

    def test_wall_interruption_keeps_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = run([sys.executable, '-c', 'import time; time.sleep(5)'], root/'run', root/'ledger.json', 'timeout', self.limits(wall_seconds=1))
            self.assertEqual(result['receipt']['state'], 'interrupted')
            self.assertEqual(result['receipt']['reason'], 'wall-limit')
            self.assertEqual(result['settlement']['state'], 'pending-interruption')
            self.assertEqual(result['settlement']['budget_cpu_seconds'], 2)

    def test_initialization_interrupt_and_budget_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('experiments.resource006.subprocess.Popen', side_effect=KeyboardInterrupt):
                result = run([sys.executable, '-c', 'pass'], root/'init', root/'ledger.json', 'init', self.limits())
            self.assertEqual(result['receipt']['state'], 'interrupted')
            self.assertTrue((root/'init/RECEIPT.json').exists())
            self.assertEqual(result['settlement']['state'], 'pending-interruption')
            reserve(root/'ledger.json', 'remainder', self.limits(cpu_seconds=CAP_CPU-2))
            with self.assertRaisesRegex(ValueError, 'RESOURCE_ALLOCATION_EXHAUSTED'):
                reserve(root/'ledger.json', 'exhausted', self.limits())
            with self.assertRaisesRegex(ValueError, 'RESOURCE_LIMIT_KEYS'):
                reserve(root/'other.json', 'bad', {'unknown': 1})

    def test_python_aliases_use_current_interpreter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for alias in ['python', 'python3']:
                result = run([alias, '-c', 'import sys; print(sys.executable)'], root/alias, root/'ledger.json', alias, self.limits())
                self.assertEqual(result['receipt']['state'], 'complete')
                self.assertEqual(result['receipt']['requested_command'][0], alias)
                self.assertEqual(result['receipt']['normalized_command'][0], sys.executable)
                self.assertEqual((root/alias/'stdout.log').read_text().strip(), sys.executable)

    def test_bad_executables_refuse_without_changing_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root/'ledger.json'
            reserve(ledger, 'preserved', self.limits())
            before = ledger.read_bytes()
            for index, executable in enumerate(['/definitely/missing/alpha006-command', 'relative-command', str(root)]):
                result = run([executable], root/str(index), ledger, 'refused%d' % index, self.limits())
                self.assertEqual(result['receipt']['state'], 'refused')
                self.assertFalse(result['receipt']['reservation_created'])
                self.assertIsNone(result['settlement'])
                self.assertTrue((root/str(index)/'REFUSAL.json').exists())
                self.assertEqual(ledger.read_bytes(), before)
            with self.assertRaises(ValueError):
                run(['bad\x00path'], root/'null', ledger, 'null', self.limits())
            self.assertFalse((root/'null').exists())
            self.assertEqual(ledger.read_bytes(), before)

    def test_launch_error_has_bounded_typed_detail(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('experiments.resource006.subprocess.Popen', side_effect=OSError('e'*1000)):
                result = run([sys.executable, '-c', 'pass'], root/'run', root/'ledger.json', 'launcherror', self.limits())
            self.assertEqual(result['receipt']['reason'], 'launch-or-monitor-error')
            self.assertEqual(result['receipt']['error']['type'], 'OSError')
            self.assertEqual(len(result['receipt']['error']['message']), 512)
            self.assertEqual(result['settlement']['budget_cpu_seconds'], 2)
