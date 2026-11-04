"""Synthetic release-boundary fixtures. These tests do not operate a registered pilot."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from connected_enterprise import runner
from scripts import qualify_omega_release as helper, release_connected014 as release
from tests.test_connected_omega_release import COMMIT, qualification_fixture, sha, v4_payloads


class PaidReachRelease(unittest.TestCase):
    def setUp(self):
        self.payloads = v4_payloads()
        self.payloads.update({name: b'synthetic pilot fixture\n'
                              for name in (*runner.REACH_RELEASE_PATHS, *runner.LEGACY_RELEASE_PATHS)})
        files = {name: sha(raw) for name, raw in self.payloads.items()}
        cart = {name: files[name] for name in v4_payloads() if name.startswith('mechanism_harness/')}
        cart['mechanism_harness/inventor_native.py'] = files['mechanism_harness/inventor_native.py']
        self.native = {name: files[name] for name in set(cart) | set(runner.REACH_NATIVE_PATHS)}
        self.manifest = {'schema': 'agi-alpha/connected014-source-distribution/v1', 'files': files,
                         'executing_source': {'files': files, 'sha256': helper.digest(files)},
                         'omega_v4_native_source': cart, 'omega_reach_native_source': self.native}
        self.archive_sha = 'a' * 64
        self.receipt = qualification_fixture(self.manifest, self.archive_sha)
        nested = {k: self.receipt[k] for k in ('source_commit', 'source_sha256', 'source_archive_sha256',
                  'actual_release_download', 'completed_resume_export_unchanged',
                  'completed_resume_authority_unchanged', 'native_audit_accepted')}
        nested.update(schema=helper.REACH_SCHEMA, accepted=True, primary=False, arm='pilot', scenario='central',
                      native_source_sha256=helper.digest(self.native), native_export_sha256='d' * 64,
                      commands=[])
        target = '/synthetic/paid-reach/engineering-account'
        for stage, args in helper.account_actions(target, reach=True):
            nested['commands'].append({'stage': stage, 'command': ['python', *args], 'returncode': 0,
                                       'stdout_sha256': 'b' * 64, 'stderr_sha256': 'c' * 64})
        self.receipt['paid_reach'] = nested

    def verify(self, receipt):
        return helper.validate_receipt(receipt, self.manifest, self.archive_sha, COMMIT)

    def test_partial_checkout_fails_before_source_freeze(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, 'inherited_paths', return_value=[]):
            root = Path(tmp)
            for name in (*runner.OMEGA_V4_RELEASE_PATHS, *runner.REACH_RELEASE_PATHS, *runner.LEGACY_RELEASE_PATHS):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            self.assertTrue(set(runner.REACH_RELEASE_PATHS) <= set(runner.source_paths(root)))
            self.assertTrue(set(runner.LEGACY_RELEASE_PATHS) <= set(runner.source_paths(root)))
            test = root / runner.LEGACY_RESUME_TEST
            test.unlink()
            with self.assertRaisesRegex(ValueError, 'LEGACY_RESUME_RELEASE_DEPENDENCY_MISSING'):
                runner.source_paths(root)
            test.touch()
            (root/'mechanism_harness/reach_native.py').unlink()
            with self.assertRaisesRegex(ValueError, 'PAID_REACH_SOURCE_DEPENDENCY_MISSING'):
                runner.source_paths(root)

    def test_canonical_inventory_covers_every_live_resume_source_map(self):
        from mechanism_harness import cart_native, economical_native, inventor, mechanism_native, reach_native
        files = set(runner.source_paths(runner.ROOT))
        for module in (inventor, economical_native, mechanism_native, cart_native, reach_native):
            source = module.source_identity()
            with self.subTest(module=module.__name__):
                self.assertIn('mechanism_harness/inventor_native.py', source)
                self.assertTrue(files.issuperset(source))

    def test_resealed_archive_cannot_ship_partial_legacy_operators(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = b'synthetic legacy member'
            files = {runner.LEGACY_RESUME_TEST: sha(raw)}
            manifest = {'schema': 'agi-alpha/connected014-source-distribution/v1', 'files': files,
                        'executing_source': {'files': files, 'sha256': helper.digest(files)}}
            archive = Path(tmp) / 'source.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr(runner.LEGACY_RESUME_TEST, raw)
                z.writestr('SOURCE_MANIFEST.json', json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'LEGACY_RESUME_RELEASE_DEPENDENCY_MISSING'):
                release.archive_manifest(archive)

    def test_resealed_archive_cannot_remove_parent_v4_or_independent_checker(self):
        for missing in ('mechanism_harness/cart_native.py', 'mechanism_harness/reach_verify.py',
                        'mechanism_harness/inventor_native.py', runner.LEGACY_RESUME_TEST):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                manifest = copy.deepcopy(self.manifest)
                del manifest['files'][missing]
                manifest['omega_v4_native_source'].pop(missing, None)
                manifest['omega_reach_native_source'].pop(missing, None)
                manifest['executing_source']['sha256'] = helper.digest(manifest['files'])
                archive = Path(tmp)/'source.zip'
                with zipfile.ZipFile(archive, 'w') as z:
                    for name in manifest['files']:
                        z.writestr(name, self.payloads[name])
                    z.writestr('SOURCE_MANIFEST.json', json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'PAID_REACH'):
                    release.archive_manifest(archive)

    def test_pilot_only_document_test_or_summary_cannot_downgrade_to_legacy(self):
        for name in sorted(runner.REACH_MARKERS):
            with self.subTest(orphan=name):
                with self.assertRaisesRegex(ValueError, 'PAID_REACH'):
                    helper.reach_source({'files': {name: '0' * 64}})
        self.assertIsNone(helper.reach_source({'files': {'connected_enterprise/channels.py': '0' * 64}}))

    def test_nested_receipt_is_required_only_for_pilot_archives(self):
        self.assertIs(self.verify(self.receipt), self.receipt)
        old = copy.deepcopy(self.receipt)
        del old['paid_reach']
        with self.assertRaisesRegex(ValueError, 'PAID_REACH'):
            self.verify(old)
        self.manifest.pop('omega_reach_native_source')
        for name in runner.REACH_RELEASE_PATHS:
            self.manifest['files'].pop(name)
        self.assertIs(self.verify(old), old)
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_PAID_REACH'):
            self.verify(self.receipt)

    def test_nested_source_evidence_approval_and_public_fields_are_bound(self):
        for key, value in [('source_commit', 'c' * 40), ('source_archive_sha256', 'b' * 64),
                           ('source_sha256', 'c' * 64), ('native_source_sha256', 'e' * 64),
                           ('native_audit_accepted', False), ('completed_resume_authority_unchanged', False),
                           ('completed_resume_export_unchanged', False), ('primary', True),
                           ('scenario', 'weak'), ('arm', 'organic'), ('actual_release_download', True),
                           ('orders', []), ('native_export_sha256', 'invalid')]:
            with self.subTest(key=key):
                altered = copy.deepcopy(self.receipt)
                altered['paid_reach'][key] = value
                with self.assertRaises(ValueError):
                    self.verify(altered)

    def test_inherited_cart_and_reach_cannot_claim_different_bytes_for_one_file(self):
        self.manifest['omega_v4_native_source']['mechanism_harness/cart_native.py'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'PAID_REACH_EXACT_NATIVE_SOURCE_CLOSURE'):
            helper.reach_source(self.manifest)

    def test_nested_run_audit_resume_must_share_the_distinct_engineering_account(self):
        for kind in ('another-account', 'same-cart-account', 'wrong-arm', 'failed-audit', 'raw-log',
                     'unknown-interpreter', 'missing-resume'):
            with self.subTest(kind=kind):
                altered = copy.deepcopy(self.receipt)
                rows = altered['paid_reach']['commands']
                if kind == 'another-account':
                    rows[2]['command'][4] = '/different/account'
                elif kind == 'same-cart-account':
                    for row in rows[1:]:
                        row['command'][4] = altered['commands'][1]['command'][-1]
                elif kind == 'wrong-arm':
                    rows[1]['command'][6] = 'organic'
                elif kind == 'failed-audit':
                    rows[2]['returncode'] = 1
                elif kind == 'raw-log':
                    rows[2]['raw_stdout'] = 'synthetic private payload'
                elif kind == 'unknown-interpreter':
                    rows[2]['command'][0] = {'private': 'synthetic'}
                else:
                    rows.pop()
                with self.assertRaises(ValueError):
                    self.verify(altered)

    def test_nested_download_hash_must_equal_the_parent_receipt_hash(self):
        # Deliberately inconsistent synthetic claims exercise only rejection.
        altered = copy.deepcopy(self.receipt)
        altered.update(actual_release_download=True, download_receipt_sha256='e' * 64)
        altered['paid_reach'].update(actual_release_download=True, download_receipt_sha256='f' * 64)
        with self.assertRaises(ValueError):
            self.verify(altered)

    def test_engineering_replay_observes_audit_and_checks_actual_authority_bytes(self):
        for fault in ('none', 'audit', 'authority', 'export'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                logs = Path(tmp)
                account = logs/'engineering-account'
                invocation = []

                def execute(command, cwd, log, deadline, commands):
                    stage = 'source-identity' if command[1] == '-c' else command[3]
                    invocation.append(stage)
                    stdout = {'accepted': fault != 'audit'}
                    if stage == 'source-identity':
                        stdout = self.native
                    elif stage == 'run':
                        account.mkdir()
                        helper.write(account/'SOURCE.json', self.native)
                        helper.write(account/'CONTRACT.json', {'arm': 'pilot', 'scenario': 'central',
                                     'source_sha256': helper.digest(self.native)})
                        (account/'NATIVE_EXPORT.json').write_bytes(b'{}\n')
                        for suffix in helper.AUTHORITY_SUFFIXES[:4]:
                            (account/('account.sqlite'+suffix)).write_bytes(b'synthetic authority bytes')
                    elif stage == 'resume' and fault in ('authority', 'export'):
                        name = 'account.sqlite.actions.jsonl' if fault == 'authority' else 'NATIVE_EXPORT.json'
                        (account/name).write_bytes(b'changed synthetic bytes')
                    helper.write(log.with_suffix('.stdout'), stdout)
                    log.with_suffix('.stderr').write_bytes(b'')
                    record = {'command': command, 'returncode': 0, 'extra_private_data': 'keep local'}
                    commands.append(record)
                    return record

                receipt = {'commands': []}
                with patch.object(helper, 'run_command', side_effect=execute):
                    if fault == 'none':
                        helper.exercise_account(logs, logs, account, self.native, None, receipt, reach=True)
                        self.assertEqual(invocation, ['source-identity', 'run', 'audit', 'resume'])
                        self.assertIs(receipt['native_audit_accepted'], True)
                        self.assertIs(receipt['completed_resume_authority_unchanged'], True)
                        self.assertNotIn('extra_private_data', receipt['commands'][0])
                    else:
                        with self.assertRaises(ValueError):
                            helper.exercise_account(logs, logs, account, self.native, None, receipt, reach=True)


if __name__ == '__main__':
    unittest.main()
