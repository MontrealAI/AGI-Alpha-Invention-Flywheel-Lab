import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch
import zipfile

PATH = Path(__file__).resolve().parents[1]/'scripts/release_connected014.py'
SPEC = importlib.util.spec_from_file_location('release014', PATH)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
COMMIT = 'a'*40

class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.assets = self.root/'assets'
        self.assets.mkdir()
        source = b'print("auditable simulated work")\n'
        files = {'service.py':hashlib.sha256(source).hexdigest()}
        identity = {'files':files, 'sha256':hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}
        self.source_manifest = {'schema':'agi-alpha/connected014-source-distribution/v1', 'files':files, 'executing_source':identity}
        with zipfile.ZipFile(self.assets/'connected014-source.zip', 'w') as archive:
            archive.writestr('service.py', source)
            archive.writestr('SOURCE_MANIFEST.json', json.dumps(self.source_manifest))
        (self.assets/'connected014-keyfree.zip').write_bytes(b'public key-free artifact')
        for name in ('RELEASE_NOTES.md', *release.PAPERS):
            (self.assets/name).write_text('Test fixture only; not a publication.')
        release.write(self.assets/'PUBLICATION.json', {'source_sha256':identity['sha256']})
        release.write(self.assets/'QUALIFICATION.json', {'accepted':True, 'source_sha256':identity['sha256'],
            'source_archive':{'sha256':release.digest(self.assets/'connected014-source.zip')},
            'public_archive':{'sha256':release.digest(self.assets/'connected014-keyfree.zip')}})
        self.manifest = {'schema':'agi-alpha/connected014-release/v1', 'source_commit':COMMIT,
            'source_sha256':identity['sha256'], 'tag':release.tag(COMMIT)}
        release.seal(self.assets, self.manifest)

    def tearDown(self):
        self.temporary.cleanup()

    def test_source_bound_assets_are_accepted(self):
        self.assertEqual(release.verify_assets(self.assets, COMMIT)['source_commit'], COMMIT)

    def test_resealed_source_mismatch_requires_explicit_composed_wrapper(self):
        release.write(self.assets/'PUBLICATION.json', {'source_sha256':'e'*64})
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'COMPOSED_PUBLICATION_REQUIRED'):
            release.verify_assets(self.assets, COMMIT)

    def composed_asset_fixture(self):
        # Synthetic checksummed assets, not actual clean operation or financial evidence.
        root = PATH.parents[1]
        from tests.test_publication_composition import registration
        binding = registration()
        current = self.source_manifest['executing_source']['files']
        prior = binding['historical_files']
        binding.update(current_files=current, current_source_sha256=release.canonical_digest(current),
            source_delta={p:{'before_sha256':prior.get(p),'after_sha256':current.get(p)}
                          for p in sorted(set(prior)|set(current)) if prior.get(p)!=current.get(p)})
        import shutil
        for name in release.PAPERS:
            shutil.copyfile(root/'docs/completion015'/name,self.assets/name)
        shutil.copyfile(root/'historical/operator022/source.zip',self.assets/'HISTORICAL_8AB_SOURCE.zip')
        q=release.read(self.assets/'QUALIFICATION.json')
        q.update(no_git_execution=True,completed_resume_financially_unchanged=True,source_files=current)
        q.update(schema='agi-alpha/connected014-clean-qualification/v1',
            commands=[{'command':['python','-m','connected_enterprise',a], 'returncode':0,
                       'stdout':str(i)+'.stdout','stderr':str(i)+'.stderr'}
                      for i,a in enumerate(['run','resume','audit','package','audit'])],
            logs={str(i)+'.'+stream:'d'*64 for i in range(5) for stream in ['stdout','stderr']},
            native_and_operating_audit={'accepted':True,'source_sha256':release.canonical_digest(current)},
            keyfree_public_audit={'accepted':True,'source_sha256':release.canonical_digest(current)})
        release.write(self.assets/'QUALIFICATION.json',q)
        binding.update(qualification_sha256=release.digest(self.assets/'QUALIFICATION.json'),
                       source_archive_sha256=q['source_archive']['sha256'],public_archive_sha256=q['public_archive']['sha256'])
        release.write(self.assets/'COMPOSED_PUBLICATION.json',binding)
        release.seal(self.assets,self.manifest)

    def test_composed_actual_asset_verifier_accepts_bound_synthetic_fixture(self):
        self.composed_asset_fixture()
        release.verify_assets(self.assets,COMMIT)

    def test_composed_historical_pdf_tamper_fails_even_after_outer_reseal(self):
        self.composed_asset_fixture()
        (self.assets/'PAPER.pdf').write_bytes(b'forged economics')
        release.seal(self.assets,self.manifest)
        with self.assertRaisesRegex(ValueError,'HISTORICAL_PAPER_ASSET_CHANGED'):
            release.verify_assets(self.assets,COMMIT)

    def test_composed_qualification_tamper_fails_even_after_outer_reseal(self):
        self.composed_asset_fixture()
        q=release.read(self.assets/'QUALIFICATION.json');q['completed_resume_financially_unchanged']=False
        release.write(self.assets/'QUALIFICATION.json',q);release.seal(self.assets,self.manifest)
        with self.assertRaisesRegex(ValueError,'ACTUAL_QUALIFICATION'):
            release.verify_assets(self.assets,COMMIT)

    def test_composed_wrapper_cannot_be_dropped_after_outer_reseal(self):
        self.composed_asset_fixture()
        (self.assets/'COMPOSED_PUBLICATION.json').unlink();release.seal(self.assets,self.manifest)
        with self.assertRaisesRegex(ValueError,'COMPOSED_PUBLICATION_REQUIRED'):
            release.verify_assets(self.assets,COMMIT)

    def test_wrong_commit_or_tag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_OR_TAG'):
            release.verify_assets(self.assets, 'b'*40)
        self.manifest['tag'] = 'unqualified-branch'
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'SOURCE_OR_TAG'):
            release.verify_assets(self.assets, COMMIT)

    def test_replaced_source_member_rejected_even_after_outer_reseal(self):
        with zipfile.ZipFile(self.assets/'connected014-source.zip', 'w') as archive:
            archive.writestr('service.py', b'forged accepted work')
            archive.writestr('SOURCE_MANIFEST.json', json.dumps(self.source_manifest))
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'SOURCE_MEMBER_HASH'):
            release.verify_assets(self.assets, COMMIT)

    def test_extra_archive_member_cannot_escape_source_closure(self):
        with zipfile.ZipFile(self.assets/'connected014-source.zip', 'a') as archive:
            archive.writestr('unregistered_service.py', 'grant free money')
        with self.assertRaisesRegex(ValueError, 'MANIFEST_REQUIRED'):
            release.archive_manifest(self.assets/'connected014-source.zip')

    def test_zip_traversal_symlink_and_private_state_are_refused(self):
        for name, mode in [('../escape',0o100644), ('secret.adaptive-simulation-key',0o100644), ('account.sqlite.actions.jsonl',0o100644), ('source/link',0o120777)]:
            archive_path = self.root/'unsafe.zip'
            with zipfile.ZipFile(archive_path, 'w') as archive:
                item = zipfile.ZipInfo(name)
                item.external_attr = mode << 16
                archive.writestr(item, 'private or hostile')
            with self.assertRaisesRegex(ValueError, 'UNSAFE_OR_PRIVATE'):
                release.archive_manifest(archive_path)

    def test_duplicate_source_members_are_refused(self):
        archive_path = self.root/'duplicates.zip'
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('same.py', 'first')
                archive.writestr('same.py', 'second')
        with self.assertRaisesRegex(ValueError, 'UNIQUE_BOUNDED'):
            release.archive_manifest(archive_path)

    def test_asset_tamper_extra_asset_and_changed_checksums_fail(self):
        path = self.assets/'connected014-keyfree.zip'
        path.write_bytes(b'replaced artifact')
        with self.assertRaisesRegex(ValueError, 'ASSET_HASH'):
            release.verify_assets(self.assets, COMMIT)
        release.seal(self.assets, self.manifest)
        (self.assets/'unexpected.txt').write_text('unregistered')
        with self.assertRaisesRegex(ValueError, 'ASSET_SET'):
            release.verify_assets(self.assets, COMMIT)
        (self.assets/'unexpected.txt').unlink()
        (self.assets/'SHA256SUMS.txt').write_text('partial checksum')
        with self.assertRaisesRegex(ValueError, 'CHECKSUM_SET'):
            release.verify_assets(self.assets, COMMIT)

    def test_positive_qualification_flag_cannot_hide_rebound_archive(self):
        path = self.assets/'QUALIFICATION.json'
        receipt = release.read(path)
        receipt['public_archive']['sha256'] = '0'*64
        release.write(path, receipt)
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'ARCHIVE_BINDING'):
            release.verify_assets(self.assets, COMMIT)

    def test_dirty_or_wrong_checkout_cannot_prepare_release(self):
        with patch.object(release.subprocess, 'check_output', return_value='b'*40+'\n'):
            with self.assertRaisesRegex(ValueError, 'CLEAN_EXACT'):
                release.prepare(self.root, self.root/'prepared', COMMIT, self.root)

    def test_tag_requires_full_commit(self):
        for value in ['main', 'a'*12, 'G'*40, COMMIT+'\n']:
            with self.assertRaisesRegex(ValueError, 'FULL_SOURCE'):
                release.tag(value)

    def test_missing_research_asset_fails_after_reseal(self):
        (self.assets/'PAPER.pdf').unlink()
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'COMPLETE_RELEASE_ASSET'):
            release.verify_assets(self.assets, COMMIT)

    def test_resealed_foreign_gate_cannot_qualify_download(self):
        release.write(self.assets/'RELEASE_GATE.json', {'source_commit':'b'*40, 'event':'push', 'branch':'main', 'required_workflows':{}})
        release.seal(self.assets, self.manifest)
        with self.assertRaisesRegex(ValueError, 'MAIN_RELEASE_GATE'):
            release.verify_assets(self.assets, COMMIT)

    def test_moved_main_and_wrong_existing_tag_never_create_release(self):
        gate = {name:{'head_sha':COMMIT} for name in release.REQUIRED_WORKFLOWS}
        applicability = {'changed_paths':['connected_enterprise/finance.py'], 'base_commit':'c'*40, 'conservative_all_conditionals':False}
        with patch.object(release, 'qualifying_runs', return_value=gate), patch.object(release, 'push_applicability', return_value=applicability), patch.object(release.subprocess, 'run') as command:
            def moved(endpoint, optional=False):
                if '/actions/' in endpoint:
                    return {'workflow_runs':[]}
                return {'object':{'sha':'b'*40, 'type':'commit'}}
            with patch.object(release, 'gh', side_effect=moved):
                with self.assertRaisesRegex(ValueError, 'MAIN_MOVED'):
                    release.publish(self.assets, COMMIT, 'owner/repo', 7, 1)
            command.assert_not_called()
            def wrong_tag(endpoint, optional=False):
                if '/actions/' in endpoint:
                    return {'workflow_runs':[]}
                if '/heads/main' in endpoint:
                    return {'object':{'sha':COMMIT, 'type':'commit'}}
                if '/git/ref/tags/' in endpoint:
                    return {'object':{'sha':'b'*40, 'type':'commit'}}
                return None
            with patch.object(release, 'gh', side_effect=wrong_tag):
                with self.assertRaisesRegex(ValueError, 'TAG_SOURCE'):
                    release.publish(self.assets, COMMIT, 'owner/repo', 7, 1)
            command.assert_not_called()

    def test_download_rejects_retargeted_tag_before_fetching_assets(self):
        responses = [{'object':{'sha':'b'*40, 'type':'commit'}}, {'tag_name':release.tag(COMMIT)}]
        with patch.object(release, 'gh', side_effect=responses), patch.object(release.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'TAG_SOURCE_CHANGED'):
                release.download(self.root/'download', self.root/'DOWNLOAD.json', COMMIT, 'owner/repo')
            command.assert_not_called()

    def test_local_operation_failure_never_claims_actual_release_download(self):
        import scripts.qualify_connected014 as qualifier
        with patch.object(qualifier, 'run_command', side_effect=TimeoutError('bounded test interruption')):
            with self.assertRaisesRegex(TimeoutError, 'interruption'):
                release.operate_download(self.assets, self.root/'operation-check', COMMIT, 1)
        receipt = release.read(self.root/'operation-check/DOWNLOADED_RELEASE_RUN.json')
        self.assertFalse(receipt['accepted'])
        self.assertFalse(receipt['actual_release_download'])

    def operation_command_fixture(self, private=False):
        def execute(arguments, cwd, log, deadline, commands):
            kind = arguments[3]
            target = Path(arguments[arguments.index('--output')+1])
            target.mkdir(parents=True, exist_ok=True)
            if kind == 'run':
                release.write(target/'FROZEN.json', {'source':{'sha256':self.manifest['source_sha256']}})
                release.write(target/'REPORT.json', {'fixture':'artifact transport test only'})
            elif kind == 'audit':
                release.write(target/'PACKAGE_AUDIT.json', {'accepted':True, 'source_sha256':self.manifest['source_sha256']})
            elif kind == 'package':
                path = Path(arguments[arguments.index('--archive')+1])
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('account.sqlite.adaptive-simulation-key' if private else 'source/service.py', b'fixture')
            commands.append({'command':arguments, 'returncode':0})
        return execute

    def test_private_candidate_is_never_promoted_to_uploadable_operation_archive(self):
        import scripts.qualify_connected014 as qualifier
        output = self.root/'private-artifact-check'
        with patch.object(qualifier, 'run_command', side_effect=self.operation_command_fixture(private=True)), patch.object(qualifier, 'native_state', return_value={'account':'unchanged'}):
            with self.assertRaisesRegex(ValueError, 'UNSAFE_OR_PRIVATE'):
                release.operate_download(self.assets, output, COMMIT, 10)
        self.assertFalse((output/'downloaded-operation-keyfree.zip').exists())
        self.assertFalse(release.read(output/'DOWNLOADED_RELEASE_RUN.json')['accepted'])

    def test_actual_operation_archive_hash_and_public_audit_are_retained(self):
        import scripts.qualify_connected014 as qualifier
        with zipfile.ZipFile(self.assets/'connected014-keyfree.zip', 'w') as archive:
            archive.writestr('source/service.py', b'released evidence fixture')
        qualification = release.read(self.assets/'QUALIFICATION.json')
        qualification['public_archive']['sha256'] = release.digest(self.assets/'connected014-keyfree.zip')
        release.write(self.assets/'QUALIFICATION.json', qualification)
        release.seal(self.assets, self.manifest)
        output = self.root/'public-artifact-check'
        with patch.object(qualifier, 'run_command', side_effect=self.operation_command_fixture()), patch.object(qualifier, 'native_state', return_value={'account':'unchanged'}):
            receipt = release.operate_download(self.assets, output, COMMIT, 10)
        archive = output/'downloaded-operation-keyfree.zip'
        self.assertTrue(receipt['accepted'])
        self.assertEqual(receipt['downloaded_operation_package']['sha256'], release.digest(archive))
        self.assertEqual(receipt['downloaded_operation_package']['bytes'], archive.stat().st_size)
        self.assertTrue(receipt['downloaded_operation_public_audit']['accepted'])
        self.assertEqual(len(receipt['commands']), 6)
        with zipfile.ZipFile(archive) as source:
            release.checked_members(source)

    def test_child_cpu_over_envelope_retains_failure_before_further_work(self):
        import scripts.qualify_connected014 as qualifier
        zero = {key:0. for key in ('self_user','self_system','children_user','children_system')}
        over = {**zero, 'children_user':2400.5}
        output = self.root/'cpu-envelope-check'
        with patch.object(release, 'cpu_usage', side_effect=[zero, zero, over, over]), patch.object(qualifier, 'run_command') as command:
            with self.assertRaisesRegex(TimeoutError, 'CPU_ENVELOPE_EXCEEDED'):
                release.operate_download(self.assets, output, COMMIT, 10)
        receipt = release.read(output/'DOWNLOADED_RELEASE_RUN.json')
        self.assertFalse(receipt['accepted'])
        self.assertTrue(receipt['resources']['cpu_envelope_exceeded'])
        self.assertEqual(receipt['resources']['total_measured_cpu_seconds'], 2400.5)
        self.assertEqual(command.call_count, 1)

    def checkpoint_fixture(self, parent):
        operation = parent/'operation'
        operation.mkdir(parents=True)
        source = operation/'source'
        source.mkdir()
        (source/'service.py').write_bytes(b'print("auditable simulated work")\n')
        identity = self.source_manifest['executing_source']
        frozen = {'source':identity, 'sha256':'f'*64, 'protocol':{'central_seeds':[17],
            'adverse_seeds':[], 'channel_control_seeds':[], 'cases':['central'], 'arms':['growth']}}
        release.write(operation/'FROZEN.json', frozen)
        job = {'id':'job-1', 'service_id':'reconciliation', 'accepted':True, 'work_keys':['job-1']}
        for field, filename in [('input','input.json'), ('artifact','artifact.json'), ('receipt','acceptance.json')]:
            relative = 'service-inputs/job-1/'+filename
            path = source/relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'fixture':field}))
            job[field], job[field+'_sha256'] = relative, release.digest(path)
        release.write(operation/'SERVICES.json', {'source_hashes':{}, 'jobs':[job]})
        world = operation/'worlds/17-central-growth'; world.mkdir(parents=True)
        release.write(world/'RESULT.json', {'fixture':'unqualified result bytes only'})
        release.write(world/'STATE.json', {'fixture':'synthetic queued intent', 'signature':'public HMAC witness'})
        (world/'account.sqlite.adaptive-simulation-key').write_text('DO NOT PUBLISH')
        (world/'account.sqlite').write_text('DO NOT PUBLISH')
        (source/'extra.env').write_text('DO NOT PUBLISH')
        return operation, frozen

    def checkpoint_guards(self, frozen):
        # Transport fixtures mock metadata rederivation only; no business/audit runs.
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch('connected_enterprise.runner.read_freeze', return_value=frozen))
        stack.enter_context(patch('adaptive_enterprise.instruments._validate_manifest'))
        return stack

    def test_failure_checkpoint_preserves_only_bound_public_records(self):
        output = self.root/'failure-preservation'; operation, frozen = self.checkpoint_fixture(output)
        unknown = operation/'worlds/unregistered'; unknown.mkdir()
        (unknown/'RESULT.json').write_text('DO NOT PUBLISH')
        with self.checkpoint_guards(frozen):
            receipt = release.failure_checkpoint(operation, output, COMMIT, self.manifest['source_sha256'])
        archive = output/receipt['path']
        self.assertEqual(receipt['sha256'], release.digest(archive))
        self.assertEqual(receipt['scope'], 'UNQUALIFIED_FAILURE_CHECKPOINT_NOT_RESUME_AUTHORITY')
        with zipfile.ZipFile(archive) as zipped:
            names = release.checked_members(zipped)
            self.assertIn('worlds/17-central-growth/RESULT.json', names)
            self.assertIn('worlds/17-central-growth/STATE.json', names)
            self.assertIn('source/service-inputs/job-1/input.json', names)
            self.assertFalse(any('.sqlite' in name or name.endswith('.env') or 'unregistered' in name for name in names))
            metadata = json.loads(zipped.read('FAILURE_CHECKPOINT.json'))
            self.assertIn('REPORT.json', metadata['missing_optional_files'])
            for name, binding in metadata['files'].items():
                raw = zipped.read(name)
                self.assertEqual(len(raw), binding['bytes'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), binding['sha256'])

    def test_failure_manifest_cannot_promote_arbitrary_private_path(self):
        output = self.root/'private-path'; operation, frozen = self.checkpoint_fixture(output)
        services = release.read(operation/'SERVICES.json')
        services['jobs'][0].update(input='extra.env', input_sha256=release.digest(operation/'source/extra.env'))
        release.write(operation/'SERVICES.json', services)
        with self.checkpoint_guards(frozen), self.assertRaisesRegex(ValueError, 'CANONICAL_FAILURE_SERVICE_PATH'):
            release.failure_checkpoint(operation, output, COMMIT, self.manifest['source_sha256'])
        self.assertFalse((output/'failed-operation-keyfree.zip').exists())

    def test_failure_capture_rejects_symlink_hardlink_and_changed_bound_bytes(self):
        import os
        for kind in ['symlink', 'hardlink', 'changed']:
            with self.subTest(kind=kind):
                output = self.root/kind; operation, frozen = self.checkpoint_fixture(output)
                target = operation/'source/service-inputs/job-1/input.json'
                if kind == 'changed':
                    target.write_text('changed bytes')
                else:
                    original = operation/'original.json'; original.write_bytes(target.read_bytes()); target.unlink()
                    target.symlink_to(original) if kind == 'symlink' else os.link(original, target)
                with self.checkpoint_guards(frozen), self.assertRaises(ValueError):
                    release.failure_checkpoint(operation, output, COMMIT, self.manifest['source_sha256'])
                self.assertFalse((output/'failed-operation-keyfree.zip').exists())

    def test_cpu_failure_preserves_checkpoint_and_accounts_cleanup_without_more_commands(self):
        import scripts.qualify_connected014 as qualifier
        output = self.root/'actual-failure-fixture'
        zero = {key:0. for key in ('self_user','self_system','children_user','children_system')}
        over = {**zero, 'children_user':2400.5}; cleanup = {**over, 'self_user':0.25}
        frozen = {'value':None}
        def execute(*args):
            _, frozen['value'] = self.checkpoint_fixture(output)
        def metadata(_):return frozen['value']
        with patch('connected_enterprise.runner.read_freeze', side_effect=metadata), patch('adaptive_enterprise.instruments._validate_manifest'), patch.object(release, 'cpu_usage', side_effect=[zero, zero, over, cleanup]), patch.object(qualifier, 'run_command', side_effect=execute) as command:
            with self.assertRaisesRegex(TimeoutError, 'CPU_ENVELOPE_EXCEEDED'):
                release.operate_download(self.assets, output, COMMIT, 10)
        receipt = release.read(output/'DOWNLOADED_RELEASE_RUN.json')
        self.assertFalse(receipt['accepted'])
        self.assertEqual(command.call_count, 1)
        self.assertEqual(receipt['failure']['message'], 'DOWNLOADED_OPERATION_CPU_ENVELOPE_EXCEEDED')
        self.assertEqual(receipt['resources']['total_measured_cpu_seconds'], 2400.75)
        self.assertTrue((output/receipt['failure_checkpoint']['path']).exists())
        self.assertFalse((output/'downloaded-operation-keyfree.zip').exists())

    def test_checkpoint_error_never_masks_original_failure(self):
        import scripts.qualify_connected014 as qualifier
        output = self.root/'checkpoint-error'
        with patch.object(qualifier, 'run_command', side_effect=TimeoutError('original boundary')), patch.object(release, 'failure_checkpoint', side_effect=ValueError('privacy refusal')):
            with self.assertRaisesRegex(TimeoutError, 'original boundary'):
                release.operate_download(self.assets, output, COMMIT, 10)
        receipt = release.read(output/'DOWNLOADED_RELEASE_RUN.json')
        self.assertFalse(receipt['accepted'])
        self.assertEqual(receipt['failure']['message'], 'original boundary')
        self.assertEqual(receipt['checkpoint_failure']['message'], 'privacy refusal')

