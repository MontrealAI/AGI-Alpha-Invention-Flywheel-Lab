"""Independent executable old/new/strong-alternative testing; no model or payment mocks."""
import copy
import unittest
from frontier_omega import executable as e


class ExecutedFrontierReplay(unittest.TestCase):
    def setUp(self):
        self.suite={
           "schema":e.SUITE,"problem_id":"blocked-capacity-example",
           "historical_cutoff":"2026-10-12","as_of":"2026-11-16",
           "cases":[
              {"input":{"requested":12,"capacity":8},"expected":{"served":8}},
              {"input":{"requested":3,"capacity":10},"expected":{"served":3}},
              {"input":{"requested":0,"capacity":3},"expected":{"served":0}}],
           "inputs":["requested","capacity"],"min_pass_bps":10000,
           "max_operations":200,"acceptance_text_sha256":e.digest("Bounded capacity")}
        def method(role,ident,formula,available,cost):
            return {"schema":e.METHOD,"role":role,"id":ident,"available_at":available,
               "source_sha256":"1"*64,
               "instrument":{"name":ident,"inputs":["requested","capacity"],
                  "outputs":{"served":{"formula":formula}}},
               "complete_unit_cost_microUSD":cost,"cost_basis":"DECLARED_SCENARIO"}
        self.arms=[
           method("HISTORICAL_FRONTIER","old","requested","2026-10-01",100),
           method("CURRENT_FRONTIER","new","min(requested,capacity)","2026-11-01",60),
           method("STRONG_ALTERNATIVE","ordinary","min(requested,capacity)","2026-10-05",80)]

    def test_historical_alternative_defeats_novelty(self):
        receipt=e.compare(self.suite,self.arms)
        self.assertEqual(receipt["verdict"],"HISTORICALLY_FEASIBLE_VIA_STRONG_ALTERNATIVE")
        self.assertEqual([m["reproduced_pass_bps"] for m in receipt["methods"]],[6666,10000,10000])
        self.assertTrue(receipt["accepted_on_registered_cases"])
        self.assertFalse(receipt["customer_demand_verified"])
        self.assertFalse(receipt["economic_feasibility_established"])
        self.assertEqual(receipt["financial_operations"],0)

    def test_newly_solved_is_only_a_finite_test_result(self):
        self.arms[2]["available_at"]="2026-11-05"
        self.arms[2]["complete_unit_cost_microUSD"]=100
        receipt=e.compare(self.suite,self.arms)
        self.assertEqual(receipt["verdict"],"REPRODUCED_FINITE_TEST_CROSSING_HISTORICAL_PROVENANCE_UNVERIFIED")
        self.assertFalse(receipt["asserted_historical_availability_independently_verified"])

    def test_current_incumbent_matches_cheaper(self):
        self.arms[2]["available_at"]="2026-11-05"
        self.arms[2]["complete_unit_cost_microUSD"]=30
        self.assertEqual(e.compare(self.suite,self.arms)["verdict"],"CURRENT_CONTROL_MATCHES_OR_BEATS_ON_DECLARED_COST")

    def test_no_crossing_if_old_method_already_passed(self):
        self.arms[0]["instrument"]["outputs"]["served"]={"formula":"min(requested,capacity)"}
        self.arms[2]["available_at"]="2026-11-05"
        self.assertEqual(e.compare(self.suite,self.arms)["verdict"],"NO_REPRODUCED_TECHNICAL_CROSSING")

    def test_wrong_current_outputs_fail(self):
        self.arms[1]["instrument"]["outputs"]["served"]=999
        self.assertFalse(e.compare(self.suite,self.arms)["methods"][1]["accepted_on_finite_cases"])

    def test_rejects_python_execution_in_declarative_formula(self):
        self.arms[1]["instrument"]["outputs"]["served"]={"formula":"__import__('os').system('echo not-allowed')"}
        self.assertFalse(e.compare(self.suite,self.arms)["methods"][1]["accepted_on_finite_cases"])

    def test_rejects_change_to_acceptance_contract(self):
        p={"id":"blocked-capacity-example","acceptance":"Bounded capacity"}
        self.assertEqual(e.compare(self.suite,self.arms,problem=p)["compared_problem_id"],p["id"])
        p["acceptance"]="changed by tester"
        with self.assertRaises(ValueError):e.compare(self.suite,self.arms,problem=p)

    def test_rejects_historical_method_after_cutoff(self):
        self.arms[0]["available_at"]="2026-11-12"
        with self.assertRaises(ValueError):e.compare(self.suite,self.arms)

    def test_rejects_invalid_input_binding(self):
        self.arms[0]["instrument"]["inputs"]=["wrong"]
        with self.assertRaises(ValueError):e.compare(self.suite,self.arms)

    def test_rejects_duplicate_role(self):
        self.arms[2]["role"]="CURRENT_FRONTIER"
        with self.assertRaises(ValueError):e.compare(self.suite,self.arms)

    def test_rejects_ambiguous_json(self):
        with self.assertRaises(ValueError):e.strict_json('{"a":1,"a":2}')

    def test_unknown_cost_stays_unknown(self):
        self.arms[1]["complete_unit_cost_microUSD"]=None
        self.arms[1]["cost_basis"]="UNKNOWN"
        receipt=e.compare(self.suite,self.arms)
        self.assertIsNone(receipt["methods"][1]["reported_complete_unit_cost_microUSD"])
        self.assertFalse(receipt["economic_feasibility_established"])

    def test_deterministic_replay_receipt(self):
        self.assertEqual(e.compare(self.suite,self.arms),e.compare(self.suite,self.arms))

    def test_synthetic_entrypoint(self):
        receipt=e.demo()
        self.assertEqual(receipt["verdict"],"HISTORICALLY_FEASIBLE_VIA_STRONG_ALTERNATIVE")
        self.assertEqual(receipt["methods"][2]["reproduced_pass_bps"],10000)


if __name__=="__main__":unittest.main()
