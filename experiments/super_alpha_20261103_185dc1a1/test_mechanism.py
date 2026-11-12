import unittest
from copy import deepcopy

from .fixtures import PROVIDER_IDS, public_spec, secret_worlds, triple_queries
from .independent import (
    adaptive_transcript_attack,
    composed_transcript_candidates,
    ordinary_complete_offer,
    public_quote_prediction,
    public_quote_projection,
    reconstruct_from_complement_quotes,
    verify_complete_offer,
)
from .mechanism import ConfidentialExchange, compile_composition, execute, oracle


class TranscriptAttackTests(unittest.TestCase):
    def test_adaptive_threshold_attack_observes_only_public_responses(self):
        worlds = {str(value): value for value in range(8)}
        prediction = lambda hypothesis, bid: {"accept": bid >= hypothesis}
        observations = []

        def oracle(bid):
            observations.append(bid)
            return {"accept": bid >= 5}

        result = adaptive_transcript_attack(oracle, worlds, range(8), prediction)
        self.assertEqual(result["remaining_candidates"], ["5"])
        self.assertEqual(result["query_count"], len(observations))
        self.assertLessEqual(result["query_count"], 3)

    def test_constant_output_cannot_identify_secret(self):
        result = adaptive_transcript_attack(
            lambda query: {"status": "unavailable"},
            {str(value): value for value in range(8)},
            range(8),
            lambda hypothesis, query: {"status": "unavailable"},
        )
        self.assertEqual(result["ambiguity"], 8)
        self.assertEqual(result["query_count"], 0)

    def test_globally_stable_tariff_retains_raw_ask_pair(self):
        def output(ask, query):
            tariff = 3 if ask <= 3 else 7
            return {"accept": query >= tariff, "tariff": tariff}

        result = adaptive_transcript_attack(
            lambda query: output(2, query),
            {str(value): value for value in (2, 3, 6, 7)},
            range(10),
            output,
        )
        self.assertEqual(result["remaining_candidates"], ["2", "3"])

    def test_individually_coarse_successor_outputs_can_identify_secret(self):
        worlds = {str(value): value for value in range(8)}
        first = [{"query": None, "response": {"bucket": 0}}]
        second = [{"query": None, "response": {"bucket": 1}}]
        first_predictor = lambda hypothesis, query: {"bucket": hypothesis // 4}
        second_predictor = lambda hypothesis, query: {"bucket": (hypothesis + 1) // 4}
        self.assertEqual(len(composed_transcript_candidates(worlds, [(first, first_predictor)])), 4)
        self.assertEqual(len(composed_transcript_candidates(worlds, [(second, second_predictor)])), 4)
        self.assertEqual(
            composed_transcript_candidates(worlds, [(first, first_predictor), (second, second_predictor)]),
            ["3"],
        )

    def test_outside_domain_observation_does_not_manufacture_reconstruction(self):
        with self.assertRaisesRegex(ValueError, "outside the public hypothesis"):
            adaptive_transcript_attack(
                lambda query: {"value": 100},
                {"one": 1, "two": 2},
                [None],
                lambda hypothesis, query: {"value": hypothesis},
            )


class CompleteOfferTests(unittest.TestCase):
    def setUp(self):
        self.spec = public_spec("primary")
        self.asks = dict(zip(PROVIDER_IDS, (200, 300, 600, 700)))
        self.query = {"excluded": [], "price_cap_cents": 3000}

    def test_generated_delivery_equals_independent_complete_broker(self):
        for job_id in ("primary", "successor", "resource_conflict"):
            spec = public_spec(job_id)
            for mode in ("exact", "coarse"):
                response = oracle(spec, self.asks, mode, self.query)
                checked = verify_complete_offer(spec, self.asks, mode, self.query, response)
                self.assertTrue(checked["valid"], checked["errors"])

    def test_corrupt_delivered_work_is_rejected(self):
        response = oracle(self.spec, self.asks, "exact", self.query)
        response["output"][0] += 1
        checked = verify_complete_offer(self.spec, self.asks, "exact", self.query, response)
        self.assertIn("incorrect_delivered_integer_matvec", checked["errors"])

    def test_same_provider_cannot_supply_three_capacity_one_blocks(self):
        response = oracle(self.spec, self.asks, "exact", self.query)
        response["route"] = ["p0", "p0", "p0"]
        checked = verify_complete_offer(self.spec, self.asks, "exact", self.query, response)
        self.assertIn("invalid_capacity_type_or_resource_assignment", checked["errors"])

    def test_public_shared_resource_constraint_is_binding(self):
        spec = public_spec("resource_conflict")
        response = oracle(spec, self.asks, "exact", self.query)
        self.assertFalse("p0" in response["route"] and "p1" in response["route"])
        response["route"] = ["p0", "p1", "p2"]
        checked = verify_complete_offer(spec, self.asks, "exact", self.query, response)
        self.assertIn("invalid_capacity_type_or_resource_assignment", checked["errors"])

    def test_complete_price_and_costs_cannot_omit_support(self):
        response = oracle(self.spec, self.asks, "exact", self.query)
        response["cost_breakdown"]["support_cents"] = 0
        response["quoted_price_cents"] -= self.spec["costs_cents"]["support"]
        checked = verify_complete_offer(self.spec, self.asks, "exact", self.query, response)
        self.assertIn("incorrect_complete_price", checked["errors"])
        self.assertIn("incorrect_complete_cost_breakdown", checked["errors"])

    def test_whole_offer_declines_when_outside_option_wins(self):
        spec = deepcopy(self.spec)
        buyer = {"benefit_cents": 4800, "outside_option_utility_cents": 4800, "budget_cents": 3000}
        response = oracle(spec, self.asks, "exact", self.query, buyer)
        self.assertEqual(response["status"], "buyer_declined")
        self.assertIsNone(response["output"])
        self.assertTrue(verify_complete_offer(spec, self.asks, "exact", self.query, response, buyer)["valid"])

    def test_stable_coarsening_can_destroy_an_otherwise_feasible_order(self):
        asks = {provider: 200 for provider in PROVIDER_IDS}
        query = {"excluded": [], "price_cap_cents": 1200}
        exact = ordinary_complete_offer(self.spec, asks, "exact", query)
        coarse = ordinary_complete_offer(self.spec, asks, "coarse", query)
        self.assertEqual(exact["status"], "offer_accepted")
        self.assertEqual(coarse["status"], "buyer_declined")

    def test_tampered_executable_program_cannot_be_delivered(self):
        route = compile_composition(self.spec, ("p0", "p1", "p2"))
        route["source"] = route["source"].replace("part_0 + part_1 + part_2", "part_0 + part_1")
        with self.assertRaisesRegex(ValueError, "program does not match"):
            execute(self.spec, route)

    def test_complete_bundle_quotes_identify_raw_exact_asks(self):
        exchange = ConfidentialExchange(self.spec, self.asks, "exact")
        result = reconstruct_from_complement_quotes(exchange.ask, PROVIDER_IDS, 3000)
        self.assertTrue(result["identified"])
        self.assertEqual(result["released_tariffs_cents"], self.asks)
        self.assertEqual(result["query_count"], 4)

    def test_adaptive_attack_separates_exact_and_stable_coarse_outputs(self):
        worlds = secret_worlds()
        for mode, expected_ambiguity in (("exact", 1), ("coarse", 16)):
            exchange = ConfidentialExchange(self.spec, self.asks, mode)
            result = adaptive_transcript_attack(
                lambda query: public_quote_projection(exchange.ask(query)),
                worlds,
                triple_queries(),
                lambda hypothetical_asks, query: public_quote_prediction(self.spec, hypothetical_asks, mode, query),
            )
            self.assertEqual(result["ambiguity"], expected_ambiguity)

    def test_successor_cannot_silently_reset_disclosure_partition(self):
        exchange = ConfidentialExchange(self.spec, self.asks, "coarse")
        successor = public_spec("successor")
        successor["tariff_cents"] = {"200": 600, "600": 600, "300": 700, "700": 700}
        with self.assertRaisesRegex(ValueError, "cannot reset"):
            exchange.successor(successor)

    def test_invalid_underpaying_tariff_is_rejected(self):
        spec = deepcopy(self.spec)
        spec["tariff_cents"]["700"] = 600
        with self.assertRaisesRegex(ValueError, "cannot cover"):
            ConfidentialExchange(spec, self.asks, "coarse")


if __name__ == "__main__":
    unittest.main()
