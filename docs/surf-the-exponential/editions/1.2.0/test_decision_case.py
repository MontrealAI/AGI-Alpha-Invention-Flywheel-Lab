"""Regression and adversarial checks for the finite decision bridge."""
import copy
import json
from pathlib import Path
import unittest
import decision_case as producer
import check_decision_case as checker

class DecisionBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = producer.study()

    def test_complete_independent_audit(self):
        self.assertEqual(checker.audit(self.result)['status'], 'PASS')

    def test_three_way_is_not_a_pairwise_failure(self):
        r = self.result['three_way_witness']
        self.assertEqual(r['minimal_incompatible_sets'], [[0,1,2]])
        for pair in ((0,1),(0,2),(1,2)):
            self.assertTrue(producer.shared_actions(r['rows'],pair))
        self.assertFalse(producer.shared_actions(r['rows'],(0,1,2)))
        self.assertEqual(r['minimum_labels'],2)

    def test_initial_two_messages_not_three(self):
        r = producer.construct(producer.config())
        self.assertEqual((r['minimum_cost'],r['route']['signal_labels'],len(r['route']['queries'])),(5,2,1))
        checker.audit_route(producer.config(),r)

    def test_new_action_can_remove_need_for_observation(self):
        c=producer.config(fallback_unit_cost=4);r=producer.construct(c)
        self.assertEqual((r['minimum_cost'],r['route']['queries']),(4,[]))
        checker.audit_route(c,r)

    def test_before_frontier_keeps_best_complete_alternative(self):
        r=producer.construct(producer.config(query_cost=5))
        self.assertEqual((r['minimum_cost'],r['decision']),(7,'DECLINE_NO_SURPLUS'))
        self.assertEqual(r['route']['queries'],[])

    def test_price_equality_is_not_strict_surplus(self):
        r=producer.construct(producer.config(query_cost=2,opening_cash=6))
        self.assertEqual((r['minimum_cost'],r['decision']),(6,'DECLINE_NO_SURPLUS'))

    def test_unfunded_positive_surplus_is_declined(self):
        r=producer.construct(producer.config(opening_cash=4))
        self.assertEqual(r['worst_case_surplus'],1)
        self.assertEqual(r['decision'],'DECLINE_UNFUNDED')

    def test_competition_can_erase_capture(self):
        r=producer.construct(producer.config(quote=4))
        self.assertEqual(r['decision'],'DECLINE_NO_SURPLUS')

    def test_announcement_without_query_authority_does_not_help(self):
        r=producer.construct(producer.config(allowed_queries=[]))
        self.assertEqual(r['minimum_cost'],7)

    def test_successor_needs_new_distinctions(self):
        c=producer.config(demand=2,quote=11,opening_cash=10);r=producer.construct(c)
        self.assertEqual((r['minimum_cost'],r['route']['signal_labels'],len(r['route']['queries'])),(10,3,2))
        checker.audit_route(c,r)

    def test_inherited_channel_can_be_retired_instead_of_overtrusted(self):
        c=producer.config(demand=2,quote=11,opening_cash=10,allowed_queries=[0]);r=producer.construct(c)
        self.assertEqual((r['minimum_cost'],r['route']['queries'],r['decision']),(12,[],'DECLINE_NO_SURPLUS'))

    def test_strong_conventional_oracle_on_all_operating_cases(self):
        for entry in self.result['cases'].values():
            checker.audit_route(entry['config'],entry['result'])

    def reject_mutation(self,edit):
        r=copy.deepcopy(self.result);edit(r)
        with self.assertRaises((ValueError,KeyError,TypeError)):
            checker.audit(r)

    def test_omitted_matrix_rejected(self):
        self.reject_mutation(lambda r:r['matrices'].pop())

    def test_fake_minimal_observation_rejected(self):
        self.reject_mutation(lambda r:r['matrices'][238].update(minimum_labels=1))

    def test_omitted_three_way_witness_rejected(self):
        self.reject_mutation(lambda r:r['matrices'][238].update(minimal_incompatible_sets=[]))

    def test_wrong_action_in_emitted_policy_rejected(self):
        self.reject_mutation(lambda r:r['cases']['after_frontier']['result']['route']['policy'][0].update(action='INVENTED'))

    def test_false_source_status_reading_rejected(self):
        self.reject_mutation(lambda r:r['cases']['after_frontier']['result']['route']['traces'][0].update(signal=[9]))

    def test_changed_delivery_quantity_rejected(self):
        self.reject_mutation(lambda r:r['cases']['changed_successor']['result']['route']['traces'][1].update(delivered_units=999))

    def test_false_successor_cost_rejected(self):
        self.reject_mutation(lambda r:r['cases']['changed_successor']['result'].update(minimum_cost=5))

    def test_future_receipt_not_prefunding(self):
        self.reject_mutation(lambda r:r['cases']['cash_still_missing']['result'].update(decision='ADMIT_MODEL_ONLY'))

    def test_fake_actual_revenue_rejected(self):
        self.reject_mutation(lambda r:r['scope'].update(actual_revenue=1000000))

    def test_fake_new_model_observation_rejected(self):
        self.reject_mutation(lambda r:r['scope'].update(new_capability_delta_measured=True))

    def test_rehashed_protocol_does_not_change_registered_terms(self):
        def edit(r):
            r['protocol']['economic_grid']['quote']=[1000]
            r['protocol_sha256']=producer.digest(r['protocol'])
        self.reject_mutation(edit)

    def test_boolean_is_not_a_cost(self):
        with self.assertRaises(ValueError):producer.construct(producer.config(query_cost=True))

    def test_duplicate_or_forbidden_queries_rejected(self):
        for queries in ([0,0],[3],[-1],[1,0]):
            with self.assertRaises(ValueError):producer.construct(producer.config(allowed_queries=queries))

    def test_exact_regeneration(self):
        stored=json.loads((Path(__file__).parent/'evidence/decision_results.json').read_text())
        self.assertEqual(self.result,stored)

    def test_closed_form_minima_match_constructed_and_independent_routes(self):
        for demand in (1,2):
            for query in range(7):
                for fallback in (4,5,7,9,12):
                    expected=min(4+query,8,fallback) if demand==1 else min(8+2*query,12,2*fallback)
                    self.assertEqual(checker.exhaustive_cost(demand,query,fallback,(0,1,2),True),expected)
                    self.assertEqual(producer.construct(producer.config(demand=demand,query_cost=query,fallback_unit_cost=fallback))['minimum_cost'],expected)

    def test_grid_denominators_and_counts(self):
        self.assertEqual(self.result['economic_summary'],{'cases':840,'ADMIT_MODEL_ONLY':286,'DECLINE_NO_SURPLUS':222,'DECLINE_UNFUNDED':332})
        self.assertEqual(sum(self.result['matrix_summary']['minimum_label_counts'].values())+self.result['matrix_summary']['no_feasible_partition'],512)

    def test_no_action_world_is_not_fixed_by_any_observation(self):
        for mask in range(512):
            record=self.result['matrices'][mask]
            if 0 in record['rows']:self.assertIsNone(record['minimum_labels'])

if __name__=='__main__':unittest.main()
