import copy
from pathlib import Path
import sys
import tempfile
import unittest

from commercial.portfolio_services import ROOT, build_packet, evaluate_receipt, receipt_expression, render_packet, verify_packet
from experiments.resource006_v3 import run


class PortfolioServicesTests(unittest.TestCase):
    def test_repaired_driver_handles_real_native_success_and_failure(self):
        before = (ROOT / 'historical/commercial-010/attempt-v2/run_commercial010.py').read_bytes()
        after = (ROOT / 'run_commercial010.py').read_bytes()
        limits = {'wall_seconds': 5, 'cpu_seconds': 1, 'memory_bytes': 134217728, 'output_bytes': 20000, 'storage_bytes': 100000}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, command, state in [('success', 'print("real-supervisor-check")', 'complete'), ('failure', 'raise SystemExit(7)', 'failed')]:
                output = root / name
                result = run([sys.executable, '-c', command], output, root / 'resources.json', name, limits, cwd=ROOT)
                self.assertEqual(result['receipt']['state'], state)
                self.assertNotIn('receipt_path', result)
                with self.assertRaises(KeyError):
                    evaluate_receipt(before, result, output)
                self.assertEqual(evaluate_receipt(after, result, output), str(output / 'RECEIPT.json'))
                self.assertTrue((output / 'RECEIPT.json').is_file())

    def test_unsupported_revenue_or_security_attestation_rejected(self):
        packet = build_packet(ROOT)
        packet['claims'][6]['answer'] = 'We observed one billion dollars and are SOC2 certified.'
        with self.assertRaises(ValueError):
            verify_packet(ROOT, packet, render_packet(packet))

    def test_source_identity_mutation_rejected(self):
        packet = build_packet(ROOT)
        packet['claims'][0]['evidence'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            verify_packet(ROOT, packet, render_packet(packet))

    def test_appended_unchecked_markdown_rejected(self):
        packet = build_packet(ROOT)
        with self.assertRaises(ValueError):
            verify_packet(ROOT, packet, render_packet(packet) + b'\nWe guarantee every future customer outcome.\n')

    def test_public_scope_and_missing_question_rejected(self):
        packet = build_packet(ROOT)
        self.assertTrue(verify_packet(ROOT, packet, render_packet(packet))['accepted'])
        missing = copy.deepcopy(packet)
        missing['claims'].pop()
        with self.assertRaises(ValueError):
            verify_packet(ROOT, missing, render_packet(missing))
        packet['scope'] = 'OBSERVED_COMMERCIAL'
        with self.assertRaises(ValueError):
            verify_packet(ROOT, packet, render_packet(packet))

    def test_receipt_checker_does_not_execute_arbitrary_candidate_code(self):
        raw = b"x={'receipt_path': __import__('os').getcwd()}"
        with self.assertRaises(ValueError):
            receipt_expression(raw)


if __name__ == '__main__':
    unittest.main()
