"""Current supplementary binding and immutable historical publication proofs."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from functools import lru_cache
from connected_enterprise.runner import identity

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / 'docs/completion015'
DELTA = ROOT / 'evidence/completion015/qualification/COMPOSED_RELEASE_DELTA.json'
SUPPLEMENT = ROOT / 'evidence/overnight022/publication-binding'
PR33_SOURCE = 'f937cb4e553812ad532d987fdbbfb6ff2f7f21f049530b2a0fce677ca1a29fe9'
PRIOR_SOURCE = '411eed021e5a80606cf8468d3bfc9f1920cc03439013c0991c37060e059ecf23'
TRANSPORT = ROOT / 'evidence/overnight022/PROOF_BUNDLE.json'


@lru_cache(maxsize=1)
def bundle_payloads(manifest_raw, archive_raw):
    from commercial.ledger import strict_json
    from flywheel.archive_v2 import MAX_BYTES, MAX_FILES
    manifest = strict_json(manifest_raw)
    if (manifest.get('schema') != 'agi-alpha/overnight022-proof-bundle/v1'
            or manifest.get('source_commit') != '328835b30b3fed52b491f33f86ad008c60c37704'
            or len(archive_raw) != manifest['bundle']['bytes'] or len(archive_raw) > MAX_BYTES
            or hashlib.sha256(archive_raw).hexdigest() != manifest['bundle']['sha256']):
        raise ValueError('PROOF_TRANSPORT_IDENTITY_MISMATCH')
    files = manifest['files']
    if len(files) != manifest['file_count'] or len(files) > MAX_FILES:
        raise ValueError('PROOF_TRANSPORT_FILE_BOUND')
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        if ([entry.filename for entry in entries] != sorted(files)
                or sum(entry.file_size for entry in entries) != manifest['uncompressed_bytes']
                or manifest['uncompressed_bytes'] > MAX_BYTES):
            raise ValueError('PROOF_TRANSPORT_MEMBER_SET_OR_BOUND')
        payloads = {}
        for entry in entries:
            name = entry.filename; path = Path(name); record = files[name]
            if (path.is_absolute() or '..' in path.parts or path.as_posix() != name
                    or not name.startswith(('campaign/overnight-022/', 'evidence/overnight022/'))
                    or entry.is_dir() or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('PROOF_TRANSPORT_MEMBER_SCOPE')
            raw = archive.read(entry)
            if (len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != record['sha256']
                    or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != record['git_blob_sha1']
                    or record['git_mode'] != '100644'):
                raise ValueError('PROOF_TRANSPORT_MEMBER_CHANGED')
            payloads[name] = raw
    return payloads


def record_bytes(path):
    path = Path(path); name = path.relative_to(ROOT).as_posix()
    if TRANSPORT.is_file():
        raw = TRANSPORT.read_bytes(); manifest = json.loads(raw)
        if name in manifest['files']:
            archive = ROOT / manifest['bundle']['path']
            if manifest['bundle']['path'] != 'evidence/overnight022/PROOF_BUNDLE.zip' or archive.is_symlink():
                raise ValueError('PROOF_TRANSPORT_PATH_REFUSED')
            return bundle_payloads(raw, archive.read_bytes())[name]
    return path.read_bytes()


def read(path):
    return json.loads(record_bytes(path))


def sha(path):
    return hashlib.sha256(record_bytes(path)).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class PublicationBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preserved=tempfile.TemporaryDirectory(prefix='operator022-publication-source-')
        cls.baseline=Path(cls.preserved.name)
        manifest=json.loads((ROOT/'historical/operator022/MANIFEST.json').read_text())
        archive=ROOT/'historical/operator022/source.zip'
        if (manifest['git_commit']!='8abfb96d4ef859e30ca344d7933ec2a2f49012c1'
                or hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['archive_sha256']
                or archive.stat().st_size!=manifest['archive_bytes']):
            raise ValueError('IMMUTABLE_OPERATOR022_SOURCE_REQUIRED')
        with zipfile.ZipFile(archive) as z:
            entries=z.infolist()
            if (len(entries)>10000 or sum(e.file_size for e in entries)>512*1024*1024
                    or len(entries)!=len(set(e.filename for e in entries))
                    or set(z.namelist())!=set(manifest['files'])):
                raise ValueError('BOUNDED_EXACT_OPERATOR022_SOURCE_REQUIRED')
            for e in entries:
                p=Path(e.filename);raw=z.read(e)
                if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(e.external_attr>>16) or hashlib.sha256(raw).hexdigest()!=manifest['files'][e.filename]:
                    raise ValueError('OPERATOR022_SOURCE_CHANGED')
                target=cls.baseline/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if identity(cls.baseline)['sha256']!=manifest['source_sha256']:
            raise ValueError('OPERATOR022_SOURCE_CLOSURE_CHANGED')

    @classmethod
    def tearDownClass(cls):
        cls.preserved.cleanup()

    def setUp(self):
        self.publication = read(PAPERS / 'PUBLICATION.json')
        self.delta = read(DELTA)
        self.binding = self.delta['operator022_publication_binding']
        self.pr33_binding = self.delta['pr30_publication_binding']
        self.pr33_publication = read(ROOT / self.binding['prior_records']['publication']['path'])
        self.pr33_delta = read(ROOT / self.binding['prior_records']['composed_release_delta']['path'])
        self.prior = read(ROOT / self.pr33_binding['prior_records']['publication']['path'])
        self.prior_delta = read(ROOT / self.pr33_binding['prior_records']['composed_release_delta']['path'])
        self.historical_proof = read(ROOT / self.binding['historical_pr33_closure_proof']['path'])
        self.current_proof = read(ROOT / self.binding['source_closure_proof']['path'])

    def test_current_publication_matches_actual_source_identity(self):
        current = identity(self.baseline)
        self.assertEqual(current['sha256'], self.publication['source_sha256'])
        self.assertEqual(current['sha256'], self.delta['release_qualification_source_sha256'])
        self.assertEqual(current['sha256'], self.binding['current_source_sha256'])
        self.assertEqual(current['files'], self.current_proof['current_files'])
        self.assertEqual(current['sha256'], canonical_sha(self.current_proof['current_files']))
        self.assertEqual(len(current['files']), self.delta['release_identity_files'])
        self.assertEqual(len(current['files']), self.binding['current_identity_files'])
        self.assertEqual(self.binding, read(SUPPLEMENT / 'BINDING_DELTA.json'))

    def test_exact_historical_prior_source_recovered_by_removing_only_added_planner(self):
        files = dict(self.historical_proof['current_files'])
        self.assertEqual(len(files), 143)
        self.assertEqual(canonical_sha(files), PR33_SOURCE)
        self.assertEqual(self.pr33_publication['source_sha256'], PR33_SOURCE)
        self.assertEqual(self.pr33_binding['current_source_sha256'], PR33_SOURCE)
        added = self.pr33_binding['added_identity_file']
        self.assertEqual(files.pop(added['path']), added['sha256'])
        self.assertEqual(canonical_sha(files), PRIOR_SOURCE)
        self.assertEqual(canonical_sha(files), self.prior['source_sha256'])
        self.assertEqual(len(files), self.prior_delta['release_identity_files'])
        self.assertEqual(len(files), 142)
        self.assertEqual(self.pr33_delta['release_identity_files'], self.prior_delta['release_identity_files'] + 1)
        self.assertEqual(self.historical_proof['added'], {added['path']: added['sha256']})
        self.assertEqual(self.historical_proof['existing_files_changed'], [])

    def test_historical_embedded_delta_and_additive_planner_map_are_preserved(self):
        self.assertEqual(self.pr33_publication['release_source_delta'], self.pr33_delta)
        self.assertEqual(self.pr33_binding, self.pr33_delta['pr30_publication_binding'])
        old = self.prior_delta['changed_or_added_identity_files']
        new = self.pr33_delta['changed_or_added_identity_files']
        self.assertEqual(set(new) - set(old), {'portfolio_scale/staged_coupling.py'})
        for path, value in old.items():
            self.assertEqual(new[path], value)
        self.assertEqual(self.pr33_delta['performance016'], self.prior_delta['performance016'])

    def test_current_delta_matches_only_declared_operator_source_changes(self):
        self.assertEqual(self.publication['release_source_delta'], self.delta)
        prior = self.historical_proof['current_files']
        current = identity(self.baseline)['files']
        changes = {path: {'before_sha256': prior.get(path), 'after_sha256': current.get(path)}
                   for path in sorted(set(prior) | set(current)) if prior.get(path) != current.get(path)}
        self.assertEqual(changes, self.binding['changed_or_added_identity_files'])
        self.assertEqual(changes, self.current_proof['changed_or_added_identity_files'])
        self.assertEqual(self.binding['removed_identity_files'], {})
        cumulative = copy.deepcopy(self.pr33_delta['changed_or_added_identity_files'])
        for path, value in changes.items():
            if path in cumulative:
                cumulative[path]['after_sha256'] = value['after_sha256']
            else:
                cumulative[path] = value
        self.assertEqual(cumulative, self.delta['changed_or_added_identity_files'])
        for path, value in cumulative.items():
            self.assertEqual(current[path], value['after_sha256'])
        self.assertEqual(self.delta['unchanged_original_identity_files'], len(current) - len(cumulative))
        self.assertEqual(self.binding['unchanged_prior_identity_files'], sum(prior.get(path) == value for path, value in current.items()))

    def test_all_prior_and_supplementary_records_remain_byte_exact(self):
        records = [*self.binding['prior_records'].values(), *self.pr33_binding['prior_records'].values(),
                   self.binding['historical_pr33_closure_proof'], self.binding['source_closure_proof'],
                   *self.binding['engineering_evidence'].values()]
        for record in records:
            path = ROOT / record['path']
            self.assertFalse(path.is_symlink())
            raw = record_bytes(path)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), record['sha256'])
            git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            self.assertEqual(git_blob, record['git_blob'])
            if 'bytes' in record:
                self.assertEqual(len(raw), record['bytes'])

    def test_historical_paper_economics_resource_failures_and_financial_sources_unchanged(self):
        allowed = {'source_sha256', 'source_binding_scope', 'release_source_delta'}
        for former in [self.prior, self.pr33_publication]:
            self.assertEqual({k: v for k, v in self.publication.items() if k not in allowed},
                             {k: v for k, v in former.items() if k not in allowed})
            for name, digest in former['files'].items():
                self.assertEqual(Path(name).name, name)
                self.assertEqual(sha(PAPERS / name), digest)
            self.assertEqual(sha(PAPERS / 'PDF_QA.json'), former['pdf_qa_sha256'])
        delta_changes = {'release_qualification_source_sha256', 'changed_or_added_identity_files',
                         'unchanged_original_identity_files', 'release_identity_files', 'source_changes',
                         'operator022_publication_binding'}
        self.assertEqual({k: v for k, v in self.delta.items() if k not in delta_changes},
                         {k: v for k, v in self.pr33_delta.items() if k not in delta_changes})
        self.assertEqual(self.delta['source_changes'][:-1], self.pr33_delta['source_changes'])
        for path in ['adaptive_enterprise/account.py', 'commercial/ledger.py', 'connected_enterprise/engine.py',
                     'connected_enterprise/finance.py', 'experiments/commerce006.py', 'vendor/alpha_claim/protected_exchange.py']:
            self.assertEqual(hashlib.sha256((self.baseline/path).read_bytes()).hexdigest(), self.historical_proof['current_files'][path])
        self.assertIn('do not retrospectively qualify', self.publication['source_binding_scope'])
        self.assertIn('does not establish that the paper exercised', self.publication['source_binding_scope'])
        self.assertIn('actual downloaded-release operation', self.publication['source_binding_scope'])

    def test_engineering_evidence_is_bound_and_failed_collector_stays_failed(self):
        evidence = self.binding['engineering_evidence']
        qualification = read(ROOT / evidence['clean_archive_qualification']['path'])
        self.assertTrue(qualification['accepted'])
        self.assertTrue(qualification['no_git_execution'])
        self.assertTrue(qualification['completed_resume_financially_unchanged'])
        self.assertEqual(qualification['source_sha256'], self.binding['current_source_sha256'])
        self.assertEqual(qualification['source_files'], identity(self.baseline)['files'])
        self.assertIn('NOT_PERFORMED', qualification['runtime']['dependency_installation'])
        proof = read(ROOT / evidence['public_registered_operator_reproduction']['path'])
        failed = read(ROOT / evidence['preserved_failed_collector']['path'])
        registered = read(SUPPLEMENT / 'REGISTERED_FROZEN.json')
        source = dict(registered['source']['files'])
        source.pop(registered['registration_path'])
        self.assertEqual(source, identity(self.baseline)['files'])
        self.assertEqual(canonical_sha(registered['source']['files']), proof['source_sha256'])
        self.assertTrue(proof['accepted'])
        self.assertTrue(proof['public_audit']['accepted'])
        self.assertEqual(proof['scope'], 'ENGINEERING_REPRODUCTION_FROM_CLEAN_SOURCE_ARCHIVE_NOT_PUBLISHED_RELEASE')
        self.assertFalse(failed['accepted'])
        self.assertEqual(proof['prior_failed_result_sha256'], sha(ROOT / evidence['preserved_failed_collector']['path']))
        failure = read(ROOT / evidence['preserved_binding_failure']['path'])
        self.assertNotEqual(failure['exit_code'], 0)
        self.assertIn('PAPER_EXECUTING_SOURCE_CHANGED', record_bytes(ROOT / evidence['preserved_binding_failure_stderr']['path']).decode())

    def test_proof_transport_preserves_exact_records_and_existing_bounds(self):
        manifest = json.loads(TRANSPORT.read_bytes())
        payloads = bundle_payloads(TRANSPORT.read_bytes(), (ROOT / manifest['bundle']['path']).read_bytes())
        self.assertEqual(len(payloads), 92)
        self.assertEqual(manifest['original_inventory_count'], 95)
        self.assertEqual(manifest['executing_source']['sha256'], identity(self.baseline)['sha256'])
        self.assertEqual(manifest['executing_source']['files'], len(identity(self.baseline)['files']))
        self.assertEqual(read(SUPPLEMENT / 'BINDING_DELTA.json'), self.binding)

    def test_corrupted_proof_transport_cannot_replace_original_records(self):
        raw = TRANSPORT.read_bytes(); manifest = json.loads(raw)
        archive = (ROOT / manifest['bundle']['path']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'PROOF_TRANSPORT_IDENTITY_MISMATCH'):
            bundle_payloads(raw, archive[:-1] + bytes([archive[-1] ^ 1]))

    def test_binding_regression_and_metadata_do_not_enter_operating_identity(self):
        files = identity(ROOT)['files']
        excluded = ['tests/test_publication_binding.py', 'docs/completion015/PUBLICATION.json',
                    'evidence/completion015/qualification/COMPOSED_RELEASE_DELTA.json']
        excluded += [r['path'] for r in self.binding['prior_records'].values()]
        excluded += [r['path'] for r in self.pr33_binding['prior_records'].values()]
        excluded += [path.relative_to(ROOT).as_posix() for path in SUPPLEMENT.rglob('*') if path.is_file()]
        for path in excluded:
            self.assertNotIn(path, files)

    def test_new_native_source_has_its_own_delta_and_executed_qualification(self):
        binding=read(ROOT/'campaign/completion-024/CURRENT_SOURCE_BINDING.json')
        current=identity(ROOT);prior=identity(self.baseline)
        self.assertEqual(binding['schema'],'agi-alpha/completion024-current-source-binding/v1')
        self.assertEqual(binding['source'],current)
        self.assertEqual(binding['historical_source_sha256'],prior['sha256'])
        changes={p:{'before_sha256':prior['files'].get(p),'after_sha256':current['files'].get(p)} for p in sorted(set(prior['files'])|set(current['files'])) if prior['files'].get(p)!=current['files'].get(p)}
        self.assertEqual(binding['changes'],changes)
        self.assertNotEqual(current['sha256'],prior['sha256'])
        qualification=read(ROOT/binding['qualification']['path'])
        self.assertEqual(sha(ROOT/binding['qualification']['path']),binding['qualification']['sha256'])
        self.assertTrue(qualification['accepted'])
        self.assertTrue(qualification['completed_resume_financially_unchanged'])
        self.assertEqual(qualification['source_sha256'],current['sha256'])
        self.assertEqual(qualification['source_files'],current['files'])
        self.assertEqual(binding['historical_claim'],'Original operator022 publication remains immutable; it does not qualify this new source or its financial changes.')


if __name__ == '__main__':
    unittest.main()
