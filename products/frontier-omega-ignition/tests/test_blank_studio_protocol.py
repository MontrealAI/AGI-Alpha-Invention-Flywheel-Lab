"""Approval policy tests for the prospective public study; these tests do not exercise a live provider."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from ignition import construction, delivery, evaluation
from qa import qualify_blank_studio as study
import qualify_live


class BlankStudioProtocol(unittest.TestCase):
    def setUp(self):
        self.payload = {"rows": [{"name": "sample"}]}
        self.case = {"name": "Model-supplied illustration", "input": self.payload, **study.reference(self.payload)}
        self.definition = {"columns": [{"source": "name", "target": "cost_center", "type": "text"}],
                           "extra_fields": "reject"}
        self.spec = {"purpose": study.PURPOSE, "kind": "record_migration",
                     "definition": self.definition, "cases": [self.case]}

    def test_separate_predeclaration_and_intake(self):
        submitted = json.dumps(study.intake(), ensure_ascii=False)
        self.assertNotIn("construction_spec", submitted)
        self.assertNotIn("Équipe 71", submitted)
        self.assertNotIn("Cellule 028", submitted)
        self.assertEqual(study.intake()["mission"]["resources"]["max_model_calls"], 8)
        self.assertNotIn("direct_after_research", submitted)
        self.assertEqual(study.digest(study.held_out_cases()),
                         "95450fc17290b01f43c6fb9f52038508e39da15be8826f96906dc4518f52c466")

    def test_semantic_review_and_reserved_inputs(self):
        self.assertIsNone(study.review(self.spec))
        altered = copy.deepcopy(self.spec)
        altered["cases"][0]["expected"]["rows"][0]["cost_center"] = "altered"
        self.assertIn("reference", study.review(altered))
        self.spec["cases"] = [study.held_out_cases()[0]]
        self.assertIn("reserved", study.review(self.spec))
        self.definition["extra_fields"] = "drop"
        self.assertIn("admission", study.review(self.spec))

    def test_example_based_proposal_and_recipient_protocol(self):
        demonstration = {"rows": [{"name": "d1"}, {"name": "d2"}]}
        self.spec["definition"] = {"input_fields": ["name"], "targets": [{"name": "cost_center", "type": "text"}],
                                   "extra_fields": "reject",
                                   "demonstrations": [{"input": demonstration, **study.reference(demonstration)}]}
        self.assertIsNone(study.review(self.spec))
        self.spec["cases"].extend(study.held_out_cases())
        contract = construction.freeze_contract(self.spec)
        artifact = construction.build(contract, {"kind": "record_migration", "program": self.definition})
        receipt = evaluation.evaluate(contract, artifact)
        self.assertEqual(receipt["status"], "pass")
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            archive = delivery.export_bundle(contract, artifact, receipt, {})
            self.assertEqual(qualify_live.check_portable(archive, work)["verified_exit"], 0)
            self.assertTrue(all(row["matched"] for row in study.replay_recipient(work)))
