"""Exposed engineering controls for the preregistered whole-buyer repair."""
import copy
import hashlib
import importlib.util
import unittest
from pathlib import Path

from .choice import ALTERNATIVES, quote, subset_key
from .intent import evaluate
from .offer import COSTS
from .planning import plan


def row(ident='a', buyer='buyer', partner=None):
    return dict(id=ident, buyer=buyer, price=200, terms_id='complete-contract-v1',
                partner=partner, value=500, outside=100, collected=200,
                response='consented', accepted=True,
                costs={k: 50 if k == 'production' else 0 for k in COSTS})


def choices(rows, bundles, joint=500, outside=100, consent=True):
    result = {}
    for ids in bundles:
        groups = {}
        for r in rows:
            if r['id'] in ids:
                groups.setdefault(r['buyer'], []).append(r)
        for buyer, group in groups.items():
            result.setdefault(buyer, {})[subset_key(r['id'] for r in group)] = {
                'joint_value': joint, 'quote': quote(group), 'consent': consent,
                'outside': dict(human=outside, competitor_ai=70, self_service=50, no_purchase=0)}
    return result


def partners(rows, bundles):
    result = {}
    for ids in bundles:
        groups = {}
        for r in rows:
            if r['id'] in ids and r['partner'] is not None:
                groups.setdefault(r['partner'], []).append(r)
        for partner, group in groups.items():
            result.setdefault(partner, {})[subset_key(r['id'] for r in group)] = {
                'consent': True, 'quote': quote(group)}
    return result


def scenario(rows, bundles, **kw):
    result = dict(buyers=choices(rows, bundles), assumptions_known_at=5,
                  collection_lower_bounds={r['id']: r['price'] for r in rows},
                  costs={subset_key(ids): {k: sum(r['costs'][k] for r in rows if r['id'] in ids)
                                          for k in COSTS} for ids in bundles},
                  partners=partners(rows, bundles))
    result.update(kw)
    return result


