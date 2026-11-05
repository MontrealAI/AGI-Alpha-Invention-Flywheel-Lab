"""GENESIS must ship and qualify as a complete optional native release path."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from commercial.ledger import digest
from connected_enterprise.runner import (
    GENESIS_RELEASE_PATHS, genesis_release_paths, source_paths,
)
from genesis_enterprise.native import source_files
from scripts import release_connected014 as release

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'a' * 40


class GenesisReleaseClosureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.required = set(GENESIS_RELEASE_PATHS) | set(source_files(ROOT))

    def populate(self):
        for name in self.required:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic inventory fixture, not executable evidence\n')

    def archive(self, names):
        path = self.root/'source.zip'
        raw = b'synthetic inventory fixture, not executable evidence\n'
        files = {name: hashlib.sha256(raw).hexdigest() for name in names}
        identity = {'files': files, 'sha256': digest(files)}
        manifest = {'schema': 'agi-alpha/connected014-source-distribution/v1',
                    'files': files, 'executing_source': identity}
        with zipfile.ZipFile(path, 'w') as archive:
            for name in files:
                archive.writestr(name, raw)
            archive.writestr('SOURCE_MANIFEST.json', json.dumps(manifest))
        return path, manifest

    def test_complete_closure_includes_native_runtime_and_default_protocol(self):
        self.populate()
        self.assertEqual(genesis_release_paths(self.root), self.required)
        self.assertIn('campaign/genesis-enterprise-002/PROTOCOL.json', self.required)
        self.assertTrue(set(source_files(ROOT)) <= self.required)

    def test_canonical_inventory_uses_genesis_closure(self):
        # Isolate the hook from unrelated optional historical campaign closures.
        (self.root/'genesis-required.py').touch()
        with patch('connected_enterprise.runner.inherited_paths', return_value=[]), \
             patch('connected_enterprise.runner.genesis_release_paths', return_value={'genesis-required.py'}) as closure:
            self.assertIn('genesis-required.py', source_paths(self.root))
        closure.assert_called_once_with(self.root)

    def test_every_missing_member_is_rejected(self):
        self.populate()
        for name in sorted(self.required):
            with self.subTest(name=name):
                path = self.root/name
                raw = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, 'GENESIS_.*(REQUIRED|MISSING)'):
                    genesis_release_paths(self.root)
                path.write_bytes(raw)

    def test_symlinked_member_is_rejected(self):
        self.populate()
        path = self.root/'campaign/genesis-enterprise-002/PROTOCOL.json'
        path.unlink()
        path.symlink_to(self.root/'genesis_enterprise/policy.py')
        with self.assertRaisesRegex(ValueError, 'GENESIS_COMPLETE_RELEASE_SOURCE_REQUIRED'):
            genesis_release_paths(self.root)

    def test_markerless_historical_shim_and_workflow_remain_readable(self):
        names = {'connected_enterprise/genesis.py', '.github/workflows/genesis-enterprise-002.yml'}
        for name in names:
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        self.assertEqual(genesis_release_paths(self.root), set())
        archive, expected = self.archive(names)
        self.assertEqual(release.archive_manifest(archive), expected)

    def test_complete_archive_is_accepted(self):
        archive, expected = self.archive(self.required)
        self.assertEqual(release.archive_manifest(archive), expected)

    def test_resealed_partial_archive_cannot_hide_missing_members(self):
        for name in sorted(self.required):
            with self.subTest(name=name):
                archive, _ = self.archive(self.required - {name})
                with self.assertRaisesRegex(ValueError, 'GENESIS_EXACT_RELEASE_SOURCE_CLOSURE_REQUIRED'):
                    release.archive_manifest(archive)

    def assets(self):
        archive, source = self.archive(self.required)
        assets = self.root/'assets'
        assets.mkdir()
        archive.rename(assets/'connected014-source.zip')
        (assets/'connected014-keyfree.zip').write_bytes(b'key-free fixture')
        for name in ('RELEASE_NOTES.md', *release.PAPERS):
            (assets/name).write_text('synthetic release fixture, not qualification\n')
        release.write(assets/'PUBLICATION.json', {'source_sha256': source['executing_source']['sha256']})
        release.write(assets/'QUALIFICATION.json', {
            'accepted': True, 'source_sha256': source['executing_source']['sha256'],
            'source_archive': {'sha256': release.digest(assets/'connected014-source.zip')},
            'public_archive': {'sha256': release.digest(assets/'connected014-keyfree.zip')},
        })
        manifest = {'schema': 'agi-alpha/connected014-release/v1', 'source_commit': COMMIT,
                    'source_sha256': source['executing_source']['sha256'], 'tag': release.tag(COMMIT)}
        release.seal(assets, manifest)
        return assets, source, manifest

    def test_release_requires_genesis_qualification_even_after_reseal(self):
        assets, _, _ = self.assets()
        with self.assertRaisesRegex(ValueError, 'SOURCE_BOUND_GENESIS_QUALIFICATION_REQUIRED'):
            release.verify_assets(assets, COMMIT)

    def test_release_calls_source_bound_genesis_validator(self):
        assets, source, manifest = self.assets()
        receipt = {'actual_release_download': False}
        release.write(assets/'GENESIS_QUALIFICATION.json', receipt)
        release.seal(assets, manifest)
        # Validator semantics are exercised independently by its own tests.
        with patch('scripts.qualify_genesis_release.validate_receipt') as validate:
            release.verify_assets(assets, COMMIT)
        validate.assert_called_once_with(receipt, source,
            release.digest(assets/'connected014-source.zip'), COMMIT)

    def test_prepublication_receipt_cannot_claim_actual_download(self):
        assets, _, manifest = self.assets()
        release.write(assets/'GENESIS_QUALIFICATION.json', {'actual_release_download': True})
        release.seal(assets, manifest)
        with patch('scripts.qualify_genesis_release.validate_receipt'), \
             self.assertRaisesRegex(ValueError, 'GENESIS_PREPUBLICATION_QUALIFICATION_REQUIRED'):
            release.verify_assets(assets, COMMIT)

    def test_workflow_qualifies_archive_then_actual_downloaded_source(self):
        text = (ROOT/'.github/workflows/connected014-release.yml').read_text()
        clean = text.index('name: Qualify GENESIS from the exact clean source archive')
        publish = text.index('name: Bind immutable release assets')
        self.assertLess(clean, publish)
        self.assertIn('cp "$RUNNER_TEMP/genesis-qualified/QUALIFICATION.json"', text)
        downloaded = text.index('name: Operate and audit GENESIS from the actual downloaded release source')
        self.assertLess(text.index('name: Install the released flexibility experiment'), downloaded)
        step = text[downloaded:text.index('name: Retain only key-free released GENESIS evidence')]
        self.assertIn('working-directory: ${{ runner.temp }}/downloaded-release-operation/source', step)
        self.assertIn('--download-receipt "$RUNNER_TEMP/RELEASE_DOWNLOAD.json"', step)
        self.assertIn('${{ runner.temp }}/released-genesis/public', text)
        self.assertNotIn('${{ runner.temp }}/released-genesis/operation', text)


if __name__ == '__main__':
    unittest.main()
