import copy
import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest import mock

from commercial.ledger import canonical, digest, strict_json
from . import postfreeze_replay
from .economics import cases, request_rows
from .postfreeze_replay import _bind_native_account, _same_construction_field
from .service import prepare_manifest
from .study import ROOT


class PostfreezeVerifierRepresentationTests(unittest.TestCase):
    def test_persisted_phase_keys_and_roles_have_equal_json_meaning(self):
        recorded = {'phases': {'provider': {'0': True}}, 'roles': ['direct', 'prepared']}
        regenerated = {'phases': {'provider': {0: True}}, 'roles': ('direct', 'prepared')}
        self.assertTrue(_same_construction_field('construction', recorded, regenerated))

    def test_changed_construction_fact_is_rejected(self):
        recorded = {'phases': {'provider': {'0': True}}}
        regenerated = {'phases': {'provider': {0: False}}}
        self.assertFalse(_same_construction_field('construction', recorded, regenerated))

    def test_omitted_construction_evidence_is_rejected(self):
        self.assertFalse(_same_construction_field('construction', {'probe': {'result': 'DONE'}}, {}))

    def test_changed_role_assignment_is_rejected(self):
        self.assertFalse(_same_construction_field('construction', {'roles': ['direct']}, {'roles': ('prepared',)}))

    def test_program_fields_do_not_gain_a_normalization_exception(self):
        self.assertFalse(_same_construction_field('program', {'0': True}, {0: True}))

    def test_probe_fields_do_not_gain_a_normalization_exception(self):
        self.assertFalse(_same_construction_field('probe_transcript', {'0': True}, {0: True}))