class WholeBuyerTests(unittest.TestCase):
    def check(self, rows, bundles, buyer_choices=None, **kw):
        args = dict(wallets={r['buyer']: 1000 for r in rows}, available=1000,
                    earned=1000, sunk_acquisition=30,
                    buyer_choices=buyer_choices if buyer_choices is not None else choices(rows, bundles))
        args.update(kw)
        return evaluate(rows, bundles, **args)

    def test_pinned_incumbent_false_winner_and_repaired_refusal(self):
        path = Path(__file__).with_name('fixtures') / 'intent_before_whole_choice.py'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                         'bce149a60f112f28950e2e81151a29df304cceff')
        spec = importlib.util.spec_from_file_location('enterprise078.transactional_admission._control', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [row('a'), row('b')]
        bundles = [['a'], ['a', 'b']]
        old = module.evaluate(rows, bundles, wallets={'buyer': 1000}, available=1000,
                              earned=1000, sunk_acquisition=30)
        self.assertEqual(old['selected_bundle'], ['a', 'b'])
        result = self.check(rows, bundles, choices(rows, bundles, outside=300))
        self.assertEqual(result['selected_bundle'], [])  # Singleton also ties outside.
        explicit = choices(rows, bundles)
        explicit['buyer'][subset_key(['a', 'b'])]['outside']['human'] = 300
        self.assertEqual(self.check(rows, bundles, explicit)['selected_bundle'], ['a'])

    def test_joint_complementarity_is_not_vetoed_by_individual_utility(self):
        rows = [row('a'), row('b')]
        for r in rows:
            r['value'] = 0
            r['response'] = 'uncontacted'
        result = self.check(rows, [['a', 'b']], choices(rows, [['a', 'b']], joint=600))
        self.assertEqual(result['selected_bundle'], ['a', 'b'])
        self.assertEqual(result['selected_scenario_net_microUSD'], 270)

    def test_individual_consent_and_budget_do_not_imply_bundle_consent(self):
        rows = [row('a'), row('b')]
        evidence = choices(rows, [['a'], ['b']])
        result = self.check(rows, [['a', 'b']], evidence)
        self.assertEqual(result['selected_bundle'], [])
        self.assertIn('WHOLE_BUYER_CHOICE_UNESTABLISHED:buyer', result['outcomes'][1]['reasons'])

    def test_distinct_buyers_can_participate(self):
        rows = [row('a', 'buyer_a'), row('b', 'buyer_b')]
        self.assertEqual(self.check(rows, [['a', 'b']])['selected_bundle'], ['a', 'b'])

    def test_each_outside_option_is_required(self):
        rows, bundles = [row()], [['a']]
        for alternative in ALTERNATIVES:
            with self.subTest(alternative=alternative):
                evidence = choices(rows, bundles)
                del evidence['buyer'][subset_key(['a'])]['outside'][alternative]
                self.assertEqual(self.check(rows, bundles, evidence)['selected_bundle'], [])

    def test_explicit_unavailable_is_not_missing_or_zero(self):
        rows, bundles = [row()], [['a']]
        evidence = choices(rows, bundles)
        outside = evidence['buyer'][subset_key(['a'])]['outside']
        outside['competitor_ai'] = {'available': False}
        self.assertEqual(self.check(rows, bundles, evidence)['selected_bundle'], ['a'])
        outside['no_purchase'] = {'available': False}
        with self.assertRaisesRegex(ValueError, 'NO_PURCHASE_MUST_REMAIN_AVAILABLE'):
            self.check(rows, bundles, evidence)

    def test_best_outside_wins_and_ties_refuse(self):
        rows, bundles = [row()], [['a']]
        for rival in (300, 301):
            evidence = choices(rows, bundles)
            evidence['buyer'][subset_key(['a'])]['outside']['competitor_ai'] = rival
            self.assertEqual(self.check(rows, bundles, evidence)['selected_bundle'], [])

    def test_exact_bundle_refusal_survives_individual_consents(self):
        rows, bundles = [row()], [['a']]
        self.assertEqual(self.check(rows, bundles, choices(rows, bundles, consent=False))['selected_bundle'], [])

    def test_quote_price_and_terms_must_match(self):
        rows, bundles = [row()], [['a']]
        for field, value in [('price', 199), ('terms_id', 'stale-contract')]:
            evidence = choices(rows, bundles)
            evidence['buyer'][subset_key(['a'])]['quote']['a'][field] = value
            result = self.check(rows, bundles, evidence)
            self.assertEqual(result['selected_bundle'], [])
            self.assertIn('WHOLE_BUYER_QUOTE_CHANGED:buyer', result['outcomes'][1]['reasons'])

    def test_boolean_price_not_equal_to_integer_receipt(self):
        rows, bundles = [row()], [['a']]
        rows[0]['price'] = 1
        evidence = choices(rows, bundles)
        evidence['buyer'][subset_key(['a'])]['quote']['a']['price'] = True
        rows[0]['collected'] = 1
        with self.assertRaisesRegex(ValueError, 'EXACT_NONNEGATIVE_MONEY_REQUIRED'):
            self.check(rows, bundles, evidence)

    def test_order_does_not_change_participation(self):
        rows, bundles = [row('a'), row('b')], [['a', 'b']]
        evidence = choices(rows, bundles, joint=600)
        a = self.check(rows, bundles, evidence)
        b = self.check(rows[::-1], [['b', 'a']], evidence)
        self.assertEqual(set(a['selected_bundle']), set(b['selected_bundle']))
        self.assertEqual(a['selected_scenario_net_microUSD'], b['selected_scenario_net_microUSD'])

    def test_partner_participation_is_not_implied(self):
        rows = [row(partner='supplier')]
        self.assertEqual(self.check(rows, [['a']])['selected_bundle'], [])
        self.assertEqual(self.check(rows, [['a']], partners=partners(rows, [['a']]))['selected_bundle'], ['a'])

    def test_retrospective_is_not_prospective(self):
        result = self.check([row()], [['a']])
        self.assertEqual(result['information_timing'], 'retrospective')
        self.assertIsNone(result['prospective_selected_bundle'])
        self.assertFalse(result['native_catalog_admitted'])
        self.assertEqual(result['native_mutations'], 0)


class ProspectiveTests(unittest.TestCase):
    def check(self, rows=None, bundles=None, scenarios=None, **kw):
        rows = [row()] if rows is None else rows
        bundles = [['a']] if bundles is None else bundles
        scenarios = {'registered': scenario(rows, bundles)} if scenarios is None else scenarios
        inputs = [{k: r[k] for k in ('id', 'buyer', 'price', 'terms_id', 'partner')} for r in rows]
        args = dict(wallets={r['buyer']: 1000 for r in rows}, available=1000, earned=1000,
                    sunk_acquisition=30, decision_time=5, scenarios=scenarios)
        args.update(kw)
        return plan(inputs, bundles, **args)

    def test_positive_is_conditional_and_does_not_book_anything(self):
        result = self.check()
        self.assertEqual(result['selected_bundle'], ['a'])
        self.assertEqual(result['worst_case_net_microUSD'], 120)
        self.assertFalse(result['native_catalog_admitted'])
        self.assertFalse(result['observed_customer_evidence'])
        self.assertFalse(result['paid_commerce'])
        self.assertEqual(result['native_mutations'], 0)
        self.assertIsNone(result['forecast_expected_net'])

    def test_nonpayment_bound_preserves_no_entry(self):
        rows, bundles = [row()], [['a']]
        bad = scenario(rows, bundles, collection_lower_bounds={'a': 0})
        result = self.check(rows, bundles, {'paid': scenario(rows, bundles), 'nonpayment': bad})
        self.assertEqual(result['selected_bundle'], [])
        self.assertEqual(result['outcomes'][1]['worst_case_net_microUSD'], -80)

    def test_scenario_cost_shocks_are_not_ignored(self):
        rows, bundles = [row()], [['a']]
        for category in ('production', 'correction', 'support', 'financing', 'host_model', 'liability_tail'):
            with self.subTest(category=category):
                shock = scenario(rows, bundles)
                shock['costs'][subset_key(['a'])][category] += 201
                result = self.check(rows, bundles, {'base': scenario(rows, bundles), 'shock': shock})
                self.assertEqual(result['selected_bundle'], [])

    def test_all_scenarios_require_participation_even_with_positive_net(self):
        rows, bundles = [row(partner='supplier')], [['a']]
        for defect in ('buyer', 'partner', 'consent'):
            bad = scenario(rows, bundles)
            entry = bad['buyers']['buyer'][subset_key(['a'])]
            if defect == 'buyer':
                entry['outside']['competitor_ai'] = 301
            elif defect == 'consent':
                entry['consent'] = False
            else:
                bad['partners']['supplier'][subset_key(['a'])]['consent'] = False
            result = self.check(rows, bundles, {'good': scenario(rows, bundles), 'bad': bad})
            self.assertEqual(result['selected_bundle'], [])
            self.assertEqual(result['outcomes'][1]['worst_case_net_microUSD'], 120)

    def test_cannot_switch_bundle_after_learning_scenario(self):
        rows, bundles = [row('a'), row('b')], [['a'], ['b']]
        left = scenario(rows, bundles, collection_lower_bounds={'a': 200, 'b': 0})
        right = scenario(rows, bundles, collection_lower_bounds={'a': 0, 'b': 200})
        result = self.check(rows, bundles, {'left': left, 'right': right})
        self.assertEqual(result['selected_bundle'], [])

    def test_maximin_and_registered_order_ties(self):
        rows, bundles = [row('a'), row('b')], [['a'], ['b']]
        left = scenario(rows, bundles, collection_lower_bounds={'a': 100, 'b': 200})
        right = scenario(rows, bundles, collection_lower_bounds={'a': 100, 'b': 99})
        result = self.check(rows, bundles, {'left': left, 'right': right})
        self.assertEqual(result['selected_bundle'], ['a'])
        right['collection_lower_bounds']['b'] = 100
        self.assertEqual(self.check(rows, bundles, {'left': left, 'right': right})['selected_bundle'], ['a'])

    def test_no_entry_wins_economic_ties(self):
        rows, bundles = [row()], [['a']]
        state = scenario(rows, bundles, collection_lower_bounds={'a': 50})
        self.assertEqual(self.check(rows, bundles, {'tie': state})['selected_bundle'], [])

    def test_whole_wallet_and_upfront_cash_not_future_receipts(self):
        rows, bundles = [row('a'), row('b')], [['a', 'b']]
        state = scenario(rows, bundles, buyers=choices(rows, bundles, joint=600))
        for kw, reason in [({'wallets': {'buyer': 300}}, 'SHARED_BUYER_WALLET_EXCEEDED'),
                           ({'available': 90}, 'BUNDLE_NOT_EARNED_FUNDED:base'),
                           ({'earned': 90}, 'BUNDLE_NOT_EARNED_FUNDED:base')]:
            result = self.check(rows, bundles, {'base': state}, **kw)
            self.assertEqual(result['selected_bundle'], [])
            self.assertIn(reason, result['outcomes'][1]['reasons'])

    def test_unknown_bounds_and_costs_remain_unknown(self):
        rows, bundles = [row()], [['a']]
        for defect in ('missing_bound', 'unknown_bound', 'missing_costs', 'unknown_cost'):
            state = scenario(rows, bundles)
            if defect == 'missing_bound':
                del state['collection_lower_bounds']['a']
            elif defect == 'unknown_bound':
                state['collection_lower_bounds']['a'] = None
            elif defect == 'missing_costs':
                del state['costs'][subset_key(['a'])]
            else:
                state['costs'][subset_key(['a'])]['host_model'] = None
            result = self.check(rows, bundles, {'unknown': state})
            self.assertEqual(result['selected_bundle'], [])
            self.assertIsNone(result['outcomes'][1]['worst_case_net_microUSD'])

    def test_missing_cost_category_rejected(self):
        state = scenario([row()], [['a']])
        del state['costs'][subset_key(['a'])]['financing']
        with self.assertRaisesRegex(ValueError, 'COMPLETE_COST_CATEGORIES_REQUIRED'):
            self.check(scenarios={'bad': state})

    def test_joint_package_costs_need_not_equal_singleton_sums(self):
        rows, bundles = [row('a'), row('b')], [['a'], ['b'], ['a', 'b']]
        state = scenario(rows, bundles, buyers=choices(rows, bundles, joint=600))
        state['costs'][subset_key(['a', 'b'])]['onboarding'] = 400
        result = self.check(rows, bundles, {'coordination': state})
        self.assertEqual(result['selected_bundle'], ['a'])
        self.assertEqual(result['outcomes'][3]['worst_case_net_microUSD'], -130)

    def test_partner_consent_cannot_transfer_across_terms_or_package(self):
        rows, bundles = [row('a', partner='supplier'), row('b', partner='supplier')], [['a', 'b']]
        state = scenario(rows, bundles, buyers=choices(rows, bundles, joint=600))
        state['partners'] = partners(rows, [['a'], ['b']])
        self.assertEqual(self.check(rows, bundles, {'base': state})['selected_bundle'], [])
        state['partners'] = partners(rows, bundles)
        rows[0]['terms_id'] = 'different-obligations-v2'
        state['buyers'] = choices(rows, bundles, joint=600)
        self.assertEqual(self.check(rows, bundles, {'base': state})['selected_bundle'], [])

    def test_future_dated_assumptions_rejected(self):
        state = scenario([row()], [['a']], assumptions_known_at=6)
        with self.assertRaisesRegex(ValueError, 'FUTURE_INFORMATION_FORBIDDEN'):
            self.check(scenarios={'future': state})

    def test_realized_collection_and_acceptance_fields_rejected(self):
        inputs = [{k: row()[k] for k in ('id', 'buyer', 'price', 'terms_id')}]
        args = dict(wallets={'buyer': 1000}, available=1000, earned=1000,
                    sunk_acquisition=30, decision_time=5, scenarios={'base': scenario([row()], [['a']])})
        for field in ('collected', 'accepted'):
            bad = copy.deepcopy(inputs)
            bad[0][field] = 200
            with self.assertRaisesRegex(ValueError, 'PREDECISION_OFFER_FIELDS_ONLY'):
                plan(bad, [['a']], **args)
            state = scenario([row()], [['a']])
            state[field] = {'a': 200}
            with self.assertRaisesRegex(ValueError, 'PREDECISION_SCENARIO_FIELDS_ONLY'):
                self.check(scenarios={'future': state})

    def test_realized_outcomes_cannot_change_separate_predecision_plan(self):
        rows = [row()]
        state = scenario(rows, [['a']])
        before = self.check(rows, scenarios={'base': state})
        rows[0]['collected'] = 0
        rows[0]['accepted'] = False
        self.assertEqual(before, self.check(rows, scenarios={'base': state}))

    def test_empty_scenario_set_and_duplicate_bundles_rejected(self):
        with self.assertRaisesRegex(ValueError, 'REGISTERED_PREDECISION_SCENARIOS_REQUIRED'):
            self.check(scenarios={})
        with self.assertRaisesRegex(ValueError, 'DISTINCT_REGISTERED_BUNDLE_REQUIRED'):
            self.check(bundles=[['a'], ['a']])

    def test_malformed_money_is_rejected(self):
        for value in (True, -1, 1.5, float('nan'), float('inf')):
            state = scenario([row()], [['a']], collection_lower_bounds={'a': value})
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(scenarios={'bad': state})

    def test_input_not_mutated(self):
        rows, bundles = [row()], [['a']]
        scenarios = {'base': scenario(rows, bundles)}
        before = copy.deepcopy((rows, bundles, scenarios))
        self.check(rows, bundles, scenarios)
        self.assertEqual((rows, bundles, scenarios), before)


if __name__ == '__main__':
    unittest.main()
