"""GENESIS103 additive signed-checkpoint resume preflight cases (C7-C9).

Only fresh ephemeral BusinessAccount authorities; no historical key or account is touched.
"""
from pathlib import Path
import tempfile
import unittest

from genesis_enterprise import native
from genesis_enterprise.policy import choose, digest
from flexibility063.native import BusinessAccount
from flexibility063.kernel import solve
from flexibility063.verify import verify
from commercial.terms_exact_v2 import prospective_terms

ROOT = Path(__file__).resolve().parents[1]


class SignedActiveResumeSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='genesis103-preflight-')
        self.output = Path(self.temp.name) / 'operation'
        native.register(ROOT, self.output, ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json')

    def tearDown(self):
        self.temp.cleanup()

    def make_signed_active(self, *, late_spend):
        output = self.output
        p, manifest, _, reg = native._bound(output)
        job = manifest['jobs'][0]
        ident, hour = job['id'], 24
        order = 'g002-' + ident
        private = output / 'private'
        private.mkdir(mode=0o700)
        with BusinessAccount(output / 'source', manifest, private / 'account',
                             opening=p['opening'], working=0, contract=reg['contract']) as account:
            account.cost('genesis-development', p['development'], 0)
            account.advance(hour)
            for kind in ('acquisition', 'maintenance'):
                if p[kind]:
                    account.cost('genesis-' + kind + '-' + ident, p[kind], hour)
            before = account.export()['ledger']['summary']
            decision = choose(p['offer'], p['tools'], available=before['available'],
                              earned=before['unrestrictedEarned'],
                              seed_allowed=p['first_delivery_may_use_seed'])
            picked = decision['selected']
            self.assertIsNotNone(picked)
            terms = prospective_terms(
                order, picked['price'], hour + 10, hour + 2,
                residual=p['offer']['reserve'] - p['offer']['fee'], fee=p['offer']['fee'],
                counterparty_obligations='Synthetic purchase of independently checked computational dispatch only. No physical energy delivery or real customer money.')
            account.begin_order(ident, order, 'buyer-' + order, picked['price'],
                                p['offer']['budget'], hour, hour + 3, terms)
            artifact = solve(job['request'], picked['mode'])
            completed = account.complete_order(order, ident, artifact,
                                               hour if late_spend else hour + 1)
            self.assertTrue(completed['accepted'])
            reference = solve(job['request'], 'conventional')
            native._save(output / 'public/controls' / (ident + '.json'), reference)
            receipt = None
            if late_spend:
                receipt = account.spend(
                    'genesis-production-' + ident, 'qualified-computational-delivery',
                    picked['resource_cost'], hour,
                    {'binding': reg['binding'], 'request_sha256': digest(job['request']),
                     'executor': picked['tool'], 'scope': 'COMPUTATIONAL_ONLY'},
                    expected_net=picked['contribution'], allow_seed=True)
                self.assertIsNotNone(receipt)
            row = {
                'job_id': ident, 'decision': decision,
                'decision_state': {key: before[key] for key in ('available', 'unrestrictedEarned')},
                'accepted': True, 'resource_receipt': receipt,
                'artifact_sha256': digest(artifact),
                'ordinary_accepted': verify(job['request'], reference)['accepted'],
                'construction_cpu_seconds': 0,
            }
            state = {'binding': reg['binding'], 'index': 0, 'phase': 'release',
                     'rows': [], 'active': row}
            native._save(private / 'STATE.json', account.seal_checkpoint(state))
            self.assertTrue(account.audit()['accepted'])
        tape_path = private / 'account.actions.jsonl'
        self.assertTrue(tape_path.exists())
        return tape_path, private / 'STATE.json'

    def assert_preflight_blocks_without_writes(self, *, late_spend):
        tape, checkpoint = self.make_signed_active(late_spend=late_spend)
        original_tape, original_checkpoint = tape.read_bytes(), checkpoint.read_bytes()
        with self.assertRaisesRegex(ValueError, '^ACTIVE_PRODUCTION_MUST_PRECEDE_DELIVERY$'):
            native.operate(self.output, max_steps=1)
        self.assertEqual(tape.read_bytes(), original_tape)
        self.assertEqual(checkpoint.read_bytes(), original_checkpoint)

    def test_signed_missing_spend_fails_before_release(self):
        self.assert_preflight_blocks_without_writes(late_spend=False)

    def test_signed_late_same_hour_spend_fails_before_release(self):
        self.assert_preflight_blocks_without_writes(late_spend=True)

    def test_normal_signed_incomplete_checkpoint_resumes_to_same_business(self):
        first = native.operate(self.output, max_steps=6)
        self.assertFalse(first['complete'])
        self.assertTrue(first['accepted'])
        finished = native.operate(self.output)
        self.assertTrue(finished['accepted'])
        self.assertTrue(finished['complete'])
        self.assertEqual(finished['simulated_profit_microUSD'], 135900000)
        original = (self.output / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.output), finished)
        self.assertEqual((self.output / 'public/native-export.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
