import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from .__main__ import write_result
from .runner import buyer, cases, experiment, plan_path
from .water import construct, conventional_milp
from .verify import verify, exhaustive_optimum
from mechanism_harness.core import digest

ROOT=Path(__file__).resolve().parents[1]

class BuyerTests(unittest.TestCase):
    def setUp(self):
        self.request=json.loads((ROOT/'omega/request.json').read_text())

    def test_complete_conventional_control_all_registered_cases(self):
        result=experiment(ROOT)
        self.assertEqual(result['case_count'],24)
        self.assertTrue(result['successor']['ordinary_equal_content_reuse_identical'])
        self.assertTrue(result['verdicts']['blue_sky'].startswith('STOP'))

    def test_delivered_primary_displaces_freshwater(self):
        result=buyer(self.request)
        self.assertEqual(result['certificate']['reuse_units'],6)
        self.assertEqual(result['interval_corners_checked'],16)
        self.assertEqual(result['model_api_calls'],0)

    def test_exhaustive_oracle_is_integer_optimum(self):
        proof=exhaustive_optimum(self.request)
        self.assertEqual(proof['objective'],[0,150])
        self.assertEqual(proof['allocations_exhausted'],256)

    def test_boolean_objective_is_not_an_integer_certificate(self):
        plan=construct(self.request)
        plan['objective'][0]=False
        with self.assertRaisesRegex(ValueError,'EXACT_INTEGER_OBJECTIVE'):verify(self.request,plan)

    def test_tampered_plan_fails_independent_checker(self):
        plan=construct(self.request)
        plan['allocation'][0][0]+=1
        with self.assertRaises(ValueError): verify(self.request,plan)

    def test_different_mission_never_inherits_proof(self):
        plan=construct(self.request)
        self.request['sources'][0]['upper_quality'][0]+=1
        with self.assertRaisesRegex(ValueError,'BINDING'): verify(self.request,plan)

    def test_source_refusal_is_not_overridden(self):
        self.request['sources'][0]['consent']=False
        self.assertEqual(construct(self.request)['status'],'MODEL_INFEASIBLE')
        self.assertEqual(conventional_milp(self.request)['status'],'MODEL_INFEASIBLE')

    def test_sink_refusal_is_not_overridden(self):
        self.request['sinks'][0]['consent']=False
        self.assertEqual(construct(self.request)['status'],'MODEL_INFEASIBLE')

    def test_worse_than_outside_cost_refuses(self):
        for source in self.request['sources']: source['unit_cost_cents']=1000
        self.assertEqual(construct(self.request)['status'],'MODEL_INFEASIBLE')

    def test_external_account_is_explicit_import_not_credential_execution(self):
        self.request['model_route']='buyer_owned_account_external'
        with self.assertRaisesRegex(ValueError,'PROPOSAL_FILE'): buyer(self.request)
        result=buyer(self.request,construct(self.request))
        self.assertTrue(result['certificate']['accepted'])
        self.assertEqual(result['pathway']['sequence'],['verify'])
        self.assertEqual(result['model_api_calls'],0)

    def test_resource_exhaustion_not_infeasibility(self):
        with self.assertRaisesRegex(RuntimeError,'RESOURCE_CHECKPOINT'): construct(self.request,max_states=1)

    def test_external_request_schema_validated(self):
        self.request['model_route']='buyer_owned_account_external'
        plan=construct(self.request)
        self.request['sources'][0]['upper_quality'][0]=-1
        plan['request_sha256']=digest(self.request)
        with self.assertRaises(ValueError): buyer(self.request,plan)

    def test_large_options_fail_bounded_without_false_infeasibility(self):
        self.request['sources'][0]['capacity']=1000000000
        self.request['sinks'][0]['demand']=1000000000
        with self.assertRaisesRegex(RuntimeError,'RESOURCE_CHECKPOINT'): construct(self.request,max_states=50)

    def test_arbitrary_integer_width_stops_before_machine_range_length(self):
        self.request['sources'][0]['capacity']=10**100
        self.request['sinks'][0]['demand']=10**100
        with self.assertRaisesRegex(RuntimeError,'RESOURCE_CHECKPOINT_NOT_INFEASIBILITY'):
            construct(self.request,max_states=50)
        with self.assertRaisesRegex(RuntimeError,'EXACT_ORACLE_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY'):
            exhaustive_optimum(self.request,max_candidates=50)

    def test_oracle_requires_positive_integer_budget(self):
        for budget in [0,-1,True,1.5]:
            with self.assertRaisesRegex(ValueError,'POSITIVE_CANDIDATE_BUDGET_REQUIRED'):
                exhaustive_optimum(self.request,max_candidates=budget)

    def test_corner_enumeration_resource_checkpoint(self):
        self.request['freshwater_cap']=6
        self.request['sources']=[dict(id='zero'+str(i),capacity=0,upper_quality=[0,0],unit_cost_cents=0,consent=True) for i in range(15)]
        with self.assertRaisesRegex(RuntimeError,'CORNER_RESOURCE_CHECKPOINT'): buyer(self.request)

    def test_negative_and_boolean_amounts_rejected(self):
        for value in [-1,True,1.2]:
            request=copy.deepcopy(self.request);request['freshwater_cap']=value
            with self.assertRaises(ValueError): construct(request)

    def test_independent_quality_failure(self):
        plan=construct(self.request)
        plan['allocation']=[[0,3],[3,0]]
        plan['objective']=[0,150]
        with self.assertRaisesRegex(ValueError,'QUALITY'):verify(self.request,plan)

class ResultRecoveryTests(unittest.TestCase):
    def test_identical_retry_preserves_completed_bytes_and_conflict_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'receipt.json'
            value={'accepted':True,'request':'fixture'}
            write_result(output,value)
            original=output.read_bytes(); inode=output.stat().st_ino
            write_result(output,value)
            self.assertEqual(output.read_bytes(),original)
            self.assertEqual(output.stat().st_ino,inode)
            with self.assertRaises(FileExistsError):write_result(output,{'accepted':False})
            self.assertEqual(output.read_bytes(),original)

    def test_process_exit_before_and_after_commit_can_be_retried(self):
        script='''import os, sys
from pathlib import Path
import omega.__main__ as module
real_link=module.os.link
def interrupted(source,destination):
    if sys.argv[2]=='after': real_link(source,destination)
    os._exit(17)
module.os.link=interrupted
module.write_result(Path(sys.argv[1]),{'accepted':True,'request':'fixture'})
'''
        for point in ['before','after']:
            with self.subTest(point=point),tempfile.TemporaryDirectory() as directory:
                output=Path(directory)/'receipt.json'
                result=subprocess.run([sys.executable,'-c',script,str(output),point],cwd=ROOT,check=False)
                self.assertEqual(result.returncode,17)
                self.assertEqual(output.exists(),point=='after')
                if output.exists():self.assertEqual(json.loads(output.read_text()),{'accepted':True,'request':'fixture'})
                write_result(output,{'accepted':True,'request':'fixture'})
                self.assertEqual(json.loads(output.read_text()),{'accepted':True,'request':'fixture'})

    def test_existing_symlink_is_not_followed_or_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'original.json'; output=Path(directory)/'receipt.json'
            target.write_text('private content')
            output.symlink_to(target)
            with self.assertRaises(FileExistsError):write_result(output,{'accepted':True})
            self.assertTrue(output.is_symlink())
            self.assertEqual(target.read_text(),'private content')

if __name__=='__main__': unittest.main()
