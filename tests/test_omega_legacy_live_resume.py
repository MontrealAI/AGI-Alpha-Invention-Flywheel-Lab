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
from connected_enterprise.finance import JournalAccount, audit_journal
from mechanism_harness import cart_campaign, cart_native, economical_learning, economical_native
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


class RegisteredNativeTermsTests(unittest.TestCase):
    def test_public_auditors_reject_replayable_alternate_accounts(self):
        from tests.test_omega_cart_native import PILOT, small_native_fixture

        for operator, native, field, value in [
                (inventor, inventor_native, 'opening', 200_000_000_000),
                (economical_native, inventor_native, 'working', 1_000_000),
                (mechanism_native, mechanism_native, 'contract', 'alternate-fixture-contract'),
                (cart_native, cart_native, 'opening', 200_000_000_000),
                (cart_native, cart_native, 'working', 1_000_000),
                (cart_native, cart_native, 'contract', 'alternate-fixture-contract')]:
            with (self.subTest(operator=operator.__name__, field=field), TemporaryDirectory() as directory,
                  small_workload(), ExitStack() as fixture):
                out = Path(directory) / 'new'
                if operator is cart_native:
                    execute = cart_campaign.execute
                    fixture.enter_context(small_native_fixture())
                    fixture.enter_context(patch.object(cart_campaign, 'execute', lambda: execute(PILOT)))

                def alternate_account(*args, **kwargs):
                    return JournalAccount(*args, **{**kwargs, field: value})

                # Model a producer supplying a coherent wrong account. Bypass its
                # own publication check only while constructing hostile evidence.
                with patch.object(native, 'JournalAccount', alternate_account), ExitStack() as producer:
                    if operator is economical_native:
                        producer.enter_context(patch.object(inventor_native, 'audit_operation'))
                    elif operator in (mechanism_native, cart_native):
                        producer.enter_context(patch.object(operator, 'audit'))
                    report = operator.run(out)

                exported = inventor_native.read(out / 'NATIVE_EXPORT.json')
                self.assertEqual(report.get('native', report)['opening_microUSD'], native.OPENING)
                self.assertEqual(exported['ledger']['config'][field], value)
                checked = audit_journal(exported, root=out / 'runtime', manifest=inventor_native.read(out / 'MANIFEST.json'))
                self.assertGreater(checked['connected_native_actions_covered'], 0)
                with self.assertRaisesRegex(ValueError, 'REGISTERED_NATIVE_ACCOUNT_CONFIG_CHANGED'):
                    operator.audit(out)


class RegisteredOperatingPolicyTests(unittest.TestCase):
    def test_replayable_omission_at_the_registered_investment_boundary(self):
        for operator in (inventor, economical_native, mechanism_native):
            with self.subTest(operator=operator.__name__), TemporaryDirectory() as directory, ExitStack() as fixture:
                out = Path(directory) / 'new'
                if operator is mechanism_native:
                    cases = ((391101, 'complementary'),)
                    execute = mechanism_campaign.execute
                    fixture.enter_context(patch.object(mechanism_campaign, 'CASES', cases))
                    fixture.enter_context(patch.object(mechanism_campaign, 'execute', lambda: execute(cases)))
                else:
                    fixture.enter_context(small_workload())
                    fixture.enter_context(patch.object(inventor_native, 'INDEXES', tuple(range(8, 16))))

                original_spend = JournalAccount.spend
                eligible = []

                def omit(account, ident, kind, amount, day, work, expected_net, allow_seed=False):
                    if ident in ('omega-successor', 'v3-successor'):
                        state = account.snapshot()['summary']
                        eligible.append(min(state['available'], state['unrestrictedEarned']) >= amount)
                        return None
                    return original_spend(account, ident, kind, amount, day, work, expected_net, allow_seed)

                with patch.object(JournalAccount, 'spend', omit), ExitStack() as producer:
                    if operator is economical_native:
                        producer.enter_context(patch.object(inventor_native, 'audit_operation'))
                    elif operator is mechanism_native:
                        producer.enter_context(patch.object(operator, 'audit'))
                    operator.run(out)
                self.assertEqual(eligible, [True])
                self.assertFalse((out/'SUCCESSOR.json').exists())
                with self.assertRaisesRegex(ValueError, 'REGISTERED_EARNED_SUCCESSOR_DECISION_CHANGED'):
                    operator.audit(out)

    def test_native_buyer_substitution_and_extra_wallet(self):
        for operator in (inventor, mechanism_native):
            with self.subTest(operator=operator.__name__), TemporaryDirectory() as directory, small_workload():
                out = Path(directory) / 'new'
                original_execute = JournalAccount.execute
                mutations = []

                def change(account, op, args, day):
                    if operator is inventor and op in ('wallet', 'offer'):
                        mutations.append(op)
                        args = {**args, 'buyer': 'SIM-unregistered'}
                    if operator is mechanism_native and op == 'wallet' and not mutations:
                        mutations.append(op)
                        original_execute(account, 'wallet', {'buyer': 'SIM-bystander', 'amount': 1}, day)
                    return original_execute(account, op, args, day)

                with patch.object(JournalAccount, 'execute', change), patch.object(operator, 'audit'):
                    operator.run(out)
                self.assertTrue(mutations)
                with self.assertRaisesRegex(ValueError, 'REGISTERED_NATIVE_TRADE_OPERATIONS_CHANGED'):
                    operator.audit(out)

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
            # None of these single-market recovery fixtures earns its registered
            # successor price by the decision point. Deferral remains auditable.
            self.assertIsNone(result.get('native', result)['successor'])
            self.assertFalse((out / 'SUCCESSOR.json').exists())
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
