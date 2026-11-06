#!/usr/bin/env python3
"""Focused tests for the constructed artifacts and consequential failure controls."""

import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import check_construct_case as independent
import construct_case as case


class ConstructiveCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads((case.ROOT / "construct_protocol.json").read_text(encoding="utf-8"))
        cls.result = case.build_results(cls.protocol)

    def test_constructed_artifacts_answer_every_declared_query(self):
        states = self.result["states"]
        for family in ("primary", "successor"):
            result = self.result[family]
            artifact = result["artifact"]
            queries = result["query_parameters"]
            self.assertEqual(result["state_query_checks"], len(states) * len(queries))
            for index, state in enumerate(states):
                for query_index, query in enumerate(queries):
                    expected = max(state) <= query if family == "primary" else min(state) >= query[0] and max(state) <= query[1]
                    self.assertEqual(artifact["decoder"][artifact["state_labels"][index]][query_index], expected)

    def test_exhaustive_partitions_confirm_family_relative_minima(self):
        result = self.result["partition_enumeration"]
        self.assertEqual(result["partition_count"], 21147)
        self.assertEqual(result["primary"], {"exact_partition_count": 260, "minimum_labels": 3})
        self.assertEqual(result["successor"], {"exact_partition_count": 8, "minimum_labels": 6})

    def test_single_query_does_not_inherit_family_lower_bound(self):
        signatures = [[max(state) <= 90] for state in self.result["states"]]
        self.assertEqual(case.construct(signatures)["class_count"], 2)

    def test_pairwise_witnesses_distinguish_every_constructed_label(self):
        for family in ("primary", "successor"):
            artifact = self.result[family]["artifact"]
            count = artifact["class_count"]
            witnesses = artifact["separating_queries"]
            self.assertEqual(len(witnesses), count * (count - 1) // 2)
            self.assertEqual(len({(w["left_label"], w["right_label"]) for w in witnesses}), len(witnesses))
            for witness in witnesses:
                left, right, query = witness["left_label"], witness["right_label"], witness["query_index"]
                self.assertNotEqual(artifact["decoder"][left][query], artifact["decoder"][right][query])

    def test_mean_loses_information_before_the_primary_query(self):
        states = self.result["states"]
        left, right = states.index([60, 100]), states.index([80, 80])
        labels = self.result["representations"]["mean_only"]["state_labels"]
        self.assertEqual(labels[left], labels[right])
        self.assertNotEqual(max(states[left]) <= 90, max(states[right]) <= 90)
        self.assertFalse(self.result["representations"]["mean_only"]["primary_exact"])

    def test_retained_maximum_cannot_recover_successor_information(self):
        states = self.result["states"]
        left, right = states.index([60, 80]), states.index([80, 80])
        labels = self.result["representations"]["constructed_primary"]["state_labels"]
        self.assertEqual(labels[left], labels[right])
        self.assertNotEqual(min(states[left]) >= 80, min(states[right]) >= 80)
        self.assertFalse(self.result["representations"]["constructed_primary"]["successor_exact"])
        self.assertTrue(self.result["representations"]["constructed_successor"]["successor_exact"])

    def test_strong_conventional_controls_tie(self):
        controls = self.result["representations"]
        self.assertEqual(controls["constructed_primary"], controls["conventional_maximum"])
        self.assertEqual(controls["constructed_successor"], controls["conventional_minimum_maximum"])
        self.assertEqual(controls["raw_ordered_pair"]["label_count"], 9)
        self.assertTrue(controls["raw_ordered_pair"]["successor_exact"])

    def test_local_patch_retains_more_information_than_initial_minimum(self):
        patch = self.result["representations"]["mean_plus_flag"]
        self.assertEqual(patch["label_count"], 6)
        self.assertTrue(patch["primary_exact"])
        self.assertTrue(patch["successor_exact"])
        self.assertGreater(patch["label_count"], self.result["primary"]["artifact"]["class_count"])

    def test_shared_cost_assumptions_allow_pooling_and_conventional_tie(self):
        finance = self.result["finance"]
        self.assertEqual(finance["shared"]["successful_contribution"], 30)
        self.assertEqual(finance["shared"]["buyer_surpluses_on_success"], [10, 10])
        self.assertEqual(finance["standalone"]["value_minus_cost_per_buyer"], [-5, -5])
        self.assertTrue(finance["ordinary_shared"]["matches_shared"])

    def test_refund_obligation_defeats_success_path_funding(self):
        finance = self.result["finance"]
        success = finance["cash_paths"]["success_with_advance"]
        failure = finance["cash_paths"]["failure_with_full_refund"]
        self.assertEqual(success["minimum_opening_cash"], 50)
        self.assertEqual(failure["minimum_opening_cash"], 90)
        self.assertEqual(50 + failure["cumulative_flows"][-1], -40)
        self.assertTrue(success["feasible_at_opening_cash"]["50"])
        self.assertFalse(failure["feasible_at_opening_cash"]["50"])
        self.assertEqual(finance["all_declared_advance_paths"]["advance_reduces_full_obligation_requirement_by"], 0)

    def test_risk_neutral_participation_requires_unspecified_probability(self):
        analysis = self.result["finance"]["probability_analysis"]
        self.assertEqual(analysis["operator_nonnegative_at_or_above"], "3/4")
        points = {row["p"]: row for row in analysis["points"]}
        self.assertFalse(points["1/2"]["operator_participates"])
        self.assertTrue(points["3/4"]["operator_participates"])
        self.assertEqual(points["3/4"]["operator_expected_contribution"], "0")
        self.assertEqual(points["3/4"]["buyer_expected_surpluses"], ["15/2", "15/2"])

    def test_capital_and_success_profit_have_different_boundaries(self):
        sweep = self.result["finance"]["sweep"]
        self.assertEqual(sweep["point_count"], 121)
        self.assertEqual(sweep["cash_feasible_construction_costs"], {"minimum": 0, "maximum": 20, "count": 21})
        self.assertEqual(sweep["positive_success_but_insufficient_cash"], {"minimum": 21, "maximum": 89, "count": 69})
        self.assertEqual(sweep["zero_success_contribution_costs"], [90])

    def test_retention_policy_changes_across_the_three_declared_scenarios(self):
        rows = self.result["retention_option"]["primary_scenarios"]
        expected = [
            ({"ordinary_access": "7/4", "retain_sufficient": "6", "secure_access": "5"}, ["retain_sufficient"]),
            ({"ordinary_access": "19/8", "retain_sufficient": "6", "secure_access": "15/2"}, ["secure_access"]),
            ({"ordinary_access": "7/40", "retain_sufficient": "-3", "secure_access": "-13/10"}, ["ordinary_access"]),
        ]
        self.assertEqual(len(rows), len(expected))
        for row, (values, winners) in zip(rows, expected):
            self.assertEqual(row["policy_values"], values)
            self.assertEqual(row["best_policies"], winners)
            self.assertNotIn("deferred_access", row["policy_values"])

    def test_retention_opportunity_really_needs_a_lost_distinction(self):
        witness = self.result["retention_option"]["gap_witness"]
        self.assertEqual(witness["left_source"], [60, 80])
        self.assertEqual(witness["right_source"], [80, 80])
        self.assertEqual(witness["compact_label_left"], witness["compact_label_right"])
        self.assertFalse(witness["left_answer"])
        self.assertTrue(witness["right_answer"])
        invalid = copy.deepcopy(self.protocol["retention_option"])
        invalid["gap_witness"]["future_interval"] = [60, 80]
        with self.assertRaises(ValueError):
            case.retention_case(invalid)

    def test_retention_switch_preserves_both_optimal_policies(self):
        row = self.result["retention_option"]["switch_witness"]
        self.assertEqual(row["parameters"]["r"], "4")
        self.assertEqual(row["best_value"], "6")
        self.assertEqual(row["best_policies"], ["retain_sufficient", "secure_access"])
        for cost, winner in (("3", "secure_access"), ("5", "retain_sufficient")):
            parameters = {**row["parameters"], "r": cost}
            self.assertEqual(case.retention_decision(parameters, False)["best_policies"], [winner])

    def test_deferred_control_uses_ordinary_access_before_buying(self):
        row = self.result["retention_option"]["deferred_control"]
        self.assertEqual(row["best_policies"], ["deferred_access"])
        self.assertEqual(row["best_value"], "35/4")
        self.assertGreater(Fraction(row["best_value"]), Fraction(17, 2))
        parameters = {**row["parameters"], "q": "1"}
        certain_access = case.retention_decision(parameters, True)
        self.assertEqual(certain_access["policy_values"]["deferred_access"], "19/2")
        self.assertEqual(certain_access["best_policies"], ["ordinary_access", "deferred_access"])

    def test_optional_reconstruction_can_be_declined_without_erasing_upfront_costs(self):
        parameters = self.result["retention_option"]["deferred_control"]["parameters"]
        no_arrival = case.retention_decision({**parameters, "p": "0"}, True)
        self.assertEqual(no_arrival["policy_values"], {
            "ordinary_access": "0", "retain_sufficient": "-4",
            "secure_access": "-2", "deferred_access": "0",
        })
        expensive = case.retention_decision({**parameters, "r": "30"}, True)
        self.assertEqual(expensive["policy_values"]["ordinary_access"], "0")
        self.assertEqual(expensive["policy_values"]["secure_access"], "-2")
        self.assertEqual(expensive["policy_values"]["deferred_access"], "0")
        self.assertEqual(expensive["best_policies"], ["retain_sufficient"])

    def test_retention_costs_are_exact_and_funded_before_any_benefit(self):
        row = self.result["retention_option"]["primary_scenarios"][0]
        self.assertEqual(row["required_resource_allowance"], "8")
        self.assertEqual(row["policy_cost_bounds"], {
            "ordinary_access": "6", "retain_sufficient": "4", "secure_access": "8",
        })
        for changes in ({"resource_allowance": "7", "v": "1000"}, {"c": "-1"},
                        {"r": 0.5}, {"q": True}, {"p": "3/2"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    case.retention_decision({**row["parameters"], **changes}, False)

    def test_invalid_inputs_cannot_silently_change_the_model(self):
        for value in (True, 0.75, "-1/10", "11/10", "1/0"):
            with self.assertRaises(ValueError):
                case.probability(value)
        self.assertEqual(case.probability("3/4"), Fraction(3, 4))
        for table in ([], [[]], [[True], [False, True]], [[1], [0]]):
            with self.assertRaises(ValueError):
                case.construct(table)
        invalid = copy.deepcopy(self.protocol)
        invalid["finance"]["refundable_advance_total"] = 121
        with self.assertRaises(ValueError):
            case.validate_protocol(invalid)

    def test_independent_checker_rejects_material_evidence_mutations(self):
        mutations = []
        damaged = copy.deepcopy(self.result)
        damaged["primary"]["artifact"]["decoder"][0][0] = False
        mutations.append(("decoder", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["successor"]["artifact"]["separating_queries"].pop()
        mutations.append(("lower-bound witnesses", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["representations"]["mean_only"]["primary_exact"] = True
        mutations.append(("negative control", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["finance"]["cash_paths"]["failure_with_full_refund"]["minimum_opening_cash"] = 50
        mutations.append(("refund cash", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["scope"].pop()
        mutations.append(("scope", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["source_sha256"]["construct_protocol.json"] = "0" * 64
        mutations.append(("source hash", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["retention_option"]["primary_scenarios"][0]["policy_values"]["ordinary_access"] = "6"
        mutations.append(("retention policy value", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["retention_option"]["switch_witness"]["best_policies"].pop()
        mutations.append(("discarded retention tie", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["retention_option"]["deferred_control"]["policy_values"]["deferred_access"] = "17/2"
        mutations.append(("weakened deferred comparator", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["retention_option"]["deferred_control"]["policy_cost_bounds"]["deferred_access"] = "0"
        mutations.append(("unfunded late-route outlay", damaged))
        damaged = copy.deepcopy(self.result)
        damaged["retention_option"]["gap_witness"]["left_answer"] = True
        mutations.append(("missing-distinction witness", damaged))
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary)
            path = evidence / "construct_results.json"
            path.write_text(json.dumps(self.result), encoding="utf-8")
            independent.check_publication(evidence=evidence)
            for name, result in mutations:
                with self.subTest(mutation=name):
                    path.write_text(json.dumps(result), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        independent.check_publication(evidence=evidence)


if __name__ == "__main__":
    unittest.main()
