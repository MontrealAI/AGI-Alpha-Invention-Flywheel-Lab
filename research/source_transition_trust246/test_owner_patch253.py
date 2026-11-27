"""P0-253 pre-registered source-matched tests; synthetic/key-free only."""
import ast
import copy
import inspect
import os
from pathlib import Path
import unittest
from owner_patch253 import OWNER_UPGRADES_BLOB, REPLACEMENTS, git_blob_id, patch_historical_owner
from test_owner_differential249 import HISTORICAL_OWNER_BLOB, load_pinned_historical_codec
from test_owner_wire248 import fixture
from owner_wire248 import canonical, externalize_owner_v2, owner_pre_sign_compare

class OwnerPinnedPatch253(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get("PINNED_OWNER_UPGRADES")
        if not path:
            raise RuntimeError("PINNED_OWNER_UPGRADES_REQUIRED")
        cls.old = Path(path).read_bytes()
        cls.codec = load_pinned_historical_codec()

    def test_01_pinned_historical_source_and_codec(self):
        self.assertEqual(git_blob_id(self.old), OWNER_UPGRADES_BLOB)
        self.assertEqual(git_blob_id(Path(os.environ["PINNED_OWNER_SOURCE"]).read_bytes()), HISTORICAL_OWNER_BLOB)

    def test_02_only_five_unique_reversible_anchors(self):
        original = self.old.decode("utf-8")
        candidate = patch_historical_owner(self.old).decode("utf-8")
        for old, new in REPLACEMENTS:
            self.assertEqual(original.count(old), 1)
            self.assertEqual(candidate.count(new), 1)
        reversed_copy = candidate
        for old, new in reversed(REPLACEMENTS):
            reversed_copy = reversed_copy.replace(new, old, 1)
        self.assertEqual(reversed_copy, original)

    def test_03_no_untrusted_executable_codec(self):
        candidate = patch_historical_owner(self.old).decode("utf-8")
        ast.parse(candidate)
        for forbidden in ("codec_source", "exec(p[", "target_root/'connected_enterprise/transition_evidence.py'"):
            self.assertNotIn(forbidden, candidate)

    def test_04_original_native_authority_checks_untouched(self):
        original = self.old.decode("utf-8")
        candidate = patch_historical_owner(self.old).decode("utf-8")
        for term in ("with scope, JournalAccount(", "a.verify_checkpoint(",
                     "a.snapshot()['state_digest']", "SOURCE_UPGRADE_CLOCK_ROLLBACK",
                     "MAX_TICKET_BYTES = 16_000_000", "hmac.new(a._account._key",
                     "source_inventory(historical_root) != files"):
            self.assertIn(term, original)
            self.assertIn(term, candidate)
        self.assertIn("from connected_enterprise.transition_evidence import externalize, preflight_storage, persist_evidence", candidate)

    def test_05_source_drift_and_second_patch_fail_closed(self):
        candidate = patch_historical_owner(self.old)
        for altered in (candidate, self.old + b"\n# drift\n"):
            with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_CHANGED"):
                patch_historical_owner(altered)

    def test_06_two_field_v2_owner_wire_parity(self):
        old = fixture()
        old.pop("operating")
        blobs = {}
        owner = self.codec.externalize(copy.deepcopy(old), blobs)
        ours, ours_blobs = externalize_owner_v2(old)
        self.assertEqual(canonical(owner), canonical(ours))
        self.assertEqual(blobs, ours_blobs)
        self.assertEqual(owner_pre_sign_compare(old, ours, ours_blobs), canonical(ours))

    def test_07_nonempty_queue_and_claims_owner_wire_parity(self):
        old = fixture()
        frozen = copy.deepcopy(old)
        self.assertTrue(old["operating"]["prior_checkpoint"]["queue"])
        self.assertEqual(old["prior_record"]["permanent_tail"], [25])
        blobs = {}
        owner = self.codec.externalize(copy.deepcopy(old), blobs)
        ours, ours_blobs = externalize_owner_v2(old)
        self.assertEqual(canonical(owner), canonical(ours))
        self.assertEqual(blobs, ours_blobs)
        self.assertEqual(old, frozen)
        with self.codec.evidence_scope(blobs):
            restored = self.codec.ticket_body({"body": ours, "signature": "0" * 64})
        self.assertEqual(canonical(restored), canonical(old))

    def test_08_original_trusted_codec_functions_exist(self):
        for name in ("externalize", "preflight_storage", "persist_evidence"):
            self.assertTrue(callable(getattr(self.codec, name)))
        patch = patch_historical_owner(self.old).decode("utf-8")
        for call in ("body=externalize(body,blobs)",
                     "preflight_storage(unsigned,r,old)",
                     "persist_evidence(p['evidence_dir'],blobs)"):
            self.assertIn(call, patch)

    def test_09_source_only_candidate_has_no_account_access(self):
        self.assertEqual(list(inspect.signature(patch_historical_owner).parameters), ["raw"])
        source = inspect.getsource(patch_historical_owner)
        for forbidden in ("JournalAccount(", "subprocess.", "Path(", "open("):
            self.assertNotIn(forbidden, source)
        self.assertEqual(git_blob_id(self.old), OWNER_UPGRADES_BLOB)

if __name__ == "__main__":
    unittest.main()
