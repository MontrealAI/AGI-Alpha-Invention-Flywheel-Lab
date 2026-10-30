import copy
import unittest
from unittest.mock import patch
from adaptive_enterprise.learning import Policy, validate_public, digest, ARMS


def observation(cycle=0):
    return {'schema': 'agi-alpha/adaptive012-public/v1', 'cycle': cycle,
        'account': {'state_digest': 'a'*64, 'available_microUSD': 100_000_000, 'earned_microUSD': 1_000_000, 'cash_microUSD': 150_000_000, 'pending_payment_count': 0, 'learning_budget_microUSD': 50_000},
        'supplier': {'quoted_unit_cost_microUSD': 100_000, 'available_capacity_units': 4, 'announced_latency_hours': 1},
        'offers': [{'id': 'reconciliation-verified', 'service_id': 'reconciliation', 'segment': 'all', 'scope': 'authorized-row-reconciliation', 'method': 'generated-intake', 'verification': 'independent-row-conservation', 'remedy': 'refund-on-contract-failure', 'channel': 'authorized-synthetic-inbound', 'capacity_units': 1, 'price_microUSD': 20_000_000, 'human_anchor_microUSD': 20_000_000, 'production_cost_microUSD': 1_000_000, 'applicable_job_ids': ['job1'], 'delivery_hours': 2, 'evidence_level': 'executed-checker-qualified', 'quote_cost_microUSD': 100_000, 'onboarding_cost_microUSD': 200_000, 'payment_fee_bps': 290, 'payment_fixed_microUSD': 300_000}],
        'customers': [{'id': 'buyer1', 'segment': 'small_business', 'requested_services': ['reconciliation'], 'deadline_hours': 24, 'onboarded': False, 'settled_jobs': 0, 'last_outcome': 'NONE'}],
        'feedback': [], 'competitor_ads': [{'rival_id': 'rival1', 'service_id': 'reconciliation', 'advertised_price_microUSD': 20_000_000, 'advertised_delivery_hours': 24, 'observed_cycle': cycle, 'evidence_level': 'public-advertisement'}], 'history_digest': 'b'*64}


def feedback(decision, event_id, outcome, observed_cycle=1):
    return {'event_id': event_id, 'action_id': decision['action_id'], 'offer_id': decision['offer_id'], 'customer_id': decision['customer_id'], 'observed_cycle': observed_cycle, 'offered_price_microUSD': decision['price_microUSD'], 'outcome': outcome, 'complete_cost_microUSD': 2_000_000, 'collected_microUSD': decision['price_microUSD'] if outcome == 'SETTLED' else 0, 'delivery_hours': 2}


