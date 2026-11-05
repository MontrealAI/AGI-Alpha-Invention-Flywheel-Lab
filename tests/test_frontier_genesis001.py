"""Adversarial independent checks for frontier-to-possibility finite study."""
import copy
import importlib.util
import itertools
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'campaign' / 'frontier-genesis-001'
spec = importlib.util.spec_from_file_location('genesis', ROOT / 'genesis.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
BASE = json.loads((ROOT / 'SCENARIO.json').read_text())


def independent_optimal(s, required, excluded=frozenset()):
    """Exhaustively enumerate all subsets and permutations of operations (tiny test cases only)."""
    start = set(g.initial(s, excluded))
    optimum = None
    for size in range(len(s['operations']) + 1):
        for actions in itertools.permutations(s['operations'], size):
            caps = set(start)
            cost = 0
            for a in actions:
                if not set(a['requires']).issubset(caps):
                    break
                caps.update(a['provides'])
                cost += a['cost_cents']
            else:
                if set(required).issubset(caps):
                    optimum = cost if optimum is None else min(optimum, cost)
    return optimum


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.s = copy.deepcopy(BASE)

    def test_valid(self):
        g.validate(self.s)

    def test_optimal_known_grammar_against_exhaustive(self):
        for req in [set(['reconciled_evidence']), {'verified_evidence_product'},
                    {'qualified_engineering_package'}, {'nonexistent'}]:
            p = g.find_plan(self.s, frozenset(req))
            self.assertEqual(None if p is None else p['cost_cents'], independent_optimal(self.s, req))

    def test_counterfactual_removes_frontier_advantage(self):
        result = g.analyze(self.s)
        p = next(o for o in result['opportunities'] if o['id'] == 'verifiable_evidence_package')
        self.assertEqual(p['plan']['cost_cents'], 3200)
        self.assertEqual(p['no_frontier_plan']['cost_cents'], 6400)
        self.assertEqual(p['decision']['model_profit_cents'], 5500)

    def test_restricted_internal_does_not_unlock(self):
        p = g.find_plan(self.s, frozenset({'engineering_design'}))
        self.assertEqual(p['operations'], ['f_engineering_legacy'])

    def test_unknown_access_does_not_unlock(self):
        self.s['events'][0]['access'] = 'unverified'
        p = g.find_plan(self.s, frozenset({'verified_evidence_product'}))
        self.assertEqual(p['cost_cents'], 6400)

    def test_revoke_access_changes_decision(self):
        before = g.find_plan(self.s, frozenset({'software_artifact'}))
        self.s['events'][0]['access'] = 'restricted'
        after = g.find_plan(self.s, frozenset({'software_artifact'}))
        self.assertLess(before['cost_cents'], after['cost_cents'])

    def test_no_buyer(self):
        r = g.analyze(self.s)
        self.assertEqual(next(x for x in r['opportunities'] if x['id'] == 'no_buyer_case')['decision']['status'],
                         'NO_VOLUNTARY_BUYER')

    def test_no_margin_and_sensible_nonentry(self):
        r = g.analyze(self.s)
        o = next(x for x in r['opportunities'] if x['id'] == 'qualified_engineering_package')
        self.assertEqual(o['decision']['status'], 'NO_POSITIVE_COMPLETE_MARGIN')

    def test_positive_model_is_not_real_revenue(self):
        r = g.analyze(self.s)
        self.assertEqual(r['scope'], 'AUTHORED_SYNTHETIC_FINITE_GAME')
        self.assertEqual(next(x for x in r['opportunities'] if x['id'] == r['model_best_offer'])
                         ['commercial_readiness'], 'NOT_ESTABLISHED')

    def test_cheapest_route_can_be_existing(self):
        self.s['operations'][1]['cost_cents'] = 10000
        self.s['operations'][3]['cost_cents'] = 10000
        p = g.find_plan(self.s, frozenset({'verified_evidence_product'}))
        self.assertEqual(p['operations'], ['a_conventional_source_read', 'c_standard_code', 'e_ordinary_qualification'])

    def test_frontier_not_required_if_present_initially(self):
        self.s['initial'].append('frontier_code_agent')
        self.s['events'] = []
        p = g.find_plan(self.s, frozenset({'software_artifact'}))
        self.assertEqual(p['operations'], ['d_frontier_code'])

    def test_unauthorized_false_scope(self):
        self.s['evidence_scope'] = 'LIVE_SALES'
        with self.assertRaises(g.InvalidScenario):
            g.analyze(self.s)

    def test_negative_cost_rejected(self):
        self.s['operations'][0]['cost_cents'] = -1
        with self.assertRaises(g.InvalidScenario):
            g.validate(self.s)

    def test_float_money_rejected(self):
        self.s['offers'][0]['buyer_value_floor_cents'] = 99.5
        with self.assertRaises(g.InvalidScenario):
            g.validate(self.s)

    def test_event_source_must_be_https(self):
        self.s['events'][0]['source_url'] = 'file:///etc/passwd'
        with self.assertRaises(g.InvalidScenario):
            g.validate(self.s)

    def test_duplicate_action_rejected(self):
        self.s['operations'].append(copy.deepcopy(self.s['operations'][0]))
        with self.assertRaises(g.InvalidScenario):
            g.validate(self.s)

    def test_html_escaped(self):
        r = g.analyze(self.s)
        r['opportunities'][0]['id'] = '<script>alert(1)</script>'
        h = g.report_html(r)
        self.assertNotIn('<script>', h)

    def test_self_hiding_graph_cannot_claim_unknown_optimality(self):
        p = g.find_plan(self.s, frozenset({'unknown_new_capability'}))
        self.assertIsNone(p)

    def test_model_best_does_not_pick_negative_margin(self):
        self.assertEqual(g.analyze(self.s)['model_best_offer'], 'verifiable_evidence_package')

    def test_graph_source_event_exclusion(self):
        event = self.s['events'][0]['id']
        p = g.find_plan(self.s, frozenset({'verified_evidence_product'}), frozenset({event}))
        self.assertEqual(p['cost_cents'], 6400)


if __name__ == '__main__':
    unittest.main()
