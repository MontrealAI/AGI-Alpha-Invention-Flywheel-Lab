# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import invent
from make_demo import make_demo


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = make_demo(Path(self.temp.name) / 'project')
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def change(self, name, transform):
        path = self.root / name
        data = json.loads(path.read_text())
        transform(data)
        path.write_text(json.dumps(data))

    def runner(self, source, payload, timeout):
        # Controlled test double, NEVER production execution of source.
        self.calls.append((source, payload, timeout))
        values, distance = payload['values'], payload['distance']
        answer = sum(abs(values[i]-values[j]) <= distance for i in range(len(values)) for j in range(i+1,len(values)))
        return answer, .01 if source == b'fast-fixture' else .1

    def candidate(self, content=b'fast-fixture'):
        path = self.root / 'proposal.py'
        path.write_bytes(content)
        return path

    def test_controlled_success(self):
        result = invent.evaluate(self.root, self.candidate(), self.runner)
        self.assertEqual(result['status'], 'HOLD') # complete other costs erase modeled savings
        self.assertTrue(result['performance_pass'])
        self.assertFalse(result['economic_scenario_pass'])
        self.assertIsNone(result['actual_revenue_usd'])

    def test_scenario_not_real_profit(self):
        self.change('contract.json', lambda d: d.update(annual_jobs=1000000000))
        result = invent.evaluate(self.root, self.candidate(), self.runner)
        self.assertEqual(result['status'], 'PASS_SCOPED')
        self.assertFalse(result['model_generation_verified'])
        self.assertEqual(result['actual_customers'], 0)

    def test_same_incumbent_cannot_claim_gain(self):
        result = invent.evaluate(self.root, self.root / 'candidate.py', self.runner)
        self.assertEqual(result['weighted_speedup'], 1)
        self.assertEqual(result['status'], 'HOLD')

    def test_expected_and_ids_not_sent_to_worker(self):
        invent.evaluate(self.root, self.candidate(), self.runner)
        self.assertEqual(len(self.calls), 24)
        self.assertTrue(all(set(c[1]) == {'values', 'distance'} for c in self.calls))

    def test_wrong_incumbent_rejects_entire_result(self):
        def wrong(source, payload, limit):
            result, seconds = self.runner(source,payload,limit)
            return (result if source == b'fast-fixture' else -99), seconds
        result = invent.evaluate(self.root,self.candidate(),wrong)
        self.assertEqual(result['status'],'HOLD')
        self.assertFalse(result['correctness_pass'])

    def test_wrong_candidate(self):
        def wrong(source, payload, limit):
            answer, seconds = self.runner(source,payload,limit)
            return (False if source == b'fast-fixture' else answer), seconds
        result = invent.evaluate(self.root,self.candidate(),wrong)
        self.assertFalse(result['correctness_pass']) # bool false != numeric zero

    def test_candidate_cannot_supply_timing_record_as_answer(self):
        result = invent.evaluate(self.root,self.candidate(),lambda *a: ({'median_ns': 0}, .1))
        self.assertFalse(result['correctness_pass'])

    def test_negative_timer_rejected(self):
        result = invent.evaluate(self.root,self.candidate(),lambda *a: (0,-1))
        self.assertEqual(result['status'],'HOLD')
        self.assertIn('execution_error',result)

    def test_timeout_stops_not_skips_case(self):
        def fail(*a): raise TimeoutError('timeout')
        result = invent.evaluate(self.root,self.candidate(),fail)
        self.assertEqual(result['cases'],[])
        self.assertEqual(result['status'],'HOLD')

    def test_oversized_integer_rejected(self):
        with self.assertRaises(ValueError): invent.number(10**400)

    def test_nonfinite_contract_rejected(self):
        self.change('contract.json',lambda d:d.update(annual_jobs=float('nan')))
        with self.assertRaises(ValueError): invent.freeze(self.root)

    def test_zero_workload_weight_rejected(self):
        self.change('heldout.json',lambda d:d[0].update(weight=0))
        with self.assertRaises(ValueError): invent.freeze(self.root)

    def test_duplicate_case_rejected(self):
        self.change('heldout.json',lambda d:d[1].update(id=d[0]['id']))
        with self.assertRaises(ValueError): invent.freeze(self.root)

    def test_boolean_repeat_rejected(self):
        self.change('contract.json',lambda d:d.update(repeats=True))
        with self.assertRaises(ValueError): invent.freeze(self.root)

    def test_symlink_rejected(self):
        path=self.root/'link.py'; path.symlink_to(self.root/'candidate.py')
        with self.assertRaises(ValueError): invent.read_bytes(path)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError): invent.loads('{"x":1,"x":2}')

    def test_mutations_after_freeze_not_used(self):
        original=(self.root/'incumbent.py').read_bytes()
        def mutate(source,payload,limit):
            (self.root/'incumbent.py').write_text('tampered')
            self.assertIn(source,(original,b'fast-fixture'))
            return self.runner(source,payload,limit)
        result=invent.evaluate(self.root,self.candidate(),mutate)
        self.assertEqual(result['inputs']['incumbent.py'],invent.sha(original))

    def test_missing_docker_fail_closed(self):
        with patch('invent.shutil.which',return_value=None):
            result=invent.evaluate(self.root,self.candidate())
        self.assertEqual(result['status'],'HOLD')
        self.assertIn('Docker unavailable',result['execution_error'])

    def test_generation_missing_codex_no_output(self):
        target=self.root/'out'
        with patch('invent.shutil.which',return_value=None):
            with self.assertRaises(RuntimeError): invent.propose(self.root,target)
        self.assertFalse(target.exists())

    def test_output_limit_parent(self):
        with self.assertRaises(ValueError):
            invent.bounded_process([sys.executable,'-c','print("x"*2000000)'],b'',5)

    def test_search_records_missing_runtime_without_inference(self):
        target=self.root/'search'
        with patch('invent.DockerRunner',side_effect=RuntimeError('absent')), patch('invent.propose') as model:
            result=invent.search(self.root,target,2)
        self.assertEqual(result['status'],'HOLD')
        model.assert_not_called()
        self.assertTrue((target/'SEARCH.json').is_file())

    def test_search_never_labels_selected_candidate_qualified(self):
        def generate(project,target,model,feedback,provider_timeout):
            target.mkdir()
            (target/'candidate.py').write_bytes(b'fast-fixture')
            return {'candidate':str(target/'candidate.py')}
        with patch('invent.DockerRunner',return_value=self.runner), patch('invent.propose',side_effect=generate):
            result=invent.search(self.root,self.root/'search',2)
        self.assertEqual(result['status'],'SELECTED_NOT_QUALIFIED')
        self.assertTrue(result['fresh_evaluator_cases_required'])
        self.assertEqual(len(result['trials']),2)

    def test_search_records_model_failure_no_fallback(self):
        with patch('invent.DockerRunner',return_value=self.runner), patch('invent.propose',side_effect=RuntimeError('blocked')):
            result=invent.search(self.root,self.root/'search',2)
        self.assertEqual(result['status'],'HOLD')
        self.assertEqual(len(result['trials']),1)
        self.assertFalse((self.root/'search'/'candidate.py').exists())


    def test_parent_real_timer(self):
        output, seconds=invent.bounded_process([sys.executable,'-c','import time;time.sleep(.03);print(1)'],b'',5)
        self.assertEqual(output,b'1\n'); self.assertGreaterEqual(seconds,.03)


if __name__ == '__main__': unittest.main()
