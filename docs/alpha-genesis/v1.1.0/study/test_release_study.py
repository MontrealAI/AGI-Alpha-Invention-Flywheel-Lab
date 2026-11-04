"""Adversarial checks for the actual emitted artifacts and reference calculations."""
import ast
import csv
from fractions import Fraction as F
import importlib.util
from itertools import product, permutations
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import companion as c

ROOT=Path(__file__).resolve().parents[1]

class ReleaseStudy(unittest.TestCase):
    def test_control_does_not_call_candidate(self):
        with patch.object(c, 'replay', side_effect=RuntimeError('candidate disabled')):
            result=c.conventional_schedule(c.REQUIREMENTS,c.RELEASES)
        self.assertEqual(result['evaluations'],5)
    def test_control_no_shared_result_object(self):
        result=c.replay_study()
        self.assertIsNot(result['selective'],result['conventional_dependency_control'])
        result['selective']['completed'].clear()
        self.assertEqual(len(result['conventional_dependency_control']['completed']),5)
    def test_control_empty_releases(self):
        self.assertEqual(c.conventional_schedule({'a':{'x'}},[])['evaluations'],0)
    def test_control_empty_requirements(self):
        a=c.replay('dependency',{'a':set()},[{'x'}]); b=c.conventional_schedule({'a':set()},[{'x'}])
        self.assertEqual(a['trace'],b['trace'])
    def test_control_duplicate_releases(self):
        req={'a':{'x'},'b':{'x','y'}};events=[{'x'},{'x'},{'y'}]
        self.assertEqual(c.replay('dependency',req,events)['trace'],c.conventional_schedule(req,events)['trace'])
    def test_control_unavailable_dependency(self):
        self.assertEqual(c.conventional_schedule({'a':{'z'}},[{'x'}])['completed'],[])
    def test_control_all_two_capability_sequences(self):
        req={'empty':set(),'x':{'x'},'y':{'y'},'both':{'x','y'}}
        for event_ids in product(range(4),repeat=4):
            events=[{v for j,v in enumerate(('x','y')) if k&(1<<j)} for k in event_ids]
            self.assertEqual(c.replay('dependency',req,events)['trace'],c.conventional_schedule(req,events)['trace'])
    def test_announcement_not_access(self):
        r=c.audit_access_trace({'a':{'x'}},[{'announced':['x']}])
        self.assertEqual(r[0]['eligible_now'],[])
    def test_revocation_suspends_not_erases(self):
        r=c.audit_access_trace({'a':{'x'}},[{'add':['x']},{'remove':['x']}])
        self.assertEqual(r[-1]['historically_qualified'],['a'])
        self.assertEqual(r[-1]['eligible_now'],[])
        self.assertEqual(r[-1]['suspended'],['a'])
    def test_access_restored_history_not_new(self):
        r=c.audit_access_trace({'a':{'x'}},[{'add':['x']},{'remove':['x']},{'add':['x']}])
        self.assertEqual(r[-1]['eligible_now'],['a']);self.assertEqual(r[-1]['newly_qualified'],[])
    def test_contradictory_event_rejected(self):
        with self.assertRaises(ValueError):c.audit_access_trace({'a':{'x'}},[{'add':['x'],'remove':['x']}])
    def test_unknown_removal_is_noop(self):
        r=c.audit_access_trace({'a':{'x'}},[{'remove':['not_present']}]);self.assertEqual(r[-1]['accessible'],[])
    def test_incomplete_index_misses_real_route(self):
        r=c.adversarial_replay_study()['omitted_route']
        self.assertEqual(r['recorded_index_selected'],[]);self.assertEqual(r['actual_supplied_routes_allow'],['task'])
    def test_replay_positive_net_saving(self):self.assertEqual(c.replay_margin(25,5,1,3,0),17)
    def test_replay_overhead_reverses_saving(self):self.assertEqual(c.replay_margin(25,5,1,25,0),-5)
    def test_replay_missed_route_reverses_saving(self):self.assertEqual(c.replay_margin(25,5,1,3,30),-13)
    def test_replay_negative_cost_rejected(self):
        with self.assertRaises(ValueError):c.replay_margin(25,5,1,-3,0)
    def test_replay_fractional_count_rejected(self):
        with self.assertRaises(ValueError):c.replay_margin(2.5,1,1,0,0)
    def test_malformed_matrix_rejected(self):
        with self.assertRaises(ValueError):c.inverse2(((1,2,3),(3,4,5)))
    def test_malformed_vector_rejected(self):
        with self.assertRaises(ValueError):c.apply(((1,0),(0,1)),(1,))
    def test_float_input_rejected(self):
        with self.assertRaises(ValueError):c.funding_need([0.1])
    def test_boolean_input_rejected(self):
        with self.assertRaises(ValueError):c.paths(n=True)
    def test_invalid_fraction_rejected(self):
        with self.assertRaises(ValueError):c.exact('1/0')
    def test_fractional_cash_reserve_schedule(self):
        self.assertEqual(c.funding_need(['-1/3','1/4'],['1/10','1/2','0']),F(5,6))
    def test_empty_cash_schedule(self):
        self.assertEqual(c.funding_need([]),0);self.assertEqual(c.funding_need([],['3/2']),F(3,2))
    def test_negative_reserve_rejected(self):
        with self.assertRaises(ValueError):c.funding_need([],[-1])
    def test_study_invariants_not_assert_statements(self):
        tree=ast.parse((ROOT/'study'/'companion.py').read_text())
        self.assertFalse(any(isinstance(n,ast.Assert) for n in ast.walk(tree)))
    def test_require_survives_optimized_python(self):
        result=subprocess.run([sys.executable,'-O','-c',"import companion; companion.require(False, 'sentinel')"],cwd=ROOT/'study',capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('sentinel',result.stderr)
    def test_emitted_observer_executes_exactly(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'new';c.emit_results(out)
            spec=importlib.util.spec_from_file_location('emitted',out/'compiled_observer.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            for x,y in product(range(-5,6),repeat=2):
                self.assertEqual(module.estimate(str(x),str(y)),(F(x+y,2),F(x-y,2)))
            plan=json.loads((out/'measurement_plan.json').read_text())
            self.assertEqual(plan['rows'],[['1','1'],['1','-1']])
            with (out/'lag.csv').open() as f: self.assertEqual(len(list(csv.DictReader(f))),6)
    def test_existing_output_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'keep.txt';marker.write_text('unchanged')
            with self.assertRaises(ValueError):c.emit_results(Path(folder))
            self.assertEqual(marker.read_text(),'unchanged')
    def test_output_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'alias';p.symlink_to(Path(folder)/'missing',target_is_directory=True)
            with self.assertRaises(ValueError):c.emit_results(p)
    def test_generated_files_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a',Path(folder)/'b';c.emit_results(a);c.emit_results(b)
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},{p.name:p.read_bytes() for p in b.iterdir()})

if __name__=='__main__':unittest.main()
