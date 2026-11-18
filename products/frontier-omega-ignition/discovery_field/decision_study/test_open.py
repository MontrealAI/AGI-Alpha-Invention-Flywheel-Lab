import unittest

from discovery_field.decision_study import evaluate, open_decisions


class OpenProposalTests(unittest.TestCase):
    def test_freedom_withdrawal_and_same_domain_mismatch(self):
        public = open_decisions.packet()
        template = {key: "A separately reviewable hypothesis" for key in public["shape"]["candidates"][0]}
        template["citations"] = [{"source": "B", "quote": evaluate.sources()["B"]["excerpt"]}]
        template["test"] = "Test a single scenario on an edge board to infer throughput across a fleet."
        answer = {"candidates": [template], "first_experiment": "defer"}
        check, = open_decisions.assess(answer)
        self.assertTrue(check["all_citations_bound"])
        self.assertEqual(check["scientific_verdict"], "requires independent assessment of the proposed relation and test")
        missing, = open_decisions.assess(answer, withdrawn={"B"})
        self.assertFalse(missing["all_citations_bound"])
        template["citations"] = []
        unconstrained, = open_decisions.assess(answer)
        self.assertTrue(unconstrained["complete_fields"])
        self.assertFalse(unconstrained["all_citations_bound"])

    def test_quote_not_in_attributed_source(self):
        row = {"citations": [{"source": "A", "quote": evaluate.sources()["B"]["excerpt"]}]}
        check, = open_decisions.assess({"candidates": [row]})
        self.assertTrue(check["citations"][0]["available"])
        self.assertFalse(check["all_citations_bound"])
        self.assertFalse(check["complete_fields"])


if __name__ == "__main__":
    unittest.main()
