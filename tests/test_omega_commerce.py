"""Real local workflow execution, independent byte checks and adverse transitions."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import canonical, digest

from omega.commerce import (CommerceFixture, COST_POLICY, MICRO, SCOPE, inspect_continuation,
                            offer, reinvestment_view, run_fixture)


class SellerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='omega-commerce-test-')
        self.root = Path(self.tmp.name)
        self.artifact = self.root / 'fixture.txt'
        self.artifact.write_bytes(b'Authored delivery fixture; no commercial edition or entitlement.\n')
        self.path = self.root / 'workflow.sqlite'
        self.shop = CommerceFixture(self.path, self.artifact)

    def tearDown(self):
        self.shop.close()
        self.tmp.cleanup()

    def selected(self, ident='buyer', kind='self_hosted', session=None):
        self.shop.act(ident + ':discovery', 'discover', ident, offer_id=kind, session_id=session)
        self.shop.act(ident + ':choose', 'choose', ident, consent=True)

    def paid(self, ident='buyer', kind='self_hosted', session=None):
        self.selected(ident, kind, session)
        self.shop.act(ident + ':payment', 'payment', ident, provider='TEST_DOUBLE', status='succeeded')
        self.shop.act(ident + ':entitle', 'entitle', ident)

    def test_optional_quotes_expose_scope_currency_and_rights(self):
        self.assertEqual([offer(k)['price_microUSD'] for k in ('self_hosted', 'group_webinar', 'founder_private')],
                         [299 * MICRO, 99 * MICRO, 20000 * MICRO])
        for kind in ('self_hosted', 'group_webinar', 'founder_private'):
            quote = offer(kind)
            self.assertEqual(quote['scope'], SCOPE)
            self.assertEqual(quote['currency'], 'USD')
            self.assertIn('UNRESOLVED', quote['license_status'])
            self.assertFalse(quote['ongoing_support'])

    def test_decline_has_no_payment_entitlement_or_native_posting(self):
        self.shop.act('d', 'discover', 'declined', offer_id='self_hosted', session_id=None)
        self.shop.act('c', 'choose', 'declined', consent=False)
        with self.assertRaisesRegex(ValueError, 'CONSENTED_UNPAID'):
            self.shop.act('p', 'payment', 'declined', provider='TEST_DOUBLE', status='succeeded')
        report = self.shop.report()
        self.assertEqual(report['funnel_counts']['simulated_captures'], 0)
        self.assertEqual(report['native_account_postings'], 0)

    def test_failed_payment_and_unavailable_provider_cannot_deliver(self):
        self.selected()
        for status in ('unavailable', 'failed'):
            self.shop.act(status, 'payment', 'buyer', provider='TEST_DOUBLE', status=status)
        with self.assertRaisesRegex(ValueError, 'CAPTURED_PAYMENT'):
            self.shop.act('no-access', 'entitle', 'buyer')
        with self.assertRaisesRegex(ValueError, 'SIMULATED_PROVIDER'):
            self.shop.act('live', 'payment', 'buyer', provider='stripe', status='succeeded')
        self.assertEqual(self.shop.report()['funnel_counts']['simulated_captures'], 0)

    def test_interrupted_restart_duplicate_capture_and_actual_download(self):
        self.paid()
        before = self.shop.report()['funnel_counts']
        self.shop.close()
        self.shop = CommerceFixture(self.path, self.artifact)
        self.shop.act('buyer:payment', 'payment', 'buyer', provider='TEST_DOUBLE', status='succeeded')
        self.assertEqual(self.shop.report()['funnel_counts'], before)
        with self.assertRaisesRegex(ValueError, 'IDEMPOTENT_WORKFLOW_PAYLOAD_CHANGED'):
            self.shop.act('buyer:payment', 'payment', 'buyer', provider='TEST_DOUBLE', status='failed')
        receipt = self.shop.act('download', 'download', 'buyer')
        self.assertEqual(receipt['state'], 'download_ready')
        staged = self.shop.report()
        self.assertEqual(staged['funnel_counts']['delivered'], 0)
        self.assertEqual(staged['receipt_reconciliation_microUSD']['fixture_recognition_after_delivery_and_reversals'], 0)
        output = self.root / 'buyer-download.txt'
        self.shop.download_copy('buyer', output)
        self.shop.download_copy('buyer', output)
        self.assertEqual(output.read_bytes(), self.artifact.read_bytes())
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), receipt['artifact_sha256'])
        self.shop.act('onboard', 'onboard', 'buyer')
        self.assertEqual(self.shop.report()['funnel_counts']['onboarded'], 1)

    def test_changed_download_bytes_fail_before_delivery(self):
        self.paid()
        self.artifact.write_bytes(b'Changed artifact')
        with self.assertRaisesRegex(ValueError, 'ACTUAL_DOWNLOAD_BYTES_CHANGED'):
            self.shop.act('download', 'download', 'buyer')
        self.assertEqual(self.shop.report()['funnel_counts']['delivered'], 0)

    def test_refund_revokes_access_preserves_processing_cost(self):
        self.paid()
        self.shop.act('download', 'download', 'buyer')
        self.shop.download_copy('buyer', self.root / 'delivered.txt')
        self.shop.act('refund', 'refund', 'buyer')
        report = self.shop.report()['receipt_reconciliation_microUSD']
        self.assertEqual(report['synthetic_captures'], report['refunds_and_lost_disputes'])
        self.assertGreater(report['processing_and_dispute_fee_envelope'], 0)
        self.assertLess(report['net_captured_value_before_other_costs_not_cash'], 0)
        with self.assertRaisesRegex(ValueError, 'ACTIVE_STAGED_DOWNLOAD'):
            self.shop.download_copy('buyer', self.root / 'revoked.txt')

    def test_dispute_after_refund_adds_fee_without_double_principal(self):
        self.paid()
        self.shop.act('refund', 'refund', 'buyer')
        self.shop.act('dispute', 'dispute', 'buyer')
        self.shop.act('resolution', 'resolve_dispute', 'buyer', result='buyer_wins')
        report = self.shop.report()
        receipt = report['receipt_reconciliation_microUSD']
        self.assertEqual(receipt['refunds_and_lost_disputes'], 299 * MICRO)
        self.assertGreater(receipt['processing_and_dispute_fee_envelope'], COST_POLICY['dispute_fee_microUSD'])
        self.assertEqual(report['founder']['modeled_required_minutes'], 20)
        self.assertFalse(report['founder']['autonomous_claim'])

    def test_capture_does_not_imply_settlement(self):
        self.paid()
        self.shop.act('held', 'settle', 'buyer', provider='TEST_DOUBLE', status='held')
        view = self.shop.report()['receipt_reconciliation_microUSD']
        self.assertEqual(view['synthetic_gross_settlements'], 0)
        self.assertEqual(view['unsettled_capture_receivables_before_refunds'], 299 * MICRO)
        self.assertEqual(view['fixture_recognition_after_delivery_and_reversals'], 0)
        self.assertEqual(view['unfulfilled_order_liability'], 299 * MICRO)
        self.shop.act('settled', 'settle', 'buyer', provider='TEST_DOUBLE', status='settled')
        self.assertEqual(self.shop.report()['receipt_reconciliation_microUSD']['synthetic_gross_settlements'], 299 * MICRO)

    def test_process_interruption_rolls_back_uncommitted_workflow_command(self):
        self.paid()
        before = self.shop.audit()
        script = "import os,sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE'); c.execute('INSERT INTO commands(id,request,receipt) VALUES (?,?,?)',('interrupted',b'{}',b'{}')); os._exit(7)"
        child = subprocess.run([sys.executable, '-c', script, str(self.path)], check=False)
        self.assertEqual(child.returncode, 7)
        self.assertEqual(self.shop.audit(), before)

    def test_existing_foreign_database_is_refused_without_any_byte_change(self):
        foreign = self.root / 'unrelated.sqlite'
        with sqlite3.connect(foreign) as connection:
            connection.execute('CREATE TABLE unrelated(value TEXT)')
            connection.execute('INSERT INTO unrelated VALUES (?)', ('preserve me',))
        before = foreign.read_bytes()
        with self.assertRaisesRegex(ValueError, 'EXISTING_OWNED_WORKFLOW_REQUIRED'):
            CommerceFixture(foreign, self.artifact)
        self.assertEqual(foreign.read_bytes(), before)
        with sqlite3.connect(foreign) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [('unrelated',)])
            self.assertEqual(connection.execute('SELECT value FROM unrelated').fetchall(), [('preserve me',)])

    def test_existing_empty_or_metadata_missing_database_is_not_adopted(self):
        for name in ('empty.sqlite', 'missing-metadata.sqlite'):
            foreign = self.root / name
            with sqlite3.connect(foreign) as connection:
                if name.startswith('missing'):
                    connection.execute('CREATE TABLE commands(value TEXT)')
            before = foreign.read_bytes()
            with self.assertRaisesRegex(ValueError, 'EXISTING_OWNED_WORKFLOW_REQUIRED'):
                CommerceFixture(foreign, self.artifact)
            self.assertEqual(foreign.read_bytes(), before)

    def test_failed_copy_cannot_recognize_delivery_or_overwrite_destination(self):
        self.paid()
        self.shop.act('download', 'download', 'buyer')
        destination = self.root / 'existing.txt'
        destination.write_bytes(b'Unrelated buyer file')
        with self.assertRaisesRegex(ValueError, 'EXISTING_DOWNLOAD_DESTINATION_DIFFERS'):
            self.shop.download_copy('buyer', destination)
        self.assertEqual(destination.read_bytes(), b'Unrelated buyer file')
        view = self.shop.report()
        self.assertEqual(view['funnel_counts']['delivered'], 0)
        self.assertEqual(view['receipt_reconciliation_microUSD']['fixture_recognition_after_delivery_and_reversals'], 0)
        with self.assertRaisesRegex(ValueError, 'ACTIVE_DELIVERED_ORDER_REQUIRED'):
            self.shop.act('onboard', 'onboard', 'buyer')
        with self.assertRaisesRegex(ValueError, 'ACTUAL_COPY_ENTRYPOINT_REQUIRED'):
            self.shop.act('fabricated-copy', 'download_complete', 'buyer')

    def test_interrupted_after_actual_copy_recovers_without_false_delivery(self):
        self.paid()
        self.shop.act('download', 'download', 'buyer')
        destination = self.root / 'interrupted-delivery.txt'
        script = """import os,sys
