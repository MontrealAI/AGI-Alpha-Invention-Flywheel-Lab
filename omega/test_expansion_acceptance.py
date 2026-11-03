"""Independent adversarial acceptance checks for the expandable experiment.

These tests challenge the delivered bytes and declared scope rather than trusting
the constructor's success flag. Financial and public-information checks are added
against the native bridge once its public interface is available.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import tempfile
import unittest

from omega import compatibility
from omega import expansion_market as market


class IndependentCapabilityAcceptance(unittest.TestCase):
    def test_new_finite_machines_against_independent_state_pair_oracle(self):
        """Test new transition systems with a different exact checking method."""
        alphabet = ('a', 'b')
        for seed in range(16):
            rng = random.Random('independent-compatibility-development-' + str(seed))
            n = 1 + seed % 4
            table = [{a: (rng.randrange(n), str(rng.randrange(3)))
                      for a in alphabet} for _ in range(n)]

            def query(word):
                state, outputs = 0, []
                for symbol in word:
                    state, value = table[state][symbol]
                    outputs.append(value)
                return tuple(outputs)

            contract = compatibility.buyer_contract(
                'independent-development-' + str(seed), alphabet, max_states=n,
                assumptions=compatibility.package_contract()['buyer_supplied_assumptions'])
            adapter = compatibility.ActiveLearner(query, contract).learn()
            # Pair-graph traversal uses original transitions, independently of
            # learner observations and the shipped bounded-word validator.
            pending, seen = [(0, adapter['initial'])], set()
            while pending:
                left, right = pending.pop()
                if (left, right) in seen:
                    continue
                seen.add((left, right))
                for symbol in alphabet:
                    target, expected = table[left][symbol]
                    actual = adapter['transitions'][str(right)][symbol]
                    self.assertEqual(actual['output'], expected, (seed, left, right, symbol))
                    pending.append((target, actual['next']))

    def test_rehashed_semantically_wrong_delivery_is_rejected(self):
        """A mutually consistent package manifest is not output acceptance."""
        contract = compatibility.package_contract()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            result = compatibility.build_product(path, contract)
            self.assertTrue(result['accepted'])
            adapter = json.loads((path / 'adapter.json').read_text())
            initial = str(adapter['initial'])
            adapter['transitions'][initial]['commit']['output'] = 'fictitious_commit'
            raw = compatibility.canonical(adapter) + b'\n'
            (path / 'adapter.json').write_bytes(raw)
            manifest = json.loads((path / 'manifest.json').read_text())
            manifest['files']['adapter.json'] = hashlib.sha256(raw).hexdigest()
            manifest['accepted'] = True
            (path / 'manifest.json').write_bytes(compatibility.canonical(manifest))
            acceptance = compatibility.accept_product(path, contract)
            self.assertFalse(acceptance['accepted'])
            self.assertEqual(acceptance['reason'], 'COUNTEREXAMPLE')

    def test_decline_never_constructs_or_spends_probe_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'not-created'
            result = compatibility.build_product(path, proceed=False)
            self.assertEqual(result['query_count'], 0)
            self.assertFalse(path.exists())
            self.assertFalse(result['accepted'])

    def test_unverified_state_bound_is_not_established_by_finite_success(self):
        """A longer-memory oracle can defeat an incorrectly declared bound.

        This is a retained falsifier of universal compatibility claims, not an
        intended passing result for a real machine outside the contract.
        """
        contract = compatibility.package_contract(max_states=1)
        adapter = {'schema': compatibility.SCHEMA,
                   'alphabet': list(compatibility.ALPHABET), 'initial': 0,
                   'transitions': {'0': {a: {'next': 0, 'output': 'ok'}
                                         for a in compatibility.ALPHABET}}}

        def more_than_one_state(sequence):
            return tuple('late_state' if i >= 99 else 'ok'
                         for i, _ in enumerate(sequence))

        finite = compatibility.independent_acceptance(adapter, contract,
                                                      more_than_one_state)
        self.assertTrue(finite['accepted'])
        self.assertTrue(finite['conditional_on_buyer_assumptions'])
        long_word = ['append'] * 100
        self.assertNotEqual(compatibility.execute_adapter(adapter, long_word),
                            more_than_one_state(long_word))

    def test_permission_and_contract_changes_cannot_be_relabelled_as_acceptance(self):
        contract = compatibility.package_contract()
        contract['buyer_supplied_assumptions']['local_probe_authorized'] = False
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'PERMISSION_MISSING'):
                compatibility.build_product(Path(tmp) / 'not-created', contract)


class IndependentMarketAcceptance(unittest.TestCase):
    def test_matched_acquisition_does_not_depend_on_policy_name(self):
        """Common market draws must match if both policies buy the same reach."""
        world = market.worlds()['capability_gap']
        left = market.MarketRunner(world, mode='joint', seed=17)
        right = market.MarketRunner(world, mode='ordinary_reuse', seed=17)
        common = {'kind': 'campaign', 'size': 100, 'day': 0,
                  'price_cents': 29900, 'channel': 0, 'cost_cents': 50500}
        a, _ = left._contacts({**common, 'id': 'market-joint-0-1'})
        b, _ = right._contacts({**common, 'id': 'market-ordinary_reuse-0-1'})
        self.assertEqual([x['customer_id'] for x in a],
                         [x['customer_id'] for x in b])

    def test_customer_budget_does_not_follow_the_offered_price(self):
        world = market.worlds()['capability_gap']
        world['budget_cents'] = [37123]
        for price in market.PRICES:
            choice = market.buyer_choice(world, 29, 'independent-budget', 0,
                                         price, enhanced=False)
            self.assertEqual(choice['budget_cents'], 37123)
            if choice['provider'] == 'us':
                self.assertLessEqual(choice['price_cents'] + choice['adoption_cents'], 37123)

    def test_no_purchase_is_a_real_outside_option(self):
        world = market.worlds()['capability_gap']
        world['need_bps'] = 0
        for price in market.PRICES:
            choice = market.buyer_choice(world, 17, 'no-need', 0, price, True)
            self.assertEqual(choice['provider'], 'decline')
            self.assertEqual(choice['net_benefit_cents'], 0)

    def test_public_observation_rejects_a_hidden_world_field(self):
        runner = market.MarketRunner(market.worlds()['capability_gap'])
        public = market.public_state(runner.state,
                                     {'available_cents': 10000000, 'profit_cents': 0,
                                      'unrestricted_earned_cents': 0})
        with self.assertRaisesRegex(ValueError, 'ONLY_DECLARED_PUBLIC'):
            market.decide({**public, 'future_buyer_values': [1000000]}, 'joint')

    def test_nonentry_does_not_trigger_compulsory_construction(self):
        runner = market.MarketRunner(market.worlds()['capability_gap'], mode='nonentry')
        public = market.public_state(runner.state,
                                     {'available_cents': 10000000, 'profit_cents': 0,
                                      'unrestricted_earned_cents': 0})
        self.assertEqual(market.decide(public, 'nonentry')['kind'], 'wait')


if __name__ == '__main__':
    unittest.main()
