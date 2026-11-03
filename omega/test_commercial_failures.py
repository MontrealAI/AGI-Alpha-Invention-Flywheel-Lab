"""Payment refusal and delayed collection on the actual product adapter."""
from pathlib import Path
import tempfile
import unittest
from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount
from omega import product

ROOT = Path(__file__).resolve().parents[1]


class CommercialFailureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.directory = Path(self.temporary.name)
        self.manifest = product.prepare_manifest(ROOT, self.directory/'product', hypothetical_rights=True)
        self.account = JournalAccount(ROOT, self.manifest, self.directory/'account.sqlite',
                                      opening=100_000*product.MICRO, working=0, contract='payment-regression')

    def tearDown(self):
        self.account.close()
        self.temporary.cleanup()

    def offer(self, wallet):
        a, m = self.account, self.manifest
        terms = product.terms_for(m, 'order', 'self_hosted', 0)
        a.execute('register_terms', {'id':'order:terms','terms':terms}, 0)
        a.execute('wallet', {'buyer':'buyer','amount':wallet}, 0)
        a.execute('offer', {'id':'order','buyer':'buyer','price':product.PRICE['self_hosted'],
                           'job_id':m['jobs'][0]['id'],'deadline':24,'terms_id':'order:terms'}, 0)
        a.execute('event', {'id':'order','action':'consent','event_id':'order:consent'}, 0)

    def test_nonpayment_and_expired_choice_never_create_revenue(self):
        self.offer(1)
        with self.assertRaisesRegex(ValueError, 'buyer funds or collateral unavailable'):
            self.account.execute('event', {'id':'order','action':'fund','event_id':'order:fund'}, 0)
        self.account.execute('event', {'id':'order','action':'cancel','event_id':'order:cancel'}, 25)
        record = self.account.export()
        self.assertEqual(record['ledger']['summary']['collections'], 0)
        self.assertEqual(record['ledger']['summary']['revenue'], 0)
        self.assertEqual(record['ledger']['summary']['expenses'], 0)
        self.assertTrue(product.replay(record, root=ROOT, manifest=self.manifest)['accepted'])

    def test_collections_wait_for_delivery_acceptance_and_release(self):
        self.offer(product.PRICE['self_hosted'])
        a, m = self.account, self.manifest
        a.execute('event', {'id':'order','action':'fund','event_id':'order:fund'}, 0)
        self.assertEqual(a.snapshot()['summary']['collections'], 0)
        self.assertIsNone(a.spend('future-income','production',product.MICRO,0,{},product.MICRO))
        for ident, amount in product.cost_rows(m['jobs'][0], 'order', m['costs']):
            a.cost(ident, amount, 12)
        artifact = product.produce(ROOT, m, m['jobs'][0]['id'])
        a.execute('event', {'id':'order','action':'prepare','event_id':'order:prepare',
                            'artifact_sha256':digest(artifact)}, 12)
        self.assertEqual(a.snapshot()['summary']['collections'], 0)
        a.execute('event', {'id':'order','action':'release','event_id':'order:release'}, 12)
        self.assertEqual(a.snapshot()['summary']['collections'], product.PRICE['self_hosted'])
        self.assertTrue(product.replay(a.export(), root=ROOT, manifest=m)['accepted'])


if __name__ == '__main__':
    unittest.main()
