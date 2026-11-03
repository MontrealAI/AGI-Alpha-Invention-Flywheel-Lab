import copy
from pathlib import Path
import tempfile
import unittest
from commercial.ledger import strict_json, digest
from .economics import buyer_response, protocol, cases, source_copy, operate
from .study import analyze, validate_case_spec
from .service import prepare_manifest, load_contracts, delivery, verify_delivery


class NativeAcceptanceTests(unittest.TestCase):
    def test_positive_tie_prefers_existing_outside_option(self):
        result = buyer_response('positive', 'K1', 0, 500_000_000,
                                {'autonomous': 500_000_000, 'human_software': 2_000_000_000,
                                 'human_AI': 2_000_000_000, 'self_service': 2_000_000_000}, protocol())
        self.assertNotEqual(result['choice'], 'seller')

    def test_missing_confirmation_rows_fail_before_analysis(self):
        with self.assertRaisesRegex(ValueError, 'DENOMINATOR'):
            analyze([])

    def test_substituting_an_easier_world_or_schedule_is_rejected(self):
        original = cases(development=True)[0]
        self.assertTrue(validate_case_spec(original))
        altered = copy.deepcopy(original)
        altered['providers'][0]['config']['idempotency'] = 'none'
        with self.assertRaisesRegex(ValueError, 'WORLD_OR_SCHEDULE'):
            validate_case_spec(altered)
        altered = copy.deepcopy(original)
        altered['operating_schedule'] = 'lost_ack'
        with self.assertRaisesRegex(ValueError, 'WORLD_OR_SCHEDULE'):
            validate_case_spec(altered)

    def test_native_resume_rebuilds_public_receipts_without_reseeding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_copy(root/'source')
            specs = cases(development=True)[:1]
            first = operate(root/'account', root/'source', specs, 'ordinary', 'positive', 10000,
                            'test-only-development', True)
            self.assertTrue(first['native_audit_accepted'])
            self.assertEqual(first['accepted_and_collected'], 1)
            record = strict_json((root/'account/PUBLIC_ACCOUNT.json').read_bytes())
            manifest = strict_json((root/'account/MANIFEST.json').read_bytes())
            artifact = delivery(root/'source', manifest, 'order-00')
            self.assertTrue(verify_delivery(root/'source', manifest, 'order-00', artifact)['accepted'])
            changed = copy.deepcopy(artifact)
            changed['program'] = {'entry': 'fake', 'nodes': {'fake': {'finish': 'delivered', 'obligations': []}}}
            self.assertFalse(verify_delivery(root/'source', manifest, 'order-00', changed)['accepted'])
            (root/'account/PUBLIC_ACCOUNT.json').unlink()
            (root/'account/RESULT.json').unlink()
            resumed = operate(root/'account', root/'source', specs, 'ordinary', 'positive', 10000,
                              'test-only-development', True)
            self.assertEqual(first['native_actions_sha256'], resumed['native_actions_sha256'])
            self.assertEqual(digest(record), digest(strict_json((root/'account/PUBLIC_ACCOUNT.json').read_bytes())))
            self.assertTrue((root/'account/RESULT.json').is_file())


if __name__ == '__main__':
    unittest.main()
