"""Synthetic receipt association tests; no live or platform qualification."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
import reconcile_release_evidence as reconcile
import test_owner_handoff as owner_fixture


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = owner_fixture.OwnerHandoffTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        f = self.fixture
        matrix = json.loads((HERE.parent / 'evidence/QUALIFICATION-MATRIX.json').read_text())
        f.content['evidence/QUALIFICATION-MATRIX.json'] = json.dumps(matrix).encode()
        for name in reconcile.REQUIRED_FILES:
            f.content.setdefault(name, b'Synthetic receipt-test fixture only')
        for name in reconcile.LIVE_SOURCE_FILES | {'bridge/strategy_demo.py'}:
            f.content[name] = b'Synthetic source bytes; not executable product code'
        f.write_archive()
        self.archive_hash = hashlib.sha256(f.archive.read_bytes()).hexdigest()
        self.args = argparse.Namespace(archive=f.archive, expected_sha256=self.archive_hash,
            source_sha=owner_fixture.SOURCE, source_product_tree='b'*40,
            operation_receipt=f.op/'QUALIFICATION.json', asset_dir=f.assets, live_receipt=None, model_evidence_archive=None,
            output=f.root/'reconciled')
        modules = sorted(set(sum(reconcile.FIXTURE_MODULES.values(), [])) | {'test_workflow_strategies', 'test_independent_strategies'})
        python_log = '\n'.join('test_fixture ('+name+'.Tests.test_fixture) ... ok' for name in modules)+'\nRan 25 tests in 0.1s\nOK\n'
        http = {'status':'PASS','checks':['builder critic repair executed with frozen cases'],
                'model_calls':4,'strategies':[{'strategy':name,'passed':True,'model_calls':3} for name in sorted(reconcile.STRATEGIES)]}
        self.entries = [
            (['node','--test','tests/fixture.test.cjs'], 'ℹ tests 30\n', ''),
            (['python','-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'], '', python_log),
            (['python','-B','launch.py','--help'], 'usage: synthetic', ''),
            (['node','evidence/UI_HTTP_WORKFLOW_REPLAY.cjs'], json.dumps(http), ''),
            (['python','-B','-m','bridge.strategy_demo','--workspace',str(f.root/'paired'), '--output',str(f.op/'STRATEGY-DEMONSTRATION.json')], '{}', ''),
        ]
        self.write_operations()
        self.browser = {'source_revision':owner_fixture.SOURCE,'status':'PASS','errors':[],'http_failures':[],
                        'platform':'linux','checks':sorted(reconcile.BROWSER_CHECKS),'screenshots':['HARNESS-fixture.png']}
        (f.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps(self.browser))
        self.paired = {'schema':'alpha-genesis-paired-retrieval/v1',
            'source_sha256':{name:hashlib.sha256(f.content[name]).hexdigest() for name in reconcile.PAIRED_SOURCE_FILES},
            'protocol':{'shared_per_arm_budget':{'model_calls':2,'tool_actions':2}},
            'arms':[{'arm':'no-retrieval','status':'complete','model_calls':2,'actions':2,'failed_initial_checks':1,'fixture_source_fetches':0,'honest_abstention':True,'matches_withheld_source':False,'verification':{'passed':True}},
                    {'arm':'retrieval','status':'complete','model_calls':2,'actions':2,'failed_initial_checks':1,'fixture_source_fetches':1,'honest_abstention':False,'matches_withheld_source':True,'verification':{'passed':True}}],
            'competent_conventional_control':{'matches_withheld_source':True,'model_calls':0}}
        self.write_paired()

    def write_operations(self):
        f = self.fixture
        for path in f.op.glob('operation-*.txt'):
            path.unlink()
        rows = []
        for index,(command,stdout,stderr) in enumerate(self.entries,1):
            rows.append({'command':command,'returncode':0})
            (f.op/f'operation-{index}.stdout.txt').write_text(stdout)
            (f.op/f'operation-{index}.stderr.txt').write_text(stderr)
        self.operation = {'schema':'alpha-genesis-harness-downloaded-operation/v1',
            'source_revision':owner_fixture.SOURCE,'archive_sha256':self.archive_hash,
            'verdict':'PASSED IN SCOPE','host':{'platform':'Linux synthetic test host'},'operations':rows}
        self.args.operation_receipt.write_text(json.dumps(self.operation))

    def write_paired(self):
        (self.fixture.op/'STRATEGY-DEMONSTRATION.json').write_text(json.dumps(self.paired))

    def rows(self):
        matrix,audit = reconcile.reconcile(self.args)
        return {row['id']:row for row in matrix['criteria']}, matrix, audit

    def live_receipt(self):
        self.args.live_receipt = self.fixture.assets/'HOSTED-LOCAL-QUALIFICATION.json'
        self.args.model_evidence_archive = self.fixture.assets/'MODEL-EVIDENCE.zip'
        self.live_files = {'LOCAL-WORKFLOWS-HOSTED.json':json.dumps({
            'source_revision':owner_fixture.SOURCE,'source_product_tree':'b'*40,'source_unchanged':True,
            'runs':[{'policy':policy,'status':'complete','events':[{'kind':'model_completed'}],
                     'verification':{'passed':True},'external_execution':{'returncode':0,'result':{'output':{'result':34}}},
                     'strong_control':{'accepted':True}} for policy in ['single-model','actor-critic','parallel-exploration']]}).encode()}
        value = {'schema':'alpha-harness/hosted-local-qualification/v1','source_revision':owner_fixture.SOURCE,
            'source_product_tree':'b'*40,'source_unchanged':True,'status':'FAIL',
            'source_sha256':{name:hashlib.sha256(self.fixture.content[name]).hexdigest() for name in reconcile.LIVE_SOURCE_FILES},
            'host':{'platform':'linux','python':'3.12','accelerator':'CPU','inference_threads':2},
            'downloads':{'runtime_archive':{'verified':True,'sha256':'d'*64,'bytes':1,'url':'https://example.invalid/runtime'},
                         'model':{'verified':True,'sha256':'e'*64,'bytes':1,'url':'https://example.invalid/model'},
                         'runtime_binary_sha256':'f'*64},
            'commands':[{'entrypoint':'probe_local_workflows.py','returncode':0,'timed_out':False}],
            'qualifications':{key:('NOT_TESTED' if key in {'quote_construction','successor_reuse','independent_export'} else 'PASS') for key in reconcile.LIVE_KEYS}}
        self.write_live(value)
        return value

    def write_live(self,value):
        value['published_sha256']={name:hashlib.sha256(data).hexdigest() for name,data in self.live_files.items()}
        raw=(json.dumps(value)+'\n').encode()
        self.args.live_receipt.write_bytes(raw)
        with zipfile.ZipFile(self.args.model_evidence_archive,'w') as bundle:
            for name,data in dict(self.live_files, **{'HOSTED-LOCAL-QUALIFICATION.json':raw}).items():
                info=zipfile.ZipInfo(name);info.create_system=3;info.external_attr=0o100644<<16
                bundle.writestr(info,data)

    def platform_receipts(self):
        for system,launcher in [('Darwin','Launch-HARNESS.command'),('Windows','Launch-HARNESS.cmd')]:
            browser = dict(self.browser, platform='darwin' if system == 'Darwin' else 'win32', server_mode='external-native-launcher')
            browser['checks']=[value for value in browser['checks'] if value != 'spawned connector announced its own loopback origin']+['native source launcher supplied the verified loopback origin']
            data=b'{"experiments":["synthetic"]}'
            browser['exports']=[{'file':'GENESIS-NEXT-browser-export.json','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]
            (self.fixture.assets/(system+'-GENESIS-NEXT-browser-export.json')).write_bytes(data)
            value = {'source_revision':owner_fixture.SOURCE,'archive_sha256':self.archive_hash,'status':'PASS',
                'host':'macOS-15-synthetic' if system == 'Darwin' else 'Windows-2025-synthetic',
                'scope':'Synthetic receipt fixture; no actual OS evidence', 'browser_report':browser,
                'launcher':launcher,'launcher_interpreter':{'version':'3.12','executable':'synthetic'},
                'checks':{'loopback_authentication':{'bootstrap':'PASS','unauthenticated_status':403,'authenticated_status':200},
                          'native_workspace':{'genesis_state_created_at_requested_path':True},
                          'genesis_startup_diagnostic':{'status':'PASS','stage':'complete','interpreter':'synthetic',
                              'completed_stages':['imports','workflow_initialization','genesis_initialization','genesis_status']}},
                'operations':[{'command':['node','--test','tests/fixture.test.cjs'],'returncode':0},
                              {'command':[launcher,'--help'],'returncode':0},
                              {'command':['node','evidence/UI_BROWSER_REPLAY.cjs'],'returncode':0}]}
            (self.fixture.assets/f'PLATFORM-{system}-VERIFICATION.json').write_text(json.dumps(value))
            (self.fixture.assets/f'{system}-HARNESS-fixture.png').write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

    def test_actual_fixture_receipts_qualify_only_scoped_rows(self):
        rows,matrix,audit = self.rows()
        for identifier in ['A1','A2','C2','F2','G1','G2','G3','G4','G5','H1','H2','I1','J1','O10','O12']:
            self.assertEqual(rows[identifier]['status'],'PASS',identifier)
        for identifier in ['B2','C1','D1','I2']:
            self.assertEqual(rows[identifier]['status'],'NOT TESTED',identifier)
        for identifier in reconcile.BLOCKED:
            self.assertEqual(rows[identifier]['status'],'BLOCKED')
        for identifier in reconcile.UNRESOLVED_GENESIS_FAILURES:
            self.assertEqual(rows[identifier]['status'],'FAIL')
        for identifier in ('O2','O3'):
            self.assertEqual(rows[identifier]['status'],'NOT TESTED')
        self.assertFalse(matrix['commercially_validated'])
        self.assertEqual(audit['archive_sha256'],self.archive_hash)
        self.assertIn(owner_fixture.SOURCE,reconcile.markdown_report(matrix))

    def test_g1_excludes_only_documented_repository_composer_skip_and_discloses_it(self):
        cmd,out,err = self.entries[1]
        self.entries[1] = (cmd,out,err + reconcile.G1_OUT_OF_SCOPE_SKIP + '\n')
        self.write_operations()
        rows,matrix,_ = self.rows()
        self.assertEqual(rows['G1']['status'], 'PASS')
        self.assertIn('repository-only canonical composer test was skipped', rows['G1']['remaining_dependency_or_scope'])
        self.assertFalse(matrix['commercially_validated'])
        for identifier in reconcile.BLOCKED:
            self.assertEqual(rows[identifier]['status'], 'BLOCKED')

    def test_g1_skip_exception_cannot_hide_another_reason_identity_or_result(self):
        passed = 'test_fixture (test_bridge.Tests.test_fixture) ... ok\n'
        exact = reconcile.G1_OUT_OF_SCOPE_SKIP
        self.assertTrue(reconcile.module_passed(passed + exact, 'test_bridge', 'G1'))
        for line in [exact.replace('Canonical research source is intentionally absent from standalone distribution', 'missing credentials'),
                     exact.replace('NativeBoundaryTests', 'HTTPBoundaryTests'),
                     exact.replace('test_existing_composer_is_read_only_and_scope_is_explicit', 'test_post_requires_token_and_json'),
                     exact.replace("skipped 'Canonical research source is intentionally absent from standalone distribution'", 'FAIL'),
                     exact + ' unverified suffix']:
            with self.subTest(line=line):
                self.assertFalse(reconcile.module_passed(passed + line, 'test_bridge', 'G1'))
        self.assertFalse(reconcile.module_passed(passed + exact + '\n' + exact, 'test_bridge', 'G1'))
        self.assertFalse(reconcile.module_passed(exact, 'test_bridge', 'G1'))
        self.assertFalse(reconcile.module_passed(passed + exact, 'test_bridge'))
        self.assertFalse(reconcile.module_passed(passed + exact, 'test_bridge', 'G4'))
        self.assertFalse(reconcile.module_passed('test_fixture (test_providers.Tests.test_fixture) ... skipped missing transport', 'test_providers', 'G1'))

    def test_operation_lookup_is_by_command_after_new_operation_inserted(self):
        self.entries.insert(0,(['python','-c','pass'],'',''))
        self.write_operations()
        rows,_,_ = self.rows()
        self.assertEqual(rows['C2']['status'],'PASS')
        self.assertEqual(rows['F2']['status'],'PASS')

    def test_failed_operation_never_promotes_historical_pass(self):
        value=json.loads(self.args.operation_receipt.read_text())
        value['operations'][0]['returncode']=1;value['verdict']='INVALID'
        self.args.operation_receipt.write_text(json.dumps(value))
        rows,_,_=self.rows()
        self.assertEqual(rows['H1']['status'],'FAIL')
        self.assertEqual(rows['G2']['status'],'NOT TESTED')

    def test_skipped_security_module_is_not_pass(self):
        cmd,out,err=self.entries[1]
        self.entries[1]=(cmd,out,err.replace('test_fixture (test_chatgpt.Tests.test_fixture) ... ok','test_fixture (test_chatgpt.Tests.test_fixture) ... skipped optional dependency'))
        self.write_operations()
        self.assertEqual(self.rows()[0]['G2']['status'],'NOT TESTED')

    def test_missing_graphical_reopen_check_is_not_pass(self):
        self.browser['checks'].remove('saved project survives reload; downloaded JSON reopens in fresh browser storage')
        (self.fixture.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps(self.browser))
        self.assertEqual(self.rows()[0]['A1']['status'],'NOT TESTED')

    def test_browser_missing_or_failed_http_proof_cannot_qualify_linux_or_native(self):
        for evidence in ({}, {'http_failures':[{'path':'/api/genesis-next/status','status':500}]}):
            self.browser.pop('http_failures',None)
            self.browser.update(evidence)
            (self.fixture.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps(self.browser))
            self.platform_receipts()
            rows,_,_=self.rows()
            with self.subTest(evidence=evidence):
                for identifier in ('A1','I1','I2'):
                    self.assertEqual(rows[identifier]['status'],'NOT TESTED',identifier)

    def test_failed_graphical_receipt_is_preserved_as_fail(self):
        self.browser['status']='FAIL'
        (self.fixture.assets/'BROWSER-VERIFICATION.json').write_text(json.dumps(self.browser))
        self.assertEqual(self.rows()[0]['I1']['status'],'FAIL')

    def test_paired_false_contrast_is_fail(self):
        self.paired['arms'][0]['honest_abstention']=False;self.write_paired()
        self.assertEqual(self.rows()[0]['F2']['status'],'FAIL')

    def test_paired_changed_source_is_refused(self):
        self.paired['source_sha256']['bridge/workflows.py']='0'*64;self.write_paired()
        with self.assertRaisesRegex(ValueError,'source hash'):self.rows()

    def test_paired_receipt_without_extracted_command_is_not_pass(self):
        self.entries=self.entries[:-1];self.write_operations()
        self.assertEqual(self.rows()[0]['F2']['status'],'NOT TESTED')

    def test_both_real_platform_receipts_required_for_narrow_i2(self):
        self.platform_receipts()
        rows,_,_=self.rows()
        self.assertEqual(rows['I2']['status'],'PASS')
        self.assertIn('Finder/Explorer',rows['I2']['remaining_dependency_or_scope'])
        self.assertEqual(rows['B5']['status'],'BLOCKED')
        (self.fixture.assets/'PLATFORM-Windows-VERIFICATION.json').unlink()
        self.assertEqual(self.rows()[0]['I2']['status'],'NOT TESTED')

    def test_foreign_platform_archive_is_refused(self):
        self.platform_receipts();path=self.fixture.assets/'PLATFORM-Windows-VERIFICATION.json'
        value=json.loads(path.read_text());value['archive_sha256']='0'*64;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'different source or archive'):self.rows()

    def test_linux_browser_cannot_be_labeled_windows_pass(self):
        self.platform_receipts();path=self.fixture.assets/'PLATFORM-Windows-VERIFICATION.json'
        value=json.loads(path.read_text());value['browser_report']['platform']='linux';path.write_text(json.dumps(value))
        self.assertEqual(self.rows()[0]['I2']['status'],'NOT TESTED')

    def test_platform_receipt_without_host_cannot_pass(self):
        self.platform_receipts();path=self.fixture.assets/'PLATFORM-Darwin-VERIFICATION.json'
        value=json.loads(path.read_text());value.pop('host');path.write_text(json.dumps(value))
        self.assertEqual(self.rows()[0]['I2']['status'],'NOT TESTED')

    def test_final_live_partial_failure_preserves_each_result(self):
        value=self.live_receipt();value['status']='FAIL';value['qualifications']['quote_construction']='FAIL'
        self.write_live(value)
        rows,matrix,_=self.rows()
        self.assertEqual(rows['B2']['status'],'PASS')
        self.assertEqual(rows['C1']['status'],'PASS')
        self.assertEqual(rows['D1']['status'],'PASS')
        self.assertIn('quote construction: FAIL',rows['D1']['remaining_dependency_or_scope'])
        self.assertEqual(matrix['live_qualification_summary']['status'],'FAIL')
        for identifier in reconcile.BLOCKED:self.assertEqual(rows[identifier]['status'],'BLOCKED')

    def test_workshop_receipts_reconcile_and_refuse_stale_source(self):
        fixture = self.fixture
        for name in reconcile.WORKSHOP_SOURCES:
            fixture.content.setdefault('bridge/' + name, name.encode())
        fixture.write_archive()
        self.archive_hash = self.args.expected_sha256 = reconcile.digest(fixture.archive.read_bytes())
        self.write_operations()
        live = self.live_receipt()
        live['qualifications']['workshop'] = 'PASS'
        live['workshop_scopes'] = dict.fromkeys(reconcile.WORKSHOP_SCOPES, True)
        source_hashes = {name: reconcile.digest(fixture.content['bridge/' + name]) for name in reconcile.WORKSHOP_SOURCES}
        for scope, names in reconcile.WORKSHOP_SCOPES.items():
            live['commands'].append({'entrypoint': 'qualify_workshop.py', 'returncode': 0, 'timed_out': False})
            receipt = {'schema': 'alpha-genesis/workshop-local-qualification/v1', 'scope': scope,
                       'status': 'PASS', 'platform': 'linux', 'expected_model': 'fixture',
                       'source_revision': live['source_revision'], 'source_product_tree': live['source_product_tree'],
                       'sources_sha256': source_hashes, 'model_sha256': live['downloads']['model']['sha256'],
                       'runtime_sha256': live['downloads']['runtime_binary_sha256'],
                       'unchanged_artifact_reuse': True, 'cases': []}
            for name, count in names.items():
                docket = dict.fromkeys(('checked', 'accepted', 'planned'), count)
                docket.update(status='admitted', current=True, passed=True,
                              artifact_hashes={'instrument.json': reconcile.digest(b'{}')})
                mission = {'id': name, 'docket': docket, 'source_sha256': source_hashes}
                proof = {'mission': mission, 'observations': [{}] * count}
                artifact = io.BytesIO()
                members = dict.fromkeys(reconcile.WORKSHOP_BUNDLE, b'{}')
                members.update({'PROOF.json': json.dumps(proof).encode(),
                                'RUN_INSTRUMENT.py': fixture.content['bridge/instruments.py'],
                                'RUN_WORKSHOP.py': fixture.content['bridge/workshop_protocol.py']})
                with zipfile.ZipFile(artifact, 'w') as bundle:
                    for member, data in members.items():
                        bundle.writestr(member, data)
                self.live_files['workshop/' + name + '.zip'] = artifact.getvalue()
                receipt['cases'].append({'name': name, 'id': name, 'status': 'complete', 'docket': docket,
                                         'sources_sha256': source_hashes, 'replay_exit': 0,
                                         'bundle_sha256': reconcile.digest(artifact.getvalue()),
                                         'events': [{'kind': 'model_completed', 'detail': {
                                             'provider': 'local', 'reported_model': 'fixture'}}]})
            self.live_files['WORKSHOP-' + scope.upper() + '-QUALIFICATION.json'] = json.dumps(receipt).encode()
        self.write_live(live)
        self.assertEqual(self.rows()[0]['W1']['status'], 'PASS')
        report = 'WORKSHOP-CONTRAST-QUALIFICATION.json'
        contrast = json.loads(self.live_files[report])
        contrast['sources_sha256']['server.py'] = 'a' * 64
        self.live_files[report] = json.dumps(contrast).encode()
        self.write_live(live)
        with self.assertRaisesRegex(ValueError, 'Evidence source hash differs'):
            self.rows()

    def test_old_commit_live_receipt_cannot_inherit_pass(self):
        value=self.live_receipt();value['source_revision']='c'*40;self.write_live(value)
        with self.assertRaisesRegex(ValueError,'source'):self.rows()

    def test_live_changed_during_execution_cannot_pass(self):
        value=self.live_receipt();value['source_unchanged']=False;self.write_live(value)
        with self.assertRaisesRegex(ValueError,'source'):self.rows()

    def test_live_pass_with_only_license_hash_is_refused(self):
        value=self.live_receipt();value['source_sha256']={'LICENSE':hashlib.sha256(self.fixture.content['LICENSE']).hexdigest()};self.write_live(value)
        with self.assertRaisesRegex(ValueError,'required inference'):self.rows()

    def test_live_pass_without_runtime_provenance_is_refused(self):
        value=self.live_receipt();value['downloads']={};self.write_live(value)
        with self.assertRaisesRegex(ValueError,'download provenance'):self.rows()

    def test_flat_live_manifest_substitution_is_refused(self):
        value=self.live_receipt();value['host']['python']='different';self.args.live_receipt.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'Flat live receipt'):self.rows()

    def test_model_pass_without_completed_event_is_refused(self):
        value=self.live_receipt();raw=json.loads(self.live_files['LOCAL-WORKFLOWS-HOSTED.json'])
        for row in raw['runs']:row['events']=[]
        self.live_files['LOCAL-WORKFLOWS-HOSTED.json']=json.dumps(raw).encode();self.write_live(value)
        with self.assertRaisesRegex(ValueError,'completed model event'):self.rows()

    def test_current_quote_trial_requires_006_driver_and_raw_receipt(self):
        value=self.live_receipt()
        value['qualifications']={key:('PASS' if key=='local_inference' else 'NOT_TESTED') for key in reconcile.LIVE_KEYS}
        value['commands']=[{'entrypoint':'qualify_quote_workflow_006.py','returncode':1,'timed_out':False}]
        raw=json.dumps({'source_revision':owner_fixture.SOURCE,'product_tree_sha':'b'*40,
                        'arms':[{'events':[{'kind':'model_completed'}]}]}).encode()
        self.live_files={'LOCAL-QUOTE-QUALIFICATION-006.json':raw}
        self.write_live(value)
        rows,_,_=self.rows()
        self.assertEqual(rows['B2']['status'],'PASS')
        self.assertEqual(rows['D1']['status'],'NOT TESTED')
        self.live_files={'LOCAL-QUOTE-QUALIFICATION-005.json':raw}
        self.write_live(value)
        with self.assertRaisesRegex(ValueError,'completed model event'):self.rows()
        self.live_files={'LOCAL-QUOTE-QUALIFICATION-006.json':raw}
        value['commands'][0]['entrypoint']='qualify_quote_workflow_005.py'
        self.write_live(value)
        with self.assertRaisesRegex(ValueError,'actual inference driver execution'):self.rows()

    def test_trial_005_preserves_registered_004_acceptance_and_resources(self):
        before=json.loads((HERE.parent/'evidence/LOCAL-QUOTE-PROTOCOL-004.json').read_text())
        after=json.loads((HERE.parent/'evidence/LOCAL-QUOTE-PROTOCOL-005.json').read_text())
        metadata={'schema','trial_id','predecessor_summary','predecessor_summaries',
                  'scaffolding_disclosure','diagnostic_revision','changes_from_fourth_trial'}
        self.assertEqual({key:value for key,value in before.items() if key not in metadata},
                         {key:value for key,value in after.items() if key not in metadata})
        self.assertEqual(after['trial_id'],'quote-trial-005')
        self.assertEqual(after['diagnostic_revision']['source'],'bridge/instruments.py')

    def test_trial_006_preserves_frozen_acceptance_resources_and_controls(self):
        before=json.loads((HERE.parent/'evidence/LOCAL-QUOTE-PROTOCOL-005.json').read_text())
        after=json.loads((HERE.parent/'evidence/LOCAL-QUOTE-PROTOCOL-006.json').read_text())
        for key in ['contract','fields','manufacturing_cases','lab_cases','arms',
                    'finite_inference_budget','acceptance_rules','full_cost_boundaries','model',
                    'construction_format_instruction','inheritance_format_instruction']:
            self.assertEqual(before[key],after[key],key)
        self.assertEqual(after['trial_id'],'quote-trial-006')
        self.assertEqual(after['structured_output']['wire_request']['response_format']['type'],'json_schema')

    def test_empty_external_digest_refused(self):
        self.args.expected_sha256=''
        with self.assertRaisesRegex(ValueError,'digest'):self.rows()

    def frontier_receipt(self,status='PASS'):
        receipt={'schema':'alpha-genesis-live-frontier-observation/v1','status':status,
            'source_revision':owner_fixture.SOURCE,'archive_sha256':self.archive_hash,
            'source_sha256':{name:hashlib.sha256(self.fixture.content[name]).hexdigest() for name in reconcile.FRONTIER_SOURCE_FILES},
            'inference_calls':0,'real_credentials_used':False,'paid_requests_enabled':False,
            'source_url':reconcile.FRONTIER_URL,'allowed_hosts':['developers.openai.com'],'source_observation_attempts':1,
            'http_dispatch_verified':True,'background_monitoring_started':False,'stopped':True,'temporary_workspace_removed':True,
            'opportunity_status':'reconsider','observation':{'status':'INITIAL_OBSERVATION','previous_sha256':None,'replayed':True,'sha256':'d'*64},
            'actual_source_sha256':'d'*64,'evidence_event':{'url':reconcile.FRONTIER_URL,'content_sha256':'d'*64,'evidence_status':'reported'}}
        path=self.fixture.assets/'FRONTIER-MONITOR-VERIFICATION.json';path.write_text(json.dumps(receipt))
        return path,receipt

    def test_frontier_pass_is_scoped_to_reported_observation(self):
        self.frontier_receipt();rows,_,_=self.rows()
        self.assertEqual(rows['O13']['status'],'PASS');self.assertEqual(rows['O7']['status'],'NOT TESTED')
        self.assertEqual(rows['O11']['status'],'BLOCKED');self.assertEqual(rows['O6']['status'],'FAIL')

    def test_frontier_false_dispatch_or_promoted_evidence_is_refused(self):
        for change in ('dispatch','promoted','source'):
            path,value=self.frontier_receipt()
            if change=='dispatch':value['http_dispatch_verified']=False
            elif change=='promoted':value['evidence_event']['evidence_status']='reproduced'
            else:value['source_sha256']['bridge/frontier_monitor.py']='0'*64
            path.write_text(json.dumps(value))
            with self.subTest(change=change),self.assertRaises(ValueError):self.rows()

    def test_frontier_blocked_attempt_remains_blocked(self):
        path,value=self.frontier_receipt('BLOCKED');value['http_dispatch_verified']=False;value.pop('evidence_event');path.write_text(json.dumps(value))
        self.assertEqual(self.rows()[0]['O13']['status'],'BLOCKED')

    def test_native_help_without_live_wrapper_session_or_export_cannot_pass(self):
        for change in ('session','export','workspace','startup','interpreter'):
            self.platform_receipts();path=self.fixture.assets/'PLATFORM-Windows-VERIFICATION.json';value=json.loads(path.read_text())
            if change=='session':value['checks']['loopback_authentication']['authenticated_status']=403
            elif change=='workspace':value['checks'].pop('native_workspace')
            elif change=='startup':value['checks'].pop('genesis_startup_diagnostic')
            elif change=='interpreter':value['checks']['genesis_startup_diagnostic']['interpreter']='different'
            else:(self.fixture.assets/'Windows-GENESIS-NEXT-browser-export.json').write_bytes(b'tampered')
            path.write_text(json.dumps(value))
            with self.subTest(change=change):self.assertEqual(self.rows()[0]['I2']['status'],'NOT TESTED')

    def test_credential_free_foundry_probe_does_not_qualify_model_construction(self):
        record={'schema':'harness-foundry-native-probe/v1','status':'PASS','source_revision':owner_fixture.SOURCE,
            'archive_sha256':self.archive_hash,'live_model_construction':'NOT_TESTED','generated_code_executed':False,
            'source_manifest':{'bridge/upgrade_foundry.py':hashlib.sha256(self.fixture.content['bridge/upgrade_foundry.py']).hexdigest()}}
        (self.fixture.assets/'UPGRADE-FOUNDRY-HOST-VERIFICATION.json').write_text(json.dumps(record))
        mac=dict(record,status='BLOCKED')
        (self.fixture.assets/'Darwin-UPGRADE-FOUNDRY-HOST-VERIFICATION.json').write_text(json.dumps(mac))
        rows,_,_=self.rows();self.assertEqual(rows['O11']['status'],'BLOCKED');self.assertIn('probe: PASS',rows['O11']['actual_test_or_required_procedure'])
        self.assertIn('Darwin-UPGRADE-FOUNDRY-HOST-VERIFICATION.json',rows['O11']['evidence_location'])
        mac['archive_sha256']='0'*64
        (self.fixture.assets/'Darwin-UPGRADE-FOUNDRY-HOST-VERIFICATION.json').write_text(json.dumps(mac))
        with self.assertRaisesRegex(ValueError,'exact-source'):self.rows()


class GenesisRawProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='harness-genesis-reconcile-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.product = HERE.parent
        commands = [
            [sys.executable,'-B','-m','bridge.genesis_next','demo','--workspace',str(cls.folder/'workspace'),'--authorize','--output',str(cls.folder/'demo.json')],
            [sys.executable,'-B','scripts/qualify_genesis_successor.py','freeze','--output',str(cls.folder/'freeze.json')],
            [sys.executable,'-B','scripts/qualify_genesis_successor.py','run','--freeze',str(cls.folder/'freeze.json'),'--output',str(cls.folder/'successor.json')],
        ]
        for command in commands:
            result = subprocess.run(command,cwd=cls.product,capture_output=True,text=True)
            if result.returncode:
                raise AssertionError(result.stderr or result.stdout)
        cls.demo = json.loads((cls.folder/'demo.json').read_text())
        cls.frozen = (cls.folder/'freeze.json').read_bytes()
        cls.successor = json.loads((cls.folder/'successor.json').read_text())
        cls.content = {name:(cls.product/name).read_bytes() for name in set(reconcile.GENESIS_SOURCES.values()) | {'bridge/'+name for name in reconcile.GENESIS_DEPENDENCY_NAMES}}

    def test_actual_constructed_source_and_fresh_successor_validate(self):
        self.assertTrue(reconcile.genesis_demo_passed(self.demo,self.content))
        self.assertTrue(reconcile.genesis_successor_passed(self.frozen,self.successor,self.content))

    def test_missing_constructed_candidate_source_is_refused(self):
        value = copy.deepcopy(self.demo);value['experiment']['artifacts'].pop('candidate.py')
        with self.assertRaisesRegex(ValueError,'constructed source'):
            reconcile.genesis_demo_passed(value,self.content)

    def test_missing_or_changed_schema_dependency_is_refused(self):
        for name in ('workflow_schemas.py', 'output_schema.py'):
            value = copy.deepcopy(self.demo); value['experiment']['source']['dependency_sha256'].pop(name)
            with self.assertRaisesRegex(ValueError, 'dependency source identity'):
                reconcile.genesis_demo_passed(value,self.content)
            value = copy.deepcopy(self.demo); value['experiment']['source']['dependency_sha256'][name] = '0'*64
            with self.assertRaisesRegex(ValueError, 'dependency differs'):
                reconcile.genesis_demo_passed(value,self.content)

    def test_forged_successor_acceptance_cannot_pass_even_with_new_digest(self):
        value = copy.deepcopy(self.successor)
        decision = next(row for row in value['arms'][1]['decisions'] if row['accepted'] is True)
        case = next(row for row in value['successor_instances'] if row['id']==decision['id'])
        case['spec']['expected']['result'] += 1
        value['instances_sha256'] = reconcile.canonical_digest({'initial':value['initial_instances'],'successor':value['successor_instances']})
        self.assertFalse(reconcile.genesis_successor_passed(self.frozen,value,self.content))

    def test_missing_competent_control_cannot_pass(self):
        value = copy.deepcopy(self.successor)
        value['arms'] = [arm for arm in value['arms'] if arm['arm']!='strong_ordinary_memoization']
        self.assertFalse(reconcile.genesis_successor_passed(self.frozen,value,self.content))

    def test_forged_successor_summary_cannot_override_raw_decisions(self):
        value = copy.deepcopy(self.successor);value['arms'][1]['adjudicated'] = 31
        self.assertFalse(reconcile.genesis_successor_passed(self.frozen,value,self.content))

    def test_changed_source_freeze_is_refused(self):
        frozen = json.loads(self.frozen);frozen['source_sha256']['candidate']='0'*64
        with self.assertRaisesRegex(ValueError,'frozen archived source'):
            reconcile.genesis_successor_passed(json.dumps(frozen).encode(),self.successor,self.content)


if __name__ == '__main__':
    unittest.main()
