"""P0-251 preregistered synthetic POSIX durable transport regressions."""
import copy
import hashlib
import hmac
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import tempfile
import unittest

from owner_signed_boundary250 import DOMAIN
from owner_wire248 import canonical
from owner_durable251 import publish_bundle, verify_bundle
from test_owner_signed_boundary250 import owner_lock
from test_owner_wire248 import fixture
from test_owner_differential249 import load_pinned_historical_codec


def _worker(root, original, lock, key, queue):
    try:
        receipt = publish_bundle(root, original, lock, key)
        queue.put(("ok", receipt["bundle_sha256"]))
    except Exception as exc:
        queue.put(("failed", type(exc).__name__ + ":" + str(exc)))


class OwnerDurable251Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = load_pinned_historical_codec()

    def new(self):
        old = fixture()
        return old, owner_lock(old), secrets.token_bytes(32)

    def publish(self, root, old, lock, key):
        before = copy.deepcopy(old)
        receipt = publish_bundle(root, old, lock, key)
        self.assertEqual(old, before)
        self.assertTrue(receipt["synthetic_hmac_verified"])
        self.assertEqual(receipt["file_count"], 4)
        return receipt

    def test_source_matched_owner_can_verify_persisted_nonempty_queue(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            receipt = self.publish(root, old, lock, key)
            where = Path(root) / ("bundle-" + receipt["bundle_sha256"])
            ticket = json.loads((where / "ticket.json").read_bytes())
            blobs = {name: (where / ref["sha256"]).read_bytes()
                     for name, ref in ticket["body"]["evidence"].items()}
            with self.historical.evidence_scope({hashlib.sha256(raw).hexdigest(): raw
                                                 for raw in blobs.values()}):
                recovered = self.historical.ticket_body(ticket, key=key)
            self.assertEqual(canonical(recovered), canonical(old))
            self.assertTrue(recovered["operating"]["prior_checkpoint"]["queue"])
            self.assertEqual(recovered["prior_record"]["permanent_tail"], [25])

    def test_interrupted_before_rename_is_not_committed_and_exact_retry_succeeds(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_INTERRUPTED"):
                publish_bundle(root, old, lock, key, interrupt_before_publish=True)
            self.assertFalse(any(p.name.startswith("bundle-") for p in Path(root).iterdir()))
            self.assertTrue(any(p.name.startswith(".pending-") for p in Path(root).iterdir()))
            receipt = self.publish(root, old, lock, key)
            self.assertEqual(verify_bundle(root, receipt["bundle_sha256"], old, key), receipt)

    def test_exact_repeat_is_idempotent_no_replaced_bytes(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            receipt = self.publish(root, old, lock, key)
            first = {p.name: p.read_bytes() for p in
                     (Path(root) / ("bundle-" + receipt["bundle_sha256"])).iterdir()}
            repeat = self.publish(root, old, lock, key)
            self.assertEqual(receipt, repeat)
            second = {p.name: p.read_bytes() for p in
                      (Path(root) / ("bundle-" + receipt["bundle_sha256"])).iterdir()}
            self.assertEqual(first, second)

    def test_missing_and_extra_committed_files_fail_closed(self):
        for failure in ("missing", "extra"):
            old, lock, key = self.new()
            with tempfile.TemporaryDirectory() as root:
                r = self.publish(root, old, lock, key)
                folder = Path(root) / ("bundle-" + r["bundle_sha256"])
                data_files = [p for p in folder.iterdir() if p.name != "ticket.json"]
                if failure == "missing":
                    data_files[0].unlink()
                else:
                    (folder / "not-addressed").write_bytes(b"unexpected")
                with self.subTest(failure=failure), self.assertRaises(ValueError):
                    verify_bundle(root, r["bundle_sha256"], old, key)

    def test_corrupt_file_and_wrong_signature_reject(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            r = self.publish(root, old, lock, key)
            with self.assertRaisesRegex(ValueError, "HMAC_MISMATCH"):
                verify_bundle(root, r["bundle_sha256"], old, secrets.token_bytes(32))
            folder = Path(root) / ("bundle-" + r["bundle_sha256"])
            data_file = next(p for p in folder.iterdir() if p.name != "ticket.json")
            data_file.write_bytes(data_file.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                verify_bundle(root, r["bundle_sha256"], old, key)

    def test_link_swap_and_hardlink_rejected(self):
        for kind in ("symlink", "hardlink"):
            old, lock, key = self.new()
            with tempfile.TemporaryDirectory() as root:
                r = self.publish(root, old, lock, key)
                folder = Path(root) / ("bundle-" + r["bundle_sha256"])
                data_file = next(p for p in folder.iterdir() if p.name != "ticket.json")
                original_raw = data_file.read_bytes()
                elsewhere = Path(root) / "outside-synthetic"
                elsewhere.write_bytes(original_raw)
                data_file.unlink()
                if kind == "symlink":
                    data_file.symlink_to(elsewhere)
                else:
                    os.link(elsewhere, data_file)
                with self.subTest(kind=kind), self.assertRaises((OSError, ValueError)):
                    verify_bundle(root, r["bundle_sha256"], old, key)

    def test_owner_original_and_liabilities_are_immutable(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            r = self.publish(root, old, lock, key)
            for field, value in (("cash", 0), ("claims", 0), ("permanent_tail", [])):
                changed = copy.deepcopy(old)
                changed["prior_record"][field] = value
                with self.subTest(field=field), self.assertRaises(ValueError):
                    verify_bundle(root, r["bundle_sha256"], changed, key)
                with self.assertRaises(ValueError):
                    publish_bundle(root, changed, lock, key)
            changed = copy.deepcopy(old)
            changed["operating"]["prior_checkpoint"]["queue"] = []
            with self.assertRaises(ValueError):
                verify_bundle(root, r["bundle_sha256"], changed, key)

    def test_private_root_or_symlinked_root_required(self):
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "owner"
            root.mkdir(mode=0o700)
            alias = Path(parent) / "alias"
            alias.symlink_to(root, target_is_directory=True)
            with self.assertRaises((OSError, ValueError)):
                publish_bundle(alias, old, lock, key)
            root.chmod(0o755)
            with self.assertRaisesRegex(ValueError, "PRIVATE_OWNER_DIRECTORY"):
                publish_bundle(root, old, lock, key)

    def test_two_processes_same_signed_bundle_no_clobber(self):
        if not hasattr(os, "fork"):
            self.skipTest("POSIX fork-based test")
        old, lock, key = self.new()
        with tempfile.TemporaryDirectory() as root:
            ctx = multiprocessing.get_context("fork")
            queue = ctx.Queue()
            children = [ctx.Process(target=_worker, args=(root, old, lock, key, queue))
                        for _ in range(2)]
            for child in children:
                child.start()
            for child in children:
                child.join(timeout=25)
                self.assertEqual(child.exitcode, 0)
            outcomes = [queue.get(timeout=5) for _ in children]
            self.assertTrue(all(x[0] == "ok" for x in outcomes), outcomes)
            self.assertEqual(outcomes[0][1], outcomes[1][1])
            self.assertEqual(len([p for p in Path(root).iterdir()
                                  if p.name.startswith("bundle-")]), 1)
            verify_bundle(root, outcomes[0][1], old, key)


if __name__ == "__main__":
    unittest.main()