from omega.commerce import CommerceFixture
shop=CommerceFixture(sys.argv[1],sys.argv[2])
original=shop._apply
def interrupt(state,request,*,verify_bytes):
    if request['operation']=='download_complete': os._exit(8)
    return original(state,request,verify_bytes=verify_bytes)
shop._apply=interrupt
shop.download_copy('buyer',sys.argv[3])
"""
        child = subprocess.run([sys.executable, '-c', script, str(self.path), str(self.artifact), str(destination)], check=False)
        self.assertEqual(child.returncode, 8)
        self.assertEqual(destination.read_bytes(), self.artifact.read_bytes())
        self.assertEqual(self.shop.report()['funnel_counts']['delivered'], 0)
        self.shop.close()
        self.shop = CommerceFixture(self.path, self.artifact)
        self.shop.download_copy('buyer', destination)
        self.shop.download_copy('buyer', destination)
        view = self.shop.report()
        self.assertEqual(view['funnel_counts']['delivered'], 1)
        self.assertEqual(view['receipt_reconciliation_microUSD']['fixture_recognition_after_delivery_and_reversals'], 299 * MICRO)

    def test_seller_won_dispute_restores_undelivered_entitlement(self):
        self.paid()
        self.shop.act('dispute', 'dispute', 'buyer')
        self.shop.act('won', 'resolve_dispute', 'buyer', result='seller_wins')
        self.shop.act('download', 'download', 'buyer')
        self.shop.download_copy('buyer', self.root / 'won-dispute.txt')
        self.shop.act('onboard', 'onboard', 'buyer')
        view = self.shop.report()
        self.assertEqual(view['funnel_counts']['disputes'], 1)
        self.assertEqual(view['funnel_counts']['delivered'], 1)
        self.assertEqual(view['funnel_counts']['onboarded'], 1)

    def test_unknown_help_is_counted_and_known_help_does_not_claim_resolution(self):
        self.paid()
        known = self.shop.act('known', 'help', 'buyer', code='MODEL_UNAVAILABLE')
        self.assertTrue(known['known_diagnostic'])
        self.assertFalse(known['resolved'])
        self.assertTrue((Path(__file__).resolve().parents[1] / known['document']).is_file())
        unknown = self.shop.act('unknown', 'help', 'buyer', code='UNSEEN_ERROR')
        self.assertFalse(unknown['known_diagnostic'])
        report = self.shop.report()
        self.assertEqual(report['founder']['exception_count'], 1)
        self.assertEqual(report['founder']['modeled_required_minutes'], 12)

    def test_finite_founder_capacity_enforced_before_simulated_payment(self):
        self.shop.close()
        self.path = self.root / 'limited.sqlite'
        self.shop = CommerceFixture(self.path, self.artifact, founder_budget_minutes=105)
        self.paid('one', 'founder_private', 'private-one')
        self.selected('two', 'founder_private', 'private-two')
        with self.assertRaisesRegex(ValueError, 'FOUNDER_CAPACITY_EXHAUSTED'):
            self.shop.act('two:payment', 'payment', 'two', provider='TEST_DOUBLE', status='succeeded')
        self.shop.act('one:deliver', 'deliver_session', 'one', founder_supplied='SIMULATED_RECEIPT')
        report = self.shop.report()
        self.assertEqual(report['funnel_counts']['simulated_captures'], 1)
        self.assertEqual(report['founder']['modeled_required_minutes'], 105)

    def test_session_capacity_and_shared_preparation(self):
        state = {'sessions': {}, 'founder_reserved_minutes': 0, 'exceptions': []}
        row = {'offer': offer('group_webinar'), 'session_id': 'group'}
        for _ in range(500):
            self.shop._reserve_session(state, row)
        self.assertEqual(state['founder_reserved_minutes'], 330)
        with self.assertRaisesRegex(ValueError, 'SESSION_FULL'):
            self.shop._reserve_session(state, row)
        row['session_id'] = 'second-group'
        with self.assertRaisesRegex(ValueError, 'FOUNDER_CAPACITY'):
            self.shop._reserve_session(state, row)

    def test_receipt_tampering_detected_on_replay(self):
        self.selected()
        original = self.shop.db.execute('SELECT receipt FROM commands WHERE id=?', ('buyer:choose',)).fetchone()[0]
        changed = json.loads(original)
        changed['state'] = 'payment_captured'
        self.shop.db.execute('UPDATE commands SET receipt=? WHERE id=?', (json.dumps(changed).encode(), 'buyer:choose'))
        with self.assertRaisesRegex(ValueError, 'WORKFLOW_REPLAY_RECEIPT_CHANGED'):
            self.shop.audit()
        with self.assertRaisesRegex(ValueError, 'WORKFLOW_REPLAY_RECEIPT_CHANGED'):
            self.shop.act('buyer:choose', 'choose', 'buyer', consent=True)

    def test_no_original_account_recovery_never_creates_or_reseeds(self):
        missing = self.root / 'original-unavailable'
        result = inspect_continuation(missing)
        self.assertEqual(result['status'], 'BLOCKED_ORIGINAL_RECOVERY_STATE_MISSING')
        self.assertFalse(result['new_account_created'])
        self.assertFalse(missing.exists())
        compact = self.root / 'compact-only'
        compact.mkdir()
        (compact / 'RESULT.json').write_text('{"cash":75200}')
        self.assertEqual(inspect_continuation(compact)['status'], 'BLOCKED_ORIGINAL_RECOVERY_STATE_MISSING')
        self.assertEqual([p.name for p in compact.iterdir()], ['RESULT.json'])

    def test_recovery_consistency_never_claims_original_custody_and_checks_tape_header(self):
        from omega.seller import declared_registration
        directory = self.root / 'candidate-recovery-fixture'
        (directory / 'source').mkdir(parents=True)
        registration = declared_registration()
        config = {'contract': 'omega-research:' + digest(registration)}
        record = {'ledger': {'config': config, 'actions': [], 'actions_sha256': digest([])},
                  'connected_journal': {'scope': 'synthetic consistency-test stub'}}
        files = {'registration.json': registration, 'manifest.json': {}, 'result.json': {},
                 'native-public-export.json': record,
                 'account.sqlite.connected-journal.json': {'body': record['connected_journal'], 'signature': '0' * 64}}
        for name, content in files.items():
            (directory / name).write_bytes(canonical(content))
        header = {'schema': 'agi-alpha/commercial010-durable-actions/v1', 'config': config}
        tape = directory / 'account.sqlite.actions.jsonl'
        tape.write_bytes(canonical(header) + b'\n')
        key = directory / 'account.sqlite.adaptive-simulation-key'
        key.write_bytes(b'X' * 32)
        key.chmod(0o600)
        original_reader = Path.read_bytes
        def deny_key_read(path):
            if path == key:
                raise AssertionError('Recovery preflight must not read private authority bytes')
            return original_reader(path)
        with patch('omega.commerce.replay_audit', return_value={'accepted': True}), patch.object(Path, 'read_bytes', deny_key_read):
            result = inspect_continuation(directory)
            self.assertEqual(result['status'], 'CANDIDATE_RECOVERY_CONSISTENT_REQUIRES_ORIGINAL_CUSTODY_PROVENANCE')
            self.assertFalse(result['private_key_contents_read'])
            self.assertFalse(result['continuation_authorized'])
            tape.write_bytes(canonical({**header, 'config': {'contract': 'other'}}) + b'\n')
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_RECOVERY_TAPE_HEADER_MISMATCH'):
                inspect_continuation(directory)

    def test_stale_download_time_rejected_before_writing_destination(self):
        self.paid()
        self.shop.act('download', 'download', 'buyer', hour=10)
        destination = self.root / 'stale-time.txt'
        with self.assertRaisesRegex(ValueError, 'WORKFLOW_TIME_REGRESSION'):
            self.shop.download_copy('buyer', destination, hour=0)
        self.assertFalse(destination.exists())
        self.shop.download_copy('buyer', destination, hour=10)
        self.assertEqual(self.shop.report()['funnel_counts']['delivered'], 1)

    def test_artifact_growth_after_open_is_refused_before_read_or_copy(self):
        self.paid()
        self.shop.act('download', 'download', 'buyer')
        with self.artifact.open('ab') as stream:
            stream.write(b'additional bytes')
        destination = self.root / 'grown-artifact.txt'
        with patch.object(Path, 'open', side_effect=AssertionError('size guard must precede opening bytes')):
            with self.assertRaisesRegex(ValueError, 'ACTUAL_DOWNLOAD_BYTES_CHANGED'):
                self.shop.download_copy('buyer', destination)
        self.assertFalse(destination.exists())

    def test_profit_survives_cash_deferral_without_authorizing_spend(self):
        summary = {'profit': 1000 * MICRO, 'available': 50 * MICRO, 'unrestrictedEarned': 50 * MICRO}
        before = copy.deepcopy(summary)
        result = reinvestment_view(summary, 100 * MICRO, 200 * MICRO)
        self.assertEqual(result['decision'], 'DEFER')
        self.assertEqual(result['reason'], 'INSUFFICIENT_UNRESTRICTED_CASH')
        self.assertEqual(result['recorded_profit_microUSD_unchanged'], 1000 * MICRO)
        self.assertFalse(result['spending_authority'])
        self.assertEqual(summary, before)

    def test_complete_fixture_has_zero_native_postings_and_no_annual_claim(self):
        report = run_fixture(self.root / 'complete', self.artifact)
        self.assertTrue(report['audit']['accepted'])
        self.assertEqual(report['native_account_postings'], 0)
        self.assertIsNone(report['complete_cost_profit_microUSD'])
        self.assertIsNone(report['trailing_365_day_profit_microUSD'])
        self.assertEqual(report['funnel_counts']['simulated_captures'], 5)
        self.assertEqual(report['founder']['modeled_required_minutes'], 467)
        self.assertEqual(report['founder']['exception_count'], 2)


if __name__ == '__main__':
    unittest.main()
