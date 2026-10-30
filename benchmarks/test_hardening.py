import copy
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('frontier_hardened', ROOT/'human_frontier.py')
hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hf)


class BenchmarkHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT/'illustrative_cases.json').read_text())

    def rejects(self, path, value):
        data = copy.deepcopy(self.source)
        current = data
        for key in path[:-1]: current = current[key]
        current[path[-1]] = value
        with self.assertRaises(ValueError): hf.analyze(data)

    def test_usd_and_units_are_enforced(self):
        for path, value in [(['metadata','currency'],'CAD'), (['metadata','currency'],None),
            (['metadata','unit'],'EUR_per_job'), (['roles','writer','currency'],'EUR'),
            (['roles','writer','unit'],'USD_per_year'),
            (['models','gpt-6.1-sol','currency'],'CAD'),
            (['models','gpt-6.1-sol','unit'],'USD_per_token')]:
            with self.subTest(path=path, value=value): self.rejects(path,value)

    def test_all_nested_shapes_refused_as_value_errors(self):
        paths = [['metadata'],['roles'],['models'],['wage_burden'],['roles','writer'],
            ['models','gpt-6.1-sol'], ['cases',0,'role'], ['cases',0,'ai_non_model_costs'],
            ['cases',0,'autonomous_phases',0,'name'], ['cases',0,'autonomous_phases',0,'model']]
        for path in paths:
            for value in (None, [], True, 7):
                with self.subTest(path=path,value=value): self.rejects(path,value)

    def test_required_nested_numeric_fields(self):
        for path in (['roles','writer','wage_usd_per_hour'],
                     ['models','gpt-6.1-sol','input_usd_per_million'],
                     ['wage_burden','employer_cost_per_hour']):
            data=copy.deepcopy(self.source)
            current=data
            for key in path[:-1]: current=current[key]
            del current[path[-1]]
            with self.subTest(path=path), self.assertRaises(ValueError): hf.analyze(data)

    def test_zero_denominator_and_nonpositive_wage(self):
        self.rejects(['wage_burden','wage_salary_per_hour'],0)
        self.rejects(['roles','writer','wage_usd_per_hour'],0)

    def test_numeric_property_mutations(self):
        rng = random.Random(10430)
        paths = [['cases',0,'human_hours'], ['roles','writer','wage_usd_per_hour'],
                 ['models','gpt-6.1-sol','output_usd_per_million']]
        values = ['NaN','Infinity','-Infinity',True,None,{},[], '1e999999999',
                  '1e-999999999','9'*100, '-0.01', '1000000001']
        for _ in range(120):
            path,value=rng.choice(paths),rng.choice(values)
            with self.subTest(path=path,value=value): self.rejects(path,value)

    def test_cli_rejects_duplicate_json_and_dangling_output_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'duplicate.json'
            source.write_text('{"metadata":{},"metadata":{}}')
            target=root/'result.json'
            command=[sys.executable,str(ROOT/'human_frontier.py'),'--input',str(source),'--output',str(target)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,2)
            self.assertIn('Duplicate JSON field',result.stderr)
            self.assertFalse(target.exists())
            target.symlink_to(root/'missing')
            result=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,2)
            self.assertIn('Preserve prior output',result.stderr)
            self.assertTrue(target.is_symlink())

    def test_hosted_workflow_discovers_benchmark_assertions(self):
        workflow=(ROOT.parent/'.github/workflows/campaign.yml').read_text()
        self.assertIn("python -m unittest discover -s benchmarks -p 'test_*.py' -v",workflow)
