"""Independent assertions and adverse-model cases for the bounded game maker."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest

from mechanism_harness.game_maker import (
    choices, evaluate, follower, invent, rederive, validate,
)

FIXTURE = Path(__file__).with_name('game_maker_fixture.json')


def sample(): return json.loads(FIXTURE.read_text())


class GameMakerTests(unittest.TestCase):
    def test_author_fixture_does_not_claim_real_data(self):
        s=sample()
        self.assertEqual(validate(s)['basis'], 'DECLARED_COMPLETE_INFORMATION_SYNTHETIC')

    def test_synthesizes_complementary_new_arrangement(self):
        r=invent(sample()); w=r['winner']
        self.assertEqual(r['status'],'EXACT_DECLARED_FINITE_GAME_OPTIMUM')
        self.assertEqual(w['operators'],['evidence_in_production','pooled_commissioning'])
        self.assertEqual(w['quote'],19)
        self.assertEqual(w['expected_profit'],'41/10')
        self.assertEqual(w['worst_loss'],1)
        self.assertEqual(r['states_evaluated'],20) # four constructible sets x five prices
        self.assertEqual(r['optimality_gap_fraction'],'0')

    def test_single_changes_cannot_make_central_transaction_profitable(self):
        s=sample()
        for ops in ((),('evidence_in_production',),('pooled_commissioning',)):
            r=evaluate(s,ops,19)
            if r is not None: self.assertLess(r['scenarios'][0]['profit'],0)
            else: self.assertEqual(ops,())  # base plan cannot prefinance all promised work
        self.assertEqual(evaluate(s,('evidence_in_production','pooled_commissioning'),19)['scenarios'][0]['profit'],5)

    def test_buyer_refusal_and_outside_tie(self):
        b=sample()['buyer_profiles']
        self.assertEqual(choices(b,{x['id'] for x in b},20,None)[0],[])
        self.assertEqual(len(choices(b,{x['id'] for x in b},19,None)[0]),4)
        self.assertEqual(choices(b,{x['id'] for x in b},19,19)[0],[])

    def test_copycat_rival_follower_is_financially_rational(self):
        s=sample(); row=s['scenarios'][1]
        r=follower(s,('evidence_in_production','pooled_commissioning'),row,19)
        self.assertEqual(r['quote'],19)  # parity rival gets a conservative tie break
        self.assertGreaterEqual(r['rival_profit'],0)
        self.assertEqual(r['seller_buyers'],[])

    def test_payment_delay_profit_is_not_cash(self):
        r=invent(sample()); delayed=r['winner']['scenarios'][2]
        self.assertEqual(delayed['profit'],5)
        self.assertEqual(delayed['collected'],0)
        self.assertEqual(delayed['unrestricted_cash_end'],19)
        self.assertLess(delayed['unrestricted_cash_end'],25) # cannot self-fund a 25-unit next investment

    def test_buyer_refusal_rational_nonentry(self):
        s=sample()
        for b in s['buyer_profiles']:b['value']=0
        winner=invent(s)['winner']
        self.assertIsNone(winner['quote'])
        self.assertEqual(winner['expected_profit'],'0')

    def test_inadequate_liquidity_for_work_precludes_selling(self):
        s=sample(); s['opening_cash']=40
        w=invent(s)['winner']
        self.assertIsNone(w['quote'])

    def test_reserves_protected(self):
        s=sample();s['protected_cash']=40
        self.assertIsNone(invent(s)['winner']['quote'])

    def test_no_risk_appetite_prohibits_copycat_exposure(self):
        s=sample();s['limits']['max_loss']=0
        for r in [invent(s)['winner']]:
            self.assertEqual(r['worst_loss'],0)

    def test_downside_risk_can_favor_hold(self):
        s=sample()
        for row in s['scenarios']:
            row['accepted']=False;row['collected']=False
        self.assertIsNone(invent(s)['winner']['quote'])

    def test_partner_outside_option_is_binding(self):
        s=sample();s['operators'][0]['partner_payment']=5;s['operators'][0]['partner_outside']=6
        self.assertNotIn('evidence_in_production',invent(s)['winner']['operators'])
        s['operators'][0]['partner_payment']=6
        self.assertEqual(len([x for x in invent(s)['winner']['operators'] if x=='evidence_in_production']),0) # no assumed cheap partner

    def test_partner_payment_not_free(self):
        s=sample();s['operators'][0]['partner_payment']=3;s['operators'][0]['partner_outside']=3
        row=evaluate(s,('evidence_in_production','pooled_commissioning'),19)
        self.assertEqual(row['scenarios'][0]['full_cost'],74)

    def test_missing_dependency_prevents_synthesis(self):
        s=sample(); s['operators'][0]['requires']=['pooled_commissioning']
        row=invent(s)
        self.assertEqual(row['winner']['operators'],['pooled_commissioning','evidence_in_production'])

    def test_cycle_is_not_a_valid_mechanism(self):
        s=sample(); s['operators'][0]['requires']=['pooled_commissioning'];s['operators'][1]['requires']=['evidence_in_production']
        self.assertIsNone(invent(s)['winner']['quote'])

    def test_negative_result_is_preserved_under_funding_shock(self):
        s=sample();s['opening_cash']=65
        result=invent(s)
        self.assertIsNone(result['winner']['quote'])
        self.assertEqual(result['status'],'EXACT_DECLARED_FINITE_GAME_OPTIMUM')

    def test_absence_of_buyer_is_not_assumed_sale(self):
        s=sample();s['scenarios'][0]['active_buyers']=[]
        r=evaluate(s,('evidence_in_production','pooled_commissioning'),19)
        self.assertEqual(r['scenarios'][0]['recognized'],0)
        self.assertEqual(r['scenarios'][0]['profit'],-1)

    def test_exact_rederivation_detects_tampered_claim(self):
        s=sample();r=invent(s)
        self.assertTrue(rederive(s,r)['accepted'])
        r2=copy.deepcopy(r);r2['winner']['scenarios'][0]['profit']+=1
        with self.assertRaisesRegex(ValueError,'CERTIFICATE_CHANGED'):rederive(s,r2)

    def test_rederive_saved_cli_style_record(self):
        s=sample();r=invent(s);r['replay']=rederive(s,r)
        self.assertTrue(rederive(s,r)['accepted'])
        r['replay']['accepted']=False
        with self.assertRaisesRegex(ValueError,'REPLAY_RECEIPT_CHANGED'):rederive(s,r)

    def test_rejected_work_does_not_create_buyer_surplus(self):
        s=sample()
        for case in s['scenarios']:
            case['accepted']=False;case['collected']=False
        x=evaluate(s,('evidence_in_production','pooled_commissioning'),19)
        self.assertTrue(all(r['buyer_gain_over_outside']==0 for r in x['scenarios']))

    def test_search_bound_is_not_a_claim_of_optimality(self):
        s=sample();s['limits']['max_states']=1
        r=invent(s)
        self.assertEqual(r['status'],'SEARCH_BOUND_EXHAUSTED')
        self.assertIsNone(r['winner'])

    def test_invalid_information_or_prices_rejected(self):
        s=sample();s['basis']='PRIVATE_ORACLE'
        with self.assertRaises(ValueError):invent(s)
        s=sample();s['price_grid']=[20,19]
        with self.assertRaises(ValueError):invent(s)

    def test_zero_weight_or_unbalanced_scenarios_rejected(self):
        s=sample();s['scenarios'][0]['weight_bps']=7000
        with self.assertRaises(ValueError):validate(s)

    def test_reference_follower_best_response_enumeration(self):
        # Independent brute-force rival payoffs for the copycat scenario.
        s=sample();o=('evidence_in_production','pooled_commissioning')
        rivals=[]
        for p in s['rival']['price_grid']:
            _,won,_=choices(s['buyer_profiles'],set(x['id'] for x in s['buyer_profiles']),19,p)
            n=len(won)
            pay=n*p - (1 + (46+6*n if n else 0))
            rivals.append((pay,p))
        self.assertEqual(max(rivals),(5,19))
        self.assertEqual(follower(s,o,s['scenarios'][1],19)['quote'],19)

if __name__=='__main__':unittest.main()
