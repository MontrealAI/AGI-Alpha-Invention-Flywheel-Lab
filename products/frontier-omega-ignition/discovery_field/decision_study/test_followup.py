import copy
import json
from pathlib import Path
import tempfile
import unittest

from discovery_field.decision_study import calibration_bounds, evaluate, open_decisions, report


class ScientificFollowupTests(unittest.TestCase):
    def test_reopen_free_ideas_and_source_withdrawals(self):
        receipt = open_decisions.replay()
        for index, row in enumerate(receipt["rows"]):
            for citation in row["citations"]:
                self.assertFalse(receipt["withdrawal"][citation["source"]][index])

    def test_mathematical_witnesses_survive_independent_enumeration(self):
        observed = json.loads((evaluate.HERE / "calibration_observation.json").read_text())
        self.assertEqual(observed["code_sha256"], evaluate.sha((evaluate.HERE / "calibration_bounds.py").read_bytes()))
        for key, value in calibration_bounds.check().items():
            self.assertEqual(value, observed[key])
        malformed = {"A": {"trials": [0, 5], "passes": 3}, "B": {"trials": [6, 2], "passes": 4}}
        with self.assertRaises(ValueError):
            calibration_bounds.bounds(malformed)

    def test_additional_site_counts_and_degenerate_totals(self):
        three = {"A": {"trials": [1, 2, 3], "passes": 3},
                 "B": {"trials": [3, 2, 1], "passes": 0}}
        answer = calibration_bounds.bounds(three)
        self.assertEqual(answer["minimum"]["difference"], "1/3")
        self.assertEqual(answer["maximum"]["difference"], "2/3")
        zero = {"trials": [6], "passes": 0}
        full = {"trials": [4], "passes": 4}
        self.assertEqual(calibration_bounds.bounds({"B": zero, "A": full})["minimum"]["difference"], "1")
        with self.assertRaises(ValueError):
            calibration_bounds.bounds({"A": three["A"], "B": full})

    def test_changed_design_cannot_inherit_an_independent_review(self):
        source = json.loads((evaluate.HERE / "included.json").read_text())
        real = source["cases"][0]
        reviews = {real["answer_sha256"]: {"claim_faithful": True, "proposed_test_usable": True}}
        forged = copy.deepcopy(source)
        forged["cases"][0]["answer"]["claim"] = "A model always wins these comparisons."
        forged["cases"][0]["answer_sha256"] = evaluate.fingerprint(forged["cases"][0]["answer"])
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory, "changed.json")
            changed.write_text(json.dumps(forged))
            result = report.evaluate_record(changed, reviews)[0]
            self.assertTrue(result["narrow_evidence_decision"])
            self.assertFalse(result["reviewed_fact_and_proposed_test"])
            self.assertIsNone(result["scientific_review"])