class NativeArmBindingTests(unittest.TestCase):
    """Use only original public records, never private account recovery state."""

    @classmethod
    def setUpClass(cls):
        evidence = Path(__file__).with_name('evidence')
        archive = evidence / 'public-evidence.tar.gz'
        metadata = strict_json((evidence / 'public-evidence.manifest.json').read_bytes())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != metadata['archive_sha256']:
            raise ValueError('ORIGINAL_PUBLIC_EVIDENCE_CHANGED')
        cls.accounts = {}
        with tarfile.open(archive) as bundle:
            economics = strict_json(bundle.extractfile('ECONOMICS.json').read())
            for declared in economics['accounts']:
                identity = declared['identity']
                record = strict_json(bundle.extractfile(f'native/{identity}/PUBLIC_ACCOUNT.json').read())
                manifest = strict_json(bundle.extractfile(f'native/{identity}/MANIFEST.json').read())
                cls.accounts[identity] = (declared, record, manifest)
        cls.requests = request_rows(cases())

    def setUp(self):
        self.seen = {'exports': set(), 'manifests': set()}

    def bind(self, target, record=None, manifest=None):
        declared, original, original_manifest = self.accounts[target]
        _bind_native_account(original if record is None else record,
                             original_manifest if manifest is None else manifest,
                             prepare_manifest(ROOT, self.requests, target),
                             declared['capital_USD'], self.seen)

    def test_all_eighteen_original_public_accounts_remain_distinct(self):
        for identity in self.accounts:
            self.bind(identity)
        self.assertEqual(len(self.seen['exports']), 18)
        self.assertEqual(len(self.seen['manifests']), 18)

    def test_lower_capital_substitution_even_with_rehashed_declarations(self):
        _, record, manifest = self.accounts['ordinary-positive-10000']
        declared = copy.deepcopy(self.accounts['ordinary-positive-100000'][0])
        declared.update(native_export_sha256=digest(record),
                        financial_microUSD=record['ledger']['summary'])
        # The old checker accepted these caller-controlled matching fields.
        self.assertEqual(declared['native_export_sha256'], digest(record))
        self.assertEqual(declared['financial_microUSD'], record['ledger']['summary'])
        with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_MANIFEST_MISMATCH'):
            self.bind(declared['identity'], record, manifest)

    def test_same_capital_arm_and_region_substitutions_are_rejected(self):
        for source in ('treatment-positive-10000', 'ordinary-weak-10000'):
            with self.subTest(source=source):
                _, record, manifest = self.accounts[source]
                with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_MANIFEST_MISMATCH'):
                    self.bind('ordinary-positive-10000', record, manifest)

    def test_native_opening_cannot_be_replaced_by_a_matching_summary(self):
        _, record, _ = self.accounts['ordinary-positive-100000']
        record = copy.deepcopy(record)
        record['ledger']['config']['opening'] = 10_000 * 1_000_000
        record['connected_journal']['opening'] = 10_000 * 1_000_000
        with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_CAPITAL_MISMATCH'):
            self.bind('ordinary-positive-100000', record)

    def test_native_working_capital_and_contract_are_bound(self):
        identity = 'ordinary-positive-10000'
        for key, value in (('working', 1), ('contract', 'another-contract')):
            record = copy.deepcopy(self.accounts[identity][1])
            record['ledger']['config'][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_CAPITAL_MISMATCH'):
                    self.bind(identity, record)

    def test_replay_rejects_substitution_after_caller_rehashes_all_declarations(self):
        # Exercise the actual replay hookup, not only the helper. Full frozen-
        # source qualification separately runs the native audit without mocks.
        archive = Path(__file__).with_name('evidence') / 'public-evidence.tar.gz'
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            with tarfile.open(archive) as bundle:
                bundle.extractall(output, filter='data')
            source, target = 'ordinary-positive-10000', 'ordinary-positive-100000'
            for name in ('PUBLIC_ACCOUNT.json', 'MANIFEST.json'):
                (output / 'native' / target / name).write_bytes(
                    (output / 'native' / source / name).read_bytes())
            economics = strict_json((output / 'ECONOMICS.json').read_bytes())
            original = next(row for row in economics['accounts'] if row['identity'] == source)
            replaced = next(row for row in economics['accounts'] if row['identity'] == target)
            for key in ('native_export_sha256', 'native_actions_sha256', 'financial_microUSD', 'action_count'):
                replaced[key] = copy.deepcopy(original[key])
            (output / 'ECONOMICS.json').write_bytes(canonical(economics))
            execution = strict_json((output / 'EXECUTION.json').read_bytes())
            execution['economics_sha256'] = digest(economics)
            (output / 'EXECUTION.json').write_bytes(canonical(execution))
            # Avoid a historical source checkout and native account creation in
            # this unit regression; all scientific and receipt checks remain real.
            with mock.patch.object(postfreeze_replay, 'verify_freeze'), \
                    mock.patch.object(postfreeze_replay, 'audit_journal', return_value={'accepted': True}), \
                    mock.patch('experiments.outlearning_20261102_906c4f4d.service.prepare_manifest',
                               side_effect=lambda root, requests, identity: prepare_manifest(ROOT, requests, identity)):
                with self.assertRaisesRegex(ValueError, 'DUPLICATE_NATIVE_ACCOUNT_EVIDENCE'):
                    postfreeze_replay.replay(output, economics['freeze_sha256'])

    def test_every_delivery_namespace_and_registered_request_is_bound(self):
        identity = 'ordinary-positive-10000'
        _, _, original = self.accounts[identity]
        variants = [copy.deepcopy(original) for _ in range(3)]
        variants[0]['jobs'][-1]['delivery_path'] = variants[0]['jobs'][-1]['delivery_path'].replace(identity, 'treatment-positive-10000')
        variants[1]['jobs'].pop()
        variants[2]['jobs'][0]['request']['case_spec']['seed'] = 'replacement'
        for manifest in variants:
            with self.subTest(manifest_sha256=digest(manifest)):
                with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_MANIFEST_MISMATCH'):
                    self.bind(identity, manifest=manifest)

    def test_native_manifest_commitments_must_match_verified_identity(self):
        identity = 'ordinary-positive-10000'
        for section in ('ledger', 'connected_journal'):
            record = copy.deepcopy(self.accounts[identity][1])
            config = record[section]['config'] if section == 'ledger' else record[section]
            config['manifest_sha256'] = '0' * 64
            with self.subTest(section=section):
                with self.assertRaisesRegex(ValueError, 'NATIVE_REGISTERED_ACCOUNT_IDENTITY_MISMATCH'):
                    self.bind(identity, record)

    def test_duplicate_export_and_rewrapped_account_are_rejected(self):
        identity = 'ordinary-positive-10000'
        self.bind(identity)
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_NATIVE_ACCOUNT_EVIDENCE'):
            self.bind(identity)
        rewrapped = copy.deepcopy(self.accounts[identity][1])
        rewrapped['signature_verification'] += ' Rewrapped public metadata.'
        self.assertNotEqual(digest(rewrapped), digest(self.accounts[identity][1]))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_NATIVE_ACCOUNT_EVIDENCE'):
            self.bind(identity, rewrapped)

    def test_identical_action_histories_in_distinct_original_accounts_are_allowed(self):
        first, second = 'no-deploy-positive-10000', 'no-deploy-weak-10000'
        self.assertEqual(self.accounts[first][1]['ledger']['actions_sha256'],
                         self.accounts[second][1]['ledger']['actions_sha256'])
        self.bind(first)
        self.bind(second)


if __name__ == '__main__':
    unittest.main()