class AdaptiveLearningTests(unittest.TestCase):
    def test_exact_public_schema_rejects_latent_information_at_every_level(self):
        for target, field in [('root', 'seed'), ('account', 'private_buyer_value'), ('supplier', 'future_cost'), ('offer', 'reservation_price'), ('customer', 'world_label'), ('ad', 'actual_rival_cost')]:
            data = observation()
            row = data if target == 'root' else data[target] if target in {'account', 'supplier'} else data[{'offer': 'offers', 'customer': 'customers', 'ad': 'competitor_ads'}[target]][0]
            row[field] = 99
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_public(data)

    def test_validated_observation_and_act_never_mutate_input(self):
        original = observation()
        snapshot = copy.deepcopy(original)
        validated = validate_public(original)
        validated['offers'][0]['price_microUSD'] = 1
        policy = Policy()
        decision = policy.act(original)
        self.assertEqual(original, snapshot)
        self.assertEqual(policy.act(original), decision)
        self.assertEqual(policy.export()['action_count'], 1)

    def test_future_feedback_or_ads_and_nan_bool_money_refuse(self):
        data = observation()
        data['competitor_ads'][0]['observed_cycle'] = 1
        with self.assertRaises(ValueError):
            validate_public(data)
        for path, value in [('cost', True), ('latency', float('nan'))]:
            data = observation()
            if path == 'cost': data['offers'][0]['production_cost_microUSD'] = value
            else: data['supplier']['announced_latency_hours'] = value
            with self.assertRaises(ValueError): validate_public(data)

    def test_binary_rejection_is_censored_conversion_not_value_oracle(self):
        policy = Policy()
        first = policy.act(observation())
        data = observation(1)
        data['feedback'] = [feedback(first, 'decline1', 'NO_PURCHASE')]
        policy.act(data)
        stats = next(s for s in policy.export()['statistics'].values() if s['purchase_no'])
        self.assertEqual(stats['purchase_no'], 1)
        self.assertNotIn('reservation_price', str(policy.export()))
        self.assertFalse(any(k in stats for k in ['willingness_to_pay', 'buyer_value', 'reservation_value']))

    def test_duplicate_feedback_never_double_counts_acceptance_or_settlement(self):
        policy = Policy()
        first = policy.act(observation())
        accepted = feedback(first, 'accepted1', 'ACCEPTED')
        settled = feedback(first, 'settled1', 'SETTLED')
        data = observation(1)
        data['feedback'] = [accepted, settled, settled]
        policy.act(data)
        data['cycle'] = 2
        data['competitor_ads'][0]['observed_cycle'] = 2
        policy.act(data)
        stats = next(s for s in policy.export()['statistics'].values() if s['settled'])
        self.assertEqual(stats['purchase_yes'], 1)
        self.assertEqual(stats['settled'], 1)
        self.assertEqual(stats['collected_microUSD'], first['price_microUSD'])

    def test_pending_payment_is_not_a_default_or_collection_failure(self):
        policy = Policy()
        first = policy.act(observation())
        data = observation(1)
        data['feedback'] = [feedback(first, 'pending1', 'PENDING')]
        policy.act(data)
        state = policy.export()
        self.assertIn(first['action_id'], state['pending_action_ids'])
        self.assertTrue(all(s['refunded'] == 0 and s['purchase_no'] == 0 for s in state['statistics'].values()))
        data = observation(2)
        data['feedback'] = [feedback(first, 'settled1', 'SETTLED', 2)]
        policy.act(data)
        self.assertNotIn(first['action_id'], policy.export()['pending_action_ids'])

    def test_conflicting_event_identity_is_rejected_and_stale_pending_not_reopened(self):
        policy = Policy()
        first = policy.act(observation())
        data = observation(1)
        data['feedback'] = [feedback(first, 'terminal1', 'SETTLED')]
        policy.act(data)
        data = observation(2)
        data['feedback'] = [feedback(first, 'stale-pending', 'PENDING', 2)]
        policy.act(data)
        self.assertNotIn(first['action_id'], policy.export()['pending_action_ids'])
        data = observation(3)
        data['feedback'] = [feedback(first, 'terminal1', 'REFUNDED', 3)]
        with self.assertRaises(ValueError): policy.act(data)

    def test_costed_probe_is_adjudicated_without_turning_rejection_into_price(self):
        policy = Policy()
        policy.act(observation())
        probe = policy.act(observation(1))
        self.assertEqual(probe['action'], 'EXPERIMENT')
        data = observation(2)
        data['feedback'] = [feedback(probe, 'probe-decline', 'NO_PURCHASE', 2)]
        policy.act(data)
        record = policy.export()['diagnostic_adjudications'][0]
        self.assertEqual(record['decision'], 'INCONCLUSIVE_COMPARE_BOUNDED_ALTERNATIVE')
        self.assertEqual(record['source_event_ids'], ['probe-decline'])
        self.assertEqual(record['reported_realized_contribution_microUSD'], -2_000_000)
        self.assertIn('unknown', record['inference'])

    def test_observed_quality_failure_becomes_executable_applicability_constraint(self):
        policy = Policy()
        policy.act(observation())
        probe = policy.act(observation(1))
        data = observation(2)
        data['feedback'] = [feedback(probe, 'quality-reject', 'REJECTED_QUALITY', 2)]
        decision = policy.act(data)
        self.assertEqual(decision['action'], 'WITHDRAW')
        self.assertEqual(policy.export()['diagnostic_adjudications'][0]['decision'], 'REQUIRE_ALTERNATIVE_EXECUTABLE_PIPELINE')
        alternative = copy.deepcopy(data['offers'][0])
        alternative.update(id='qualified-repair', method='different-verified-intake')
        data['offers'].append(alternative)
        data['history_digest'] = 'c'*64
        self.assertEqual(policy.act(data)['offer_id'], 'qualified-repair')

    def test_complete_cost_formula_includes_unconditional_costs(self):
        policy = Policy()
        data = observation()
        decision = policy.act(data)
        candidate = policy.export()['trace'][0]['selected_public_estimates']
        offer = data['offers'][0]
        fee = (decision['price_microUSD'] * offer['payment_fee_bps'] + 9999)//10000 + offer['payment_fixed_microUSD']
        expected = candidate['purchase_probability_estimate'] * (candidate['collection_probability_estimate'] * decision['price_microUSD'] - fee - offer['onboarding_cost_microUSD']) - offer['production_cost_microUSD'] - data['supplier']['quoted_unit_cost_microUSD'] - offer['quote_cost_microUSD'] - decision['learning_cost_microUSD']
        self.assertEqual(decision['expected_net_microUSD'], int(expected//1))
        self.assertLessEqual(decision['learning_cost_microUSD'], data['account']['learning_budget_microUSD'])

    def test_unavailable_capacity_expired_sla_no_applicability_and_loss_no_bid(self):
        for mode in ['capacity', 'deadline', 'applicability', 'loss', 'cash']:
            data = observation()
            if mode == 'capacity': data['supplier']['available_capacity_units'] = 0
            if mode == 'deadline': data['customers'][0]['deadline_hours'] = 1
            if mode == 'applicability': data['offers'][0]['applicable_job_ids'] = []
            if mode == 'loss': data['offers'][0]['production_cost_microUSD'] = 200_000_000
            if mode == 'cash': data['account']['available_microUSD'] = 0; data['account']['earned_microUSD'] = 0
            with self.subTest(mode=mode): self.assertEqual(Policy().act(data)['action'], 'WITHDRAW')

    def test_price_is_human_anchored_and_no_automatic_ai_cost_markup(self):
        data = observation()
        decision = Policy().act(data)
        anchor = data['offers'][0]['human_anchor_microUSD']
        self.assertGreaterEqual(decision['price_microUSD'], int(anchor*.5))
        self.assertLessEqual(decision['price_microUSD'], int(anchor*1.4))
        self.assertGreater(decision['price_microUSD'], data['offers'][0]['production_cost_microUSD'] * 2)

    def test_repeat_channel_requires_prior_authorized_context(self):
        data = observation()
        data['offers'][0]['channel'] = 'authorized_repeat'
        self.assertEqual(Policy().act(data)['action'], 'WITHDRAW')
        data['customers'][0]['onboarded'] = True
        self.assertNotEqual(Policy().act(data)['action'], 'WITHDRAW')
        inbound = observation()
        inbound['offers'][0]['channel'] = 'qualified_inbound'
        self.assertNotEqual(Policy().act(inbound)['action'], 'WITHDRAW')

    def test_price_search_extends_boundary_then_refines_with_trace(self):
        data = observation()
        data['competitor_ads'][0]['advertised_price_microUSD'] = 200_000_000
        policy = Policy()
        decision = policy.act(data)
        search = policy.export()['trace'][-1]['selected_public_estimates']['price_search']
        self.assertTrue(search['initial_boundary_triggered'])
        self.assertEqual(search['tested_factor_range'], [.35, 1.65])
        self.assertEqual(search['local_factor_resolution'], .01)
        self.assertEqual(search['local_price_resolution_microUSD'], 200_000)
        self.assertGreaterEqual(decision['price_microUSD'], 7_000_000)
        self.assertLessEqual(decision['price_microUSD'], 33_000_000)
        self.assertTrue(search['final_declared_boundary_hit'])
        self.assertIn('not a claim of global', search['scope'])

    def test_interior_refinement_and_fixed_control_scope_are_explicit(self):
        adaptive = Policy()
        adaptive.act(observation())
        search = adaptive.export()['trace'][-1]['selected_public_estimates']['price_search']
        self.assertFalse(search['initial_boundary_triggered'])
        self.assertEqual(search['tested_factor_range'], [.5, 1.4])
        self.assertGreater(search['evaluated_prices'], 7)
        fixed = Policy('strong_fixed')
        decision = fixed.act(observation())
        search = fixed.export()['trace'][-1]['selected_public_estimates']['price_search']
        self.assertEqual(decision['price_microUSD'], 19_000_000)
        self.assertEqual(search['tested_factor_range'], [.95, .95])
        self.assertEqual(search['local_factor_resolution'], 0)

    def test_multiple_complete_offers_can_change_scope_method_and_channel(self):
        data = observation()
        second = copy.deepcopy(data['offers'][0])
        second.update(id='evidence-packet', method='source-matrix', scope='source-grounded-evidence', verification='independent-citations', channel='repeat-client', production_cost_microUSD=500_000)
        data['offers'].append(second)
        decision = Policy().act(data)
        self.assertEqual(decision['offer_id'], 'evidence-packet')
        selected = Policy().act(data)
        self.assertEqual(selected['channel'], 'repeat-client')

    def test_exploration_has_costed_competing_hypotheses_and_falsifiers(self):
        policy = Policy()
        policy.act(observation())
        data = observation(1)
        decision = policy.act(data)
        self.assertTrue(decision['exploration'])
        experiment = decision['experiment']
        self.assertGreaterEqual(experiment['experiment_resource_cost_microUSD'], 0)
        self.assertEqual(experiment['maximum_exposure_microUSD'], decision['max_exposure_microUSD'])
        self.assertEqual(len(experiment['competing_hypotheses']), 4)
        self.assertTrue(all(h['falsifier'] for h in experiment['competing_hypotheses']))
        self.assertIn('switch_rule', experiment)
        self.assertGreater(experiment['decision_value_upper_bound_microUSD'], 0)

    def test_opponent_pattern_comes_from_observed_delayed_ads(self):
        policy = Policy()
        for cycle, price in [(0, 24_000_000), (1, 22_000_000), (2, 20_000_000)]:
            data = observation(cycle)
            data['competitor_ads'][0]['advertised_price_microUSD'] = price
            policy.act(data)
        signal = policy.export()['trace'][-1]['selected_public_estimates']['opponent_signal']
        self.assertEqual(signal['pattern'], 'bounded_delayed_observed_quote_trend')
        self.assertLess(signal['bounded_projected_quote_microUSD'], signal['advertised_comparator_price_microUSD'])
        ablated = Policy('no_opponent')
        ablated.act(observation())
        self.assertEqual(ablated.export()['trace'][0]['selected_public_estimates']['opponent_signal']['pattern'], 'not_used_by_arm')

    def test_change_detection_is_observed_and_resets_uncertainty(self):
        policy = Policy()
        actions = []
        for cycle in range(12):
            data = observation(cycle)
            if actions:
                previous = actions[-1]
                data['feedback'] = [feedback(previous, 'event'+str(cycle), 'SETTLED' if cycle <= 6 else 'NO_PURCHASE', cycle)]
            actions.append(policy.act(data))
        data = observation(12)
        data['feedback'] = [feedback(actions[-1], 'event12', 'NO_PURCHASE', 12)]
        policy.act(data)
        self.assertTrue(policy.export()['change_events'])
        self.assertEqual(len(policy.export()['change_events'][0]['source_event_ids']), 12)

    def test_quality_rejection_never_counts_as_purchase(self):
        policy = Policy()
        decision = policy.act(observation())
        data = observation(1)
        data['feedback'] = [feedback(decision, 'quality-only', 'REJECTED_QUALITY')]
        policy.act(data)
        self.assertEqual(sum(s['purchase_yes'] for s in policy.export()['statistics'].values()), 0)
        self.assertEqual(sum(s['quality_rejects'] for s in policy.export()['statistics'].values()), 1)

    def test_legacy_control_calls_actual_retained_optimizer_and_uses_returned_quote(self):
        from enterprise.pricing import optimize_price
        data = observation()
        policy = Policy('strategic_011_public_priors')
        with patch('enterprise.pricing.optimize_price', wraps=optimize_price) as solver:
            decision = policy.act(data)
            self.assertEqual(solver.call_count, 1)
            args = solver.call_args.args
            expected = optimize_price(*args, **solver.call_args.kwargs)
            self.assertEqual(decision['price_microUSD'], int(round(expected['price'] * 1_000_000)))
            data['cycle'] = 1
            data['history_digest'] = 'c'*64
            policy.act(data)
            self.assertEqual(solver.call_count, 1)
        selected = policy.export()['trace'][0]['selected_public_estimates']
        adapter = selected['legacy_public_adapter']
        self.assertEqual(adapter['source_call_path'], 'enterprise.pricing.optimize_price')
        self.assertEqual(adapter['public_input']['trust'], adapter['public_input']['rival_trust'])
        self.assertEqual(adapter['declared_common_priors']['rival_cost_multiplier'], 1)
        self.assertEqual(adapter['declared_common_priors']['collection_probability'], .95)
        self.assertEqual(adapter['declared_common_priors']['refund_probability'], .03)
        self.assertEqual(adapter['declared_common_priors']['our_hours'], 3)
        self.assertEqual(adapter['declared_common_priors']['rival_hours'], 24)
        self.assertTrue(policy.export()['trace'][1]['selected_public_estimates']['legacy_public_adapter']['cache_hit'])

    def test_actual_joint_bundle_quote_is_not_overwritten_by_factor_policy(self):
        for arm in ['full_adaptive', 'strategic_011_public_priors', 'strong_fixed']:
            data = observation()
            data['offers'][0].update(id='operations-bundle', service_id='operations_bundle', method='operations_bundle', capacity_units=3, human_anchor_microUSD=60_000_000, price_microUSD=43_123_456)
            data['customers'][0]['requested_services'] = ['operations_bundle']
            data['competitor_ads'][0]['service_id'] = 'operations_bundle'
            policy = Policy(arm)
            decision = policy.act(data)
            self.assertEqual(decision['price_microUSD'], 43_123_456)
            search = policy.export()['trace'][0]['selected_public_estimates']['price_search']
            self.assertIn('enterprise.pricing.optimize_bundle', search['source_call_path'])
            self.assertEqual(search['evaluated_prices'], 1)

    def test_control_arms_receive_same_information_and_keep_distinct_methods(self):
        data = observation()
        for arm in ARMS:
            policy = Policy(arm)
            decision = policy.act(data)
            self.assertEqual(decision['evidence_digest'], digest(data))
            if arm == 'strong_fixed': self.assertEqual(decision['price_microUSD'], int(data['offers'][0]['human_anchor_microUSD']*.95))
            if arm == 'ordinary_adaptive':
                later = policy.act(observation(1))
                self.assertIsNone(later['experiment'])
        with self.assertRaises(ValueError): Policy('omniscient')
