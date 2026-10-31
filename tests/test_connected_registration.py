import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise.engine import default_config
from connected_enterprise.registration import SCHEMA, validate

ROOT=Path(__file__).resolve().parents[1]


def registration():
    cfg=default_config();cfg.update(horizon_days=7,customer_pool=8,arrival_bps=10000,retention_bps=10000,nonpayment_bps=0)
    return {'schema':SCHEMA,'label':'operator022-development','evidence_role':'development','seeds':[22001],
            'configs':{'central':cfg},'arms':['baseline','growth'],'control_arm':'baseline','candidate_arm':'growth',
            'service_cohort_seed':14013026,'workers':1}


class ConnectedRegistrationValidationTests(unittest.TestCase):
    def test_malformed_design_fails_before_creating_accounts(self):
        mutations=[lambda r:r['seeds'].append(r['seeds'][0]),lambda r:r.__setitem__('workers',False),
                   lambda r:r.__setitem__('label','../unsafe'),lambda r:r.__setitem__('candidate_arm','baseline'),
                   lambda r:r['configs']['central'].__setitem__('production_cost',-1),
                   lambda r:r['configs']['central'].__setitem__('horizon_days',0),
                   lambda r:r['configs']['central']['human_comparator']['reconciliation'].__setitem__('hours',float('nan'))]
        for mutation in mutations:
            r=registration();mutation(r)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate(r)

    def test_complete_cost_and_contract_configuration_cannot_be_omitted(self):
        r=registration();r['configs']['central'].pop('support_cost')
        with self.assertRaisesRegex(ValueError,'EXACT_CONNECTED_CONFIGURATION_REQUIRED'):validate(r)
        r=registration();r['configs']['central']['clearing_hours']=r['configs']['central']['payment_deadline_hours']
        with self.assertRaisesRegex(ValueError,'COMPLETE_LIFECYCLE_EXCEEDS_PAYMENT_DEADLINE'):validate(r)


