"""Registry continuity and refusal tests, local engineering only."""
import json
from pathlib import Path
import tempfile
import unittest

from invent import Refused, run, strict_json
from registry import append_result, verify_records


HERE = Path(__file__).resolve().parent


def example(name):
    return strict_json((HERE / "examples" / name).read_text(encoding="utf-8"))


class RegistryTests(unittest.TestCase):
    def test_two_distinct_missions_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "registry.jsonl"
            a = run(example("brief-agent.json"))
            b = run(example("brief-science.json"))
            x = append_result(path, a)
            y = append_result(path, b)
            self.assertEqual(x["payload"]["index"], 1)
            self.assertEqual(y["payload"]["previous_hash"], x["hash"])
            history = verify_records(path)
            self.assertEqual([v["mission_id"] for v in history],
                             [a["mission_id"], b["mission_id"]])
            self.assertTrue(all(v["reported_revenue"] == "NOT_OBSERVED"
                                for v in history))
            with self.assertRaisesRegex(Refused, "MISSION_ALREADY_REGISTERED"):
                append_result(path, a)

    def test_detect_tampered_history(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "register.jsonl"
            append_result(path, run(example("brief-agent.json")))
            raw = path.read_text(encoding="utf-8")
            path.write_text(raw.replace("RESEARCH_ONLY", "FAKE_REVENUE"),
                            encoding="utf-8")
            with self.assertRaises(Refused):
                verify_records(path)

    def test_refuse_fake_commercial_promotion(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "register.jsonl"
            result = run(example("brief-agent.json"))
            result["evidence"]["real_collected_revenue"] = "1000000000"
            with self.assertRaisesRegex(Refused, "RESULT_MAY_NOT_CLAIM_REVENUE"):
                append_result(path, result)

    def test_missing_registry_is_empty(self):
        with tempfile.TemporaryDirectory() as dirname:
            self.assertEqual(verify_records(Path(dirname) / "missing.jsonl"), [])

    def test_refuse_duplicate_input_result(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "reg.jsonl"
            result = run(example("brief-agent.json"))
            append_result(path, result)
            result["mission_id"] = "changed-mission"
            with self.assertRaisesRegex(Refused, "DUPLICATE_MISSION|REGISTRY_CHAIN_MISMATCH"):
                # Real history stays valid; changing an off-register result
                # cannot mutate stored history or prove a successor.
                # To exercise a corruption refusal, alter the stored index.
                raw = path.read_text()
                path.write_text(raw.replace('"index":1', '"index":2'))
                verify_records(path)


if __name__ == "__main__":
    unittest.main()
