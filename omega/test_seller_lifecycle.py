"""Engineering fixtures; these tests never recover or replace the mission account."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from omega.native_lifecycle.acceptance import accept
from omega.seller_lifecycle import MICRO, OPENING, checkout_choice, package, run_fixture


class DownloadAcceptanceTests(unittest.TestCase):
    def test_checkout_requires_unambiguous_choice_and_explicit_consent(self):
        for choice, consent in [(None, True), (['self_hosted_demo', 'webinar'], True), ('self_hosted_demo', 1)]:
            with self.assertRaises(ValueError):
                checkout_choice(choice, consent)
        self.assertEqual(checkout_choice('self_hosted_demo', False), 'NO_ORDER')
        self.assertEqual(checkout_choice('founder_private', True), 'MANUAL_DELIVERY_NOT_EXECUTED')

    def test_exact_demo_accepted_not_genesis(self):
        receipt = accept(package())
        self.assertTrue(receipt['accepted'])
        self.assertIn('only', receipt['meaning'])

    def test_package_content_scope_and_hash_tampering_rejected(self):
        cases = [lambda x: x['files'].update({'../escape': 'bad'}),
                 lambda x: x.update(edition='GENESIS'),
                 lambda x: x['sha256'].update({'demo.py': '0' * 64}),
                 lambda x: x.update(scope='LIVE_COMMERCIAL_PRODUCT')]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                candidate = copy.deepcopy(package())
                mutate(candidate)
                with self.assertRaises(ValueError):
                    accept(candidate)


class NativeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='omega-lifecycle-unit-')
        cls.output = Path(cls.tmp.name) / 'fixture'
        cls.result = run_fixture(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def audit_process(self):
        return subprocess.run([sys.executable, '-m', 'omega.seller_lifecycle', '--output', str(self.output), '--staged', '--audit'],
                              cwd=self.output / 'source', capture_output=True, text=True)

    def test_complete_native_flow_refund_dispute_and_costs(self):
        summary = self.result['native_summary_microUSD']
        self.assertEqual(summary['cash'], OPENING - 155_200_000)
        self.assertEqual(summary['profit'], -155_200_000)
        self.assertEqual(summary['expenses'], 155_200_000)
        self.assertEqual(summary['collections'], 0)
        self.assertEqual(summary['revenue'], 0)
        self.assertEqual(summary['payables'], 0)
        self.assertTrue(summary['investmentStopped'])
        self.assertEqual(self.result['accepted_downloads'], 1)
        self.assertEqual(self.result['failed_deliveries_refunded'], 1)
        self.assertEqual(self.result['released_orders_later_reversed'], 1)
        self.assertIsNone(self.result['trailing_365_day_profit_microUSD'])
        self.assertIsNone(self.result['actual_complete_cost_profit_microUSD'])
        self.assertEqual(self.audit_process().returncode, 0)

    def test_profitable_but_insufficient_unrestricted_cash_defers(self):
        case = self.result['local_results']['liquidity']
        self.assertEqual(case['profit_microUSD'], 164 * MICRO)
        self.assertLess(case['available_microUSD'], case['requested_microUSD'])
        self.assertTrue(case['native_state_unchanged'])
        self.assertEqual(case['investment'], 'DEFERRED')

    def test_decline_help_and_manual_services_honest(self):
        self.assertFalse(self.result['local_results']['decline']['native_order_created'])
        self.assertEqual(self.result['local_results']['unavailable-model-help']['external_calls'], 0)
        self.assertTrue(self.result['local_results']['unavailable-model-help']['unresolved'])
        self.assertEqual(self.result['manual_offers']['founder_private']['delivery'], 'NOT_EXECUTED_MANUAL')
        self.assertEqual(self.result['human_exception_minutes_assumed'], 15)

    def test_same_account_completed_resume_is_idempotent(self):
        before = (self.output / 'native-public-export.json').read_bytes()
        resumed = run_fixture(self.output, resume=True)
        self.assertEqual(resumed, self.result)
        self.assertEqual(before, (self.output / 'native-public-export.json').read_bytes())
        with self.assertRaisesRegex(ValueError, 'FRESH_FIXTURE_DESTINATION_REQUIRED'):
            run_fixture(self.output)

    def test_interruption_after_fund_commit_recovers_without_duplicate_charge(self):
        target = Path(self.tmp.name) / 'interrupted'
        paused = run_fixture(target, interrupt_after='A-fund')
        self.assertFalse(paused['complete'])
        resumed = run_fixture(target, resume=True)
        self.assertEqual(resumed['native_summary_microUSD'], self.result['native_summary_microUSD'])
        self.assertEqual(resumed['native_actions_sha256'], self.result['native_actions_sha256'])

    def test_missing_private_recovery_authority_fails_without_reseed(self):
        path = self.output / 'account.sqlite.adaptive-simulation-key'
        backup = path.with_name(path.name + '.unit-backup')
        before = (self.output / 'native-public-export.json').read_bytes()
        path.rename(backup)
        try:
            with self.assertRaisesRegex(ValueError, 'ORIGINAL_FIXTURE_RECOVERY_AUTHORITY_REQUIRED'):
                run_fixture(self.output, resume=True)
            self.assertFalse(path.exists())
            self.assertEqual(before, (self.output / 'native-public-export.json').read_bytes())
        finally:
            backup.rename(path)

    def test_report_claim_tampering_fails(self):
        path = self.output / 'result.json'
        original = path.read_bytes()
        try:
            changed = json.loads(original)
            changed['trailing_365_day_profit_microUSD'] = 3_000_000_000 * MICRO
            path.write_text(json.dumps(changed))
            self.assertNotEqual(self.audit_process().returncode, 0)
        finally:
            path.write_bytes(original)

    def test_registered_policy_job_and_download_tampering_fail(self):
        candidates = [
            (self.output / 'registration.json', lambda x: x.update(opening_microUSD=100_000 * MICRO)),
            (self.output / 'manifest.json', lambda x: x['jobs'][0].update(id='unqualified-genesis')),
            (self.output / 'source' / 'download-fixture' / 'package.json', lambda x: x['files'].update({'demo.py': 'print("forged")'})),
            (self.output / 'buyer-A' / 'package.json', lambda x: x.update(edition='GENESIS')),
        ]
        for path, mutate in candidates:
            original = path.read_bytes()
            try:
                changed = json.loads(original)
                mutate(changed)
                path.write_text(json.dumps(changed))
                with self.subTest(path=path.name):
                    self.assertNotEqual(self.audit_process().returncode, 0)
            finally:
                path.write_bytes(original)

    def test_changed_native_runtime_rejected(self):
        path = self.output / 'source' / 'connected_enterprise' / 'finance.py'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n# unit-test source drift\n')
            self.assertNotEqual(self.audit_process().returncode, 0)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
