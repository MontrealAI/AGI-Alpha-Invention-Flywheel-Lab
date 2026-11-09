"""P0 main-side *executing* source-closure witness; NO native account opens.

Frozen case matrix: campaign/p0-live-manifest111/PROTOCOL.md at 5640ec69.
This test observes the real connected_enterprise.finance source publisher.
It does not substitute for original-account CAS migration or P0 owner release.
"""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import TapeExchange, digest
from connected_enterprise.finance import (
    JournalAccount, SOURCE_PATHS, source_identity, source_paths_for_manifest,
)
from connected_enterprise.engine import fresh_account_config

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "genesis-commitment001/native-services/v1":
        "campaign/genesis_commitment001/service.py",
    "public-portfolio-20261102/native-services/v2":
        "experiments/public_portfolio_20261102/verification/verify_artifacts.py",
    "flexibility063/native-services/v1":
        "flexibility063/verify.py",
    "production060/native-services/v1":
        "production060/dispatch.py",
    "inventory061/native-services/v1":
        "inventory061/independent_acceptance.py",
}


def _paths(schema):
    # Deliberately use the existing executing production dispatcher.
    return tuple(source_paths_for_manifest({"schema": schema}))


def _isolated_closure(root, paths):
    # Key-free *source* files only. No Account directories or private state.
    root.mkdir(parents=True, exist_ok=True)
    for name in paths:
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            raise AssertionError("EXPECTED_REAL_REGULAR_SOURCE:" + name)
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


class LiveManifestClosure111(unittest.TestCase):
    def test_all_five_live_routes_include_owned_base_and_sentinel(self):
        base = set(SOURCE_PATHS)
        self.assertEqual(len(base), len(SOURCE_PATHS))
        for schema, sentinel in ROUTES.items():
            with self.subTest(schema=schema):
                paths = _paths(schema)
                self.assertEqual(len(paths), len(set(paths)))
                self.assertTrue(base.issubset(paths))
                self.assertIn(sentinel, paths)
                self.assertGreater(len(paths), len(base))
                for name in paths:
                    source = ROOT / name
                    self.assertTrue(source.is_file(), name)
                    self.assertFalse(source.is_symlink(), name)

    def test_real_publisher_hashes_every_declared_file(self):
        identities = []
        for schema in ROUTES:
            with self.subTest(schema=schema):
                paths = _paths(schema)
                observed = source_identity(ROOT, {"schema": schema})
                expected = {
                    name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                    for name in paths
                }
                self.assertEqual(observed["files"], expected)
                self.assertEqual(observed["sha256"], digest(expected))
                identities.append(observed["sha256"])
        self.assertEqual(len(identities), len(set(identities)))

    def test_active_route_not_confused_with_legacy_default(self):
        baseline = tuple(source_paths_for_manifest(None))
        self.assertEqual(baseline, tuple(SOURCE_PATHS))
        self.assertEqual(
            tuple(source_paths_for_manifest({"schema": "unregistered/v1"})),
            baseline,
        )
        base_hash = source_identity(ROOT, None)["sha256"]
        self.assertNotIn(
            base_hash,
            [source_identity(ROOT, {"schema": schema})["sha256"]
             for schema in ROUTES],
        )

    def test_mutation_removal_and_symlink_refused_in_keyfree_copies(self):
        for schema, sentinel in ROUTES.items():
            with self.subTest(schema=schema), tempfile.TemporaryDirectory(
                prefix="p0-live-closure111-"
            ) as directory:
                scratch = Path(directory)
                _isolated_closure(scratch, _paths(schema))
                manifest = {"schema": schema}
                original = source_identity(scratch, manifest)
                self.assertEqual(
                    original, source_identity(ROOT, manifest),
                )
                target = scratch / sentinel
                pristine = target.read_bytes()
                target.write_bytes(pristine + b"\n# p0 witness mutation\n")
                mutated = source_identity(scratch, manifest)
                self.assertNotEqual(mutated["sha256"], original["sha256"])
                target.unlink()
                with self.assertRaises((OSError, ValueError)):
                    source_identity(scratch, manifest)
                # Link to a real source file: do not count it as original bytes.
                target.symlink_to(scratch / "connected_enterprise/finance.py")
                with self.assertRaises((OSError, ValueError)):
                    source_identity(scratch, manifest)

    def test_current_main_operating_apis_not_silently_dropped(self):
        self.assertIn(
            "_expected_before",
            inspect.signature(TapeExchange.execute).parameters,
        )
        self.assertTrue(callable(getattr(JournalAccount, "_prefix_identity", None)))
        self.assertTrue(callable(getattr(JournalAccount, "_audit_incremental", None)))
        self.assertIn("manifest", inspect.signature(source_identity).parameters)
        self.assertTrue(callable(fresh_account_config))


if __name__ == "__main__":
    unittest.main()
