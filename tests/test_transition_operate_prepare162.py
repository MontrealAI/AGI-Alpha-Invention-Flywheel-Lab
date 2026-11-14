"""Preregistered Transition162 cross-operation control-plane race, synthetic only.

This does not authenticate real accounts or execute native financial work.
Exact parent and fixed schedule: docs/transition-operate-prepare162/PROTOCOL.md.
"""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise import operations
from connected_enterprise.engine import default_config
from connected_enterprise.migration import default_policy


class OperatePrepareEpoch162(unittest.TestCase):
    def test_operating_old_epoch_cannot_overlap_new_prepare_success(self):
        with tempfile.TemporaryDirectory(prefix="transition-operate-prepare162-") as tmp:
            root = Path(tmp)
            output = root / "business"
            output.mkdir()
            (output / "source").mkdir()
            target = root / "new-source"
            target.mkdir()

            cfg = default_config()
            old = {"sha256": "a" * 64, "files": {}}
            new = {"sha256": "b" * 64, "files": {}}
            manifest = {"synthetic": "no real services, private accounts or revenue"}
            manifest_file = root / "REGISTERED-SERVICES.json"
            manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
            prior = {"body": {"state": {
                "config": cfg, "source": old, "seed": 162, "arm": "baseline",
                "last_time": 0, "current": None
            }}, "signature": "synthetic-not-HMAC"}
            operations._write(output / "STATE.json", prior)
            operations._write(output / "SERVICES.json", manifest)
            descriptor = {
                "schema": operations.SCHEMA, "source_dir": "source",
                "source": old, "business_dir": ".", "config": cfg,
                "seed": 162, "arm": "baseline",
                "manifest_sha256": digest(manifest), "upgrade_request": None,
                "scope": "CONDITIONAL_SYNTHETIC_CONNECTED_BUSINESS",
            }
            descriptor["sha256"] = digest(descriptor)
            operations._write(output / "OPERATOR.json", descriptor)
            checkpoint_sha = digest(prior)

            old_run_entered = threading.Event()
            allow_old_run_to_return = threading.Event()
            prepare_started = threading.Event()
            prepared_done = threading.Event()
            observed = {"operate_selected": None, "operator_at_old_run_exit": None}
            signed_ids = []

            def identity(source_root):
                return old if Path(source_root).absolute() == output / "source" else new

            def run_world(*args, **kwargs):
                observed["operate_selected"] = kwargs["source"]["sha256"]
                old_run_entered.set()
                if not allow_old_run_to_return.wait(10):
                    raise RuntimeError("TEST_SCHEDULER_FAILED_TO_RELEASE_OLD_OPERATION")
                current, _ = operations.read_operator(output)
                observed["operator_at_old_run_exit"] = {
                    "source": current["source"]["sha256"],
                    "pending": current["upgrade_request"] is not None,
                }
                return {"synthetic_only": "old-run-resumed"}

            def authorize_upgrade(**kwargs):
                signed_ids.append(kwargs["ident"])
                return {"body": {"synthetic_only": True}, "signature": "not-HMAC"}

            def attempt_prepare():
                prepare_started.set()
                try:
                    d = operations.prepare_upgrade(
                        target, target, manifest_file, output,
                        policy=default_policy(),
                        expected_checkpoint_sha256=checkpoint_sha,
                        ident="new-epoch-writer",
                    )
                    return ("accepted", d["upgrade_request"]["id"])
                except Exception as exc:
                    return ("rejected", type(exc).__name__ + ":" + str(exc))
                finally:
                    prepared_done.set()

            with (
                patch("connected_enterprise.runner.identity", side_effect=identity),
                patch("connected_enterprise.engine.run_world", side_effect=run_world),
                patch("connected_enterprise.upgrades.authorize_upgrade", side_effect=authorize_upgrade),
                patch("connected_enterprise.upgrades.validate_ticket", return_value=None),
                patch.object(operations, "_copy_source", return_value=new),
                patch.object(operations, "_copy_inputs", return_value=None),
            ):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    operation = pool.submit(operations.operate, output)
                    self.assertTrue(old_run_entered.wait(5),
                                    "OLD_OPERATION_MUST_SELECT_SOURCE_BEFORE_PREPARE")
                    preparation = pool.submit(attempt_prepare)
                    self.assertTrue(prepare_started.wait(5), "PREPARE_WAS_NOT_SCHEDULED")
                    try:
                        # Fixed observation window: a shared lease should prevent
                        # publication until old run_world exits. A deliberately
                        # unguarded prepare completes in this window.
                        prepare_finished_while_old_active = prepared_done.wait(2.5)
                    finally:
                        allow_old_run_to_return.set()
                    operated = operation.result(timeout=10)
                    status, detail = preparation.result(timeout=10)

            self.assertEqual(operated, {"synthetic_only": "old-run-resumed"})
            if status == "rejected":
                self.assertTrue(any(token in detail.upper() for token in (
                    "PENDING", "STALE", "CONFLICT", "LOCK", "EXCLUSIVE",
                    "FORK", "REPLAY", "REFUSED", "PREPARE", "CHANGED",
                )), "INCIDENTAL_FIXTURE_ERROR_IS_NOT_A_SAFETY_REFUSAL:" + detail)
            self.assertFalse(
                prepare_finished_while_old_active and status == "accepted",
                "TRANSITION162_OLD_OPERATION_AND_NEW_PREPARE_BOTH_ACCEPTED:"
                + repr({"status": status, "detail": detail,
                        "signed": signed_ids, "observed": observed}),
            )
            self.assertFalse(
                observed["operator_at_old_run_exit"]["pending"]
                and observed["operator_at_old_run_exit"]["source"] != old["sha256"],
                "TRANSITION162_OLD_RUN_RESUMED_UNDER_NEW_PENDING_SOURCE:"
                + repr({"status": status, "detail": detail, "observed": observed}),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
