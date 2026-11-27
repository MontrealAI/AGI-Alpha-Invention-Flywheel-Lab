"""Fixed P0-250 synthetic signer tests; never use actual account/key material."""
import copy
import hashlib
import inspect
import os
from pathlib import Path
import secrets
import unittest

from owner_wire248 import canonical
from owner_signed_boundary250 import sign_owner_locked
from test_owner_wire248 import fixture
from test_owner_differential249 import load_pinned_historical_codec


def owner_lock(original, previous_counter=1, last_day=13):
    return {
        **{k: copy.deepcopy(original[k]) for k in
           ("id", "account_path", "from_source", "to_source",
            "expected_state_digest", "historical_root", "verifier_files")},
        "previous_counter": previous_counter,
        "last_day": last_day,
        **{f + "_sha256": hashlib.sha256(canonical(original[f])).hexdigest()
           if f in original else None
           for f in ("prior_record", "prior_envelope", "operating")}
    }


class OwnerSignedBoundary250(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = load_pinned_historical_codec()

    def sign(self, original, locked=None):
        # Distinct memory-only random synthetic key per test; never recorded.
        key = secrets.token_bytes(32)
        before = copy.deepcopy(original)
        ticket, blobs = sign_owner_locked(original, owner_lock=locked or owner_lock(original),
                                          ephemeral_authority_key=key)
        self.assertEqual(original, before)
        with self.historical.evidence_scope(blobs):
            result = self.historical.ticket_body(ticket, key=key)
        self.assertEqual(self.historical.canonical(result), canonical(original))
        self.assertEqual(len(ticket["signature"]), 64)
        return ticket, blobs, key

    def test_historical_owner_authenticates_nonempty_queued_liabilities(self):
        old = fixture()
        self.assertEqual(old["prior_record"]["claims"], 25)
        self.assertTrue(old["operating"]["prior_checkpoint"]["queue"])
        self.sign(old)

    def test_legacy_no_operating_owner_authenticates(self):
        old = fixture()
        old.pop("operating")
        ticket, blobs, _ = self.sign(old)
        self.assertEqual(set(ticket["body"]["evidence"]), {"prior_record", "prior_envelope"})
        self.assertEqual(len(blobs), 2)

    def test_locked_id_path_source_runtime_and_digest_reject(self):
        for field, value in (
            ("id", "WRONG"), ("account_path", "wrong/account"),
            ("from_source", {"sha256": "1" * 64}),
            ("to_source", {"sha256": "2" * 64}),
            ("expected_state_digest", "b" * 64),
            ("historical_root", "changed"),
            ("verifier_files", {"other.py": "3" * 64}),
        ):
            old = fixture()
            locked = owner_lock(old)
            old[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "OWNER_LOCK_FIELD_CHANGED"):
                sign_owner_locked(old, owner_lock=locked,
                                  ephemeral_authority_key=secrets.token_bytes(32))

    def test_stale_skipped_or_backward_counter_and_clock_reject(self):
        for field, value in (("counter", 1), ("counter", 3), ("counter", True),
                             ("day", 12), ("day", False)):
            old = fixture()
            locked = owner_lock(old)
            old[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                sign_owner_locked(old, owner_lock=locked,
                                  ephemeral_authority_key=secrets.token_bytes(32))

    def test_old_cash_claim_and_permanent_tail_cannot_change_between_lock_and_sign(self):
        for field, value in (("cash", 0), ("claims", 0), ("permanent_tail", [])):
            old = fixture()
            locked = owner_lock(old)
            old["prior_record"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "OWNER_LOCK_EVIDENCE_CHANGED"):
                sign_owner_locked(old, owner_lock=locked,
                                  ephemeral_authority_key=secrets.token_bytes(32))

    def test_nonempty_settlement_queue_cannot_be_cleared_before_signing(self):
        old = fixture()
        locked = owner_lock(old)
        old["operating"]["prior_checkpoint"]["queue"] = []
        with self.assertRaisesRegex(ValueError, "OWNER_LOCK_EVIDENCE_CHANGED:operating"):
            sign_owner_locked(old, owner_lock=locked,
                              ephemeral_authority_key=secrets.token_bytes(32))

    def test_historical_owner_rejects_wrong_key_or_signed_body_edit(self):
        ticket, blobs, key = self.sign(fixture())
        with self.historical.evidence_scope(blobs):
            with self.assertRaisesRegex(ValueError, "SIGNATURE_MISMATCH"):
                self.historical.ticket_body(ticket, key=secrets.token_bytes(32))
            edited = copy.deepcopy(ticket)
            edited["body"]["day"] += 1
            with self.assertRaisesRegex(ValueError, "SIGNATURE_MISMATCH"):
                self.historical.ticket_body(edited, key=key)

    def test_historical_owner_rejects_missing_or_mutated_blob(self):
        ticket, blobs, key = self.sign(fixture())
        missing = dict(blobs)
        del missing[ticket["body"]["evidence"]["operating"]["sha256"]]
        with self.historical.evidence_scope(missing):
            with self.assertRaises(ValueError):
                self.historical.ticket_body(ticket, key=key)
        corrupt = dict(blobs)
        name = ticket["body"]["evidence"]["prior_record"]["sha256"]
        corrupt[name] = corrupt[name] + b" "
        with self.assertRaises(ValueError):
            with self.historical.evidence_scope(corrupt):
                self.historical.ticket_body(ticket, key=key)

    def test_target_supplied_code_is_not_a_signer_input_or_executed(self):
        # If executed, this source throws. Neither the reference signer nor
        # pinned owner's decoder is asked to import/exec it.
        sentinel = "raise AssertionError('TARGET_CODE_EXECUTED')"
        self.assertNotIn("codec_source", inspect.signature(sign_owner_locked).parameters)
        with self.assertRaises(TypeError):
            sign_owner_locked(fixture(), owner_lock=owner_lock(fixture()),
                              ephemeral_authority_key=secrets.token_bytes(32),
                              codec_source=sentinel)
        old = fixture()
        old["codec_source"] = sentinel
        with self.assertRaises(ValueError):
            sign_owner_locked(old, owner_lock=owner_lock(fixture()),
                              ephemeral_authority_key=secrets.token_bytes(32))

    def test_absent_old_lock_or_invalid_ephemeral_key_reject(self):
        old = fixture()
        lock = owner_lock(old)
        del lock["prior_record_sha256"]
        with self.assertRaisesRegex(ValueError, "EXACT_OWNER_LOCK_REQUIRED"):
            sign_owner_locked(old, owner_lock=lock, ephemeral_authority_key=secrets.token_bytes(32))
        with self.assertRaisesRegex(ValueError, "EPHEMERAL_SYNTHETIC_KEY_REQUIRED"):
            sign_owner_locked(old, owner_lock=owner_lock(old), ephemeral_authority_key=b"weak")


if __name__ == "__main__":
    unittest.main()
