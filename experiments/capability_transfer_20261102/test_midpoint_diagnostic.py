import copy
import json
import tempfile
import unittest
from pathlib import Path

from experiments.capability_transfer_20261102 import run_midpoint_diagnostic as diagnostic


class ReplayReceiptIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_path = diagnostic.HERE / 'results' / 'STAGE_B_RESULT.json'
        cls.original = diagnostic.read_bound_json(cls.original_path, diagnostic.RESULT_SHA256, 'TEST_ORIGINAL_RESULT_MISMATCH')
        cls.sources = cls.original['source_hashes']

    def validate(self, receipt):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'replay.json'
            path.write_text(json.dumps(receipt, sort_keys=True))
            result, actual_hash = diagnostic.read_replay_result(path, self.original, self.sources)
            self.assertEqual(actual_hash, diagnostic.digest(path.read_bytes()))
            return result

    def test_full_qualified_receipt_is_accepted(self):
        self.assertEqual(self.validate(self.original), self.original)

    def test_replay_requires_exact_freeze_and_source_hashes(self):
        wrong_freeze = copy.deepcopy(self.original)
        wrong_freeze['freeze_sha256'] = '0' * 64
        wrong_source = copy.deepcopy(self.original)
        wrong_source['source_hashes']['verifier.py'] = '0' * 64
        for receipt in (wrong_freeze, wrong_source):
            with self.subTest(receipt=receipt['freeze_sha256']), self.assertRaisesRegex(ValueError, 'REPLAY_FROZEN_SOURCE_OR_RECEIPT_MISMATCH'):
                self.validate(receipt)

    def test_wrong_receipt_or_incomplete_checks_are_rejected(self):
        wrong_schema = copy.deepcopy(self.original)
        wrong_schema['schema'] = 'agi-alpha/cell-pack-post-result-diagnostic/v3'
        missing_grid = copy.deepcopy(self.original)
        del missing_grid['numerical_verification']['trace_checks'][0]['step_s_runs']['0.5']
        missing_fixture = copy.deepcopy(self.original)
        missing_fixture['numerical_verification']['nodal_cases'] = 127
        wrong_scope = copy.deepcopy(self.original)
        wrong_scope['claims']['physical_K1_qualified'] = True
        for receipt in (wrong_schema, missing_grid, missing_fixture, wrong_scope):
            with self.subTest(schema=receipt['schema']), self.assertRaises(ValueError):
                self.validate(receipt)

    def test_replay_requires_literal_acceptance_and_existing_numeric_limits(self):
        cases = [('numerical_constructor_accepted', False), ('numerical_constructor_accepted', 'true'), ('max_current_difference_a', 1e-8), ('max_trace_error_a', 1e-4), ('max_kcl_residual_a', float('nan'))]
        for key, value in cases:
            receipt = copy.deepcopy(self.original)
            receipt['numerical_verification'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'REPLAY_NUMERICAL_QUALIFICATION_FAILED'):
                self.validate(receipt)

    def test_replay_argument_does_not_bypass_original_receipt_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'altered-original.json'
            path.write_bytes(self.original_path.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_RESULT_DIGEST_MISMATCH'):
                diagnostic.evaluate(path, diagnostic.HERE / 'FROZEN_STAGE_B_SERIALIZATION_FIX.json', self.original_path)


if __name__ == '__main__':
    unittest.main()
