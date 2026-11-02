import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from research.blue_sky064.probe import (FIXTURE_SHA256,REGISTRATION_HASHES,bound_json,calibration_consistency,coefficient_box,downloaded_author_forward,load_inputs,mixed_composition,monotonic_obstruction,scalar_forward,formula_vector_forward,source_curve_holdout)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'research/blue_sky064'
REGISTRATIONS=ROOT/'campaign/blue-sky-064/friction-probe'


class BlueSkyPrerequisiteTests(unittest.TestCase):
    def test_frozen_fixture_registration_and_attribution(self):
        fixture,regs=load_inputs()
        self.assertEqual(fixture['license'],'CC-BY-4.0')
        self.assertEqual(len(fixture['figure4']['published_experimental_static']),15)
        self.assertEqual(regs['REGISTRATION.json']['source_model_probe']['profile_seed'],640112)
        self.assertEqual(regs['MIXED_REGISTRATION.json']['necessary_construction_target']['increase_in_static_dynamic_ratio_at_least'],.05)

    def test_tampered_fixture_or_acceptance_contract_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);fixture=directory/'public_calibration.json'
            shutil.copyfile(SOURCE/'public_calibration.json',fixture)
            parsed=json.loads(fixture.read_text());parsed['figure4']['published_experimental_static'][0][1]+=1
            fixture.write_text(json.dumps(parsed))
            with self.assertRaisesRegex(ValueError,'BYTES_CHANGED'):bound_json(fixture,FIXTURE_SHA256)
            for name in REGISTRATION_HASHES:shutil.copyfile(REGISTRATIONS/name,directory/name)
            path=directory/'MIXED_REGISTRATION.json';registration=json.loads(path.read_text());registration['necessary_construction_target']['increase_in_static_dynamic_ratio_at_least']=0
            path.write_text(json.dumps(registration))
            with self.assertRaisesRegex(ValueError,'BYTES_CHANGED'):load_inputs(registration_dir=directory)

    def test_scalar_hertz_replay_matches_closed_form_known_contact(self):
        genes=np.array([[1.,1.],[1.,1.]])
        force,normal=scalar_forward(genes,3)
        np.testing.assert_allclose(force,[0,.5,1],rtol=0,atol=1e-15)
        np.testing.assert_allclose(normal,[0,.5**1.5,1],rtol=0,atol=1e-15)
        for actual,expected in zip(formula_vector_forward(genes,3),(force,normal)):np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-15)

    def test_exact_obstruction_does_not_confuse_optimizer_failure(self):
        result=monotonic_obstruction([.02,.04,.06,.08,.10,.12],[.03,.07,.11,.13,.09,.05],.005)
        self.assertAlmostEqual(result['uniform_error_lower_bound'],.04)
        self.assertTrue(result['impossible_in_increasing_hertz_grammar'])
        self.assertFalse(monotonic_obstruction([0,1,2],[0,1,2],0)['impossible_in_increasing_hertz_grammar'])
        with self.assertRaises(ValueError):monotonic_obstruction([1,0],[1,2],.1)

    def test_original_published_point_holdout_is_not_retuned(self):
        fixture,_=load_inputs();actual=source_curve_holdout(fixture)
        frozen=json.loads((REGISTRATIONS/'RESULT.json').read_text())['published_curve_calibration']
        for key in ['fitted_nonnegative_scale','heldout_rmse','heldout_max_abs_error']:self.assertAlmostEqual(actual[key],frozen[key],places=14)
        self.assertEqual((actual['train_count'],actual['holdout_count']),(8,7))

    def test_nominal_mixed_function_does_not_override_uncertainty_failure(self):
        fixture,regs=load_inputs();result=mixed_composition(fixture,regs['MIXED_REGISTRATION.json'])
        self.assertTrue(result['nominal_function_pass'])
        self.assertFalse(result['interval_function_pass'])
        self.assertAlmostEqual(result['nominal_ratio_increase'],.17212125749297225,places=12)
        self.assertLess(result['independent_interval_worst_ratio_increase'],0)
        self.assertIn('NOT_ESTABLISHED',result['physical_transfer'])

    def test_source_discrepancy_is_preserved_and_interval_math_has_known_boundary(self):
        fixture,_=load_inputs();result=calibration_consistency(fixture)
        failed=[r for r in result['results'] if not r['consistent_without_extra_discrepancy']]
        self.assertEqual(len(failed),3)
        self.assertAlmostEqual(next(r for r in failed if r['family']=='Batch2_R1543' and r['phase']=='d')['minimum_extra_relative_force_discrepancy'],.08164536001900621,places=12)
        points=[(1,0,1,0),(1,0,2,0)]
        lo,hi=coefficient_box(points,1/3);self.assertAlmostEqual(lo,hi)
        lo,hi=coefficient_box(points,.3);self.assertGreater(lo,hi)
        with self.assertRaises(ValueError):coefficient_box([(0,1,1,0)])

    def test_unpinned_author_code_never_executes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'author.py';path.write_text('raise RuntimeError("must not execute")')
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):downloaded_author_forward(path)

    def test_one_cli_runs_offline_in_a_clean_minimal_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir();target=root/'research/blue_sky064';target.parent.mkdir()
            shutil.copytree(SOURCE,target,ignore=shutil.ignore_patterns('__pycache__'))
            registered=root/'campaign/blue-sky-064/friction-probe';registered.mkdir(parents=True)
            for name in REGISTRATION_HASHES:shutil.copyfile(REGISTRATIONS/name,registered/name)
            output=Path(temp)/'output'
            result=subprocess.run([sys.executable,'-m','research.blue_sky064','--output',str(output)],cwd=root,text=True,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((output/'RESULT.json').read_text())
            self.assertEqual(report['forward_replay']['profiles'],32)
            self.assertIsNone(report['forward_replay']['downloaded_author_code_max_absolute_difference'])
            self.assertLess(report['forward_replay']['scalar_vector_formula_max_absolute_difference'],1e-12)
            self.assertEqual(report['blue_sky_verdict'],'HOLD_COMPLETE_ALTERNATIVES_BENEFICIARY_AND_PHYSICAL_TRANSFER_UNRESOLVED')
            self.assertFalse(report['mixed_composition']['interval_function_pass'])
            second=subprocess.run([sys.executable,'-m','research.blue_sky064','--output',str(output)],cwd=root,text=True,capture_output=True,timeout=10)
            self.assertNotEqual(second.returncode,0)
            self.assertIn('NEW_REGULAR_ABSOLUTE_OUTPUT_REQUIRED',second.stderr)


if __name__=='__main__':unittest.main()
