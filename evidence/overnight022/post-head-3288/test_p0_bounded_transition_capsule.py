import copy
import os
from pathlib import Path
import tempfile
import unittest
from p0_bounded_transition_capsule import MAX_TICKET_BYTES, canonical, prepare, sha, verify

class CapsuleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='capsule-v2-isolated-')
        self.addCleanup(self.tmp.cleanup)
        self.storage = Path(self.tmp.name) / 'anchors'
        self.storage.mkdir()
        self.account = Path(self.tmp.name) / 'simulated-owned-account.sqlite'
        self.key = os.urandom(32)
        self.old = 'a' * 64
        self.new = 'b' * 64
        self.native = 'c' * 64
        self.record = {'connected_journal': {'entries': [], 'source_history': [], 'contract': 'test'},
                       'ledger': {'actions': [], 'summary': {'cash': 99, 'tailReserve': 9}}}
        self.envelope = {'body': self.record['connected_journal'], 'signature': 'already-authenticated-original'}
        self.checkpoint = {'body': {'source_sha256': self.old, 'native_sequence': 4,
                            'native_actions_sha256': self.native, 'state': {'last_time': 2, 'queue': [{'time': 3, 'kind': 'accept', 'id': 'q'}]}},
                           'signature': 'already-authenticated-original'}

    def make(self):
        return prepare(self.storage, key=self.key, account_path=self.account, transition_id='forward-1', counter=4,
                       day=2, from_source=self.old, to_source=self.new, checkpoint=self.checkpoint,
                       prior_record=self.record, prior_envelope=self.envelope, verified_native_sequence=4,
                       verified_native_digest=self.native)

    def audit(self, record, envelope, checkpoint):
        self.assertEqual(record['ledger']['summary']['tailReserve'], 9)
        self.assertEqual(envelope['body'], record['connected_journal'])
        return {'accepted': True, 'native_sequence': 4, 'native_actions_sha256': self.native}

    def check(self, ticket, **changes):
        kw = dict(key=self.key, account_path=self.account, expected_source=self.old, expected_counter=3,
                  expected_sequence=4, expected_native_digest=self.native,
                  expected_checkpoint_sha256=sha(canonical(self.checkpoint)), historical_audit=self.audit)
        kw.update(changes)
        return verify(self.storage, ticket, **kw)

    def test_large_legacy_record_v2_is_bounded_and_reusable(self):
        self.record['ledger']['signed_history_padding'] = 'x' * 17_500_000
        ticket = self.make()
        self.assertGreater(ticket['body']['anchor_bytes'], MAX_TICKET_BYTES)
        self.assertLess(len(canonical(ticket)), 1200)
        self.assertTrue(self.check(ticket)['structurally_verified'])
        self.assertEqual(self.make(), ticket)

    def test_tampered_cas_does_not_pass_even_with_valid_signed_ticket(self):
        ticket = self.make()
        path = self.storage / (ticket['body']['anchor_sha256'] + '.json')
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'ANCHOR_SIZE_CHANGED'):
            self.check(ticket)
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE_ANCHOR_COLLISION'):
            self.make()

    def test_cross_account_stale_checkpoint_and_replay_fail(self):
        t = self.make()
        for kw in [{'account_path': self.account.with_name('other.sqlite')}, {'expected_counter': 4},
                   {'expected_checkpoint_sha256': 'd'*64}, {'expected_source': 'e'*64}]:
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, 'STALE_FORK_OR_CROSS_ACCOUNT'):
                self.check(t, **kw)

    def test_forged_ticket_body_or_signature_fails(self):
        t = self.make()
        for forged in [{**t, 'signature': '0'*64}, {'body': {**t['body'], 'day': 5}, 'signature': t['signature']}]:
            with self.assertRaisesRegex(ValueError, 'ACCOUNT_CAPSULE_HMAC_REJECTED'):
                self.check(forged)

    def test_historical_verifier_is_required(self):
        t = self.make()
        with self.assertRaisesRegex(ValueError, 'MANDATORY_PINNED_HISTORICAL_AUDIT_REJECTED'):
            self.check(t, historical_audit=lambda *_: {'accepted': False})

    def test_symlink_anchor_refused(self):
        t = self.make()
        name = t['body']['anchor_sha256'] + '.json'
        p = self.storage / name
        real = self.storage / 'original.bin'
        p.rename(real)
        p.symlink_to(real)
        with self.assertRaisesRegex(ValueError, 'REGULAR_NON_SYMLINK_ANCHOR_REQUIRED'):
            self.check(t)

    def test_wrong_checkpoint_prefix_rejected_before_persistence(self):
        self.checkpoint['body']['native_actions_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'OPERATING_NATIVE_PREFIX_OR_SOURCE_CHANGED'):
            self.make()
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_pending_queue_clock_overtake_and_inflight_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_TRANSITION_OVERTAKES_PENDING_WORK'):
            prepare(self.storage, key=self.key, account_path=self.account, transition_id='bad-time', counter=4,
                    day=4, from_source=self.old, to_source=self.new, checkpoint=self.checkpoint,
                    prior_record=self.record, prior_envelope=self.envelope, verified_native_sequence=4,
                    verified_native_digest=self.native)
        self.assertEqual(list(self.storage.iterdir()), [])
        self.checkpoint['body']['state']['current'] = {'id': 'in-flight'}
        with self.assertRaisesRegex(ValueError, 'RECOVER_INFLIGHT_OR_INVALID_QUEUE'):
            self.make()

    def test_legacy_counter_out_of_bound_rejected(self):
        with self.assertRaisesRegex(ValueError, 'FINITE_NATIVE_COUNTER_AND_CLOCK_REQUIRED'):
            prepare(self.storage, key=self.key, account_path=self.account, transition_id='bad', counter=5, day=2,
                    from_source=self.old, to_source=self.new, checkpoint=self.checkpoint,
                    prior_record=self.record, prior_envelope=self.envelope, verified_native_sequence=4,
                    verified_native_digest=self.native)

if __name__ == '__main__':
    unittest.main(verbosity=2)
