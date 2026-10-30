import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import pricing


class PortfolioInputHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((HERE/'jobs.json').read_text())
        cls.job=next(x for x in cls.source['jobs'] if x['id']=='rfp_response')

    def rejects(self,path,value):
        data=copy.deepcopy(self.source)
        current=data
        for key in path[:-1]:current=current[key]
        current[path[-1]]=value
        with self.assertRaises(ValueError):pricing.evaluate_portfolio(data)

    def test_non_usd_and_incompatible_units_refused(self):
        for path,value in [(['metadata','currency'],'CAD'),(['metadata','currency'],None),
            (['metadata','unit'],'EUR_per_job'),(['metadata','wage_loading','currency'],'EUR'),
            (['metadata','wage_roles','technical_writer','currency'],'CAD'),
            (['metadata','wage_roles','technical_writer','unit'],'USD_per_year'),
            (['jobs',0,'currency'],'CAD')]:
            with self.subTest(path=path,value=value):self.rejects(path,value)

    def test_all_malformed_nested_roles_and_unsupported_models_are_value_errors(self):
        for path in [['metadata'],['metadata','wage_roles'],['metadata','wage_loading'],
            ['metadata','wage_roles','technical_writer'],['jobs'],['jobs',0],
            ['jobs',0,'portfolio_scores_1_to_5'],['metadata','models']]:
            for value in (None,[],True,7,{}):
                with self.subTest(path=path,value=value):self.rejects(path,value)

    def test_missing_nested_fields_and_unknown_roles_are_value_errors(self):
        for path in [['metadata','wage_loading','private_industry_wage_usd'],
            ['metadata','wage_roles','technical_writer','median_hourly_usd'],
            ['jobs',0,'human_role']]:
            data=copy.deepcopy(self.source)
            current=data
            for key in path[:-1]:current=current[key]
            del current[path[-1]]
            with self.subTest(path=path),self.assertRaises(ValueError):pricing.evaluate_portfolio(data)
        self.rejects(['jobs',0,'human_role'],'invented role')

    def test_numeric_mutations_never_escape_as_untyped_errors(self):
        rng=random.Random(17030)
        paths=[['jobs',0,'human_hour_scenario'],['jobs',0,'ai_complete_won_job_cost_scenario_usd'],
            ['metadata','wage_roles','technical_writer','median_hourly_usd'],
            ['metadata','wage_loading','private_industry_wage_usd']]
        values=[True,None,[],{},'1',float('nan'),float('inf'),-1,10**400]
        for _ in range(80):
            path,value=rng.choice(paths),rng.choice(values)
            with self.subTest(path=path,value=repr(value)):self.rejects(path,value)
        self.rejects(['metadata','wage_loading','private_industry_wage_usd'],0)

    def test_malformed_scenarios_are_value_errors(self):
        for value in (None,{},[],[None],[{}],[True]):
            with self.subTest(value=value),self.assertRaises(ValueError):
                pricing.pick_price(self.job,self.source,value)
        for name,value in [('collect_prob',-1),('collect_prob',1.1),('accept_prob',True),
            ('temperature',0),('temperature',float('inf')),('repeat_horizon',2.5),
            ('repeat_probability',float('nan')),('weight',True),('id',[])]:
            scenarios=[dict(s) for s in pricing.SCENARIOS]
            scenarios[0][name]=value
            with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                pricing.pick_price(self.job,self.source,scenarios)
        scenarios=[dict(s) for s in pricing.SCENARIOS]
        del scenarios[0]['collect_prob']
        with self.assertRaises(ValueError):pricing.pick_price(self.job,self.source,scenarios)

    def test_zero_collection_or_acceptance_has_finite_no_bid(self):
        for name in ('collect_prob','accept_prob'):
            scenarios=[dict(s,**{name:0}) for s in pricing.SCENARIOS]
            result=pricing.pick_price(self.job,self.source,scenarios)
            self.assertEqual(result['status'],'NO_BID_IN_SCENARIO')
            self.assertEqual(result['expected_net_per_qualified_quote_usd'],0)
            rival=pricing.rival_best_response(100,200,10,scenarios[0])
            self.assertIsNone(rival['price'])
            self.assertEqual(rival['profit'],0)

    def test_direct_public_helpers_validate_inputs(self):
        sc=pricing.SCENARIOS[0]
        for call in [lambda:pricing.choice_prices(10,20,None,sc),
            lambda:pricing.choice_prices('10',20,100,sc),
            lambda:pricing.rival_best_response(10,100,2,None),
            lambda:pricing.evaluate_offer(10,100,2,1,{}),
            lambda:pricing.expected_repeat_deliveries(10,0,sc),
            lambda:pricing.price_candidates(1,2,2.5),
            lambda:pricing.price_candidates(False,2)]:
            with self.assertRaises(ValueError):call()

    def test_research_scope_and_unsupported_calibration_refused(self):
        self.rejects(['metadata','claim'],'OBSERVED_COMMERCIAL_SUCCESS')
        self.rejects(['metadata','all_commercial_outcomes'],'GO')
        self.rejects(['jobs',0,'market_status'],'OBSERVED_ACCEPTED_DEMAND')
        self.rejects(['metadata','models'],{'fake':{'input_usd_per_million':0}})

    def test_cli_duplicate_json_and_dangling_output_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.json';target=root/'out.json'
            source.write_text('{"metadata":{},"metadata":{},"jobs":[]}')
            command=[sys.executable,str(HERE/'pricing.py'),'--input',str(source),'--output',str(target)]
            result=subprocess.run(command,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,2)
            self.assertIn('Duplicate JSON field',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertFalse(target.exists())
            target.symlink_to(root/'missing')
            result=subprocess.run(command,capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,2)
            self.assertIn('Refuse overwrite',result.stderr)
            self.assertTrue(target.is_symlink())
