"""P0-249: key-free source-matched differential against pinned historical v2 codec.

Do not run with credentials, real accounts, signing authority or sensitive environment.
Only execute the Git-blob-verified historic owner module in isolated synthetic CI.
"""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import unittest

from owner_wire248 import (MAX_BLOB_BYTES, V1, canonical,
                           externalize_owner_v2, owner_pre_sign_compare)
from test_owner_wire248 import fixture

HISTORICAL_OWNER_BLOB = "2397091ef8e1960ad13950693d5b3cd04e2ff7c5"


def load_pinned_historical_codec():
    name = os.environ.get("PINNED_OWNER_SOURCE")
    if not name:
        raise RuntimeError("PINNED_OWNER_SOURCE_REQUIRED")
    raw = Path(name).read_bytes()
    # A Git blob digest commits to both object type/length and the file bytes.
    header = ("blob %d\0" % len(raw)).encode("ascii")
    actual = hashlib.sha1(header + raw).hexdigest()
    if actual != HISTORICAL_OWNER_BLOB:
        raise ValueError("PINNED_OWNER_GIT_BLOB_MISMATCH:" + actual)
    # The historical module runs only in the isolated, key-free synthetic
    # workflow process, never inside any historical account's signer.
    spec = importlib.util.spec_from_file_location("synthetic_pinned_owner_transition", name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PinnedOwnerDifferential249(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = load_pinned_historical_codec()

    def compare_good(self, original):
        original_before = copy.deepcopy(original)
        owner_blobs = {}
        owner_wire = self.owner.externalize(copy.deepcopy(original), owner_blobs)
        ours, ours_blobs = externalize_owner_v2(original)
        self.assertEqual(canonical(ours), self.owner.canonical(owner_wire))
        self.assertEqual(ours_blobs, owner_blobs)
        self.assertEqual(set(ours_blobs), set(owner_blobs))
        self.assertEqual(original, original_before)
        self.assertEqual(owner_pre_sign_compare(original, owner_wire, owner_blobs), canonical(owner_wire))
        with self.owner.evidence_scope(ours_blobs):
            restored = self.owner.ticket_body({"body": ours, "signature": "0"*64}, key=None)
        self.assertEqual(self.owner.canonical(restored), self.owner.canonical(original))
        return ours, ours_blobs

    def test_two_field_prior_account_without_operating(self):
        old = fixture()
        old.pop("operating")
        self.compare_good(old)

    def test_three_field_nonempty_settlement_and_permanent_claims(self):
        old = fixture()
        self.assertTrue(old["operating"]["prior_checkpoint"]["queue"])
        self.assertEqual(old["prior_record"]["claims"], 25)
        self.assertEqual(old["prior_record"]["permanent_tail"], [25])
        self.compare_good(old)

    def test_unicode_and_nested_data_owner_canonical_bytes(self):
        old = fixture()
        old["operating"]["note"] = {"é": ["Québec", "Ω", "✨", {"二": True}]}
        old["prior_record"]["additional"] = [{"a": 5, "b": [None, False, 1.25]}]
        self.compare_good(old)

    def test_historical_large_operating_blob_over_16mb(self):
        old = fixture()
        old["operating"]["prior_checkpoint"]["synthetic_large_queue"] = "Z" * (16_000_000 + 101)
        ours, blobs = self.compare_good(old)
        self.assertGreater(len(blobs[ours["evidence"]["operating"]["sha256"]]), 16_000_000)
        self.assertLess(len(blobs[ours["evidence"]["operating"]["sha256"]]), MAX_BLOB_BYTES)

    def test_counter_five_and_invalid_day_reject_before_signing(self):
        for field, value in [("counter", 5), ("counter", 0), ("counter", True),
                             ("day", -1), ("day", False)]:
            old = fixture()
            old[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    externalize_owner_v2(old)
        # The historic owner constructs a v2 representation, but its own
        # v2 resolver refuses a counter beyond the original four-upgrade limit.
        old = fixture()
        old["counter"] = 5
        blobs = {}
        wire = self.owner.externalize(copy.deepcopy(old), blobs)
        with self.owner.evidence_scope(blobs):
            with self.assertRaisesRegex(ValueError, "COUNTER_AND_CLOCK"):
                self.owner.ticket_body({"body": wire, "signature": "0"*64}, key=None)

    def test_missing_and_corrupted_blobs_fail_in_owner_scope(self):
        old = fixture()
        wire, blobs = self.compare_good(old)
        missing = dict(blobs)
        del missing[wire["evidence"]["operating"]["sha256"]]
        with self.owner.evidence_scope(missing):
            with self.assertRaises(ValueError):
                self.owner.ticket_body({"body": wire, "signature": "0"*64}, key=None)
        corrupt = dict(blobs)
        name = wire["evidence"]["operating"]["sha256"]
        corrupt[name] = corrupt[name] + b" "
        with self.assertRaises(ValueError):
            with self.owner.evidence_scope(corrupt):
                self.owner.ticket_body({"body": wire, "signature": "0"*64}, key=None)

    def test_unsigned_swapped_reference_needs_trusted_original_comparison(self):
        old = fixture()
        wire, blobs = self.compare_good(old)
        changed = copy.deepcopy(wire)
        changed["evidence"]["prior_record"], changed["evidence"]["operating"] = (
            changed["evidence"]["operating"], changed["evidence"]["prior_record"])
        with self.assertRaises(ValueError):
            owner_pre_sign_compare(old, changed, blobs)
        # Without HMAC or an owner-original comparison a generic resolver can
        # decode well-formed swapped blobs. Never call key-free decoding proof
        # authorization and never weaken the original historical HMAC gate.
        with self.owner.evidence_scope(blobs):
            restored = self.owner.ticket_body({"body": changed, "signature": "0"*64}, key=None)
        self.assertNotEqual(self.owner.canonical(restored), self.owner.canonical(old))


if __name__ == "__main__":
    unittest.main()
