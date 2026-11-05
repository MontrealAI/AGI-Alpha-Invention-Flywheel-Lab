"""GENESIS104: recovery of native-valid order prefixes after a signed checkpoint lag.

All cases create separate disposable canonical accounts using the original
local simulation authority. No historical account, key, or liability is touched.
"""
from pathlib import Path
import tempfile
import unittest

from commercial.terms_exact_v2 import prospective_terms
from flexibility063.native import BusinessAccount
from genesis_enterprise import native

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json'


class NativeOrderPrefixRecovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='genesis104-order-prefix-')
        self.home = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, name):
        output = self.home / name
        native.register(ROOT, output, PROTOCOL)
        pending = native.operate(output, max_steps=3)
        self.assertTrue(pending['accepted'])
        self.assertFalse(pending['complete'])
        p, manifest, _, reg = native._bound(output)
        job = manifest['jobs'][0]
        ident = job['id']
        order = 'g002-' + ident
        hour = 24
        from genesis_enterprise.policy import choose
        tape = native._read(output / 'public/native-export.json')
        state = tape['ledger']['summary']
        selected = choose(p['offer'], p['tools'],
                          available=state['available'], earned=state['unrestrictedEarned'],
                          seed_allowed=p['first_delivery_may_use_seed'])['selected']
        self.assertIsNotNone(selected)
        terms = prospective_terms(
            order, selected['price'], hour + 10, hour + 2,
            residual=p['offer']['reserve'] - p['offer']['fee'],
            fee=p['offer']['fee'],
            counterparty_obligations=(
                'Synthetic purchase of independently checked computational dispatch only. '
                'No physical energy delivery or real customer money.'))
        buyer = 'buyer-' + order
        expected = [
            ('wallet', {'buyer': buyer, 'amount': p['offer']['budget']}, hour),
            ('register_terms', {'id': order + '-terms', 'terms': terms}, hour),
            ('offer', {'id': order, 'buyer': buyer, 'price': selected['price'],
                       'job_id': ident, 'deadline': hour + 3,
                       'terms_id': order + '-terms'}, hour),
            ('event', {'id': order, 'action': 'consent',
                       'event_id': order + '-consent'}, hour),
            ('event', {'id': order, 'action': 'fund',
                       'event_id': order + '-fund'}, hour)
        ]
        checkpoint = output / 'private/STATE.json'
        self.assertEqual(native._read(checkpoint)['body']['state']['phase'], 'order')
        return output, p, manifest, reg, expected

    def append(self, output, p, manifest, reg, steps):
        with BusinessAccount(output / 'source', manifest, output / 'private/account',
                             opening=p['opening'], working=0,
                             contract=reg['contract']) as account:
            for op, args, day in steps:
                account.account.execute(op, args, day)
            self.assertTrue(account.audit()['accepted'])

    def matching(self, output, expected):
        ledger = native._read(output / 'public/native-export.json')['ledger']['actions']
        order = expected[2][1]['id']
        buyer = expected[0][1]['buyer']
        return [a for a in ledger if (
            (a['op'] == 'wallet' and a['args'].get('buyer') == buyer)
            or (a['op'] == 'register_terms' and a['args'].get('id') == order + '-terms')
            or (a['op'] == 'offer' and a['args'].get('id') == order)
            or (a['op'] == 'event' and a['args'].get('id') == order))]

    def test_c12_full_native_order_precedes_signed_checkpoint(self):
        output, p, manifest, reg, expected = self.prepare('full')
        self.append(output, p, manifest, reg, expected)
        tape = (output / 'private/account.actions.jsonl').read_bytes()
        checkpoint_before = (output / 'private/STATE.json').read_bytes()
        self.assertEqual(len(self.matching_after_account(output, p, manifest, reg, expected)), 5)
        self.assertEqual((output / 'private/STATE.json').read_bytes(), checkpoint_before)
        resumed = native.operate(output, max_steps=1)
        self.assertTrue(resumed['accepted'])
        self.assertEqual(native._read(output / 'private/STATE.json')['body']['state']['phase'], 'fund')
        self.assertEqual((output / 'private/account.actions.jsonl').read_bytes(), tape)
        self.assertEqual(len(self.matching(output, expected)), 5)
        final = native.operate(output)
        self.assertTrue(final['accepted'])
        self.assertTrue(final['complete'])

    def matching_after_account(self, output, p, manifest, reg, expected):
        with BusinessAccount(output / 'source', manifest, output / 'private/account',
                             opening=p['opening'], working=0,
                             contract=reg['contract']) as account:
            actions = account.export()['ledger']['actions']
        order, buyer = expected[2][1]['id'], expected[0][1]['buyer']
        return [a for a in actions if
                (a['op'] == 'wallet' and a['args'].get('buyer') == buyer)
                or (a['op'] == 'register_terms' and a['args'].get('id') == order + '-terms')
                or (a['op'] == 'offer' and a['args'].get('id') == order)
                or (a['op'] == 'event' and a['args'].get('id') == order)]

    def test_c13_every_partial_native_prefix_recovers_idempotently(self):
        for size in (1, 2, 3, 4):
            with self.subTest(prefix_length=size):
                output, p, manifest, reg, expected = self.prepare('prefix-' + str(size))
                self.append(output, p, manifest, reg, expected[:size])
                frozen_checkpoint = (output / 'private/STATE.json').read_bytes()
                resumed = native.operate(output, max_steps=1)
                self.assertTrue(resumed['accepted'])
                self.assertEqual(native._read(output / 'private/STATE.json')['body']['state']['phase'], 'fund')
                self.assertNotEqual((output / 'private/STATE.json').read_bytes(), frozen_checkpoint)
                matching = self.matching(output, expected)
                self.assertEqual(len(matching), 5)
                self.assertEqual([(a['op'], a['args'], a['day']) for a in matching], expected)
                finished = native.operate(output)
                self.assertTrue(finished['accepted'])
                self.assertTrue(finished['complete'])

    def test_c14_native_valid_wrong_prefix_rejected_without_mutation(self):
        for kind in ('budget', 'time', 'terms'):
            with self.subTest(kind=kind):
                output, p, manifest, reg, expected = self.prepare('bad-' + kind)
                modified = [(op, dict(args), day) for op, args, day in expected[:2]]
                if kind == 'budget':
                    modified = [(modified[0][0], {**modified[0][1], 'amount': p['offer']['budget'] + 1000000},
                                 modified[0][2])]
                elif kind == 'time':
                    modified = [(modified[0][0], modified[0][1], modified[0][2] + 1)]
                else:
                    terms = {**modified[1][1]['terms'],
                             'counterparty_obligations': modified[1][1]['terms']['counterparty_obligations'] + ' ALTERED'}
                    modified[1] = (modified[1][0], {**modified[1][1], 'terms': terms},
                                   modified[1][2])
                self.append(output, p, manifest, reg, modified)
                checkpoint = (output / 'private/STATE.json').read_bytes()
                tape = (output / 'private/account.actions.jsonl').read_bytes()
                with self.assertRaisesRegex(ValueError, 'REGISTERED_NATIVE_OFFER_CHANGED'):
                    native.operate(output, max_steps=1)
                self.assertEqual((output / 'private/STATE.json').read_bytes(), checkpoint)
                self.assertEqual((output / 'private/account.actions.jsonl').read_bytes(), tape)

    def test_c15_empty_native_order_prefix_unchanged(self):
        output, _, _, _, expected = self.prepare('empty')
        result = native.operate(output, max_steps=1)
        self.assertTrue(result['accepted'])
        matching = self.matching(output, expected)
        self.assertEqual(len(matching), 5)
        self.assertEqual([(a['op'], a['args'], a['day']) for a in matching], expected)


if __name__ == '__main__':
    unittest.main()
