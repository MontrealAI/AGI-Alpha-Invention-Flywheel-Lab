"""Prospective synthetic producer fault diagnostics; never starts a business account."""
import json, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from industrial064.construct import ProducerFailure, construct

class ProducerDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='industrial064-diag-')
        self.root=Path(self.tmp.name)
        (self.root/'input.json').write_text('{}')
        self.request={'input_path':'input.json'}
        self.output=self.root/'result'

    def tearDown(self): self.tmp.cleanup()

    def test_silent_negative_signal_keeps_exit_identity(self):
        with patch('industrial064.construct.subprocess.run', return_value=subprocess.CompletedProcess([], -9, '', '')):
            with self.assertRaises(ProducerFailure) as raised: construct(self.root, self.request, self.output)
        self.assertEqual(raised.exception.diagnostics['returncode'], -9)
        self.assertEqual(raised.exception.diagnostics['signal'], 9)
        self.assertEqual(raised.exception.diagnostics['stderr']['bytes'], 0)
        self.assertFalse(raised.exception.diagnostics['output_created'])

    def test_nonzero_stderr_is_committed_without_public_text(self):
        secret='opaque private-looking diagnostic line'
        with patch('industrial064.construct.subprocess.run', return_value=subprocess.CompletedProcess([], 2, 'stdout', secret)):
            with self.assertRaises(ProducerFailure) as raised: construct(self.root, self.request, self.output)
        self.assertEqual(raised.exception.diagnostics['returncode'], 2)
        self.assertIsNone(raised.exception.diagnostics['signal'])
        self.assertEqual(raised.exception.diagnostics['stderr']['bytes'], len(secret))
        self.assertNotIn(secret, str(raised.exception))

    def test_binary_stderr_never_needs_decoding_or_leaks(self):
        data=b'\xff\xfe\x00\x80'
        with patch('industrial064.construct.subprocess.run', return_value=subprocess.CompletedProcess([], 3, b'', data)) as run:
            with self.assertRaises(ProducerFailure) as raised: construct(self.root, self.request, self.output)
        self.assertIs(run.call_args.kwargs['text'], False)
        self.assertEqual(raised.exception.diagnostics['stderr']['bytes'], len(data))
        self.assertEqual(raised.exception.diagnostics['returncode'], 3)
        self.assertNotIn(repr(data), str(raised.exception))

    def test_timeout_is_distinct_from_nonzero_and_has_no_retry(self):
        with patch('industrial064.construct.subprocess.run', side_effect=subprocess.TimeoutExpired(['python'], 155, output=b'timing', stderr=b'diag')) as run:
            with self.assertRaises(ProducerFailure) as raised: construct(self.root, self.request, self.output)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(raised.exception.diagnostics['kind'], 'PRODUCER_TIMEOUT')
        self.assertEqual(raised.exception.diagnostics['timeout_seconds'], 155)
        self.assertNotIn('diag', str(raised.exception))

    def test_zero_exit_missing_output_is_not_reported_as_success(self):
        with patch('industrial064.construct.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            with self.assertRaises(ProducerFailure) as raised: construct(self.root, self.request, self.output)
        self.assertEqual(raised.exception.diagnostics['kind'], 'PRODUCER_RECEIPT_MISSING')

    def test_fresh_success_retains_constructor_contract(self):
        def producer(args, **_):
            folder=Path(args[-1]); folder.mkdir()
            (folder/'production.json').write_text(json.dumps({'status':'PASS'}))
            (folder/'solution.json').write_text(json.dumps({'plan': True}))
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch('industrial064.construct.subprocess.run', side_effect=producer) as run:
            plan, receipt=construct(self.root, self.request, self.output)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(plan, {'plan':True})
        self.assertEqual(receipt, {'status':'PASS'})

    def test_existing_output_cannot_trigger_another_attempt(self):
        self.output.mkdir()
        with patch('industrial064.construct.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'FRESH_OUTPUT_REQUIRED'):
                construct(self.root, self.request, self.output)
        run.assert_not_called()

if __name__ == '__main__': unittest.main()
