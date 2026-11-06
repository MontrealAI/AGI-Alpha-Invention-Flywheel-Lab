"""Exact implications of Invent the Economy's authored model; no market estimates.

USD units; common qualification event; all adapters succeed after qualification;
all delivery costs paid before receipts; route charges paid from receipts.
This is analysis only, not an account, operating ledger, or market-discovery engine.
"""
from fractions import Fraction as F
import json
from pathlib import Path
import unittest


def contribution(n, p, q, d, k, a=0, f=0):
    if type(n) is not int or n < 0 or not F(0) <= p <= F(1):
        raise ValueError('Invalid count or probability')
    if any(x < 0 for x in (q, d, k, a, f)):
        raise ValueError('Costs and prices must be nonnegative')
    return p * n * (q-d-f) - k-a


def event_oracle(n, p, q, d, k, a=0, f=0):
    """Separately expand both model outcomes; not empirical validation."""
    failure = -(k+a)
    success = n*q - n*d - n*f - k-a
    return (1-p)*failure + p*success


def minimum_buyers(p, q, d, k, a=0, f=0):
    margin = p*(q-d-f)
    if margin <= 0:
        return None
    return int((k+a)//margin)+1


def prefunding(n, q, d, k, a=0, f=0):
    return k+a+n*d+max(0,n*(f-q))


class Tests(unittest.TestCase):
    def test_base(self):
        self.assertEqual(contribution(4,F(4,5),300000,75000,600000),120000)
        self.assertEqual(prefunding(4,300000,75000,600000),900000)
    def test_closed_form_against_event_branches(self):
        for n in range(1,9):
            for p in (F(1,5),F(2,5),F(3,5),F(4,5),F(1)):
                for k in (0,150000,300000,450000,600000,900000,1200000):
                    for f in (0,10000,40000,100000):
                        args=(n,p,300000,75000,k,0,f)
                        self.assertEqual(contribution(*args),event_oracle(*args))
    def test_strict_threshold(self):
        for n in range(1,5):
            k=F(4,5)*n*225000
            self.assertEqual(contribution(n,F(4,5),300000,75000,k),0)
            self.assertGreater(contribution(n,F(4,5),300000,75000,k-1),0)
    def test_competitive_price_pressure(self):
        self.assertEqual(contribution(4,F(4,5),250000,75000,600000),-40000)
    def test_smaller_coalition_after_cost_reduction(self):
        self.assertEqual(contribution(3,F(4,5),300000,75000,500000),40000)
        self.assertEqual(prefunding(3,300000,75000,500000),725000)
    def test_scope_expansion_can_reduce_contribution(self):
        self.assertEqual(contribution(5,F(3,5),300000,75000,600000),75000)
        self.assertEqual(contribution(5,F(16,25),300000,75000,600000),120000)
    def test_native_route_can_destroy_viability(self):
        self.assertEqual(contribution(4,F(4,5),300000,75000,600000,f=40000),-8000)
    def test_integer_minimum(self):
        for p in (F(1,5),F(1,2),F(4,5),F(1)):
            for k in (0,100000,600000):
                n=minimum_buyers(p,300000,75000,k)
                self.assertGreater(contribution(n,p,300000,75000,k),0)
                self.assertLessEqual(contribution(n-1,p,300000,75000,k),0)
        self.assertIsNone(minimum_buyers(F(0),300000,75000,600000))
    def test_route_burden_exceeds_receipts(self):
        self.assertEqual(prefunding(4,300000,75000,600000,f=400000),1300000)
    def test_invalid_inputs(self):
        for n,p in ((-1,F(1)),(True,F(1)),(4,F(6,5))):
            with self.assertRaises(ValueError):
                contribution(n,p,300000,75000,600000)


def generate():
    cases=[('paper_four_buyers',4,F(4,5),300000,600000,0),
           ('paper_three_buyers',3,F(4,5),300000,600000,0),
           ('sensitivity_lower_setup_three_buyers',3,F(4,5),300000,500000,0),
           ('sensitivity_lower_accepted_price',4,F(4,5),250000,600000,0),
           ('sensitivity_fifth_buyer_lower_common_reliability',5,F(3,5),300000,600000,0),
           ('paper_high_route_burden',4,F(4,5),300000,600000,40000)]
    out={'scope':'Exact authored-model implications, not measured business economics',
         'source':'Invent the Economy, sections 3-5 and 9.2; October 2026',
         'currency':'illustrative USD',
         'real_buyers_identified':0,'accepted_commitments':0,'actual_revenue_usd':0,
         'assumptions':['Common binary qualification; conditional adaptations all succeed',
                        'No customer default or partial failure',
                        'No finance charges, tax, or other unmodeled costs',
                        'Full upfront development and successful delivery financing',
                        'Supplied prices are not measured willingness to pay'],
         'strict_setup_plus_coordination_limits_usd':[{'n':n,'strict_upper_bound':180000*n} for n in range(1,5)],
         'common_success_probability_strict_lower_bound':'2/3',
         'additional_route_cost_strict_upper_bound_per_successful_delivery_usd':37500,
         'cases':[]}
    for name,n,p,q,k,f in cases:
        out['cases'].append({'name':name,'n':n,'p':str(p),'q_usd':q,'k_usd':k,'d_usd':75000,'f_usd':f,
                             'expected_contribution_usd':int(contribution(n,p,q,75000,k,f=f)),
                             'prefunding_usd':prefunding(n,q,75000,k,f=f)})
    return out

if __name__=='__main__':
    path=Path(__file__).with_name('BOUNDARIES.json')
    path.write_text(json.dumps(generate(),indent=2)+'\n')
    print(path)
