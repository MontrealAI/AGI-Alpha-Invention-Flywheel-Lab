"""Engineering comparisons, not commercial confirmation or measured market payoffs."""
import copy
from fractions import Fraction as F
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from portfolio_scale.staged_coupling import choose

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT/'campaign/staged-coupling-017/EXAMPLE.json'
MICRO = 1_000_000


def exhaustive(request):
    """Separate full contingent-policy enumeration; no production helper calls."""
    budget = min(request['funding'][key] for key in ['available','unrestrictedEarned','authorized_allocation'])
    prior = {s:F(w,10000) for s,w in request['state_weights'].items()}
    def evaluate(action, belief, cost):
        if not action['authorized'] or action['responses'] is None:
            return None
        support = [s for s in belief if belief[s]>0]
        rows = action['responses']
        requirement = action['cost']+max(v[s]['future_cash_required'] for v in rows.values() for s in support)
        if requirement+cost>budget:
            return None
        if any(v[s]['net_receipts']-action['cost']-cost < -request['max_loss'] for v in rows.values() for s in support):
            return None
        estimates = [(sum(belief[s]*v[s]['rival_value'] for s in support),
                      sum(belief[s]*v[s]['net_receipts'] for s in support)-action['cost'])
                     for v in rows.values()]
        rival_max = max(r for r,_ in estimates)
        return min(v for r,v in estimates if r==rival_max)
    values = [evaluate(a,prior,0) for a in request['portfolios']]
    best = max(v for v in values if v is not None)
    for probe in request['probes']:
        if not probe['authorized'] or probe['cost']>min(budget,request['max_loss']):
            continue
        branches=[]
        for row in probe['likelihoods'].values():
            weighted={s:prior[s]*F(row[s],10000) for s in prior}
            prob=sum(weighted.values())
            if not prob:continue
            posterior={s:w/prob for s,w in weighted.items()}
            options=[evaluate(a,posterior,probe['cost']) for a in request['portfolios']]
            branches.append((prob,[v for v in options if v is not None]))
        for contingent_policy in itertools.product(*(options for _,options in branches)):
            val=-probe['cost']+F(probe['discount_bps'],10000)*sum(
                branches[i][0]*value for i,value in enumerate(contingent_policy))
            best=max(best,val)
    return best


