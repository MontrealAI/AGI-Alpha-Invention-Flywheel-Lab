"""Tests of static scenario arithmetic and truthfulness; no actual strategic calibration."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import pricing


class PortfolioPricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((HERE/'jobs.json').read_text())
        cls.jobs={x['id']:x for x in cls.data['jobs']}

    def test_exact_25_unique_opportunities(self):
        self.assertEqual(len(self.data['jobs']),25)
        self.assertEqual(len(self.jobs),25)
        self.assertGreaterEqual(len({x['sector'] for x in self.data['jobs']}),8)

    def test_no_empirical_conversion_or_proven_profit(self):
        result=pricing.evaluate_portfolio(self.data)
        self.assertEqual(result['actual_sales_usd'],0)
        self.assertEqual(result['commercial_flywheel'],'UNESTABLISHED')
        self.assertEqual(result['market_win_probabilities'],'UNCALIBRATED')
        self.assertTrue(all(q['status']!='ACTUAL_QUOTE' for q in result['jobs']))

    def test_all_prices_finite_and_cost_sensitive(self):
        result=pricing.evaluate_portfolio(self.data)
        for j in result['jobs']:
            if 'price_usd' in j:
                self.assertLessEqual(j['price_usd'],j['human_loaded_labor_proxy_usd']*1.06)
                self.assertGreater(j['price_usd'],0)
                self.assertGreater(j['expected_net_per_qualified_quote_usd'],0)
                self.assertGreaterEqual(j['model_win_probability'],0)
                self.assertLess(j['model_win_probability'],1)

    def test_optimal_is_not_guaranteed_win_or_fixed_discount(self):
        jobs=pricing.evaluate_portfolio(self.data)['jobs']
        self.assertTrue(any(abs(q.get('discount_from_human_loaded_labor_proxy_pct',5)-5)>5 for q in jobs))
        self.assertTrue(all(q.get('model_win_probability',0)<.99 for q in jobs))

    def test_strategy_optimizes_net_profit_not_win_fraction(self):
        j=self.jobs['rfp_response']; result=pricing.pick_price(j,self.data)
        self.assertGreater(result['expected_net_per_qualified_quote_usd'],result['human_anchor_expected_net_usd'])
        self.assertLess(result['price_usd'],result['human_anchor_95pct_usd'])
        self.assertGreater(result['model_win_probability'],0)

    def test_rival_changes_price_and_can_deter(self):
        j=self.jobs['rfp_response'];h=pricing.human_labor_proxy(j,self.data)
        c=j['ai_complete_won_job_cost_scenario_usd']+j['ai_onboarding_resource_cost_scenario_usd']
        sc=pricing.SCENARIOS[0]
        a=pricing.rival_best_response(.6*h,h,c,sc)
        b=pricing.rival_best_response(.9*h,h,c,sc)
        self.assertNotEqual(a['price'],b['price'])

    def test_no_bid_when_unprofitable_acquisition(self):
        j=copy.deepcopy(self.jobs['rfp_response'])
        j['ai_qualification_bid_cost_scenario_usd']=100_000
        self.assertEqual(pricing.pick_price(j,self.data)['status'],'NO_BID_IN_SCENARIO')

    def test_zero_human_hours_refused(self):
        j=copy.deepcopy(self.jobs['rfp_response']);j['human_hour_scenario']=0
        with self.assertRaises(ValueError):pricing.pick_price(j,self.data)

    def test_negative_or_nonfinite_cost_rejected(self):
        j=copy.deepcopy(self.jobs['software_bugfix']);j['ai_complete_won_job_cost_scenario_usd']=float('inf')
        with self.assertRaises(ValueError):pricing.pick_price(j,self.data)
        j['ai_complete_won_job_cost_scenario_usd']=-2
        with self.assertRaises(ValueError):pricing.pick_price(j,self.data)

    def test_boolean_numeric_refused(self):
        j=copy.deepcopy(self.jobs['rfp_response']);j['ai_complete_won_job_cost_scenario_usd']=True
        with self.assertRaises(ValueError):pricing.pick_price(j,self.data)

    def test_invalid_scenario_weights_refused(self):
        s=[dict(x) for x in pricing.SCENARIOS]
        s[0]['weight']=0.99
        with self.assertRaises(ValueError):pricing.pick_price(self.jobs['rfp_response'],self.data,s)

    def test_output_refuses_overwrite_and_preserves_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'quote.json'
            cmd=[sys.executable,str(HERE/'pricing.py'),'--output',str(out)]
            first=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
            self.assertEqual(first.returncode,0,first.stderr)
            original=out.read_bytes()
            self.assertEqual(json.loads(original)['actual_sales_usd'],0)
            second=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(out.read_bytes(),original)

    def test_source_trust_does_not_equal_real_demand(self):
        for job in self.data['jobs']:
            self.assertEqual(job['market_status'],'UNVALIDATED_COMPETITIVE_DEMAND')
            self.assertIn('NOT_METERED',job['cost_status'])
            self.assertNotIn('human_review_labor_usd',job)

    def test_our_buyer_probability_decreases_with_price_given_rival(self):
        h=1000;sc=pricing.SCENARIOS[0]
        p_low,_=pricing.choice_prices(300,400,h,sc)
        p_high,_=pricing.choice_prices(500,400,h,sc)
        self.assertGreater(p_low,p_high)

    def test_premium_human_proxy_not_enterprise_retail_price(self):
        m=self.data['metadata']
        self.assertIn('not an observed human retail price',pricing.evaluate_portfolio(self.data)['price_cap_scope'])
        self.assertEqual(m['onboarding_rule'].startswith('agent-model'),True)

    def test_all_source_roles_real(self):
        for j in self.data['jobs']:
            self.assertTrue(self.data['metadata']['wage_roles'][j['human_role']]['source'].startswith('https://www.bls.gov/'))

    def test_portfolio_duplicate_rejected(self):
        p=copy.deepcopy(self.data)
        p['jobs'][1]['id']=p['jobs'][0]['id']
        with self.assertRaises(ValueError):pricing.evaluate_portfolio(p)

if __name__=='__main__': unittest.main()

# Exact stored scenario output is an illustrative fixture, not an independent confirmation.
class PublishedReferenceTests(unittest.TestCase):
    def test_stored_scenario_recomputes_exactly(self):
        source=json.loads((HERE/'jobs.json').read_text())
        expected=json.loads((HERE/'reference_strategy_results.json').read_text())
        self.assertEqual(pricing.evaluate_portfolio(source),expected)

    def test_repeat_sensitivity_changes_price_objective(self):
        data=json.loads((HERE/'jobs.json').read_text())
        job=next(x for x in data['jobs'] if x['id']=='rfp_response')
        ret=pricing.pick_price(job,data)
        scenarios=[dict(x,repeat_probability=0,repeat_horizon=0) for x in pricing.SCENARIOS]
        single=pricing.pick_price(job,data,scenarios)
        self.assertNotEqual(ret['expected_net_per_qualified_quote_usd'],single['expected_net_per_qualified_quote_usd'])
        self.assertGreater(ret['expected_net_per_qualified_quote_usd'],single['expected_net_per_qualified_quote_usd'])

    def test_no_pure_equilibrium_claim(self):
        res=json.loads((HERE/'reference_strategy_results.json').read_text())
        self.assertTrue(all(x.get('strategic_equilibrium_claim')=='NONE' for x in res['jobs'] if 'price_usd' in x))

    def test_agent_onboarding_charged_per_won_job(self):
        data=json.loads((HERE/'jobs.json').read_text())
        job=next(x for x in data['jobs'] if x['id']=='rfp_response')
        a=pricing.pick_price(job,data)
        increased=json.loads(json.dumps(job))
        increased['ai_onboarding_resource_cost_scenario_usd']+=30
        b=pricing.pick_price(increased,data)
        self.assertLess(b['expected_net_per_qualified_quote_usd'],a['expected_net_per_qualified_quote_usd'])
