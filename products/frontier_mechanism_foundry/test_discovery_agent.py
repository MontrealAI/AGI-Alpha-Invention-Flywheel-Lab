"""Local model adapter boundaries and unverified claim tests."""
import copy
from pathlib import Path
import unittest

from invent import Refused, strict_json
from discovery_agent import (
    SPEC, check_signals, local_model_response,
    make_prompt, propose, validate_proposals,
)

ROOT = Path(__file__).resolve().parent


def fixtures():
    a = strict_json((ROOT/"examples/frontier-signals.json").read_text(encoding="utf-8"))
    b = strict_json((ROOT/"examples/offline-proposals.json").read_text(encoding="utf-8"))
    return a, b


class ResearchProposals(unittest.TestCase):
    def test_three_distinct_research_proposals(self):
        signals, ideas = fixtures()
        self.assertEqual(check_signals(signals), signals)
        self.assertEqual(validate_proposals(ideas), ideas)
        result = propose(signals, ideas, "AUTHORED_OFFLINE_FIXTURE")
        self.assertEqual(result["claim_status"], "UNVERIFIED_RESEARCH_HYPOTHESES")
        self.assertEqual(result["onchain_deployment"], "NONE")
        self.assertEqual(result["actual_collected_revenue"], "ZERO_OBSERVED")
        self.assertEqual(len(result["proposals"]), 3)

    def test_model_prompt_contains_alternatives_and_independent_checks(self):
        signals, _ = fixtures()
        prompt = make_prompt(signals)
        self.assertEqual(len(prompt), 2)
        self.assertIn("Uniswap", prompt[0]["content"])
        self.assertIn("experiment", prompt[0]["content"].lower())

    def test_refuse_copycat_candidates(self):
        signals, ideas = fixtures()
        duplicate = copy.deepcopy(ideas)
        duplicate["proposals"][1]["missing_means"] = duplicate["proposals"][0]["missing_means"]
        with self.assertRaisesRegex(Refused, "MATERIALLY_DIFFERENT"):
            propose(signals, duplicate, "AUTHORED_OFFLINE_FIXTURE")

    def test_refuse_less_than_three(self):
        signals, ideas = fixtures()
        ideas["proposals"].pop()
        with self.assertRaisesRegex(Refused, "NEED_THREE"):
            propose(signals, ideas, "AUTHORED_OFFLINE_FIXTURE")

    def test_refuse_untrusted_source_scheme(self):
        signals, _ = fixtures()
        signals["signals"][0]["source_url"] = "file:///etc/passwd"
        with self.assertRaisesRegex(Refused, "INVALID_SIGNAL_URL"):
            check_signals(signals)

    def test_refuse_remote_model_host_before_network(self):
        signals, _ = fixtures()
        with self.assertRaisesRegex(Refused, "ONLY_LOCAL_OLLAMA_ENDPOINT_ALLOWED"):
            local_model_response(signals, "local-test", "https://api.example.org/api/chat")

    def test_refuse_local_endpoint_redirect_or_credential(self):
        signals, _ = fixtures()
        for endpoint in ("http://user:pass@localhost:11434/api/chat",
                         "http://127.0.0.1:11434/admin",
                         "http://127.0.0.1:11434/api/chat?token=fake"):
            with self.assertRaisesRegex(Refused, "ONLY_LOCAL_OLLAMA_ENDPOINT_ALLOWED"):
                local_model_response(signals, "local-test", endpoint)


if __name__ == "__main__":
    unittest.main()
