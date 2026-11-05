import copy
import json
from pathlib import Path
import random
import unittest
from genesis_enterprise.policy import choose, independently_choose, improvement_decision, loads
from genesis_enterprise.native import validate_protocol

ROOT = Path(__file__).resolve().parents[1]


def protocol():
    return json.loads((ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json').read_text())


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = protocol()

    def pick(self, **kwargs):
        return choose(self.p['offer'], self.p['tools'], available=100000000,
                      earned=50000000, seed_allowed=False, **kwargs)

    def test_ordinary_tool_wins(self):
        self.assertEqual(self.pick()['selected']['tool'], 'ordinary-highs')

    def test_a_cheaper_existing_frontier_tool_can_win(self):
        t = self.p['tools'][2]
        t['access'] = 'qualified_local'
        self.assertEqual(self.pick()['selected']['tool'], t['id'])

    def test_no_price_tie_purchase(self):
        self.p['offer']['prices'] = [self.p['offer']['rival']]
        self.assertEqual(self.pick()['decision'], 'NO_ENTRY')

    def test_buyer_refusal(self):
        self.p['offer']['value'] = 0
        self.assertEqual(self.pick()['decision'], 'NO_ENTRY')

    def test_costs_destroy_margin(self):
        for t in self.p['tools']:
            t['production'] = 100000000
        self.assertEqual(self.pick()['decision'], 'NO_ENTRY')

    def test_no_invented_earned_capital(self):
        d = choose(self.p['offer'], self.p['tools'], available=100000000, earned=0, seed_allowed=False)
        self.assertEqual(d['decision'], 'NO_ENTRY')

    def test_seed_only_explicit(self):
        d = choose(self.p['offer'], self.p['tools'], available=100000000, earned=0, seed_allowed=True)
        self.assertEqual(d['decision'], 'TRADE_IN_MODEL')

    def test_reserved_cash_not_profit(self):
        self.p['offer']['reserve'] = 100000000
        self.assertEqual(self.pick()['decision'], 'NO_ENTRY')

    def test_restricted_revoked_not_eligible(self):
        for state in ('restricted', 'revoked', 'unverified'):
            for t in self.p['tools']:
                t['access'] = state
            self.assertEqual(self.pick()['decision'], 'NO_ENTRY')

    def test_boolean_money_rejected(self):
        self.p['offer']['value'] = True
        with self.assertRaises(ValueError): self.pick()

    def test_duplicate_tool_rejected(self):
        self.p['tools'].append(copy.deepcopy(self.p['tools'][0]))
        with self.assertRaises(ValueError): self.pick()

    def test_earned_above_available_rejected(self):
        with self.assertRaises(ValueError):
            choose(self.p['offer'], self.p['tools'], available=1, earned=2, seed_allowed=False)

    def test_exact_reference_2000_random_cases(self):
        rng = random.Random(20261104)
        for _ in range(2000):
            o = {k: rng.randrange(0, 101) for k in ('value', 'outside_utility', 'friction', 'budget', 'rival', 'self_service', 'fee', 'reserve')}
            o['prices'] = [rng.randrange(0, 101) for _ in range(8)]
            ts = [{'id': str(i), 'mode': 'conventional', 'production': rng.randrange(1, 40),
                   'maintenance': rng.randrange(0, 15), 'access': rng.choice(['qualified_local', 'unverified'])} for i in range(5)]
            available = rng.randrange(0, 201); earned = rng.randrange(available + 1)
            kw = {'available': available, 'earned': earned, 'seed_allowed': bool(rng.randrange(2))}
            self.assertEqual(choose(o, ts, **kw)['selected'], independently_choose(o, ts, **kw))

    def test_full_funding_cash_threshold_and_lower_price(self):
        self.p['offer']['prices'] = [30000000, 60000000]
        kw = dict(earned=5200000, seed_allowed=False)
        for available, expected in ((35200000, 30000000), (35199999, None),
                                    (65200000, 60000000), (65199999, 30000000)):
            with self.subTest(available=available):
                decision = choose(self.p['offer'], self.p['tools'], available=available, **kw)
                selected = decision['selected']
                self.assertEqual(selected['price'] if selected else None, expected)
                self.assertEqual(selected, independently_choose(self.p['offer'], self.p['tools'], available=available, **kw))

    def test_earned_production_must_also_cover_upfront_fee(self):
        for earned, trades in ((5000000, False), (5199999, False), (5200000, True)):
            with self.subTest(earned=earned):
                decision = choose(self.p['offer'], self.p['tools'], available=100000000,
                                  earned=earned, seed_allowed=False)
                self.assertEqual(decision['selected'] is not None, trades)

    def test_protocol_rejects_native_ineligible_price_before_registration(self):
        self.p['offer']['prices'] = [199999]
        with self.assertRaises(ValueError): validate_protocol(self.p)

    def test_protocol_rejects_residual_beyond_native_exposure(self):
        self.p['offer']['reserve'] = 31000000
        with self.assertRaises(ValueError): validate_protocol(self.p)

    def test_protocol_rejects_scope_inflation(self):
        self.p['boundaries']['real_transactions'] = True
        with self.assertRaises(ValueError): validate_protocol(self.p)

    def test_protocol_accepts_registered_case(self):
        validate_protocol(self.p)

    def test_protocol_rejects_negative_residual(self):
        self.p['offer']['reserve'] = 0
        with self.assertRaises(ValueError): validate_protocol(self.p)

    def test_json_duplicate(self):
        with self.assertRaises(ValueError): loads('{"a":1,"a":2}')

    def test_json_nonfinite(self):
        with self.assertRaises(ValueError): loads('{"a":NaN}')

    def test_meta_rejects_insufficient_gain(self):
        rows = [{'campaign_id': str(i), 'candidate': .7, 'baseline': .69} for i in range(100)]
        r = improvement_decision(rows, alpha=.025, practical_margin=.01, candidate_error=0, baseline_error=0)
        self.assertEqual(r['decision'], 'RETAIN_INCUMBENT')

    def test_meta_conditions_do_not_claim_self_improvement(self):
        rows = [{'campaign_id': str(i), 'candidate': 1, 'baseline': 0} for i in range(100)]
        r = improvement_decision(rows, alpha=.025, practical_margin=.01, candidate_error=0, baseline_error=0)
        self.assertEqual(r['decision'], 'ELIGIBLE_IF_PREMISES_VALID')
        self.assertFalse(r['self_improvement_established'])

    def test_meta_calibration_can_reverse(self):
        rows = [{'campaign_id': str(i), 'candidate': 1, 'baseline': 0} for i in range(100)]
        r = improvement_decision(rows, alpha=.025, practical_margin=.01, candidate_error=.4, baseline_error=.4)
        self.assertEqual(r['decision'], 'RETAIN_INCUMBENT')

    def test_meta_duplicates_not_independent(self):
        rows = [{'campaign_id': 'x', 'candidate': 1, 'baseline': 0}] * 100
        with self.assertRaises(ValueError):
            improvement_decision(rows, alpha=.025, practical_margin=.01, candidate_error=0, baseline_error=0)


if __name__ == '__main__': unittest.main()
