"""Fresh-account schema and funding regressions; production is tested by the campaign."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from commercial.terms_exact_v2 import prospective_terms
from industrial064 import service
from industrial064.native import BusinessAccount, OPENING

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT/'industrial064/inputs/baseline.json').exists(), 'Run pinned input retrieval and scripts/materialize_industrial064.py for data-dependent native integration')
class Industrial064NativeTests(unittest.TestCase):
    def setUp(self):
        requests = json.loads((ROOT/'industrial064/registration.json').read_text())['requests']
        rows = [{'id': q['id'], 'request': q,
                 'delivery_path': 'industrial064/deliveries/tests/' + q['id'] + '.json'} for q in requests]
        self.manifest = service.prepare_manifest(ROOT, rows)
        self.temp = tempfile.TemporaryDirectory(prefix='industrial064-native-test-')
        self.account = BusinessAccount(ROOT, self.manifest, Path(self.temp.name)/'account.json',
                                       contract='industrial064-regression')

    def tearDown(self):
        self.account.close(); self.temp.cleanup()

    def test_fresh_native_100k_and_public_audit(self):
        self.assertEqual(self.account.snapshot()['summary']['cash'], OPENING)
        self.assertEqual(OPENING, 100_000_000_000)
        self.assertTrue(self.account.audit()['accepted'])

    def test_no_earnings_cannot_fund_successor(self):
        receipt = self.account.spend('premature-successor', 'planning', 1_000_000, 0,
                                     {'request': 'demand105'}, expected_net=1_000_000,
                                     allow_seed=False)
        self.assertIsNone(receipt)
        self.assertEqual(self.account.snapshot()['summary']['cash'], OPENING)
        self.assertTrue(self.account.audit()['accepted'])

    def test_request_tampering_rejected(self):
        for field, value in [('input_sha256', '0'*64), ('distance_margin', 0), ('cost_ceiling_yuan', 0)]:
            modified = copy.deepcopy(self.manifest)
            modified['jobs'][0]['request'][field] = value
            with self.assertRaises(ValueError): service.load_contracts(ROOT, modified)

    def test_offer_request_cannot_change_before_acceptance(self):
        first, second = [r['id'] for r in self.manifest['jobs']]
        terms = prospective_terms('order', 100_000_000, 12, 2,
                                  residual=1_000_000, fee=200_000)
        self.account.begin_order(first, 'order', 'one-manufacturer', 100_000_000,
                                 500_000_000, 1, 5, terms)
        with self.assertRaisesRegex(ValueError, 'FUNDED_REQUEST_CHANGED'):
            self.account.complete_order('order', second, {}, 2)
        self.account.refund('order', 2)
        self.assertTrue(self.account.audit()['accepted'])


if __name__ == '__main__': unittest.main()
