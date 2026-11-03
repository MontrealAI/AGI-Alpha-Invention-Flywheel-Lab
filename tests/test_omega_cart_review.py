"""Independent exhaustive strategic checks over arbitrary posted menus."""
import copy
import itertools
import random
import unittest

from fractions import Fraction
from mechanism_harness import cart_program as carts
from mechanism_harness.market_cases import market


def oracle(m, p, private):
    # Independently enumerate ORIGINAL menu entries, retaining dominated prices,
    # repeated service sets and outside entries. Never call producer helpers.
    offers = p['menu']
    lookup = {tuple(o['services']): j for j, o in enumerate(m['outcomes'])}
    candidates = [(0, 0, 0, 0)]
    for bits in itertools.product((False, True), repeat=len(offers)):
        selected = [entry for include, entry in zip(bits, offers) if include]
        price = sum(entry['price_cents'] for entry in selected)
        if price > private['budget_cents']:
            continue
        services = set()
        for entry in selected:
            services.update(next(o['services'] for o in m['outcomes'] if o['id'] == entry['outcome_id']))
        j = lookup[tuple(sorted(services))]
        utility = 0 if not j else private['values'][j] - private['outside_utility'] - price
        fee = (price * m['payment_bps'] + 9999) // 10000
        contribution = price - fee - m['outcomes'][j]['cost_cents']
        candidates.append((utility, contribution, j, price))
    best_utility = max(x[0] for x in candidates)
    selected = min((x for x in candidates if x[0] == best_utility),
                   key=lambda x: (x[2] != 0, x[1], x[3], m['outcomes'][x[2]]['id']))
    return (m['outcomes'][selected[2]]['id'], selected[3], selected[0], selected[1])


class IndependentCartChoiceReview(unittest.TestCase):
    def test_dp_matches_raw_menu_powerset_with_overlap_and_duplicate_goods(self):
        rng = random.Random(613479)
        m = market(1337, 'substitute', width=2)
        # Fixed before execution, these are engineering probes, not selected wins.
        for case in range(120):
            p = carts.null_program(m)
            p['menu'] = [{'outcome_id': rng.choice(m['outcomes'][1:])['id'],
                          'price_cents': rng.randrange(0, 2500)} for _ in range(6)]
            private = {'values': [0] + [rng.randrange(0, 5000) for _ in range(3)],
                       'budget_cents': rng.randrange(0, 5000),
                       'outside_utility': rng.randrange(0, 700)}
            actual = carts.buyer_choose(m, p, private)
            with self.subTest(case=case):
                self.assertEqual((actual['outcome_id'], actual['price_cents'],
                                  actual['utility_cents'], actual['seller_contribution_cents']),
                                 oracle(m, p, private))

    def test_full_milp_matches_tiny_exhaustive_closed_menu_search(self):
        from mechanism_harness.cart_synthesis import synthesize
        rng = random.Random(23759)
        for case in range(5):
            m = market(1337, 'substitute', width=2)
            m['types'] = m['types'][:2]
            m['payment_bps'] = 0
            for outcome in m['outcomes'][1:]:
                outcome['cost_cents'] = rng.randrange(0, 3)
            for typ in m['types']:
                typ.update(values=[0] + [rng.randrange(0, 8) for _ in range(3)],
                           budget_cents=rng.randrange(1, 7), outside_utility=0, weight=1)
            cap = max(t['budget_cents'] for t in m['types']) + 1
            best = Fraction(0)
            for prices in itertools.product(range(cap + 1), repeat=3):
                if prices[2] > prices[0] + prices[1]:
                    continue
                p = carts.null_program(m)
                p['menu'] = [{'outcome_id': o['id'], 'price_cents': q}
                             for o, q in zip(m['outcomes'][1:], prices)]
                total = 0
                valid = True
                for typ in m['types']:
                    private = {key: typ[key] for key in ('values', 'budget_cents', 'outside_utility')}
                    outcome, price, utility, profit = oracle(m, p, private)
                    if profit < 0 or (outcome != 'outside' and utility < 1):
                        valid = False
                        break
                    # Independent strict-gap model: every affordable different
                    # outcome must be at least one integer cent worse.
                    for j, q in enumerate(prices, 1):
                        if q <= typ['budget_cents'] and m['outcomes'][j]['id'] != outcome:
                            if utility < typ['values'][j] - q + 1:
                                valid = False
                    total += profit
                if valid:
                    best = max(best, Fraction(total, len(m['types'])))
            built = synthesize(m, mode='full')
            with self.subTest(case=case):
                self.assertIsNotNone(built['program'])
                self.assertEqual(Fraction(built['verification']['expected_contribution_cents']), best)

    def test_changed_union_semantics_are_rejected(self):
        m = market(1337, 'substitute', width=2)
        p = carts.null_program(m)
        changed = copy.deepcopy(m)
        changed['outcomes'][-1]['services'] = ['another-service']
        with self.assertRaises(ValueError):
            carts.buyer_choose(changed, p, {'values': [0, 10, 10, 10],
                                          'budget_cents': 10, 'outside_utility': 0})

    def test_historical_213_cent_arbitrage_is_executable_under_hard_budget(self):
        m = market(1337, 'substitute', width=2)
        p = carts.null_program(m)
        p['menu'] = [{'outcome_id': 'first', 'price_cents': 518},
                     {'outcome_id': 'second', 'price_cents': 823},
                     {'outcome_id': 'joint', 'price_cents': 1554}]
        private = {'values': [0, 518, 823, 2000], 'budget_cents': 1341, 'outside_utility': 0}
        selected = carts.buyer_choose(m, p, private)
        self.assertEqual(selected['outcome_id'], 'joint')
        self.assertEqual(selected['price_cents'], 1341)
        self.assertEqual(selected['basket'], ['first', 'second'])
        self.assertEqual(oracle(m, p, private)[1], 1341)


if __name__ == '__main__':
    unittest.main()