class ConnectedRegisteredOperationTests(unittest.TestCase):
    @classmethod
    def invoke(cls,*args):
        return subprocess.run([sys.executable,'-m','connected_enterprise',*args],cwd=ROOT,
                              env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=180)

    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory(prefix='connected022-registration-');cls.directory=Path(cls.fixture.name)
        cls.output=cls.directory/'business';cls.input=cls.directory/'input.json';cls.input.write_text(json.dumps(registration()))
        cls.registered=cls.invoke('register','--config',str(cls.input),'--output',str(cls.output))
        if cls.registered.returncode:raise AssertionError(cls.registered.stderr)
        cls.created_before_operation=list(cls.output.rglob('*.sqlite*'))
        cls.step=cls.invoke('operate','--max-events','4','--output',str(cls.output))
        if cls.step.returncode:raise AssertionError(cls.step.stderr)
        cls.partial={p.parent.name:json.loads(p.read_text()) for p in (cls.output/'worlds').glob('*/RESULT.json')}
        cls.keys={p.relative_to(cls.output).as_posix():p.read_bytes() for p in cls.output.rglob('*.adaptive-simulation-key')}
        cls.no_false_completion=not (cls.output/'COMPLETE.json').exists()
        cls.resumed=cls.invoke('resume','--output',str(cls.output))
        if cls.resumed.returncode:raise AssertionError(cls.resumed.stderr)
        cls.results={p.parent.name:json.loads(p.read_text()) for p in (cls.output/'worlds').glob('*/RESULT.json')}

    @classmethod
    def tearDownClass(cls):cls.fixture.cleanup()

    def test_registration_binds_input_without_funding_an_account(self):
        self.assertEqual(self.created_before_operation,[])
        frozen=json.loads((self.output/'FROZEN.json').read_text())
        self.assertIn(frozen['registration_path'],frozen['source']['files'])
        self.assertEqual(frozen['protocol']['evidence_role'],'development')
        self.assertEqual(len(self.results),2)

    def test_pause_resume_preserves_nonempty_queue_account_key_and_native_prefix(self):
        self.assertTrue(self.no_false_completion)
        self.assertEqual(len(self.keys),2)
        for name,partial in self.partial.items():
            self.assertFalse(partial['complete']);self.assertEqual(partial['processed_events'],4)
            actions=partial['owned_account']['ledger']['actions'];final=self.results[name]
            self.assertTrue(final['complete']);self.assertGreater(final['processed_events'],4)
            self.assertEqual(actions,final['owned_account']['ledger']['actions'][:len(actions)])
        for name,key in self.keys.items():self.assertEqual(key,(self.output/name).read_bytes())

    def test_public_audit_comparison_and_scoreboard_preserve_separate_businesses(self):
        checked=self.invoke('audit','--output',str(self.output));self.assertEqual(checked.returncode,0,checked.stderr)
        compared=self.invoke('comparison','--output',str(self.output));self.assertEqual(compared.returncode,0,compared.stderr)
        paired=json.loads(compared.stdout);self.assertEqual(len(paired['pairs']),1);self.assertFalse(paired['funding_authority'])
        display=self.invoke('scoreboard','--output',str(self.output));self.assertEqual(display.returncode,0,display.stderr)
        board=json.loads(display.stdout);self.assertEqual(board['world_count'],2)
        for business in board['businesses']:
            self.assertIsNone(business['trailing_twelve_month_profit_microUSD'])
            self.assertIsNone(business['measured_frontier_inference_billing_microUSD'])

    def test_self_rehashed_config_and_source_bound_registration_tampering_fail_closed(self):
        path=self.output/'FROZEN.json';raw=path.read_bytes();f=json.loads(raw)
        try:
            f['configs']['central']['opening']+=1;f.pop('sha256');f['sha256']=digest(f);path.write_text(json.dumps(f))
            rejected=self.invoke('resume','--output',str(self.output))
            self.assertNotEqual(rejected.returncode,0);self.assertIn('FROZEN_REGISTRATION_NOT_REDERIVED_FROM_SOURCE',rejected.stderr)
        finally:path.write_bytes(raw)
        frozen=json.loads(raw);path=self.output/'source'/frozen['registration_path'];original=path.read_bytes()
        try:
            value=json.loads(original);value['seeds'].append(22002);path.write_text(json.dumps(value))
            rejected=self.invoke('resume','--output',str(self.output))
            self.assertNotEqual(rejected.returncode,0);self.assertIn('FROZEN_SOURCE_OR_CONFIGURATION_CHANGED',rejected.stderr)
        finally:path.write_bytes(original)

    def test_comparison_cannot_silently_substitute_an_unregistered_arm(self):
        rejected=self.invoke('comparison','--control','channel','--output',str(self.output))
        self.assertNotEqual(rejected.returncode,0);self.assertIn('DISTINCT_REGISTERED_COMPARISON_ARMS_REQUIRED',rejected.stderr)

    def test_cli_uses_frozen_scoreboard_instead_of_installed_implementation(self):
        from connected_enterprise import runner
        observed=[]
        def run_frozen(command,cwd):
            result=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=180)
            observed.append(result);return result.returncode
        with patch.object(sys,'argv',['connected_enterprise','scoreboard','--output',str(self.output)]), \
             patch('connected_enterprise.scoreboard.scoreboard',side_effect=AssertionError('INSTALLED_INTERPRETER_USED')), \
             patch('connected_enterprise.runner.subprocess.call',side_effect=run_frozen):
            self.assertEqual(runner.main(),0)
        self.assertEqual(len(observed),1);self.assertEqual(json.loads(observed[0].stdout)['world_count'],2)

    def test_documented_input_and_measurement_script_are_in_clean_distribution(self):
        frozen=json.loads((self.output/'FROZEN.json').read_text())
        for name in ['campaign/overnight-022/OPERATOR_INPUT.json','scripts/measure_overnight022.py']:
            self.assertIn(name,frozen['source']['files']);self.assertTrue((self.output/'source'/name).is_file())
