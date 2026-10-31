"""Economic comparison applicability is separate from mandatory qualification."""
import fnmatch
import importlib.util
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]

class CampaignTriggerScopeTests(unittest.TestCase):
    EXPECTED={
        'strategic024.yml':{'scripts/run_strategic024.py','scripts/summarize_strategic024.py','campaign/strategic-024/**','.github/workflows/strategic024.yml'},
        'sequence026.yml':{'.github/workflows/sequence026.yml','scripts/run_sequence026.py','scripts/run_commoncost026.py','scripts/run_strategic024.py','campaign/sequence-026/**'},
    }
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('scope040_release',ROOT/'scripts/release_connected014.py')
        cls.release=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.release)
    def text(self,name):return (ROOT/'.github/workflows'/name).read_text()
    def paths(self,name):
        trigger=self.text(name).split('on:\n',1)[1].split('permissions:',1)[0]
        pr=trigger.split('  pull_request:\n',1)[1].split('\n  workflow_dispatch:',1)[0]
        return set(re.findall(r"^      - ['\"]([^'\"]+)['\"]$",pr,re.M))
    def matches(self,name,path):return any(fnmatch.fnmatchcase(path,p) for p in self.paths(name))

    def test_exact_deliberate_campaign_paths_and_manual_entrypoints(self):
        for name,expected in self.EXPECTED.items():
            self.assertEqual(self.paths(name),expected)
            self.assertIn('  workflow_dispatch:',self.text(name))
            # Preserve prior PR/manual-only scheduling; do not add duplicate push cohorts.
            self.assertNotIn('\n  push:',self.text(name).split('permissions:')[0])
            self.assertIn('cancel-in-progress: false',self.text(name))
    def test_runtime_docs_tests_and_other_experiment_do_not_launch_old_cohorts(self):
        for name in self.EXPECTED:
            for path in ['connected_enterprise/finance.py','adaptive_enterprise/account.py','AGENTS.md','docs/harness/DEVELOPER_GUIDE.md','tests/test_sequence_window.py','tests/test_strategic024.py','flywheel/archive_v2.py','campaign/complete-offer-032/PROTOCOL.json']:
                with self.subTest(workflow=name,path=path):self.assertFalse(self.matches(name,path))
    def test_deliberate_protocol_and_imported_configuration_do_launch(self):
        for name,paths in self.EXPECTED.items():
            for path in paths:self.assertTrue(self.matches(name,path.replace('**','PROTOCOL.json')))
        self.assertTrue(self.matches('sequence026.yml','scripts/run_commoncost026.py'))
        self.assertTrue(self.matches('sequence026.yml','scripts/run_strategic024.py'))
    def test_all_current_regressions_and_connected_smoke_remain_mandatory(self):
        campaign=self.text('campaign.yml')
        self.assertIn('python -m unittest discover -s tests -v',campaign)
        self.assertIn('  pull_request:',campaign);self.assertIn('  push:',campaign)
        self.assertNotIn('paths:',campaign.split('permissions:',1)[0])
        connected=self.text('connected014.yml')
        self.assertIn("test_connected*.py",connected)
        self.assertIn('qualify_connected014.py --smoke',connected)
        release=self.text('connected014-release.yml')
        for command in ['qualify_connected014.py --smoke','operate-download','qualify_released_wheel035.py']:
            self.assertIn(command,release)
    def test_required_push_gates_not_waived_by_cohort_scope(self):
        required={'campaign.yml','consequential007.yml','consequential009.yml','adaptive012.yml','commercial010.yml'}
        self.assertEqual(set(self.release.REQUIRED_WORKFLOWS),required)
        for paths in [[],['AGENTS.md'],['connected_enterprise/finance.py'],['scripts/run_sequence026.py']]:
            self.assertTrue(required <= self.release.applicable_workflows(paths))
        observed=['strategic024.yml','sequence026.yml']
        self.assertTrue(set(observed)|required <= self.release.applicable_workflows([],observed))
    def test_actually_observed_failed_campaign_cannot_be_silently_ignored(self):
        head='a'*40
        run={'id':1,'run_number':1,'run_attempt':1,'status':'completed','conclusion':'failure',
             'head_sha':head,'event':'push','head_branch':'main','path':'.github/workflows/sequence026.yml','html_url':'https://github.com/example/run/1'}
        with self.assertRaisesRegex(ValueError,'EXACT_MAIN_QUALIFICATION_FAILED'):
            self.release.qualifying_runs({'sequence026.yml':[run]},head)
    def test_full_campaign_jobs_and_audits_still_exist_when_requested(self):
        strategic=self.text('strategic024.yml');sequence=self.text('sequence026.yml')
        for value in ['--stage smoke','--stage scale','summarize_strategic024.py','needs: [smoke, scale]']:
            self.assertIn(value,strategic)
        for value in ['run_sequence026.py','test_common_cost026.py','test_connected_channel*.py']:
            self.assertIn(value,sequence)

if __name__=='__main__':unittest.main()
