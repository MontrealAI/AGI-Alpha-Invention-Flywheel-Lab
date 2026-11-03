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


    def test_second_committed_release_reopens_multiorder_business_without_double_spend(self):
        """Cross-order crash: earlier accepted obligations remain while a later release commits.

        The eight source-declared inputs are fixed before running either arm.
        This is a new engineering interruption site, not a new commerce sample.
        """
        indices = (8, 9, 10, 11, 12, 13, 14, 16)
        with TemporaryDirectory(prefix='omega201-multi-control-') as d:
            with mock.patch.object(native, 'INDEXES', indices):
                baseline = native.operate(Path(d), self.POLICY, self.SOURCE, 0)
                self.assertTrue(native.audit_operation(
                    Path(d), baseline, self.SOURCE, self.POLICY)['accepted'])
                baseline_actions = native.read(Path(d) / 'NATIVE_EXPORT.json')['ledger']['actions']
        self.assertGreaterEqual(baseline['settled'], 2,
                                'fixed fixture must actually test more than one settlement')
        with TemporaryDirectory(prefix='omega201-multi-interrupted-') as d:
            root = Path(d)
            execute = native.JournalAccount.execute
            seen_releases = []

            def postcommit(account, op, args, day):
                receipt = execute(account, op, args, day)
                if op == 'event' and args.get('action') == 'release':
                    seen_releases.append(args['id'])
                    if len(seen_releases) == 2:
                        raise RuntimeError('INJECTED_SECOND_RELEASE_AFTER_COMMIT')
                return receipt

            with mock.patch.object(native, 'INDEXES', indices), mock.patch.object(
                    native.JournalAccount, 'execute', postcommit):
                with self.assertRaisesRegex(
                        RuntimeError, 'INJECTED_SECOND_RELEASE_AFTER_COMMIT'):
                    native.operate(root, self.POLICY, self.SOURCE, 0)
            self.assertEqual(len(seen_releases), 2)
            self.assertNotEqual(seen_releases[0], seen_releases[1])
            self.assertTrue((root / 'account.sqlite').exists())
            self.assertFalse((root / 'NATIVE_EXPORT.json').exists(),
                             'interrupted business must not publish completed proof')

            with mock.patch.object(native, 'INDEXES', indices):
                recovered = native.operate(root, self.POLICY, self.SOURCE, 0)
                self.assertTrue(native.audit_operation(
                    root, recovered, self.SOURCE, self.POLICY)['accepted'])
            recovered_actions = native.read(root / 'NATIVE_EXPORT.json')['ledger']['actions']
            self.assertEqual(recovered['settled'], baseline['settled'])
            self.assertEqual(recovered['refused'], baseline['refused'])
            self.assertEqual(recovered['native_summary'], baseline['native_summary'])
            self.assertEqual(len(recovered_actions), len(baseline_actions))
            releases = [a['args']['id'] for a in recovered_actions
                        if a['op'] == 'event' and a['args'].get('action') == 'release']
            self.assertEqual(len(releases), recovered['settled'])
            self.assertEqual(len(releases), len(set(releases)),
                             'no already-accepted order may settle twice on recovery')
            with mock.patch.object(native, 'INDEXES', indices):
                final = native.operate(root, self.POLICY, self.SOURCE, 0)
            self.assertEqual(final['native_summary'], recovered['native_summary'])


if __name__ == '__main__':
    import unittest
    unittest.main()
