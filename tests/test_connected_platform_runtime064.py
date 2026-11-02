"""Platform windows, free runner routing and immutable qualification references."""
import os
from pathlib import Path
import json
import re
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

from connected_enterprise.platform_runtime import (
    COMMAND_WINDOW_SECONDS, HOSTED_JOB_LIMIT_SECONDS,
    RECEIPT_SHUTDOWN_RESERVE_SECONDS, command_budget,
)

ROOT = Path(__file__).resolve().parents[1]


def workflow_jobs(text):
    body = text.split('\njobs:\n', 1)[1]
    return dict(re.findall(r'(?ms)^  ([A-Za-z0-9_-]+):\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)', body))


def workflow_steps(job):
    return re.findall(r'(?ms)^      - (.*?)(?=^      - |\Z)', job.split('\n    steps:\n', 1)[1])


class PlatformWindowTests(unittest.TestCase):
    def test_standalone_default_does_not_invent_a_platform_deadline(self):
        with patch.dict(os.environ, {}, clear=True):
            result = command_budget(now=1_000_600)
        self.assertEqual(HOSTED_JOB_LIMIT_SECONDS, 21_600)
        self.assertEqual(RECEIPT_SHUTDOWN_RESERVE_SECONDS, 300)
        self.assertEqual(COMMAND_WINDOW_SECONDS, 21_300)
        self.assertIsNone(result['timeout_seconds'])
        self.assertIsNone(result['platform_limit_seconds'])
        self.assertEqual(result['receipt_reserve_seconds'], 0)
        self.assertEqual(result['clock_source'], 'standalone-no-platform-deadline')

    def test_standalone_optional_probe_allowance_is_not_capped_by_githubs_window(self):
        result = command_budget(86_400, environ={}, now=1_000_600)
        self.assertEqual(result['timeout_seconds'], 86_400)
        self.assertIsNone(result['platform_limit_seconds'])
        self.assertEqual(result['receipt_reserve_seconds'], 0)
        for environment in ({'AGI_JOB_START_EPOCH': '1'},
                            {'GITHUB_ACTIONS': 'false', 'AGI_JOB_START_EPOCH': '1'}):
            with self.subTest(environment=environment):
                standalone = command_budget(environ=environment, now=1_000_600)
                self.assertIsNone(standalone['timeout_seconds'])
                self.assertEqual(standalone['clock_source'], 'standalone-no-platform-deadline')

    def test_elapsed_setup_is_deducted_before_any_command_starts(self):
        environment = {'GITHUB_ACTIONS': 'true', 'AGI_JOB_START_EPOCH': '1000000'}
        result = command_budget(environ=environment, now=1_000_600)
        self.assertEqual(result['elapsed_job_seconds'], 600)
        self.assertEqual(result['timeout_seconds'], 20_700)
        self.assertEqual(result['platform_limit_seconds'], 21_600)
        self.assertEqual(result['receipt_reserve_seconds'], 300)
        self.assertNotEqual(result['clock_source'], 'standalone-no-platform-deadline')
        self.assertEqual(command_budget(900, environ=environment, now=1_000_600)['timeout_seconds'], 900)
        self.assertEqual(command_budget(21_300, environ=environment, now=1_000_600)['timeout_seconds'], 20_700)

    def test_invalid_requested_allowances_never_create_work(self):
        for requested in (True, False, 0, -1, 900.0, '900', float('inf'), float('nan'), 10**1000):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                command_budget(requested, environ={}, now=1_000_600)
        with self.assertRaises(ValueError):
            command_budget(21_301, environ={'GITHUB_ACTIONS': 'true',
                                          'AGI_JOB_START_EPOCH': '1000000'}, now=1_000_600)

    def test_github_marker_is_required_and_must_be_a_valid_nonfuture_epoch(self):
        environments = [{'GITHUB_ACTIONS': 'true'}]
        environments.extend({'GITHUB_ACTIONS': 'true', 'AGI_JOB_START_EPOCH': marker}
                            for marker in ('', 'invalid', '1000000.5', '-1', True, '1000601'))
        for environment in environments:
            with self.subTest(environment=environment), self.assertRaises((ValueError, TimeoutError)):
                command_budget(environ=environment, now=1_000_600)

    def test_exhausted_platform_window_fails_instead_of_granting_a_new_window(self):
        environment = {'GITHUB_ACTIONS': 'true', 'AGI_JOB_START_EPOCH': '1000000'}
        for moment in (1_021_300, 1_021_301, 1_100_000):
            with self.subTest(moment=moment), self.assertRaises((ValueError, TimeoutError)):
                command_budget(environ=environment, now=moment)

    def test_both_release_entrypoints_import_from_outside_the_checkout(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in {'PYTHONPATH', 'PYTHONHOME'}}
        environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
        with tempfile.TemporaryDirectory(prefix='platform064-cli-import-') as directory:
            for name in ('qualify_connected014.py', 'release_connected014.py'):
                with self.subTest(script=name):
                    result = subprocess.run([sys.executable, str(ROOT/'scripts'/name), '--help'],
                                            cwd=directory, env=environment, capture_output=True,
                                            text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('usage:', result.stdout.lower())
                    self.assertFalse(list(Path(directory).iterdir()))

    @unittest.skipUnless(os.name == 'posix', 'POSIX owned-process-tree interruption')
    def test_user_interrupt_stops_the_owned_child_and_descendant_without_a_success_record(self):
        wrapper = '''
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from scripts.qualify_connected014 import run_command
directory = pathlib.Path(sys.argv[2])
commands = []
try:
    run_command([sys.executable, str(directory/'child.py'), str(directory)],
                directory, directory/'command', None, commands)
except BaseException as error:
    (directory/'INTERRUPTION.json').write_text(json.dumps({'error':type(error).__name__, 'commands':commands}))
    raise
'''
        child_code = '''
import json, os, pathlib, signal, subprocess, sys, time
directory = pathlib.Path(sys.argv[1])
descendant = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])
def terminate(*unused):
    descendant.terminate()
    descendant.wait(timeout=2)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, terminate)
(directory/'OWNED.pending').write_text(json.dumps({'child':os.getpid(), 'descendant':descendant.pid}))
(directory/'OWNED.pending').replace(directory/'OWNED.json')
while True:
    time.sleep(300)
'''
        def running(pid):
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                return False
        with tempfile.TemporaryDirectory(prefix='platform064-interruption-') as directory:
            root = Path(directory)
            (root/'child.py').write_text(textwrap.dedent(child_code))
            process = subprocess.Popen([sys.executable, '-c', textwrap.dedent(wrapper), str(ROOT), directory],
                                       cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, start_new_session=True)
            owned = None
            try:
                ready_deadline = time.monotonic()+10
                while time.monotonic() < ready_deadline and not (root/'OWNED.json').exists():
                    if process.poll() is not None:
                        self.fail('Wrapper ended before establishing its owned process tree: '+process.communicate()[1])
                    time.sleep(0.01)
                self.assertTrue((root/'OWNED.json').exists(), 'Controlled child failed to become ready')
                owned = json.loads((root/'OWNED.json').read_text())
                self.assertTrue(all(running(pid) for pid in owned.values()))
                process.send_signal(signal.SIGINT)
                _, stderr = process.communicate(timeout=12)
                self.assertNotEqual(process.returncode, 0, stderr)
                receipt = json.loads((root/'INTERRUPTION.json').read_text())
                self.assertEqual(receipt, {'error':'KeyboardInterrupt', 'commands':[]})
                for role, pid in owned.items():
                    with self.subTest(role=role):
                        self.assertFalse(running(pid), 'User interruption left owned work executing')
            finally:
                if owned is not None:
                    try:
                        os.killpg(owned['child'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=5)


class CurrentWorkflowPlatformTests(unittest.TestCase):
    def test_all_current_jobs_use_the_public_standard_runner_and_platform_window(self):
        workflows = sorted((ROOT/'.github/workflows').glob('*.yml'))
        self.assertTrue(workflows)
        for workflow in workflows:
            jobs = workflow_jobs(workflow.read_text())
            self.assertTrue(jobs, workflow.name)
            for name, job in jobs.items():
                with self.subTest(workflow=workflow.name, job=name):
                    self.assertEqual(re.findall(r'(?m)^    runs-on: (.+)$', job), ['ubuntu-latest'])
                    self.assertEqual(re.findall(r'(?m)^    timeout-minutes: (.+)$', job), ['360'])
                    self.assertNotRegex(job, r'(?m)^    (?:container|services):')
                    first = workflow_steps(job)[0]
                    self.assertIn('AGI_JOB_START_EPOCH', first)
                    self.assertIn('GITHUB_ENV', first)
                    self.assertNotIn('actions/checkout', first)

    def test_publisher_downloads_the_qualified_producer_id_not_its_current_attempt(self):
        jobs = workflow_jobs((ROOT/'.github/workflows/connected014-release.yml').read_text())
        qualification, publisher = jobs['release-qualification'], jobs['publish-and-gate']
        reference = re.search(r'(?m)^      qualified_artifact_id: \$\{\{ steps\.([A-Za-z0-9_-]+)\.outputs\.artifact-id \}\}$', qualification)
        self.assertIsNotNone(reference)
        producer = [step for step in workflow_steps(qualification)
                    if re.search(r'(?m)^        id: '+re.escape(reference.group(1))+r'$', step)]
        self.assertEqual(len(producer), 1)
        self.assertIn('uses: actions/upload-artifact@', producer[0])
        self.assertIn('${{ github.run_attempt }}', producer[0])
        downloads = [step for step in workflow_steps(publisher) if 'uses: actions/download-artifact@' in step]
        self.assertEqual(len(downloads), 1)
        self.assertIn('artifact-ids: ${{ needs.release-qualification.outputs.qualified_artifact_id }}', downloads[0])
        self.assertNotIn('github.run_attempt', downloads[0])

    def test_release_and_campaign_evidence_is_immutable_per_attempt(self):
        for name in ('connected014-release.yml', 'campaign.yml'):
            jobs = workflow_jobs((ROOT/'.github/workflows'/name).read_text())
            for job_name, job in jobs.items():
                for step in workflow_steps(job):
                    if 'uses: actions/upload-artifact@' not in step:
                        continue
                    with self.subTest(workflow=name, job=job_name):
                        names = re.findall(r'(?m)^          name: (.+)$', step)
                        self.assertEqual(len(names), 1)
                        self.assertIn('${{ github.run_attempt }}', names[0])
                        self.assertNotRegex(step, r'(?m)^          overwrite: true$')

    def test_qualified_artifact_reference_guard_rejects_missing_or_multiple_ids(self):
        publisher = workflow_jobs((ROOT/'.github/workflows/connected014-release.yml').read_text())['publish-and-gate']
        steps = workflow_steps(publisher)
        guards = [step for step in steps if step.startswith('name: Validate qualified artifact reference\n')]
        self.assertEqual(len(guards), 1)
        self.assertIn('QUALIFIED_ARTIFACT_ID: ${{ needs.release-qualification.outputs.qualified_artifact_id }}', guards[0])
        self.assertLess(steps.index(guards[0]), next(i for i, step in enumerate(steps) if 'uses: actions/download-artifact@' in step))
        script = textwrap.dedent(guards[0].split('        run: |\n', 1)[1])
        with tempfile.TemporaryDirectory(prefix='platform064-artifact-reference-') as directory:
            for artifact_id in ('13108053854', '', '0', '01', '1,2', '../private', '1;exit 0', 'not-an-id'):
                with self.subTest(artifact_id=artifact_id):
                    result = subprocess.run(['bash', '-eu', '-o', 'pipefail', '-c', script],
                                            cwd=directory, env={**os.environ, 'QUALIFIED_ARTIFACT_ID': artifact_id},
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode == 0, artifact_id == '13108053854')
                    self.assertFalse(list(Path(directory).iterdir()))

    def test_current_publication_waits_use_the_remaining_platform_window(self):
        for name in ('consequential007.yml', 'consequential009.yml', 'commercial010.yml'):
            publisher = workflow_jobs((ROOT/'.github/workflows'/name).read_text())['publish']
            with self.subTest(workflow=name):
                self.assertIn('from connected_enterprise.platform_runtime import command_budget', publisher)
                self.assertIn('command_budget()["timeout_seconds"]', publisher)
                self.assertIn('while time.monotonic() < deadline:', publisher)
                self.assertNotRegex(publisher, r'range\((?:60|180)\)')
                self.assertIn("['conclusion'] != 'success'", publisher)
                self.assertIn('head_sha=', publisher)
                self.assertIn('event=push', publisher)
        publisher = workflow_jobs((ROOT/'.github/workflows/measurement009.yml').read_text())['publish']
        self.assertNotRegex(publisher, r'range\((?:60|180)\)')
        self.assertIn("int(os.environ['AGI_JOB_START_EPOCH'])", publisher)
        self.assertIn('remaining=21600-300-(observed-started)', publisher)
        self.assertIn('if remaining<=0:', publisher)
        self.assertIn('while time.monotonic()<deadline:', publisher)
        self.assertIn("latest['conclusion']!='success'", publisher)

    def test_optional_tex_passes_recompute_the_actual_remaining_window(self):
        campaign = (ROOT/'.github/workflows/campaign.yml').read_text()
        self.assertNotRegex(campaign, r'timeout\s+60\s+pdflatex')
        self.assertRegex(campaign, r'for tex_pass in 1 2; do\n\s+tex_window=.*command_budget\(\).*\n\s+.*timeout "\$tex_window" pdflatex -no-shell-escape')

    def test_historical_measurement_admission_and_worker_envelope_stay_frozen(self):
        qualification = workflow_jobs((ROOT/'.github/workflows/measurement009.yml').read_text())['qualify']
        for required in (
                "'total_cpu_seconds':1800,'per_invocation_cpu_seconds':600,'maximum_invocations':3",
                "'additional_cpu_seconds':600,'additional_invocations':1,'combined_cpu_seconds':2400",
                "'combined_maximum_invocations':4,'per_invocation_cpu_seconds':600",
                "if maximum!=4 or allowance!=2400:",
                "'admitted':count <= maximum",
                "'refund_seconds':0,'original_local_ledger_reset':False",
                "if not report['admitted']:",
                '--wall 900 --cpu 600',
                '--memory-bytes 2147483648 --output-bytes 134217728 --storage-bytes 268435456',
                "if not observed['passed']:raise SystemExit('Hosted download/disk envelope exceeded; refuse qualification.')"):
            with self.subTest(required=required):
                self.assertIn(required, qualification)

    def test_existing_operating_export_privacy_contract_remains_in_force(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('compact_fixture064', ROOT/'tests/test_compact_failure_export031.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.CompactFailureTests().assert_workflow_upload_contract(
            (ROOT/'.github/workflows/connected014-release.yml').read_text())


if __name__ == '__main__':
    unittest.main()