class KernelCpuTests(unittest.TestCase):
    def test_deltas_count_self_and_waited_children_without_prior_usage(self):
        before = {'self_user':10.,'self_system':3.,'children_user':100.,'children_system':7.}
        after = {'self_user':12.,'self_system':4.,'children_user':150.,'children_system':11.}
        measured = release.cpu_delta(before, after)
        self.assertEqual(measured['self_cpu_seconds'], 3.)
        self.assertEqual(measured['children_cpu_seconds'], 54.)
        self.assertEqual(measured['total_measured_cpu_seconds'], 57.)
        with self.assertRaisesRegex(ValueError, 'MONOTONIC_KERNEL'):
            release.cpu_delta(after, before)

class WorkflowGateTests(unittest.TestCase):
    def row(self, **changes):
        value = {'id':1, 'run_number':1, 'run_attempt':1, 'head_sha':COMMIT,
            'event':'push', 'head_branch':'main', 'path':'.github/workflows/campaign.yml',
            'status':'completed', 'conclusion':'success', 'html_url':'https://github.com/r/actions/runs/1'}
        return {**value, **changes}

    def test_foreign_head_branch_event_or_workflow_cannot_satisfy_gate(self):
        for changes in [{'head_sha':'b'*40}, {'head_branch':'feature'}, {'event':'pull_request'}, {'path':'.github/workflows/other.yml'}]:
            self.assertEqual(release.qualifying_runs({'campaign.yml':[self.row(**changes)]}, COMMIT), {})

    def test_latest_attempt_must_pass_even_after_earlier_success(self):
        with self.assertRaisesRegex(ValueError, 'QUALIFICATION_FAILED'):
            release.qualifying_runs({'campaign.yml':[self.row(), self.row(run_attempt=2, conclusion='failure')]}, COMMIT)
        self.assertEqual(release.qualifying_runs({'campaign.yml':[self.row(), self.row(run_attempt=2, status='in_progress', conclusion=None)]}, COMMIT), {})

    def test_cancelled_and_skipped_runs_never_qualify(self):
        for conclusion in ['cancelled', 'skipped', 'failure']:
            with self.assertRaisesRegex(ValueError, 'QUALIFICATION_FAILED'):
                release.qualifying_runs({'campaign.yml':[self.row(conclusion=conclusion)]}, COMMIT)

    def test_successful_exact_main_push_is_source_bound(self):
        accepted = release.qualifying_runs({'campaign.yml':[self.row()]}, COMMIT)
        self.assertEqual(accepted['campaign.yml']['head_sha'], COMMIT)

    def test_main_commercial_qualification_is_mandatory_dispatch_only_paths_are_not(self):
        required = release.applicable_workflows(['connected_enterprise/finance.py'])
        self.assertIn('commercial010.yml', required)
        self.assertNotIn('enterprise011.yml', required)
        self.assertNotIn('connected014.yml', required)
        self.assertNotIn('measurement009.yml', required)

    def test_conditional_measurement_and_every_observed_extra_workflow_are_gated(self):
        required = release.applicable_workflows(['docs/next009/PAPER.pdf'], ['extra-security.yml', release.OWN_WORKFLOW])
        self.assertIn('measurement009.yml', required)
        self.assertIn('extra-security.yml', required)
        self.assertNotIn(release.OWN_WORKFLOW, required)
        self.assertIn('measurement009.yml', release.applicable_workflows([], conservative=True))

    def test_push_comparison_uses_full_event_range_and_exact_trees_after_path_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory)/'event.json'
            release.write(event, {'before':'c'*40, 'after':COMMIT})
            responses = [{'files':[{'filename':str(i)} for i in range(300)]},
                         {'truncated':False, 'tree':[{'path':'service.py','type':'blob','sha':'0'*40}]},
                         {'truncated':False, 'tree':[{'path':'service.py','type':'blob','sha':'0'*40}, {'path':'docs/next009/PAPER.pdf','type':'blob','sha':'1'*40}]}]
            with patch.dict(release.os.environ, {'GITHUB_EVENT_PATH':str(event)}), patch.object(release, 'gh', side_effect=responses) as api:
                result = release.push_applicability('owner/repo', COMMIT)
                self.assertIn('c'*40+'...'+COMMIT, api.call_args_list[0].args[0])
                self.assertFalse(result['conservative_all_conditionals'])
                self.assertEqual(result['changed_paths'], ['docs/next009/PAPER.pdf'])
                self.assertIn('EXACT_RECURSIVE', result['comparison_method'])

    def test_truncated_tree_cannot_hide_applicable_checks(self):
        responses = [{'parents':[{'sha':'c'*40}]}, {'files':[{'filename':str(i)} for i in range(300)]},
                     {'truncated':True, 'tree':[]}, {'truncated':False, 'tree':[]}]
        with patch.dict(release.os.environ, {}, clear=True), patch.object(release, 'gh', side_effect=responses):
            with self.assertRaisesRegex(ValueError, 'UNTRUNCATED_PUSH'):
                release.push_applicability('owner/repo', COMMIT)

    def test_exact_path_diff_includes_mode_only_changes(self):
        old = {'path':'.github/workflows/measurement009.yml', 'type':'blob', 'mode':'100644', 'sha':'d'*40}
        new = {**old, 'mode':'100755'}
        responses = [{'parents':[{'sha':'c'*40}]}, {'files':[{'filename':str(i)} for i in range(300)]},
                     {'truncated':False, 'tree':[old]}, {'truncated':False, 'tree':[new]}]
        with patch.dict(release.os.environ, {}, clear=True), patch.object(release, 'gh', side_effect=responses):
            result = release.push_applicability('owner/repo', COMMIT)
        self.assertEqual(result['changed_paths'], ['.github/workflows/measurement009.yml'])
        self.assertIn('measurement009.yml', release.applicable_workflows(result['changed_paths']))

    def test_publication_wait_can_exceed_operating_timeout_without_raising_its_cap(self):
        publish = ['release', 'publish', '--assets', '/unused', '--source-commit', COMMIT,
                   '--repository', 'owner/repo', '--run-id', '7', '--timeout-seconds', '2400']
        operate = ['release', 'operate-download', '--assets', '/unused', '--source-commit', COMMIT,
                   '--output', '/unused-operation', '--timeout-seconds', '1201']
        with patch.object(release.sys, 'argv', publish), patch.object(release, 'publish', return_value={}) as action, contextlib.redirect_stdout(io.StringIO()):
            release.main()
            self.assertEqual(action.call_args.args[-1], 2400)
        with patch.object(release.sys, 'argv', operate), patch.object(release, 'operate_download') as action, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                release.main()
            self.assertEqual(error.exception.code, 2)
            action.assert_not_called()
        with patch.object(release.sys, 'argv', [*publish[:-1], '2401']), patch.object(release, 'publish') as action, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                release.main()
            action.assert_not_called()

if __name__ == '__main__':
    unittest.main()
