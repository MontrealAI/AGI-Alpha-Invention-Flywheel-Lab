import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise.channels import ChannelBook, OPTIONAL, validate_contracts
from connected_enterprise.engine import default_config, run_world, validate_config


class ConnectedChannelLeadPreflight(unittest.TestCase):
    def assert_precommit_rejected(self, cfg, error):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); marker = root / 'fixture.txt'; marker.write_text('engineering source')
            files = {'fixture.txt': hashlib.sha256(marker.read_bytes()).hexdigest()}
            output = root / 'must-not-create'
            with patch('connected_enterprise.engine.JournalAccount', side_effect=AssertionError('ACCOUNT_MUST_NOT_OPEN')) as account:
                with self.assertRaisesRegex(ValueError, error):
                    run_world(root, {}, cfg, 13, 'growth', output, source={'files': files, 'sha256': digest(files)})
                account.assert_not_called()
            self.assertFalse(output.exists())

    def test_zero_lead_connected_contract_rejects_before_output_or_account(self):
        cfg = default_config(); cfg['channels']['pilot']['lead_days'] = 0
        self.assert_precommit_rejected(cfg, 'CONNECTED_CHANNEL_ADVANCE_LEAD_REQUIRED')

    def test_missing_pilot_rejects_before_output_or_account(self):
        cfg = default_config(); del cfg['channels']['pilot']
        self.assert_precommit_rejected(cfg, 'CONNECTED_PILOT_CHANNEL_REQUIRED')

    def test_typed_and_malformed_contracts_are_validated_precommit(self):
        for value in [True, False, '0', '2', 0.5, -1]:
            with self.subTest(lead=value):
                cfg = default_config(); cfg['channels']['pilot']['lead_days'] = value
                self.assert_precommit_rejected(cfg, 'BOUNDED_INTEGER_CHANNEL_TERMS_REQUIRED')
        cfg = default_config(); cfg['channels']['pilot'].pop('slots_per_day')
        self.assert_precommit_rejected(cfg, 'EXACT_CHANNEL_TERMS_REQUIRED')

    def test_positive_leads_and_defaults_remain_unchanged(self):
        original = default_config(); before = copy.deepcopy(original)
        self.assertEqual(validate_config(original), before)
        self.assertEqual(original, before)
        for value in [1, 2, 3650]:
            with self.subTest(lead=value):
                cfg = default_config(); cfg['channels']['pilot']['lead_days'] = value
                expected = copy.deepcopy(cfg)
                self.assertEqual(validate_config(cfg), expected)
                self.assertEqual(cfg, expected)

    def test_omitted_optional_defaults_match_financed_and_purchased_terms(self):
        for omitted in [{'failure_credit_bps'}, OPTIONAL]:
            with self.subTest(omitted=sorted(omitted)):
                cfg = default_config()
                for terms in cfg['channels'].values():
                    for name in omitted:
                        terms.pop(name, None)
                admitted = validate_config(cfg)
                book = ChannelBook(13, admitted['channels'])
                self.assertEqual(admitted['channels'], book.contracts)
                purchase = book.purchase('pilot', 0, 'engineering-financed-plan')
                self.assertEqual(admitted['channels']['pilot'], purchase['terms'])
                self.assertEqual(digest(admitted['channels']['pilot']), digest(purchase['terms']))

    def test_normalization_leaves_caller_unchanged_and_returns_detached_config(self):
        cfg = default_config(); cfg['channels']['pilot'].pop('failure_credit_bps')
        original = copy.deepcopy(cfg); admitted = validate_config(cfg)
        self.assertEqual(cfg, original)
        self.assertIsNot(admitted, cfg)
        admitted['channels']['pilot']['failure_credit_bps'] = 100
        admitted['human_comparator']['reconciliation']['hours'] = 999
        self.assertEqual(cfg, original)

    def test_normalized_resume_config_binding_is_idempotent(self):
        cfg = default_config(); cfg['channels']['pilot'].pop('failure_credit_bps')
        first = validate_config(cfg); second = validate_config(first)
        self.assertEqual(first, second)
        self.assertEqual(digest({'config': first, 'seed': 13, 'arm': 'growth'}),
                         digest({'config': second, 'seed': 13, 'arm': 'growth'}))
        self.assertEqual(first['channels']['pilot']['failure_credit_bps'], 0)

    def test_standalone_channel_book_retains_zero_lead_contract_support(self):
        terms = default_config()['channels']; terms['pilot']['lead_days'] = 0
        self.assertEqual(validate_contracts(terms)['pilot']['lead_days'], 0)
        self.assertEqual(ChannelBook(13, terms).contracts['pilot']['lead_days'], 0)


if __name__ == '__main__':
    unittest.main()
