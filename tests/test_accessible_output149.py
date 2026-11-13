"""Independent research149 regressions; no semantic truth or WCAG claim."""
import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

from research.accessible_output148 import gate
from research.accessible_output149 import review, standalone
from tests.test_accessible_output148 import record


def triplet(value):
    source = gate.canonical(value)
    html, receipt = gate.compile_bytes(source)
    return source, html, receipt


class Continuity149Tests(unittest.TestCase):
    def test_identical_authored_content_across_declared_model_labels(self):
        a = record()
        b = copy.deepcopy(a)
        b["model_label"] = "changed-unverified-model-label"
        result = review.inspect(triplet(a), triplet(b))
        self.assertEqual(result["continuity_verdict"],
                         "PASS_EXACT_AUTHORED_CONTENT_CONTINUITY_ONLY")
        self.assertTrue(result["automatic_content_carryforward"])
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["semantic_truth_verified"])
        self.assertFalse(result["wcag_conformance_verified"])
        self.assertTrue(result["requires_independent_semantic_and_assistive_review"])

    def test_content_change_under_equal_role_counts_must_hold(self):
        changes = (
            (1, "text", "Synthetic but potentially false replacement sentence."),
            (2, "href", "https://www.canada.ca/fr.html"),
            (2, "label", "Visit another official resource"),
            (3, "alt", "Different decision-flow and navigation information"),
            (3, "caption", "Different explanatory caption"),
            (4, "caption", "Different conditions table caption"),
        )
        a = record()
        for index, key, value in changes:
            with self.subTest(index=index, field=key):
                b = copy.deepcopy(a)
                b["model_label"] = "new-declared-model"
                b["blocks"][index][key] = value
                result = review.inspect(triplet(a), triplet(b))
                self.assertTrue(result["authored_content_changed"])
                self.assertEqual(result["structural_gate"], "PASS_STRUCTURAL_ONLY")
                self.assertEqual(result["continuity_verdict"],
                                 "HOLD_AUTHORED_CONTENT_CHANGED_REVIEW_REQUIRED")
                self.assertFalse(result["automatic_content_carryforward"])
                self.assertFalse(result["deployment_authorized"])
        b = copy.deepcopy(a)
        b["blocks"][4]["rows"][1][1] = "Unknown"
        self.assertTrue(review.inspect(triplet(a), triplet(b))["authored_content_changed"])

    def test_previous_gate_still_rejects_loss_or_tampering(self):
        a, b = record(), record()
        b["blocks"].pop(3)
        with self.assertRaisesRegex(ValueError, "STRUCTURAL_ROLE_COUNT_REGRESSED_IMAGE"):
            review.inspect(triplet(a), triplet(b))
        t = list(triplet(a))
        t[1] = t[1].replace(b"<main>", b"<main hidden>")
        with self.assertRaisesRegex(ValueError, "HTML_SOURCE_BINDING_FAILED"):
            review.inspect(tuple(t), triplet(a))

    def test_source_distribution_is_deterministic_and_its_manifest_reconciles(self):
        with TemporaryDirectory() as temp:
            a, b = Path(temp) / "a.zip", Path(temp) / "b.zip"
            first, second = standalone.build(a), standalone.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(first, second)
            self.assertEqual(standalone.verify(a), first)
            self.assertEqual(first["source_files"], len(standalone.SOURCES))
            with self.assertRaises(FileExistsError):
                standalone.build(a)

    def test_changed_payload_rejected_even_when_zip_crc_is_valid(self):
        with TemporaryDirectory() as temp:
            original, mutated = Path(temp) / "original.zip", Path(temp) / "mutated.zip"
            standalone.build(original)
            with ZipFile(original) as src, ZipFile(mutated, "w", compression=ZIP_DEFLATED) as out:
                for entry in src.infolist():
                    data = src.read(entry.filename)
                    if entry.filename == "research/accessible_output149/review.py":
                        data += b"\n# altered after seal\n"
                    out.writestr(entry, data)
            with self.assertRaisesRegex(ValueError, "SOURCE_ARCHIVE_HASH_MISMATCH"):
                standalone.verify(mutated)

    def test_duplicate_member_rejected(self):
        with TemporaryDirectory() as temp:
            original, mutated = Path(temp) / "original.zip", Path(temp) / "duplicate.zip"
            standalone.build(original)
            with ZipFile(original) as src, ZipFile(mutated, "w", compression=ZIP_DEFLATED) as out:
                for entry in src.infolist():
                    out.writestr(entry, src.read(entry.filename))
                out.writestr(standalone.SOURCES[0], b"fake")
            with self.assertRaisesRegex(ValueError, "EXACT_SOURCE_MEMBER_SET_REQUIRED"):
                standalone.verify(mutated)


if __name__ == "__main__":
    unittest.main()
