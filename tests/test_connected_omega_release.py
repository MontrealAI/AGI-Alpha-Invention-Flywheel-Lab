"""V4 release closure and exact packaged-operation evidence boundaries.

Synthetic archives/receipts below exercise rejection logic, never claim an
executed business. Full extracted-source operation is qualified separately.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from connected_enterprise import runner
from mechanism_harness.cart_native import source_identity
from scripts import release_connected014 as release

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'a' * 40


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_source_archive(path, payloads):
    files = {name: sha(raw) for name, raw in payloads.items()}
    manifest = {
        'schema': 'agi-alpha/connected014-source-distribution/v1',
        'files': files,
        'executing_source': {'files': files, 'sha256': release.canonical_digest(files)},
    }
    if 'mechanism_harness/cart_native.py' in files:
        manifest['omega_v4_native_source'] = {
            name: value for name, value in files.items()
            if name.startswith('mechanism_harness/')
        }
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in payloads.items():
            archive.writestr(name, raw)
        archive.writestr('SOURCE_MANIFEST.json', json.dumps(manifest))
    return manifest


def v4_payloads():
    return {
        'service.py': b'print("finite synthetic package fixture")\n',
        'mechanism_harness/cart_native.py': b'# synthetic native fixture\n',
        'mechanism_harness/cart_decision.py': b'# synthetic decision fixture\n',
        'requirements-omega-mechanisms-v3.txt': b'# synthetic fixture\n',
    }


def qualification_fixture(manifest, archive_sha256):
    from scripts import qualify_omega_release as helper
    native = manifest['omega_v4_native_source']
    receipt = {
        'schema': helper.SCHEMA, 'source_commit': COMMIT,
        'source_sha256': manifest['executing_source']['sha256'],
        'source_archive_sha256': archive_sha256,
        'native_source': native, 'native_source_sha256': helper.digest(native),
        'primary': False, 'mode': 'SEPARATE_ENGINEERING_REPRODUCTION',
        'actual_release_download': False, 'commands': [],
    }
    for key in ('accepted', 'no_git_execution', 'source_files_unchanged',
                'completed_resume_export_unchanged',
                'completed_resume_authority_unchanged', 'native_audit_accepted'):
        receipt[key] = True
    for stage in ('source-identity', 'run', 'audit', 'resume'):
        command = ['python', '-c', helper.PROBE] if stage == 'source-identity' else [
            'python', '-m', 'mechanism_harness.cart_native', stage,
            '--arm', 'adaptive', '--stress', 'central', '--output',
            '/synthetic/separate-engineering-account']
        receipt['commands'].append({
            'stage': stage, 'command': command, 'returncode': 0,
            'stdout_sha256': 'b' * 64, 'stderr_sha256': 'c' * 64,
        })
    return receipt


class OmegaReleaseSourceClosure(unittest.TestCase):
    def test_canonical_inventory_contains_complete_native_runtime_and_pins(self):
        names = set(runner.source_paths(ROOT))
        self.assertTrue(set(source_identity()) <= names)
        self.assertIn('requirements-omega-mechanisms-v3.txt', names)
        self.assertIn('requirements-commercial010.txt', names)
        self.assertIn('mechanism_harness/__init__.py', names)
        self.assertIn('scripts/qualify_omega_release.py', names)

    def test_partial_v4_distribution_fails_instead_of_silently_omitting_files(self):
        targets = ('mechanism_harness/cart_native.py',
                   'campaign/omega-economy-v4/REPAIR_PROTOCOL.md',
                   'requirements-omega-mechanisms-v3.txt',
                   'scripts/qualify_omega_release.py')
        for missing in targets:
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for name in runner.OMEGA_V4_RELEASE_PATHS:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                with patch.object(runner, 'inherited_paths', return_value=[]):
                    complete = set(runner.source_paths(root))
                    self.assertTrue(set(runner.OMEGA_V4_RELEASE_PATHS) <= complete)
                    (root / missing).unlink()
                    with self.assertRaises(ValueError):
                        runner.source_paths(root)


class OmegaPackagedSourceBoundary(unittest.TestCase):
    def setUp(self):
        from scripts import qualify_omega_release
        self.helper = qualify_omega_release
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.archive = self.root / 'source.zip'
        payloads = v4_payloads()
        self.manifest = write_source_archive(self.archive, payloads)
        for name, raw in payloads.items():
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (self.source / 'SOURCE_MANIFEST.json').write_text(json.dumps(self.manifest))

    def tearDown(self):
        self.temporary.cleanup()

    def test_exact_extracted_bytes_are_verified_against_archive(self):
        self.assertEqual(self.helper.verify_source(self.source, self.archive), self.manifest)

    def test_changed_extracted_bytes_and_missing_members_rejected(self):
        leaf = self.source / 'service.py'
        original = leaf.read_bytes()
        leaf.write_bytes(original + b'# changed\n')
        with self.assertRaises(ValueError):
            self.helper.verify_source(self.source, self.archive)
        leaf.unlink()
        with self.assertRaises(ValueError):
            self.helper.verify_source(self.source, self.archive)

    def test_symlinked_extracted_source_rejected_even_with_matching_bytes(self):
        leaf = self.source / 'service.py'
        outside = self.root / 'same-bytes.py'
        outside.write_bytes(leaf.read_bytes())
        leaf.unlink()
        leaf.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.helper.verify_source(self.source, self.archive)

    def test_native_identity_cannot_reference_absent_archive_member(self):
        self.manifest['omega_v4_native_source']['absent.py'] = 'd' * 64
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, raw in v4_payloads().items():
                archive.writestr(name, raw)
            archive.writestr('SOURCE_MANIFEST.json', json.dumps(self.manifest))
        (self.source / 'SOURCE_MANIFEST.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'NATIVE_SOURCE_CLOSURE'):
            self.helper.verify_source(self.source, self.archive)


class OmegaAuthorityBoundary(unittest.TestCase):
    def setUp(self):
        from scripts import qualify_omega_release
        self.helper = qualify_omega_release
        self.temporary = tempfile.TemporaryDirectory()
        self.account = Path(self.temporary.name) / 'account'
        self.account.mkdir()
        for suffix in self.helper.AUTHORITY_SUFFIXES[:4]:
            (self.account / ('account.sqlite' + suffix)).write_bytes(b'synthetic authority fixture')

    def tearDown(self):
        self.temporary.cleanup()

    def test_optional_zero_delivery_sidecars_are_not_created(self):
        before = set(self.account.iterdir())
        hashes = self.helper.authority_hashes(self.account)
        self.assertIsNone(hashes['.adaptive-proofs.json'])
        self.assertIsNone(hashes['.adaptive-resolutions.json'])
        self.assertEqual(set(self.account.iterdir()), before)

    def test_missing_or_symlinked_required_authority_rejected_without_repair(self):
        for suffix in self.helper.AUTHORITY_SUFFIXES[:4]:
            with self.subTest(suffix=suffix):
                target = self.account / ('account.sqlite' + suffix)
                raw = target.read_bytes()
                target.unlink()
                with self.assertRaises(ValueError):
                    self.helper.authority_hashes(self.account)
                self.assertFalse(target.exists())
                outside = self.account.parent / 'same-bytes'
                outside.write_bytes(raw)
                target.symlink_to(outside)
                with self.assertRaises(ValueError):
                    self.helper.authority_hashes(self.account)
                target.unlink()
                target.write_bytes(raw)

    def test_existing_sidecars_bind_authority_but_derived_checkpoint_does_not(self):
        before = self.helper.authority_hashes(self.account)
        for name in ('account.sqlite', 'account.sqlite.persistence.json'):
            (self.account / name).write_bytes(b'derived checkpoint changed')
        self.assertEqual(self.helper.authority_hashes(self.account), before)
        proof = self.account / 'account.sqlite.adaptive-proofs.json'
        proof.write_bytes(b'synthetic proof')
        with_proof = self.helper.authority_hashes(self.account)
        self.assertNotEqual(with_proof, before)
        proof.write_bytes(b'changed synthetic proof')
        self.assertNotEqual(self.helper.authority_hashes(self.account), with_proof)


class OmegaReceiptBoundary(unittest.TestCase):
    def setUp(self):
        from scripts import qualify_omega_release
        self.helper = qualify_omega_release
        files = {name: sha(raw) for name, raw in v4_payloads().items()}
        self.manifest = {'executing_source': {'sha256': release.canonical_digest(files)},
                         'omega_v4_native_source': files}
        self.archive_hash = 'e' * 64
        self.receipt = qualification_fixture(self.manifest, self.archive_hash)

    def verify(self, receipt):
        return self.helper.validate_receipt(receipt, self.manifest, self.archive_hash, COMMIT)

    def test_source_bound_complete_synthetic_fixture_is_accepted(self):
        self.assertEqual(self.verify(self.receipt), self.receipt)

    def test_each_acceptance_and_source_binding_is_required(self):
        changes = {
            'source_commit': 'f' * 40, 'source_sha256': 'f' * 64,
            'source_archive_sha256': 'f' * 64, 'native_source': {},
            'native_source_sha256': 'f' * 64, 'primary': True,
            'mode': 'PRIMARY', 'accepted': False, 'no_git_execution': False,
            'source_files_unchanged': False, 'completed_resume_export_unchanged': False,
            'completed_resume_authority_unchanged': False, 'native_audit_accepted': False,
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                changed = copy.deepcopy(self.receipt)
                changed[key] = value
                with self.assertRaises(ValueError):
                    self.verify(changed)

    def test_resume_must_be_completed_on_identical_absolute_account(self):
        for action in ('drop', 'failed', 'missing-output', 'different-output', 'relative-output'):
            with self.subTest(action=action):
                changed = copy.deepcopy(self.receipt)
                row = changed['commands'][-1]
                if action == 'drop': changed['commands'].pop()
                elif action == 'failed': row['returncode'] = 1
                elif action == 'missing-output': row['command'].pop()
                elif action == 'different-output': row['command'][-1] = '/synthetic/another-account'
                else: row['command'][-1] = 'relative/account'
                with self.assertRaises(ValueError):
                    self.verify(changed)

    def test_actual_download_claim_needs_download_receipt_identity(self):
        self.receipt['actual_release_download'] = True
        with self.assertRaisesRegex(ValueError, 'DOWNLOAD_RECEIPT'):
            self.verify(self.receipt)
        self.receipt['download_receipt_sha256'] = 'd' * 64
        self.verify(self.receipt)


class OmegaResealedAssetBoundary(unittest.TestCase):
    def setUp(self):
        from tests.test_connected_release import ReleaseIntegrityTests
        self.fixture = ReleaseIntegrityTests('test_source_bound_assets_are_accepted')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def add_v4(self):
        assets = self.fixture.assets
        manifest = write_source_archive(assets / 'connected014-source.zip', v4_payloads())
        identity = manifest['executing_source']['sha256']
        archive_hash = release.digest(assets / 'connected014-source.zip')
        release.write(assets / 'PUBLICATION.json', {'source_sha256': identity})
        q = release.read(assets / 'QUALIFICATION.json')
        q.update(source_sha256=identity, source_archive={'sha256': archive_hash})
        release.write(assets / 'QUALIFICATION.json', q)
        self.fixture.manifest['source_sha256'] = identity
        return qualification_fixture(manifest, archive_hash)

    def seal_and_verify(self):
        release.seal(self.fixture.assets, self.fixture.manifest)
        return release.verify_assets(self.fixture.assets, COMMIT)

    def test_legacy_non_v4_release_stays_compatible(self):
        self.seal_and_verify()

    def test_v4_release_requires_executed_receipt_even_after_reseal(self):
        self.add_v4()
        with self.assertRaisesRegex(ValueError, 'V4_QUALIFICATION_REQUIRED'):
            self.seal_and_verify()

    def test_v4_complete_synthetic_receipt_and_false_evidence_after_reseal(self):
        receipt = self.add_v4()
        path = self.fixture.assets / 'OMEGA_V4_QUALIFICATION.json'
        release.write(path, receipt)
        self.seal_and_verify()
        for key in ('completed_resume_authority_unchanged', 'native_audit_accepted'):
            with self.subTest(key=key):
                forged = copy.deepcopy(receipt)
                forged[key] = False
                release.write(path, forged)
                with self.assertRaises(ValueError):
                    self.seal_and_verify()

    def test_v4_presence_requires_main_gate_even_with_no_reported_changed_paths(self):
        receipt = self.add_v4()
        release.write(self.fixture.assets / 'OMEGA_V4_QUALIFICATION.json', receipt)
        rows = {name: {
            'head_sha': COMMIT, 'event': 'push', 'head_branch': 'main',
            'conclusion': 'success', 'path': '.github/workflows/' + name,
        } for name in release.REQUIRED_WORKFLOWS}
        gate = {'source_commit': COMMIT, 'event': 'push', 'branch': 'main',
                'required_workflows': rows,
                'applicability': {'changed_paths': [], 'conservative_all_conditionals': False}}
        target = self.fixture.assets / 'RELEASE_GATE.json'
        release.write(target, gate)
        with self.assertRaisesRegex(ValueError, 'MAIN_RELEASE_GATE_REQUIRED'):
            self.seal_and_verify()
        rows['omega-economy-v4.yml'] = {
            'head_sha': COMMIT, 'event': 'push', 'head_branch': 'main',
            'conclusion': 'success', 'path': '.github/workflows/omega-economy-v4.yml',
        }
        release.write(target, gate)
        self.seal_and_verify()


class OmegaReleaseWorkflowBoundary(unittest.TestCase):
    def test_v4_changed_source_requires_its_exact_main_qualification(self):
        for path in ('mechanism_harness/cart_native.py',
                     'campaign/omega-economy-v4/PROTOCOL.md',
                     'requirements-omega-mechanisms-v3.txt',
                     'scripts/qualify_omega_release.py'):
            with self.subTest(path=path):
                self.assertIn('omega-economy-v4.yml', release.applicable_workflows([path]))

    def test_v4_main_push_and_downloaded_execution_keep_existing_permissions(self):
        workflow = (ROOT / '.github/workflows/omega-economy-v4.yml').read_text()
        self.assertRegex(workflow, r'(?m)^  push:\s*\n    branches:\s*\[main\]')
        self.assertIn('permissions:\n  contents: read', workflow)
        self.assertNotIn('contents: write', workflow)
        release_workflow = (ROOT / '.github/workflows/connected014-release.yml').read_text()
        self.assertEqual(release_workflow.count('contents: write'), 1)
        self.assertIn('qualify_omega_release.py', release_workflow)
        self.assertIn('--download-receipt', release_workflow)


if __name__ == '__main__':
    unittest.main()
