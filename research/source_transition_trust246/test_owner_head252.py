"""Frozen P0-252 nine-case synthetic fork and head regressions."""
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import tempfile
import unittest

from owner_durable251 import publish_bundle, verify_bundle
from owner_head252 import commit_owner_transition, read_committed_head
from owner_signed_boundary250 import sign_owner_locked
from owner_wire248 import canonical
from test_owner_differential249 import load_pinned_historical_codec
from test_owner_signed_boundary250 import owner_lock
from test_owner_wire248 import fixture


def candidate(digit, *, counter=2, day=14, from_digit="a"):
    body = fixture()
    body["from_source"] = {"sha256": from_digit * 64}
    body["to_source"] = {"sha256": digit * 64}
    body["counter"] = counter
    body["day"] = day
    return body


def _race(root, key, original, q, go):
    try:
        go.wait(10)
        result = commit_owner_transition(
            root, original, owner_lock(original), key, expected_prior_head=None)
        q.put(("accepted", result["head_sha256"]))
    except Exception as exc:
        q.put(("rejected", str(exc)))


class OwnerHead252Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = load_pinned_historical_codec()

    def setup_pair(self):
        old = candidate("b")
        return old, secrets.token_bytes(32)

    def run_first(self, root, old, key):
        return commit_owner_transition(root, old, owner_lock(old), key)

    def test_01_first_commit_authenticated_head_and_original_owner_resolver(self):
        old, key = self.setup_pair()
        before = copy.deepcopy(old)
        with tempfile.TemporaryDirectory() as root:
            got = self.run_first(root, old, key)
            head = read_committed_head(root, key, original=old)
            self.assertEqual(got["head_sha256"], head["head_sha256"])
            self.assertEqual(head["body"]["predecessor"], None)
            self.assertEqual(got["counter"], old["counter"])
            folder = Path(root) / ("bundle-" + got["bundle_sha256"])
            ticket = json.loads((folder / "ticket.json").read_bytes())
            blobs = {name: (folder / ref["sha256"]).read_bytes()
                     for name, ref in ticket["body"]["evidence"].items()}
            with self.historical.evidence_scope({
                    hashlib.sha256(x).hexdigest(): x for x in blobs.values()}):
                resolved = self.historical.ticket_body(ticket, key=key)
            self.assertEqual(canonical(resolved), canonical(old))
            self.assertEqual(old, before)

    def test_02_different_target_race_has_one_winner(self):
        if not hasattr(os, "fork"):
            self.skipTest("POSIX fork only")
        old1, key = self.setup_pair()
        old2 = candidate("c")
        with tempfile.TemporaryDirectory() as bare:
            # Negative control: P0-251 alone publishes both incompatible
            # owner-locked signed bundles, so it is not a fork arbiter.
            r1 = publish_bundle(bare, old1, owner_lock(old1), key)
            r2 = publish_bundle(bare, old2, owner_lock(old2), key)
            self.assertNotEqual(r1["bundle_sha256"], r2["bundle_sha256"])
        with tempfile.TemporaryDirectory() as root:
            ctx = multiprocessing.get_context("fork")
            q, go = ctx.Queue(), ctx.Event()
            processes = [ctx.Process(target=_race, args=(root, key, old, q, go))
                         for old in (old1, old2)]
            for p in processes:
                p.start()
            go.set()
            for p in processes:
                p.join(timeout=25)
                self.assertEqual(p.exitcode, 0)
            results = [q.get(timeout=5) for _ in processes]
            self.assertEqual(sorted(x[0] for x in results),
                             ["accepted", "rejected"], results)
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 1)
            head = read_committed_head(root, key)
            self.assertEqual(head["head_sha256"],
                             next(x[1] for x in results if x[0] == "accepted"))
            self.assertIn(head["body"]["to_source"]["sha256"], {"b" * 64, "c" * 64})

    def test_03_exact_retransmission_idempotent(self):
        old, key = self.setup_pair()
        with tempfile.TemporaryDirectory() as root:
            first = self.run_first(root, old, key)
            raw = (Path(root) / "owner-head.json").read_bytes()
            repeated = self.run_first(root, old, key)
            self.assertTrue(repeated["idempotent"])
            self.assertEqual(repeated["head_sha256"], first["head_sha256"])
            self.assertEqual((Path(root) / "owner-head.json").read_bytes(), raw)
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 1)

    def test_04_valid_source_continuation(self):
        old, key = self.setup_pair()
        newer = candidate("c", counter=3, day=20, from_digit="b")
        with tempfile.TemporaryDirectory() as root:
            first = self.run_first(root, old, key)
            second = commit_owner_transition(
                root, newer, owner_lock(newer, previous_counter=2, last_day=14),
                key, expected_prior_head=first["head_sha256"])
            self.assertEqual(second["counter"], 3)
            self.assertNotEqual(first["head_sha256"], second["head_sha256"])
            head = read_committed_head(root, key, original=newer)
            self.assertEqual(head["body"]["predecessor"], first["head_sha256"])
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 2)

    def test_05_stale_fork_counter_downgrade_and_wrong_identity_fail(self):
        old, key = self.setup_pair()
        with tempfile.TemporaryDirectory() as root:
            first = self.run_first(root, old, key)
            changed = candidate("c")
            with self.assertRaises(ValueError):
                self.run_first(root, changed, key)
            cases = [
                candidate("c", counter=4, day=20, from_digit="b"),
                candidate("c", counter=3, day=13, from_digit="b"),
                candidate("c", counter=3, day=20, from_digit="a"),
                candidate("c", counter=3, day=20, from_digit="b"),
            ]
            cases[-1]["account_path"] = "other/synthetic/account"
            cases[-1]["id"] = "OTHER_SYNTHETIC"
            for case in cases:
                with self.subTest(counter=case["counter"],day=case["day"],
                                  source=case["from_source"],ident=case["id"]):
                    with self.assertRaises(ValueError):
                        commit_owner_transition(root, case,
                            owner_lock(case, previous_counter=case["counter"] - 1,
                                       last_day=min(14, case["day"])),
                            key, expected_prior_head=first["head_sha256"])
            self.assertEqual(read_committed_head(root, key)["head_sha256"],
                             first["head_sha256"])
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 1)

    def test_06_crash_after_bundle_head_absent_then_same_retry(self):
        old, key = self.setup_pair()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError,"CRASH_AFTER_BUNDLE"):
                commit_owner_transition(root, old, owner_lock(old), key,
                                        interrupt="after_bundle")
            self.assertIsNone(read_committed_head(root, key))
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 1)
            result = self.run_first(root, old, key)
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 1)
            self.assertEqual(result["head_sha256"],
                             read_committed_head(root, key, original=old)["head_sha256"])

    def test_07_crash_after_head_is_committed_and_retry_idempotent(self):
        old, key = self.setup_pair()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "CRASH_AFTER_HEAD"):
                commit_owner_transition(root, old, owner_lock(old), key,
                                        interrupt="after_head")
            head = read_committed_head(root, key, original=old)
            retry = self.run_first(root, old, key)
            self.assertTrue(retry["idempotent"])
            self.assertEqual(head["head_sha256"], retry["head_sha256"])

    def test_08_head_tamper_duplicate_wrong_key_links_and_bundle_corruption(self):
        old, key = self.setup_pair()
        with tempfile.TemporaryDirectory() as root:
            first = self.run_first(root, old, key)
            head = Path(root) / "owner-head.json"
            raw = head.read_bytes()
            with self.assertRaisesRegex(ValueError, "HMAC_MISMATCH"):
                read_committed_head(root, secrets.token_bytes(32))
            head.write_bytes(raw.replace(b'"counter":2', b'"counter":3'))
            with self.assertRaises(ValueError):
                read_committed_head(root, key)
            head.write_bytes(b'{"body":{},"body":{},"signature":"0"}')
            with self.assertRaises(ValueError):
                read_committed_head(root, key)
            head.write_bytes(raw)
            external = Path(root) / "outside"
            external.write_bytes(raw)
            head.unlink()
            head.symlink_to(external)
            with self.assertRaises((ValueError, OSError)):
                read_committed_head(root, key)
            head.unlink()
            os.link(external, head)
            with self.assertRaises((ValueError, OSError)):
                read_committed_head(root, key)
            head.unlink()
            head.write_bytes(raw)
            head.chmod(0o600)  # Exercise bundle verification, not an accidental head-mode failure.
            (Path(root) / ("bundle-" + first["bundle_sha256"]) / "ticket.json").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "PUBLISHED_TICKET_DIGEST_MISMATCH"):
                read_committed_head(root, key, original=old)

    def test_09_locked_liabilities_and_queue_stay_immutable(self):
        old, key = self.setup_pair()
        locked = owner_lock(old)
        with tempfile.TemporaryDirectory() as root:
            for field, value in (("cash", 0), ("claims", 0), ("permanent_tail", [])):
                altered = copy.deepcopy(old)
                altered["prior_record"][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    commit_owner_transition(root, altered, locked, key)
            changed = copy.deepcopy(old)
            changed["operating"]["prior_checkpoint"]["queue"] = []
            with self.assertRaises(ValueError):
                commit_owner_transition(root, changed, locked, key)
            self.assertIsNone(read_committed_head(root, key))
            self.assertEqual(len(list(Path(root).glob("bundle-*"))), 0)
            success = commit_owner_transition(root, old, locked, key)
            self.assertEqual(old["prior_record"]["claims"], 25)
            self.assertTrue(old["operating"]["prior_checkpoint"]["queue"])
            self.assertFalse(success["idempotent"])


if __name__ == "__main__":
    unittest.main()
