"""Frozen GENESIS103 C10/C11: independently reconstruct active selection before resuming."""
import copy
from pathlib import Path
import tempfile
import unittest

from genesis_enterprise import native
from genesis_enterprise.policy import choose, digest
from flexibility063.native import BusinessAccount
from flexibility063.kernel import solve
from flexibility063.verify import verify
from connected_enterprise.finance import audit_journal
from commercial.terms_exact_v2 import prospective_terms

ROOT = Path(__file__).resolve().parents[1]


class SourceBoundSignedSelection(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='genesis103-selection-')
        self.output = Path(self.temp.name) / 'operation'
        native.register(ROOT, self.output, ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json')

    def tearDown(self):
        self.temp.cleanup()

    def make_understated_selection(self):
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
            original = choose(p['offer'], p['tools'], available=before['available'],
                              earned=before['unrestrictedEarned'], seed_allowed=p['first_delivery_may_use_seed'])
            self.assertIsNotNone(original['selected'])
            decision = copy.deepcopy(original)
            self.assertGreater(decision['selected']['resource_cost'], 1)
            decision['selected']['resource_cost'] -= 1
            picked = decision['selected']
            terms = prospective_terms(
                order, picked['price'], hour + 10, hour + 2,
                residual=p['offer']['reserve'] - p['offer']['fee'], fee=p['offer']['fee'],
                counterparty_obligations='Synthetic purchase of independently checked computational dispatch only. No physical energy delivery or real customer money.')
            account.begin_order(ident, order, 'buyer-' + order, picked['price'],
                                p['offer']['budget'], hour, hour + 3, terms)
            receipt = account.spend(
                'genesis-production-' + ident, 'qualified-computational-delivery',
                picked['resource_cost'], hour,
                {'binding': reg['binding'], 'request_sha256': digest(job['request']),
                 'executor': picked['tool'], 'scope': 'COMPUTATIONAL_ONLY'},
                expected_net=picked['contribution'], allow_seed=True)
            self.assertIsNotNone(receipt)
            artifact = solve(job['request'], picked['mode'])
            completion = account.complete_order(order, ident, artifact, hour + 1)
            self.assertTrue(completion['accepted'])
            ordinary = solve(job['request'], 'conventional')
            native._save(output / 'public/controls' / (ident + '.json'), ordinary)
            row = {
                'job_id': ident, 'decision': decision,
                'decision_state': {k: before[k] for k in ('available', 'unrestrictedEarned')},
                'accepted': True, 'resource_receipt': receipt,
                'artifact_sha256': digest(artifact),
                'ordinary_accepted': verify(job['request'], ordinary)['accepted'],
                'construction_cpu_seconds': 0
            }
            state = {'binding': reg['binding'], 'index': 0, 'phase': 'release',
                     'rows': [], 'active': row}
            native._save(private / 'STATE.json', account.seal_checkpoint(state))
            exported = account.export()
            self.assertTrue(account.audit()['accepted'])
            self.assertTrue(audit_journal(exported, root=output / 'source', manifest=manifest)['accepted'])
        native._save(output / 'public/native-export.json', exported)
        native._save(output / 'public/execution.json', state)
        return private / 'account.actions.jsonl', private / 'STATE.json'

    def test_signed_real_understated_selection_rejected_before_collection(self):
        tape, checkpoint = self.make_understated_selection()
        prior_tape, prior_checkpoint = tape.read_bytes(), checkpoint.read_bytes()
        with self.assertRaisesRegex(ValueError, '^REGISTERED_OPTIMAL_DECISION_CHANGED$'):
            native.operate(self.output, max_steps=1)
        self.assertEqual(tape.read_bytes(), prior_tape)
        self.assertEqual(checkpoint.read_bytes(), prior_checkpoint)
        with self.assertRaisesRegex(ValueError, '^REGISTERED_OPTIMAL_DECISION_CHANGED$'):
            native.audit(self.output)

    def test_honest_signed_checkpoint_still_resumes_to_complete(self):
        first = native.operate(self.output, max_steps=6)
        self.assertFalse(first['complete'])
        finished = native.operate(self.output)
        self.assertTrue(finished['accepted'])
        self.assertTrue(finished['complete'])
        self.assertEqual(finished['simulated_profit_microUSD'], 135900000)
        tape = (self.output / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.output), finished)
        self.assertEqual((self.output / 'public/native-export.json').read_bytes(), tape)


if __name__ == '__main__':
    unittest.main()
