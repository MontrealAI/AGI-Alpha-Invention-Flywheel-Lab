"""T165: fixed unsigned control-plane stale cached prepare probe on owner PR40.

Protocol frozen at d6c1f0743005728c55b923405ec79b39c161b8cd
before this test code. Synthetic signed-text fixtures are NOT HMAC proofs or
original financial accounts. No authoritative source/account mutations.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise import operations
from connected_enterprise.engine import default_config
from connected_enterprise.migration import default_policy


class CachedPreparedCheckpoint165(unittest.TestCase):
    def test_cached_identical_prepare_rejects_observed_checkpoint_advance(self):
        with tempfile.TemporaryDirectory(prefix="transition-stale165-") as tmp:
            root = Path(tmp)
            output = root / "disposable-business"
            output.mkdir()
            target = root / "disposable-target"
            target.mkdir()
            manifest_path = root / "SYNTHETIC-SERVICES.json"
            manifest = {"synthetic": "no real services, customers, funds or signing"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            old_source = {"sha256": "a" * 64, "files": {}}
            target_source = {"sha256": "b" * 64, "files": {}}
            a = {"body": {"state": {
                "config": default_config(), "source": old_source,
                "seed": 165, "arm": "baseline", "last_time": 0, "current": None
            }}, "signature": "SYNTHETIC_UNAUTHENTICATED_A"}
            (output / "STATE.json").write_text(json.dumps(a), encoding="utf-8")
            old_digest = digest(a)
            signer_ids = []
            copied_sources = []

            def fake_authorize(**kwargs):
                signer_ids.append(kwargs["ident"])
                return {"body": {"scope": "UNSIGNED_SYNTHETIC_ONLY"},
                        "signature": "NO_HMAC"}

            def fake_copy_source(*args, **kwargs):
                copied_sources.append(1)
                return target_source

            def call():
                return operations.prepare_upgrade(
                    target, target, manifest_path, output,
                    policy=default_policy(),
                    expected_checkpoint_sha256=old_digest, ident="writer-A"
                )

            def before_bytes():
                history = output / "OPERATOR_HISTORY"
                return (
                    (output / "OPERATOR.json").read_bytes(),
                    (output / "SERVICES.json").read_bytes(),
                    sorted((p.relative_to(output).as_posix(), p.read_bytes())
                           for p in history.rglob("*") if p.is_file())
                    if history.exists() else []
                )

            with (
                patch("connected_enterprise.upgrades.authorize_upgrade",
                      side_effect=fake_authorize),
                patch("connected_enterprise.upgrades.validate_ticket",
                      return_value=None),
                patch("connected_enterprise.runner.identity",
                      return_value=target_source),
                patch.object(operations, "_copy_source",
                             side_effect=fake_copy_source),
                patch.object(operations, "_copy_inputs", return_value=None)
            ):
                first = call()
                self.assertEqual(first["upgrade_request"]["id"], "writer-A")
                stable = before_bytes()
                self.assertEqual(first, call(),
                                 "UNCHANGED_IDENTICAL_REQUEST_MUST_BE_IDEMPOTENT")
                self.assertEqual(stable, before_bytes(),
                                 "UNCHANGED_RETRY_MUST_NOT_WRITE")
                self.assertEqual(signer_ids, ["writer-A"])
                self.assertEqual(len(copied_sources), 1)

                b = copy.deepcopy(a)
                b["body"]["state"]["last_time"] = 24
                b["signature"] = "SYNTHETIC_UNAUTHENTICATED_B"
                self.assertNotEqual(digest(b), old_digest)
                (output / "STATE.json").write_text(
                    json.dumps(b), encoding="utf-8"
                )
                changed_state_bytes = (output / "STATE.json").read_bytes()
                self.assertNotEqual(changed_state_bytes, json.dumps(a).encode())
                # Fixed adversarial schedule: no financial/account operation.
                error = None
                returned = None
                try:
                    returned = call()
                except (ValueError, FileExistsError) as exc:
                    error = str(exc)
                self.assertIsNone(
                    returned,
                    "STALE_CACHED_PREPARE_ACCEPTED_ADVANCED_STATE: "
                    "identical writer-A request returned after checkpoint B"
                )
                self.assertIsNotNone(error, "STALE_REQUEST_MUST_BE_REFUSED")
                self.assertTrue(
                    any(token in error.upper() for token in (
                        "STALE", "CHANGED", "REPLAY", "AUTHORITY",
                        "CONFLICT", "REFUSED"
                    )),
                    "INCIDENTAL_IO_FAILURE_NOT_AN_AUTHORITY_REJECTION: " + error
                )
                self.assertEqual(stable, before_bytes(),
                                 "REFUSED_RETRY_MUST_NOT_MUTATE_OPERATOR")
                self.assertEqual(changed_state_bytes,
                                 (output / "STATE.json").read_bytes())
                self.assertEqual(signer_ids, ["writer-A"],
                                 "REFUSE_BEFORE_SECOND_SIGNING")
                self.assertEqual(len(copied_sources), 1,
                                 "REFUSE_BEFORE_SOURCE_COPY")


if __name__ == "__main__":
    unittest.main(verbosity=2)
