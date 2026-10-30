"""Finite planner regressions. Fixtures do not qualify market or physical results."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from portfolio_scale.transformational import choose, read_json

ROOT = Path(__file__).resolve().parent


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.universe = json.loads((ROOT/'universe.json').read_text())
        self.request = json.loads((ROOT/'transformational_example.json').read_text())

    def run_plan(self):
        return choose(self.request, self.universe)

    def test_existing_portfolio_is_used(self):
        self.assertEqual(len(self.universe['jobs']), 160)
        self.assertIn('fixed_capability_delivery', self.run_plan()['selected'])

    def test_complements_can_beat_individual_tools(self):
        output = self.run_plan()
        self.assertEqual(output['selected'], ['enabled_delivery', 'fixed_capability_delivery',
                                              'independent_checker', 'measurement_instrument'])
        self.assertEqual(output['cost'], 700_000_000)
        self.assertEqual(output['joint_benefits'], ['paired_instrument_value'])

    def test_unknown_research_is_not_fabricated_return(self):
        output = self.run_plan()
        self.assertEqual(output['unknown_return_actions'], ['unresolved_energy_research'])
        self.assertNotIn('unresolved_energy_research', output['selected'])

    def test_no_forced_invention(self):
        self.request['synergies'] = []
        self.assertEqual(self.run_plan()['selected'], ['fixed_capability_delivery'])

    def test_seed_only_cannot_fund_continuation(self):
        self.request['funding']['unrestrictedEarned'] = 0
        self.assertEqual(self.run_plan()['selected'], [])

    def test_available_cash_caps_earnings(self):
        self.request['funding']['available'] = 100_000_000
        self.assertLessEqual(self.run_plan()['cost'], 100_000_000)

    def test_authorized_allocation_caps_plan(self):
        self.request['funding']['authorized_allocation'] = 0
        self.assertEqual(self.run_plan()['decision'], 'RETAIN_CASH')

    def test_future_receipts_do_not_finance_upfront_cost(self):
        self.request['funding']['unrestrictedEarned'] = 1
        self.assertEqual(self.run_plan()['selected'], [])

    def test_unknown_funding_is_not_zero(self):
        self.request['funding']['available'] = None
        self.assertEqual(self.run_plan()['decision'], 'UNKNOWN_FUNDING')

    def test_unapproved_actions_never_selected(self):
        self.assertNotIn('unapproved_physical_action', self.run_plan()['selected'])

    def test_simulation_cannot_become_observed(self):
        self.request['scope'] = 'OBSERVED'
        with self.assertRaises(ValueError): self.run_plan()

    def test_currency_mismatch_refused(self):
        self.request['currency'] = 'USD'
        with self.assertRaises(ValueError): self.run_plan()

    def test_boolean_is_not_money(self):
        self.request['funding']['available'] = True
        with self.assertRaises(ValueError): self.run_plan()

    def test_float_money_refused(self):
        self.request['actions'][0]['cost'] = .5
        with self.assertRaises(ValueError): self.run_plan()

    def test_unknown_catalog_service_refused(self):
        self.request['actions'][0]['catalog_id'] = 'unrelated-service'
        with self.assertRaises(ValueError): self.run_plan()

    def test_missing_dependency_refused(self):
        self.request['actions'][0]['requires'] = ['missing']
        with self.assertRaises(ValueError): self.run_plan()

    def test_circular_dependency_refused(self):
        self.request['actions'][0]['requires'] = ['discounted_same_delivery']
        self.request['actions'][1]['requires'] = ['fixed_capability_delivery']
        with self.assertRaises(ValueError): self.run_plan()

    def test_mutual_exclusion_avoids_two_sales_of_same_order(self):
        chosen = self.run_plan()['selected']
        self.assertFalse({'fixed_capability_delivery','discounted_same_delivery'} <= set(chosen))

    def test_duplicate_joint_benefit_refused(self):
        self.request['synergies'] *= 2
        with self.assertRaises(ValueError): self.run_plan()

    def test_scenario_weights_required(self):
        self.request['scenarios']['stress'] = 1
        with self.assertRaises(ValueError): self.run_plan()

    def test_missing_adverse_scenario_refused(self):
        del self.request['actions'][0]['cash_returns']['stress']
        with self.assertRaises(ValueError): self.run_plan()

    def test_own_criteria_cannot_be_injected(self):
        self.request['success'] = True
        with self.assertRaises(ValueError): self.run_plan()

    def test_downside_limit_can_reject_high_mean_offer(self):
        self.request['synergies'] = []
        self.request['actions'] = self.request['actions'][:1]
        self.request['actions'][0]['cash_returns'] = {'ordinary':1_000_000_000,'competition':0,'stress':0}
        self.request['worst_loss_limit'] = 0
        self.assertEqual(self.run_plan()['decision'], 'RETAIN_CASH')

    def test_all_loss_making_preserves_cash(self):
        self.request['synergies'] = []
        for action in self.request['actions']:
            if action['cash_returns'] is not None:
                action['cash_returns'] = dict.fromkeys(self.request['scenarios'], 0)
        self.assertEqual(self.run_plan()['decision'], 'RETAIN_CASH')

    def test_infrastructure_budget_is_not_job_market_cap(self):
        self.request['max_states'] = 1
        self.assertEqual(self.run_plan()['decision'], 'DECOMPOSE_OR_RAISE_AUTHORIZED_PLANNING_BUDGET')

    def test_no_revenue_ceiling(self):
        for action in self.request['actions']:
            action['cost'] *= 10**9
            if action['cash_returns'] is not None:
                action['cash_returns'] = {k:v*10**9 for k,v in action['cash_returns'].items()}
        for key in ('available','unrestrictedEarned','authorized_allocation'):
            self.request['funding'][key] *= 10**9
        self.request['worst_loss_limit'] *= 10**9
        for extra in self.request['synergies']:
            extra['incremental_cash'] = {k:v*10**9 for k,v in extra['incremental_cash'].items()}
        self.assertEqual(self.run_plan()['decision'], 'CANDIDATE_ALLOCATION')

    def test_planner_does_not_mutate_inputs_or_claim_success(self):
        original = copy.deepcopy(self.request)
        output = self.run_plan()
        self.assertEqual(original, self.request)
        self.assertIs(output['execute_authorized'], False)
        self.assertIs(output['funding_independently_audited_here'], False)
        for key in ('commercial_success','capability_improvement','physical_impact'):
            self.assertEqual(output[key], 'NOT_EVALUATED')

    def test_small_random_instances_match_separate_recursive_oracle(self):
        for seed in range(60):
            rng = random.Random(seed)
            req = copy.deepcopy(self.request)
            req['synergies'] = []
            req['scenarios'] = {'ordinary':10000}
            req['funding'] = {'source':'fixture','available':12,'unrestrictedEarned':12,'authorized_allocation':12}
            req['actions'] = [dict(id=str(i),lane='instrument',catalog_id=None,cost=rng.randrange(1,8),
                requires=[],exclusive_group=None,cash_returns={'ordinary':rng.randrange(0,16)},
                evidence='fixture',authorized=True) for i in range(7)]
            def oracle(i, remaining):
                if i == len(req['actions']): return 0
                action = req['actions'][i]
                skip = oracle(i+1, remaining)
                if action['cost'] > remaining: return skip
                return max(skip, action['cash_returns']['ordinary']-action['cost']+
                           oracle(i+1, remaining-action['cost']))
            out = choose(req, self.universe)
            self.assertEqual(int(out['expected_net_cash']), oracle(0,12))

    def test_duplicate_json_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'input.json'; path.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError): read_json(path)

    def test_cli_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'result.json'
            cmd = [sys.executable, '-m','portfolio_scale.transformational','--input',
                   str(ROOT/'transformational_example.json'),'--output',str(output)]
            run = subprocess.run(cmd, cwd=ROOT.parent, capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode,0,run.stderr)
            original = output.read_bytes()
            again = subprocess.run(cmd, cwd=ROOT.parent,capture_output=True,text=True,timeout=15)
            self.assertEqual(again.returncode,2)
            self.assertEqual(original,output.read_bytes())


if __name__ == '__main__': unittest.main()
