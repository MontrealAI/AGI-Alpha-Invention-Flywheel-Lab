"""Independent post-commit interruption checks for the V4 cart operator.

These fixed engineering faults are not commercial observations. Every fault
reopens the same fresh simulation and preserves all already committed events.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mechanism_harness import cart_native as native, cart_campaign as campaign
from mechanism_harness import market_cases

PILOT = ((1337, 'substitute'),)
ORIGINAL_MARKET = market_cases.market


@contextmanager
def pilot_fixture():
    def small(*args, **kwargs):
        kwargs['width'] = 2
        return ORIGINAL_MARKET(*args, **kwargs)
    execute = campaign.execute
    with ExitStack() as stack:
        stack.enter_context(patch.object(campaign, 'CASES', PILOT))
        stack.enter_context(patch.object(campaign, 'market', side_effect=small))
        stack.enter_context(patch.object(market_cases, 'market', side_effect=small))
        stack.enter_context(patch.object(campaign, 'execute', side_effect=lambda: execute(PILOT)))
        yield


class CommittedCartRecovery(unittest.TestCase):
    def test_same_account_recovers_every_registered_postcommit_fault(self):
        # Capture an uninterrupted equal-input trajectory before any fault run.
        with TemporaryDirectory(prefix='omega-v4-review-') as d, pilot_fixture():
            base = Path(d)
            control = native.run(base / 'control')
            control_export = native.read(base / 'control' / 'NATIVE_EXPORT.json')
            control_actions = control_export['ledger']['actions']
            self.assertGreaterEqual(control['settled_buyers'], 2)
            for point in ('quote', 'wallet', 'fund', 'production', 'fee',
                          'release', 'second_release', 'maintenance'):
                with self.subTest(postcommit=point):
                    output = base / point
                    original_spend = native.JournalAccount.spend
                    original_execute = native.JournalAccount.execute
                    original_cost = native.JournalAccount.cost
                    fired = []
                    releases = []

                    def fail(label):
                        fired.append(label)
                        raise RuntimeError('INJECTED_AFTER_DURABLE_COMMIT')

                    def spend(account, ident, *args, **kwargs):
                        receipt = original_spend(account, ident, *args, **kwargs)
                        if ((point == 'quote' and ident == 'v4-quote-1') or
                            (point == 'production' and ident.startswith('v4-production-'))):
                            fail(ident)
                        return receipt

                    def execute(account, op, args, day):
                        receipt = original_execute(account, op, args, day)
                        if point == 'wallet' and op == 'wallet':
                            fail('wallet')
                        if op == 'event':
                            action = args.get('action')
                            if point == 'fund' and action == 'fund':
                                fail('fund')
                            if action == 'release':
                                releases.append(args['id'])
                                if point == 'release' or (point == 'second_release' and len(releases) == 2):
                                    fail(args['id'])
                        return receipt

                    def cost(account, ident, *args, **kwargs):
                        receipt = original_cost(account, ident, *args, **kwargs)
                        if ((point == 'fee' and ident.startswith('v4-fee-')) or
                            (point == 'maintenance' and ident == 'v4-maintenance')):
                            fail(ident)
                        return receipt

                    with (patch.object(native.JournalAccount, 'spend', spend),
                          patch.object(native.JournalAccount, 'execute', execute),
                          patch.object(native.JournalAccount, 'cost', cost)):
                        with self.assertRaisesRegex(RuntimeError, 'INJECTED_AFTER_DURABLE_COMMIT'):
                            native.run(output)
                    self.assertEqual(len(fired), 1)
                    self.assertFalse((output / 'REPORT.json').exists())
                    self.assertFalse((output / 'NATIVE_EXPORT.json').exists())
                    recovered = native.run(output, resume=True)
                    self.assertTrue(native.audit(output)['accepted'])
                    self.assertEqual(recovered['native_summary'], control['native_summary'])
                    actions = native.read(output / 'NATIVE_EXPORT.json')['ledger']['actions']
                    self.assertEqual(len(actions), len(control_actions))
                    settled = [a['args']['id'] for a in actions if a['op'] == 'event'
                               and a['args'].get('action') == 'release']
                    self.assertEqual(len(settled), len(set(settled)))
                    before = (output / 'NATIVE_EXPORT.json').read_bytes()
                    again = native.run(output, resume=True)
                    self.assertEqual(again['native_summary'], recovered['native_summary'])
                    self.assertEqual(before, (output / 'NATIVE_EXPORT.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
