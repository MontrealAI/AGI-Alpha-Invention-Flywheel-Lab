"""Exact analytical companion to a joint frontier/market discovery brief.

Uses the published paper's synthetic inputs and labeled counterfactuals. It does
not discover buyers, estimate real demand, issue commitments or control accounts.
"""
from dataclasses import dataclass, replace
from fractions import Fraction as F
from itertools import product
import json
import unittest

@dataclass(frozen=True)
class Case:
    buyers: int = 4
    probability: F = F(4, 5)
    core: F = F(600)
    coordination: F = F(0)
    price: F = F(300)
    value: F = F(360)
    adoption: F = F(0)
    delivery: F = F(75)
    route: F = F(0)
    cash: F = F(900)
    timing: str = 'all_delivery_before_payment'

    def validate(self):
        if type(self.buyers) is not int or self.buyers < 1:
            raise ValueError('positive integer buyer count required')
        if not 0 <= self.probability <= 1:
            raise ValueError('probability outside [0,1]')
        for name in ('core','coordination','price','value','adoption','delivery','route','cash'):
            if getattr(self, name) < 0:
                raise ValueError('negative ' + name)
        if self.timing not in ('all_delivery_before_payment','accepted_payment_between_deliveries'):
            raise ValueError('unmodeled timing')


def evaluate(c):
    c.validate()
    fixed = c.core + c.coordination
    success = c.buyers * (c.price - c.delivery - c.route) - fixed
    failure = -fixed
    expected = c.probability * success + (1-c.probability) * failure
    participation = c.probability * (c.value-c.price) - c.adoption
    events = [-fixed]
    if c.timing == 'all_delivery_before_payment':
        events += [-c.buyers*c.delivery, c.buyers*c.price, -c.buyers*c.route]
    else:
        for _ in range(c.buyers):
            events += [-c.delivery, c.price, -c.route]
    running = F(0); required = fixed
    for event in events:
        running += event
        required = max(required, -running)
    if running != success:
        raise AssertionError('cash path does not match success contribution')
    unit = c.probability*(c.price-c.delivery-c.route)
    minimum_buyers = int(fixed // unit) + 1 if unit > 0 else None
    return {
        'expected_contribution': expected,
        'success_contribution': success,
        'common_failure_loss': fixed,
        'buyer_expected_surplus_each': participation,
        'required_prefunding': required,
        'minimum_buyers_for_strict_positive_contribution': minimum_buyers,
        'modeled_screen_pass': expected > 0 and participation >= 0 and c.cash >= required,
        'scope': 'SUPPLIED_SYNTHETIC_MODEL_ONLY',
        'real_buyer_acceptance': False,
        'operating_authority': False,
    }


def scenarios():
    base = Case()
    return {
        'paper_four_buyer_reference': base,
        'one_buyer_leaves': replace(base, buyers=3),
        'unfunded_despite_positive_expectation': replace(base, cash=600),
        'route_burden_40': replace(base, route=40),
        'hypothetical_lower_core_cost_three_buyers': replace(base, buyers=3, core=450),
        'hypothetical_lower_cost_but_stronger_buyer_alternative': replace(base, core=450, price=200),
        'hypothetical_accepted_payment_between_deliveries': replace(base, cash=675, timing='accepted_payment_between_deliveries'),
    }


def exact_json(value):
    if isinstance(value, F):
        return {'numerator': value.numerator, 'denominator': value.denominator}
    raise TypeError(type(value).__name__)


def run():
    return {
        'scope': 'Exact supplied-model sensitivity; NOT a real-market result or learned AI effect',
        'unit': 'thousands of illustrative USD; paper reference case',
        'probability_semantics': 'One common core-qualification event; not independent buyer successes',
        'cases': {name: evaluate(case) for name, case in scenarios().items()},
        'interpretation': 'Lower AI construction cost may open a coalition, but better buyer outside options can close it. Sequential payment requires genuine acceptance and collectability before the next delivery; it is not financing already obtained.',
        'exclusions': 'Partial adaptation failures, default, refunds, taxes, financing charges, legal review and actual costs are absent; do not interpret contribution as audited profit.'
    }


class Checks(unittest.TestCase):
    def test_paper_expected_and_success(self):
        r=evaluate(Case());self.assertEqual(r['expected_contribution'],120);self.assertEqual(r['success_contribution'],300)
    def test_paper_finance(self):
        self.assertEqual(evaluate(Case())['required_prefunding'],900)
    def test_buyer_surplus(self):
        self.assertEqual(evaluate(Case())['buyer_expected_surplus_each'],48)
    def test_three_buyers(self):
        self.assertEqual(evaluate(Case(buyers=3))['expected_contribution'],-60)
    def test_fee_failure(self):
        self.assertEqual(evaluate(Case(route=40))['expected_contribution'],-8)
    def test_tech_reopens(self):
        self.assertEqual(evaluate(Case(buyers=3,core=450))['expected_contribution'],90)
    def test_outside_option_closes(self):
        self.assertEqual(evaluate(Case(core=450,price=200))['expected_contribution'],-50)
    def test_conditional_sequential_finance(self):
        r=evaluate(Case(cash=675,timing='accepted_payment_between_deliveries'))
        self.assertEqual(r['required_prefunding'],675);self.assertEqual(r['expected_contribution'],120)
    def test_cash_not_expectation(self):
        r=evaluate(Case(cash=600));self.assertGreater(r['expected_contribution'],0);self.assertFalse(r['modeled_screen_pass'])
    def test_nonpositive_unit_cannot_be_pooled_away(self):
        for n in (1,4,20):
            r=evaluate(Case(buyers=n,route=250));self.assertIsNone(r['minimum_buyers_for_strict_positive_contribution']);self.assertLess(r['expected_contribution'],0)
    def test_common_failure(self):
        self.assertEqual(evaluate(Case(buyers=4))['common_failure_loss'],600)
    def test_no_authority(self):
        for c in scenarios().values():
            r=evaluate(c);self.assertFalse(r['real_buyer_acceptance']);self.assertFalse(r['operating_authority'])
    def test_independent_expected_formula_grid(self):
        for n,p,k,f in product((1,3,4,8),(F(0),F(1,2),F(4,5),F(1)),(0,450,600),(0,40,250)):
            c=Case(buyers=n,probability=p,core=k,route=f)
            self.assertEqual(evaluate(c)['expected_contribution'],p*n*(c.price-c.delivery-f)-k)
    def test_original_cash_closed_form_grid(self):
        for n,k,d,q,f in product((1,3,4),(0,450,600),(0,75),(0,300),(0,40,400)):
            r=evaluate(Case(buyers=n,core=k,delivery=d,price=q,route=f))
            self.assertEqual(r['required_prefunding'],k+n*d+max(0,n*(f-q)))
    def test_invalid_timing(self):
        with self.assertRaises(ValueError):evaluate(Case(timing='forecast_is_cash'))
    def test_invalid_probability(self):
        with self.assertRaises(ValueError):evaluate(Case(probability=F(6,5)))

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        unittest.main(argv=[sys.argv[0]],verbosity=2)
    else:
        print(json.dumps(run(),default=exact_json,indent=2,sort_keys=True,allow_nan=False))
