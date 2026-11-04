"""Verify the original V1, V2 and V3 entry points against real native authority.

Small synthetic workloads keep the lifecycle tests local. Every account below
is created in its own temporary directory. No historical account is opened.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from commercial.ledger import strict_json
from connected_enterprise.finance import JournalAccount
from mechanism_harness import economical_learning, economical_native
from mechanism_harness import inventor, inventor_native
from mechanism_harness import market_cases, mechanism_campaign, mechanism_native


AUTHORITY = ('.adaptive-simulation-key', '.actions.jsonl', '.connected-journal.json')


@contextmanager
def small_workload():
    # Exercise the operators' real research, audit, journal and account code.
    # Only the input cohort and number of admissions differ from a campaign.
    case = ((1337, 'substitute'),)
    original_market = market_cases.market
    original_campaign = mechanism_campaign.execute

    def small_market(*args, **kwargs):
        return original_market(*args, **{**kwargs, 'width': 2})

    with ExitStack() as stack:
        for obj, name, value in (
                (inventor, 'TRAIN_SEEDS', (38_001,)),
                (inventor, 'TEST_SEEDS', (38_002,)),
                (inventor, 'TRAIN_INDICES', (8,)),
                (inventor, 'TEST_INDICES', (9,)),
                (economical_learning, 'DEVELOPMENT', ((38_011,),)),
                (economical_learning, 'CONFIRMATION', ((38_012,),)),
                (inventor_native, 'INDEXES', (8,)),
                (mechanism_campaign, 'CASES', case),
                (mechanism_campaign, 'market', small_market),
                (market_cases, 'market', small_market),
                (mechanism_campaign, 'execute', lambda: original_campaign(case))):
            stack.enter_context(patch.object(obj, name, value))
        yield


@contextmanager
def hold_files(*files):
    """Temporarily withhold specific files without cloning a signer or ledger."""
    with TemporaryDirectory(prefix='omega-authority-held-') as held:
        for path in files:
            path.rename(Path(held) / path.name)
        try:
            yield
        finally:
            for path in files:
                (Path(held) / path.name).replace(path)


class LegacyLiveResumeTests(unittest.TestCase):
    def exercise(self, operator, native, report_name):
        with TemporaryDirectory(prefix='omega-legacy-resume-') as directory, small_workload():
            out = Path(directory) / 'independent'
            with patch.object(native, 'JournalAccount', side_effect=InterruptedError('before native bootstrap')):
                with self.assertRaisesRegex(InterruptedError, 'before native bootstrap'):
                    operator.run(out)
            self.assertTrue((out / 'MANIFEST.json').is_file())
            self.assertFalse((out / report_name).exists())
            self.assertEqual(list(out.glob('account.sqlite*')), [])
            result = operator.run(out, resume=True)
            report_path = out / report_name
            export_path = out / 'NATIVE_EXPORT.json'
            manifest = strict_json((out / 'MANIFEST.json').read_bytes())
            frozen_report, frozen_export = report_path.read_bytes(), export_path.read_bytes()
            files = tuple(out / ('account.sqlite' + suffix) for suffix in AUTHORITY)
            authority = [f.read_bytes() for f in files]

            with self.subTest(boundary='current complete account'):
                self.assertEqual(operator.run(out, resume=True), result)
                self.assertEqual([f.read_bytes() for f in files], authority)

            with self.subTest(boundary='rebuild the derived SQLite database'):
                with hold_files(out / 'account.sqlite'):
                    self.assertEqual(operator.run(out, resume=True), result)
                    self.assertTrue((out / 'account.sqlite').is_file())
                    self.assertEqual([f.read_bytes() for f in files], authority)

            for missing in files:
                with self.subTest(boundary='individual authority missing', file=missing.suffix):
                    with hold_files(missing):
                        with self.assertRaisesRegex(ValueError, 'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                            operator.run(out, resume=True)
                        self.assertFalse(missing.exists())

            # Standalone auditing of saved evidence is useful after losing local
            # authority. Resuming with that evidence cannot create a replacement.
            with self.subTest(boundary='portable audit without an account'):
                with hold_files(*list(out.glob('account.sqlite*'))):
                    self.assertTrue(operator.audit(out)['accepted'])
                    with self.assertRaisesRegex(ValueError, 'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                        operator.run(out, resume=True)
                    self.assertEqual(list(out.glob('account.sqlite*')), [])

            with self.subTest(boundary='incomplete history without authority'):
                with hold_files(report_path, *list(out.glob('account.sqlite*'))):
                    # A guard that accidentally reaches the constructor could
                    # create a second account. Stop that unsafe path in the test.
                    with patch.object(native, 'JournalAccount', side_effect=AssertionError('attempted reseed')):
                        with self.assertRaisesRegex(ValueError, 'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                            operator.run(out, resume=True)
                    self.assertEqual(list(out.glob('account.sqlite*')), [])

            # This is a real, legitimate new debit, not edited report content.
            account = JournalAccount(out / 'runtime', manifest, out / 'account.sqlite',
                                     opening=native.OPENING, working=0, contract=native.CONTRACT)
            try:
                before = account.snapshot()['summary']['profit']
                account.cost('post-report-native-expense', 10_000, 364)
                self.assertTrue(account.audit()['accepted'])
                self.assertEqual(account.snapshot()['summary']['profit'], before - 10_000)
            finally:
                account.close()
            current_authority = [f.read_bytes() for f in files]
            with self.subTest(boundary='completed report behind live account'):
                with self.assertRaisesRegex(ValueError, 'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
                    operator.run(out, resume=True)
            self.assertEqual(frozen_report, report_path.read_bytes())
            self.assertEqual(frozen_export, export_path.read_bytes())
            self.assertEqual(current_authority, [f.read_bytes() for f in files])


            # Simulate a writer interrupted after persisting a different valid
            # expense intent, before native debit. Looking at a completed report
            # must not finish that writer's transaction as a side effect.
            account = JournalAccount(out / 'runtime', manifest, out / 'account.sqlite',
                                     opening=native.OPENING, working=0, contract=native.CONTRACT)
            try:
                with patch.object(account, '_perform', side_effect=InterruptedError('before later debit')):
                    with self.assertRaisesRegex(InterruptedError, 'before later debit'):
                        account.cost('post-report-pending-cost', 7_000, 364)
            finally:
                account.close()
            pending = strict_json(files[2].read_bytes())['body']['entries'][-1]
            self.assertEqual(pending['status'], 'PENDING')
            self.assertEqual(pending['request']['args']['id'], 'post-report-pending-cost')
            pending_authority = [f.read_bytes() for f in files]
            self.assertEqual(current_authority[1], pending_authority[1])
            with self.subTest(boundary='completed resume must not execute another pending intent'):
                with self.assertRaisesRegex(ValueError, 'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
                    operator.run(out, resume=True)
            self.assertEqual(frozen_report, report_path.read_bytes())
            self.assertEqual(frozen_export, export_path.read_bytes())
            self.assertEqual(pending_authority, [f.read_bytes() for f in files])

    def test_inventor_live_resume(self):
        self.exercise(inventor, inventor_native, 'REPORT.json')

    def test_economical_live_resume(self):
        self.exercise(economical_native, inventor_native, 'V2_REPORT.json')

    def test_mechanism_live_resume(self):
        self.exercise(mechanism_native, mechanism_native, 'REPORT.json')


if __name__ == '__main__':
    unittest.main()
