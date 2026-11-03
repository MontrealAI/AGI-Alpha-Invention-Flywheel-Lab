import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from omega import successor

ROOT=Path(__file__).resolve().parents[1]


class SuccessorTests(unittest.TestCase):
    def test_actual_portable_kit_requires_independent_changed_case_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'kit'
            specification=successor.plan(ROOT)
            successor.construct(ROOT,output,specification=specification)
            result=successor.verify(ROOT,output)
            self.assertTrue(result['activation_allowed'])
            self.assertEqual(result['artifact_sha256'],specification['artifact_sha256'])
            self.assertEqual(result['accepted_case_count'],6)
            self.assertEqual(result['cases'][1]['optimum'],[1,220])
            self.assertEqual(result['cases'][-1]['outcome'],'SAFE_REFUSAL_WITH_CURRENT_DOCUMENTATION')

    def test_modified_code_or_forged_manifest_cannot_activate(self):
        for target in ['omega_batch.py','manifest.json','omega/help.py']:
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'kit'
                successor.construct(ROOT,output)
                path=output/target
                if target=='manifest.json':
                    doc=json.loads(path.read_text());doc['accepted']=True;path.write_text(json.dumps(doc))
                else:path.write_text(path.read_text()+'\n# changed\n')
                with self.assertRaisesRegex(ValueError,'QUALIFICATION_'):successor.verify(ROOT,output)

    def test_candidate_success_flag_does_not_replace_independent_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'kit'
            successor.construct(ROOT,output)
            with patch.object(successor,'_execute',return_value=([{'accepted':True}],{})):
                with self.assertRaisesRegex(ValueError,'COMPLETE_INDEPENDENT_BATCH'):successor.verify(ROOT,output)

    def test_unregistered_module_cannot_run_during_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'kit'
            successor.construct(ROOT,output)
            (output/'json.py').write_text("raise RuntimeError('unregistered module must never execute')")
            with self.assertRaisesRegex(ValueError,'QUALIFICATION_FILE_SET_CHANGED'):successor.verify(ROOT,output)

    def test_fair_controls_rebuild_or_reuse_and_tie(self):
        with tempfile.TemporaryDirectory() as directory:
            result=successor.comparison(ROOT,Path(directory)/'comparison')
            self.assertTrue(result['ordinary_equal_content_reuse_ties'])
            self.assertTrue(result['conventional_additional_resolved_case'])
            self.assertFalse(result['retained_method_advantage'])
            self.assertEqual({r['accepted_cases'] for r in result['arms']},{5})
            self.assertEqual(len(result['arms']),5)

    def test_explicit_cost_components_and_source_identity_required(self):
        with self.assertRaisesRegex(ValueError,'COMPLETE_ACTION_COST'):successor.plan(ROOT,{'packaging_execution':0})
        with tempfile.TemporaryDirectory() as directory:
            specification=successor.plan(ROOT)
            specification['artifact_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'CONSTRUCTION_SPECIFICATION'):successor.construct(ROOT,Path(directory)/'kit',specification=specification)

    def test_three_fresh_task_executions_are_accepted_and_costed_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'kit'
            specification=successor.construct(ROOT,output)
            result=successor.operate_tasks(ROOT,output)
            self.assertEqual(result['accepted_case_count'],3)
            self.assertEqual(result['total_task_cost_microUSD'],3_000_000)
            self.assertEqual(specification['quoted_construction_max_microUSD']+result['total_task_cost_microUSD'],5_100_000)
            self.assertEqual(len({r['request_sha256'] for r in result['tasks']}),3)
            self.assertEqual(result['tasks'][0]['result']['result']['plan']['objective'],[1,220])
            self.assertIsNotNone(result['tasks'][2]['result']['help'])
            with self.assertRaisesRegex(ValueError,'DISTINCT_REGISTERED_SUCCESSOR_TASKS'):successor.operate_tasks(ROOT,output,['quality-successor','quality-successor'])


if __name__=='__main__':unittest.main()