class StagedCouplingTests(unittest.TestCase):
    def setUp(self):self.r=json.loads(EXAMPLE.read_text())
    def selected(self):return choose(self.r)['selected']

    def test_information_contingent_plan_and_responding_rival(self):
        r=choose(self.r);s=r['selected'];self.assertEqual(s['expected_net'],'65500000')
        self.assertEqual(s['probe'],'discriminating_test')
        self.assertEqual(s['continuations']['favorable']['portfolio'],'build_instrument_and_expand')
        self.assertEqual(s['continuations']['favorable']['rival_response'],'imitate')
        self.assertEqual(s['continuations']['unfavorable']['portfolio'],'repeat_delivery')
        self.assertEqual(r['best_nonadaptive_control']['expected_net'],'50000000')
        self.assertEqual(r['advantage_over_nonadaptive'],'15500000')

    def test_no_signal_means_no_clairvoyant_build_choice(self):
        self.r['probes']=[]
        s=self.selected();self.assertEqual(s['expected_net'],'50000000')
        self.assertNotEqual(s['expected_net'],'95000000')
        self.assertEqual(s['continuations']['prior']['rival_response'],'retain_offer')

    def test_do_not_assume_rivals_remain_passive_after_disclosure(self):
        for action in self.r['portfolios']:
            del action['responses']['imitate']
        self.assertEqual(self.selected()['expected_net'],'79000000')

    def test_easy_imitation_can_make_commerce_only_best(self):
        a=self.r['portfolios'][2]
        a['responses']['imitate']['useful'].update(net_receipts=90*MICRO,rival_value=30*MICRO)
        a['responses']['imitate']['not_useful']['rival_value']=30*MICRO
        r=self.selected();self.assertIsNone(r['probe'])
        self.assertEqual(r['continuations']['prior']['portfolio'],'repeat_delivery')
        self.assertEqual(r['expected_net'],'30000000')

    def test_expensive_probe_should_not_be_funded(self):
        self.r['probes'][0]['cost']=30*MICRO
        self.assertIsNone(self.selected()['probe'])
        self.assertEqual(self.selected()['expected_net'],'50000000')

    def test_delay_can_destroy_the_value_of_learning_first(self):
        self.r['probes'][0]['discount_bps']=5000
        self.assertIsNone(self.selected()['probe'])

    def test_no_forced_research_or_internal_budget_tax(self):
        self.r['portfolios']=self.r['portfolios'][:2]
        self.assertEqual(self.selected()['expected_net'],'30000000')
        self.assertIsNone(self.selected()['probe'])

    def test_impossible_signals_are_not_observed(self):
        p=self.r['probes'][0]
        p['likelihoods']={'same':{'useful':10000,'not_useful':10000},'never':{'useful':0,'not_useful':0}}
        r=choose(self.r);self.assertIsNone(r['selected']['probe'])
        self.assertNotIn('never',r['alternatives'][1]['continuations'])

    def test_uninformative_signal_has_no_automatic_information_bonus(self):
        self.r['probes'][0]['likelihoods']={'red':{'useful':5000,'not_useful':5000},'blue':{'useful':5000,'not_useful':5000}}
        self.assertEqual(self.selected()['expected_net'],'50000000')
        self.assertIsNone(self.selected()['probe'])

    def test_unauthorized_probe_and_portfolio_are_excluded(self):
        self.r['portfolios'][2]['authorized']=False
        self.r['probes'][0]['authorized']=False
        self.assertEqual(self.selected()['expected_net'],'30000000')

    def test_unknown_returns_do_not_become_zero_or_infinite(self):
        self.r['portfolios'][2]['responses']=None
        r=choose(self.r)
        self.assertEqual(r['unresolved_portfolios'],['build_instrument_and_expand'])
        self.assertEqual(r['selected']['expected_net'],'30000000')

    def test_unknown_funding_does_not_authorize_investment(self):
        self.r['funding']['unrestrictedEarned']=None
        r=choose(self.r);self.assertEqual(r['decision'],'UNKNOWN_FUNDING');self.assertIsNone(r['selected'])

    def test_seed_or_future_revenue_is_not_available_earned_funding(self):
        self.r['funding']['unrestrictedEarned']=0
        s=self.selected();self.assertEqual(s['expected_net'],'0')
        self.assertEqual(s['continuations']['prior']['portfolio'],'keep_liquidity')

    def test_probe_cost_reduces_followup_funding(self):
        self.r['funding']['authorized_allocation']=60*MICRO
        self.assertIsNone(self.selected()['probe'])

    def test_later_cash_requirements_must_be_funded_even_before_receipts(self):
        for values in self.r['portfolios'][2]['responses'].values():
            for v in values.values():v['future_cash_required']=50*MICRO
        self.assertEqual(self.selected()['continuations']['prior']['portfolio'],'repeat_delivery')

    def test_negative_future_cash_flow_is_supported_not_clamped(self):
        for values in self.r['portfolios'][2]['responses'].values():
            values['not_useful'].update(net_receipts=-5*MICRO,future_cash_required=5*MICRO)
        r=self.selected();self.assertLess(F(r['expected_net']),F(65500000))
        self.assertEqual(F(r['expected_net']),exhaustive(self.r))

    def test_unreserved_negative_later_liability_refuses(self):
        self.r['portfolios'][2]['responses']['imitate']['useful']['net_receipts']=-MICRO
        with self.assertRaisesRegex(ValueError,'LATER_NET_LIABILITY'):choose(self.r)

    def test_declared_loss_bound_applies_to_probe_and_action_together(self):
        self.r['max_loss']=60*MICRO
        self.assertIsNone(self.selected()['probe'])
        self.assertEqual(self.selected()['expected_net'],'50000000')

    def test_rival_best_response_ties_are_not_resolved_optimistically(self):
        self.r['probes']=[]
        a=self.r['portfolios'][2]
        for response in a['responses'].values():
            for v in response.values():v['rival_value']=0
        r=self.selected()
        self.assertEqual(r['expected_net'],'35000000')
        self.assertEqual(r['continuations']['prior']['rival_response'],'imitate')

    def test_all_unprofitable_options_retain_cash(self):
        for a in self.r['portfolios'][1:]:
            for values in a['responses'].values():
                for v in values.values():v['net_receipts']=0
        self.assertEqual(self.selected()['expected_net'],'0')

    def test_signals_cannot_reveal_unlisted_private_state_or_future_fields(self):
        self.r['hidden_actual_state']='useful'
        with self.assertRaisesRegex(ValueError,'EXACT_SCHEMA'):choose(self.r)

    def test_invalid_prior_likelihood_units_and_boolean_money_refuse(self):
        mutations=[lambda r:r['state_weights'].update(useful=1),
                   lambda r:r['probes'][0]['likelihoods']['favorable'].update(useful=1),
                   lambda r:r.update(currency='USD'),
                   lambda r:r['funding'].update(available=True)]
        for mutation in mutations:
            r=copy.deepcopy(self.r);mutation(r)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):choose(r)

    def test_missing_retain_cash_and_reused_identity_refuse(self):
        r=copy.deepcopy(self.r);r['portfolios']=r['portfolios'][1:]
        with self.assertRaises(ValueError):choose(r)
        self.r['portfolios'][2]['id']='repeat_delivery'
        with self.assertRaises(ValueError):choose(self.r)

    def test_excessive_computation_refuses_without_fake_optimality(self):
        self.r['max_evaluations']=1
        with self.assertRaisesRegex(ValueError,'BUDGET_EXCEEDED'):choose(self.r)

    def test_inputs_unchanged_and_verdicts_are_not_upgraded(self):
        original=copy.deepcopy(self.r);r=choose(self.r)
        self.assertEqual(original,self.r)
        self.assertIs(r['execution_authorized'],False);self.assertIs(r['funding_authenticated'],False)
        self.assertEqual(r['commercial_success'],'NOT_EVALUATED')
        self.assertEqual(r['capability_compounding'],'NOT_EVALUATED')

    def test_80_random_games_match_separate_exhaustive_policy_enumeration(self):
        for seed in range(80):
            rng=random.Random(seed);r=copy.deepcopy(self.r)
            w=rng.randrange(0,10001);r['state_weights']={'useful':w,'not_useful':10000-w}
            for action in r['portfolios'][1:]:
                action['cost']=rng.randrange(1,80)*MICRO
                for values in action['responses'].values():
                    for v in values.values():
                        v['net_receipts']=rng.randrange(-5,240)*MICRO
                        v['future_cash_required']=max(0,-v['net_receipts'])
                        v['rival_value']=rng.randrange(-20,50)*MICRO
            probe=r['probes'][0];probe['cost']=rng.randrange(0,40)*MICRO
            probe['discount_bps']=rng.randrange(0,10001)
            for state in r['state_weights']:
                likelihood=rng.randrange(0,10001)
                probe['likelihoods']['favorable'][state]=likelihood
                probe['likelihoods']['unfavorable'][state]=10000-likelihood
            with self.subTest(seed=seed):
                actual=F(choose(r)['selected']['expected_net'])
                self.assertEqual(actual,exhaustive(r))

    def test_cli_refuses_overwriting_existing_results_and_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'result.json'
            cmd=[sys.executable,'-m','portfolio_scale.staged_coupling','--input',str(EXAMPLE),'--output',str(output)]
            first=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertEqual(first.returncode,0,first.stderr);original=output.read_bytes()
            again=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertEqual(again.returncode,2);self.assertEqual(output.read_bytes(),original)
            bad=Path(tmp)/'bad.json';bad.write_text('{"schema":1,"schema":2}')
            cmd[cmd.index('--input')+1]=str(bad)
            error=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertEqual(error.returncode,2)


if __name__=='__main__':unittest.main()
