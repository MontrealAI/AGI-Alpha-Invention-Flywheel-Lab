"""Independent post-commit interruption/reopen qualification for Omega 201.

Test-only stacked review. Each scenario uses its own ephemeral simulated native
Account/JournalAccount and never opens or copies another owner's account.
A crash is deliberately raised AFTER the existing journal method commits.
This is an engineering adversarial check, not new economic confirmation.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from mechanism_harness import inventor as inventor
from mechanism_harness import inventor_native as native


class CommittedInterruptionReview(TestCase):
    POLICY = inventor.policy(('unit', 'unique', 'text'), True)
    SOURCE = {'review': 'omega-201-postcommit-fault-v1'}

    def _completed(self, root: Path):
        with mock.patch.object(native, 'INDEXES', (8,)):
            result = native.operate(root, self.POLICY, self.SOURCE, 0)
            self.assertTrue(native.audit_operation(root, result, self.SOURCE, self.POLICY)['accepted'])
        export = native.read(root / 'NATIVE_EXPORT.json')
        actions = export['ledger']['actions']
        self.assertEqual(result['settled'], 1)
        self.assertEqual(result['refused'], 0)
        self.assertEqual(len([a for a in actions if a['op'] == 'event'
                             and a['args'].get('id') == 'omega-trade-8'
                             and a['args'].get('action') == 'release']), 1)
        return result, actions

    def test_committed_crashes_keep_one_native_account_and_exactly_once_costs(self):
        with TemporaryDirectory(prefix='omega201-review-control-') as d:
            control, control_actions = self._completed(Path(d))
        # Distinct, registered fault points; do not select favorable fault seeds.
        for point in ('quote', 'wallet', 'fund', 'production', 'fee',
                      'release', 'maintenance'):
            with self.subTest(postcommit=point):
                with TemporaryDirectory(prefix='omega201-review-crash-') as d:
                    root = Path(d)
                    original_spend = native.JournalAccount.spend
                    original_execute = native.JournalAccount.execute
                    original_cost = native.JournalAccount.cost
                    hit = []

                    def spend(account, ident, kind, amount, day, work,
                              expected_net, allow_seed=False):
                        receipt = original_spend(account, ident, kind, amount, day,
                                                 work, expected_net, allow_seed=allow_seed)
                        if ((point == 'quote' and ident == 'quote-8') or
                            (point == 'production' and ident == 'produce-8')):
                            hit.append(ident)
                            raise RuntimeError('INJECTED_AFTER_DURABLE_COMMIT')
                        return receipt

                    def execute(account, op, args, day):
                        receipt = original_execute(account, op, args, day)
                        if ((point == 'wallet' and op == 'wallet'
                             and args.get('buyer') == 'SIM-omega-8') or
                            (point in ('fund', 'release') and op == 'event'
                             and args.get('id') == 'omega-trade-8'
                             and args.get('action') == point)):
                            hit.append(point)
                            raise RuntimeError('INJECTED_AFTER_DURABLE_COMMIT')
                        return receipt

                    def cost(account, ident, amount, day):
                        receipt = original_cost(account, ident, amount, day)
                        if ((point == 'fee' and ident == 'fee-8') or
                            (point == 'maintenance' and ident == 'annual-maintenance')):
                            hit.append(ident)
                            raise RuntimeError('INJECTED_AFTER_DURABLE_COMMIT')
                        return receipt

                    with (mock.patch.object(native, 'INDEXES', (8,)),
                          mock.patch.object(native.JournalAccount, 'spend', spend),
                          mock.patch.object(native.JournalAccount, 'execute', execute),
                          mock.patch.object(native.JournalAccount, 'cost', cost)):
                        with self.assertRaisesRegex(RuntimeError,
                                                    'INJECTED_AFTER_DURABLE_COMMIT'):
                            native.operate(root, self.POLICY, self.SOURCE, 0)
                    self.assertEqual(len(hit), 1, 'fault must fire exactly once')
                    self.assertFalse((root / 'NATIVE_EXPORT.json').exists())
                    result, actions = self._completed(root)
                    for field in ('cash', 'collections', 'expenses', 'expensePaid',
                                  'profit', 'payables', 'available'):
                        self.assertEqual(result['native_summary'][field],
                                         control['native_summary'][field])
                    self.assertEqual(len(actions), len(control_actions),
                                     'restart must not duplicate native events')
                    with mock.patch.object(native, 'INDEXES', (8,)):
                        again = native.operate(root, self.POLICY, self.SOURCE, 0)
                    self.assertEqual(again['native_summary'], result['native_summary'])


if __name__ == '__main__':
    import unittest
    unittest.main()
