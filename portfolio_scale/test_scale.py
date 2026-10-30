"""Regression tests for claims, input guards, strategic outside options and scale arithmetic."""
from __future__ import annotations
import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from portfolio_scale import engine,bundles

ROOT=Path(__file__).resolve().parent

class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'universe.json').read_text())
        cls.sample=cls.source['jobs'][0]

    def test_candidate_count_and_distinct_families(self):
        self.assertEqual(len(self.source['jobs']),160)
        self.assertEqual(len({x['family'] for x in self.source['jobs']}),20)

    def test_launch_claims_not_inferred(self):
        output=engine.offer_pricing(self.sample,self.source,engine.SEGMENTS[0],engine.TIERS[0])
        self.assertFalse(output['launch_eligible'])
        self.assertFalse(output['quality_verified'])
        self.assertFalse(output['market_quote_authorized'])

    def test_sufficiently_broad_portfolio_without_arbitrary_25_cap(self):
        out=engine.evaluate_portfolio(self.source)
        self.assertEqual(out['service_types'],160)
        self.assertEqual(out['scenario_offer_variants'],1280)
        self.assertEqual(out['actual_collected_revenue'],0)
        self.assertEqual(out['observed_commercial_flywheel'],'UNESTABLISHED')

    def test_more_than_160_jobs_is_not_refused(self):
        data=copy.deepcopy(self.source)
        extra=copy.deepcopy(data['jobs'][0]);extra['id']='future_mechanism_new_service'
        data['jobs'].append(extra)
        engine.validate(data)
        self.assertEqual(len(data['jobs']),161)

    def test_does_not_accept_duplicate_job(self):
        data=copy.deepcopy(self.source);data['jobs'].append(copy.deepcopy(data['jobs'][0]))
        with self.assertRaises(ValueError):engine.validate(data)

    def test_wrong_currency_or_pseudovalid_data_held(self):
        data=copy.deepcopy(self.source);data['jobs'][0]['quality_verified']=True
        with self.assertRaises(ValueError):engine.validate(data)
        data=copy.deepcopy(self.source);data['actual_jobs_performed']=1
        with self.assertRaises(ValueError):engine.validate(data)

    def test_risky_work_not_first_wave(self):
        data=copy.deepcopy(self.source)
        risk=[j for j in data['jobs'] if j['risk']=='APPROVAL_REQUIRED']
        self.assertGreater(len(risk),0)
        self.assertTrue(all(not j['first_wave_eligible'] for j in risk))
        risk[0]['first_wave_eligible']=True
        with self.assertRaises(ValueError):engine.validate(data)

    def test_invalid_token_budget_or_wage_refused(self):
        for val in [float('nan'),float('inf'),-1,True]:
            data=copy.deepcopy(self.source);data['jobs'][0]['autonomous_attempt_cost_hypothesis_usd']=val
            with self.subTest(val=repr(val)),self.assertRaises(ValueError):engine.validate(data)

    def test_price_is_not_win_rate_optimizer(self):
        row=engine.offer_pricing(self.sample,self.source,engine.SEGMENTS[1],engine.TIERS[0])
        self.assertNotEqual(row['quote_ratio_to_human_labor_proxy'],.05)
        self.assertGreaterEqual(row['expected_value_per_qualified_lead_usd'],0)

    def test_rival_can_refuse_unprofitable_market(self):
        sc=dict(engine.SCENARIOS[0])
        result=engine.rival_response(200,80,1000,sc)
        self.assertIsNone(result['price'])
        self.assertEqual(result['net'],0)

    def test_seller_rationally_refuses_worse_than_no_bid(self):
        data=copy.deepcopy(self.source)
        row=copy.deepcopy(data['jobs'][0]);row['autonomous_attempt_cost_hypothesis_usd']=10000
        choice=engine.offer_pricing(row,data,engine.SEGMENTS[1],engine.TIERS[0])
        self.assertEqual(choice['decision'],'NO_BID_IN_SCENARIOS')
        self.assertIsNone(choice['price_usd'])

    def test_unknown_probability_does_not_promote_a_sale(self):
        sc=dict(engine.SCENARIOS[0]);sc['accept']=1.1
        with self.assertRaises(ValueError):engine.offer_pricing(self.sample,self.source,engine.SEGMENTS[0],engine.TIERS[0],[sc])

    def test_human_cost_and_ai_cost_both_positive(self):
        q=engine.offer_pricing(self.sample,self.source,engine.SEGMENTS[0],engine.TIERS[0])
        self.assertGreater(q['human_loaded_labor_scenario_usd'],0)
        self.assertGreater(q['ai_attempt_resource_scenario_usd'],0)
        self.assertGreater(q['ai_onboarding_resource_scenario_usd'],0)

    def test_equal_quality_ai_price_war_is_adverse(self):
        a=dict(engine.SCENARIOS[0]);b=dict(engine.SCENARIOS[1])
        h,c=800,45
        x=engine.quote_evaluation(600,h,c,3,2,a)
        y=engine.quote_evaluation(600,h,c,3,2,b)
        self.assertGreater(x['net'],y['net'])

    def test_no_purchase_can_win(self):
        sc=dict(engine.SCENARIOS[3]);sc['no_purchase_cost']=.001
        win,_=engine.soft_choice(500,200,800,sc)
        self.assertLess(win,.01)

    def test_no_revenue_target_cap(self):
        r=engine.target_math([1e9,1e10,1e11,1e12],[1e5])
        self.assertEqual([x['fully_paid_active_customers_required'] for x in r],[10000,100000,1000000,10000000])
        self.assertTrue(all(x['time_to_target'].startswith('UNIDENTIFIABLE') for x in r))

    def test_target_nonfinite_refused(self):
        for n in [0,-1,float('inf'),float('nan'),True]:
            with self.subTest(n=repr(n)),self.assertRaises(ValueError):engine.target_math([n],[1e5])

    def test_twelve_bundle_hypotheses(self):
        result=bundles.evaluate_programs(self.source)
        self.assertEqual(len(result['sample_enterprise_programs']),12)
        self.assertEqual(result['observed_customers'],0)
        self.assertEqual(result['annualized_actual_revenue'],0)
        self.assertTrue(all(x['annualized_scale_is_not_earned_revenue'] for x in result['sample_enterprise_programs']))

    def test_bundle_must_not_double_count(self):
        result=bundles.evaluate_programs(self.source)
        self.assertIn('NEVER add bundle + component revenue',result['accounting_policy'])

    def test_bundle_invalid_volume_refused(self):
        for v in [0,-1,True,3.1]:
            with self.subTest(v=v),self.assertRaises(ValueError):bundles.evaluate_programs(self.source,monthly_units_per_family=v)

    def test_cli_nonoverwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'report.json'
            cmd=[sys.executable,str(ROOT/'engine.py'),'--output',str(target)]
            one=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
            self.assertEqual(one.returncode,0,one.stderr)
            prev=target.read_bytes()
            two=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(two.returncode,0)
            self.assertEqual(target.read_bytes(),prev)

    def test_fixed_reference_snapshot(self):
        reference=json.loads((ROOT/'reference_summary.json').read_text())
        self.assertEqual(reference['source_sha256'],engine.digest(self.source))
        self.assertEqual(reference['scenario_offer_variants'],1280)
        current=engine.evaluate_portfolio(self.source)
        self.assertEqual(reference['all_offers_sha256'],engine.digest(current['all_offers']))
        for x in reference['top_exploratory_offers']:
            self.assertTrue(x['decision']=='ILLUSTRATIVE_PRICE_ONLY')
            self.assertFalse(x['market_quote_authorized'])

    def test_readonly_no_external_resources(self):
        text=(ROOT/'engine.py').read_text()+(ROOT/'bundles.py').read_text()
        self.assertNotIn('requests.',text)
        self.assertNotIn('subprocess.',text)
        self.assertNotIn('http.client',text)

if __name__=='__main__':unittest.main()
