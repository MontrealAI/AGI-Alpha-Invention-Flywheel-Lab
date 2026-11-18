"""Independently registered meaning and domain checks for the bilingual intake."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import unittest

from field_lab.intake import compile_brief, guard
from field_lab.intake_qualification import score_routes, summary

HERE = Path(__file__).resolve().parent


class IntakeTest(unittest.TestCase):
    def test_complete_brief_and_character_offsets(self):
        text = "Au moins 27,5 jetons/s par utilisateur et premier contenu visible au P90 en 0,425 s au plus."
        receipt = compile_brief(text)
        self.assertEqual(receipt["answer"], {"status": "ready", "p90_ms": 425, "min_rate": 27.5})
        self.assertEqual(receipt["brief_sha256"], hashlib.sha256(text.encode()).hexdigest())
        for e in receipt["evidence"]:
            i, j = e["span"]
            self.assertEqual(text[i:j], e["text"])
            self.assertEqual(e["value"], receipt["answer"][e["field"]])

    def test_ambiguous_extra_and_opposite_bounds_defer(self):
        for text in (
            "P90 complete turn within 450 ms and at least 90 tokens/s per user.",
            "P90 first visible output within 450 ms and at most 90 tokens/s per user.",
            "P90 first visible output within 450 ms and at least 90 tokens/s for the system.",
            "P90 first visible output within 450 ms and at least 90 tokens/s per user and P95 turn within 800 ms.",
            "P95 first visible output within 450 ms and at least 90 tokens/s per user.",
            "P90 first visible output within 450 ms and P90 first visible output within 500 ms.",
            "P90 first visible output within 0 ms and at least 90 tokens/s per user.",
            "Do not require P90 first visible output within 450 ms and at least 90 tokens/s per user.",
            "Premier contenu visible au P90 sous 450 ms et au moins 90 jetons/s par utilisateur.",
        ):
            with self.subTest(text=text):
                self.assertEqual(compile_brief(text)["answer"], {"status": "defer"})

    def test_exact_json_number_or_defer(self):
        text = "P90 first visible output within 0.123456789012345678901 s and at least 8 tokens/s per user."
        self.assertEqual(compile_brief(text)["answer"], {"status": "defer"})

    def test_model_ready_requires_exact_agreement(self):
        receipt = compile_brief("P90 first visible output within 100 ms and at least 10 tokens/s per user.")
        self.assertEqual(guard(receipt, '{"min_rate":10,"status":"ready","p90_ms":100}'), receipt["answer"])
        for supplied in ('{"status":"ready","min_rate":10,"p90_ms":100,"extra":true}',
                         '{"status":"ready","p90_ms":100,"min_rate":10,"min_rate":10}',
                         '{"status":"ready","p90_ms":99,"min_rate":10}', "non-json"):
            self.assertEqual(guard(receipt, supplied), {"status": "defer"})

    def test_frozen_cases_and_uninspected_challenge_remain_separate(self):
        authored = json.loads((HERE / "intake_workload.json").read_bytes())["cases"]
        judged = json.loads((HERE / "intake_recorded" / "independent_challenge.json").read_bytes())
        known = summary(score_routes(authored), ("direct",))["direct"]
        independent = summary(score_routes(judged), ("direct","incumbent"))
        self.assertEqual((known["correct"], known["attempted"]), (12,12))
        self.assertEqual(independent["direct"]["unnecessary_defer"], 2)
        self.assertEqual(independent["incumbent"]["unsafe_ready"], 1)

    def test_public_wire_and_scopes_reopen_through_the_recipient(self):
        subprocess.run([sys.executable, "-B", str(HERE / "intake_qualification.py"), "--check"],
                       check=True, stdout=subprocess.DEVNULL)

    def test_incomplete_transport_can_never_become_accepted_defer(self):
        cases = [{"id": "no-output", "prompt": "Unknown.", "expected": {"status":"defer"}}]
        row, = score_routes(cases, {"no-output": None})
        self.assertEqual(row["model"], "incomplete")
        self.assertEqual(row["model_checked"], "incomplete")


if __name__ == "__main__":
    unittest.main()
