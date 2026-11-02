"""Public package membership and retained-evidence checks; no account operations."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from adaptive_enterprise.instruments import SOURCE_PATHS as INSTRUMENT_PATHS
from connected_enterprise.runner import source_paths as canonical_source_paths
from experiments.capability_transfer_20261102.release_inventory import (
    EXPERIMENT, SOURCE_PATHS, source_paths,
)


ROOT = Path(__file__).resolve().parents[2]
BASE_MEMBERS = set(INSTRUMENT_PATHS) | {'connected_enterprise/__init__.py'}


def membership_fixture(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('public membership fixture\n')


class ReleaseInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cell-pack-inventory-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        membership_fixture(self.root, set(SOURCE_PATHS) | BASE_MEMBERS)

    def canonical(self):
        # Exercise the real inherited inventory; unrelated optional campaigns
        # are absent from this minimal public membership fixture.
        return canonical_source_paths(self.root)

    def test_canonical_inventory_ignores_unlisted_local_data_and_state(self):
        extras = (
            'raw/measurements.csv', 'results/unregistered.json',
            'private/account.sqlite', 'private/recovery.adaptive-simulation-key',
            '_native_cost_fixtures/unregistered/MANIFEST.json',
            '__pycache__/instrument.pyc',
        )
        for name in extras:
            path = self.root / EXPERIMENT / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('excluded synthetic membership fixture\n')
        self.assertEqual(set(self.canonical()), set(SOURCE_PATHS) | BASE_MEMBERS)
        self.assertEqual(len(SOURCE_PATHS), len(set(SOURCE_PATHS)))

    def test_missing_public_receipt_refuses_partial_distribution(self):
        (self.root / EXPERIMENT / 'results/RESEARCH_ACCOUNT_PUBLIC.json.gz').unlink()
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_TRANSFER_PUBLIC_SOURCE_REQUIRED'):
            self.canonical()

    def test_linked_member_and_linked_parent_are_refused(self):
        receipt = self.root / EXPERIMENT / 'results/RESEARCH_ACCOUNT_PUBLIC.json.gz'
        target = self.root / 'outside-fixture'
        target.write_text('public membership fixture\n')
        receipt.unlink()
        receipt.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_TRANSFER_PUBLIC_SOURCE_REQUIRED'):
            source_paths(self.root)
        receipt.unlink()
        receipt.write_text('public membership fixture\n')
        results = self.root / EXPERIMENT / 'results'
        moved = self.root / 'moved-results'
        results.rename(moved)
        results.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_TRANSFER_PUBLIC_SOURCE_REQUIRED'):
            source_paths(self.root)

    def test_current_frozen_sources_and_original_evidence_are_included_exactly(self):
        included = set(source_paths(ROOT))
        experiment = ROOT / EXPERIMENT
        freeze = json.loads((experiment / 'FROZEN_STAGE_B_SERIALIZATION_FIX.json').read_text())
        manifest = json.loads((experiment / 'results/MANIFEST.json').read_text())
        expected = dict(freeze['sources'])
        expected.update({'results/' + name: item['sha256'] for name, item in manifest['files'].items()})
        for name, digest in expected.items():
            with self.subTest(member=name):
                self.assertIn(EXPERIMENT + '/' + name, included)
                self.assertEqual(hashlib.sha256((experiment / name).read_bytes()).hexdigest(), digest)

    def test_legacy_distribution_without_experiment_remains_supported(self):
        with tempfile.TemporaryDirectory(prefix='cell-pack-absent-') as empty:
            root = Path(empty)
            membership_fixture(root, BASE_MEMBERS)
            self.assertEqual(set(canonical_source_paths(root)), BASE_MEMBERS)


if __name__ == '__main__':
    unittest.main()
