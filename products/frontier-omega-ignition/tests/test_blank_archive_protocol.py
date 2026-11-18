"""Prerequisites, independent approval and actual recipient checks for the public archive task."""
import json
from pathlib import Path
import tempfile
import unittest

from ignition import construction, delivery, evaluation, family_contracts, research
from qa import qualify_blank_archive as study
import qualify_live


class BlankArchiveProtocol(unittest.TestCase):
    def setUp(self):
        self.manifest, original = study.publisher_data()
        self.confirmations, self.recipients = study.samples(original)
        self.spec = {"kind": "manifest_audit", "purpose": study.PURPOSE, "definition": {"manifest": self.manifest},
                     "cases": [{"name": "Empty delivery", "input": {"files": {}},
                                **study.reference(self.manifest, {"files": {}})}]}
        self.reserved = {study.shared.digest(study.encode(files)) for _, files in self.confirmations + self.recipients}

    def test_independently_supplied_inventory_and_reserved_inputs(self):
        intake = study.intake(self.manifest)
        self.assertNotIn("construction_spec", intake["mission"])
        self.assertNotIn("direct_after_research", intake["mission"]["resources"])
        self.assertEqual(len(self.reserved), 5)
        self.assertEqual(family_contracts.extracted_manifest(research._signals(intake["sources"], research._now(None)))["manifest"],
                         self.manifest)
        self.assertNotIn("late-91.txt", json.dumps(intake))
        self.assertNotIn("receipt-83.txt", json.dumps(intake))
        self.assertIsNone(study.review(self.spec, self.manifest, self.reserved))
        example = self.spec["cases"][0]
        example["expected"]["missing"] = []
        self.assertIn("disagrees", study.review(self.spec, self.manifest, self.reserved))
        example["input"] = study.encode(self.confirmations[0][1])
        self.assertIn("reserved", study.review(self.spec, self.manifest, self.reserved))
        self.spec["definition"] = {"manifest": dict(self.manifest, forged="0"*64)}
        self.assertIn("publisher", study.review(self.spec, self.manifest, self.reserved))

    def test_approval_and_package_replay(self):
        self.spec["cases"].extend({"name": name, "input": study.encode(files),
                                   **study.reference(self.manifest, study.encode(files))}
                                  for name, files in self.confirmations)
        contract = construction.freeze_contract(self.spec)
        artifact = construction.build(contract, {"kind": "manifest_audit", "program": {"use_frozen_manifest": True}})
        receipt = evaluation.evaluate(contract, artifact)
        self.assertEqual(receipt["status"], "pass")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            bundle = delivery.export_bundle(contract, artifact, receipt, {})
            qualify_live.check_portable(bundle, work)
            replay = study.replay(work, self.manifest, self.recipients)
        self.assertTrue(all(item["matched"] for item in replay))
        self.assertEqual(replay[0]["received"]["ok"], True)
        self.assertEqual(replay[1]["received"]["changed"], ["example-input.json"])
        self.assertEqual(replay[1]["received"]["missing"], ["artifact.json"])
        self.assertEqual(replay[1]["received"]["unexpected"], ["receipt-83.txt"])
