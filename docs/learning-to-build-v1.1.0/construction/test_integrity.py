#!/usr/bin/env python3
"""Small adversarial verifier checks; synthetic fixtures are not science results."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import check


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ParsingAndCoverage(unittest.TestCase):
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(check.VerificationError):
            check.json_text('{"accepted":false,"accepted":true}')

    def test_nan_json_rejected(self):
        with self.assertRaises(check.VerificationError):
            check.json_text('{"quality":NaN}')

    def test_overflow_json_number_rejected(self):
        with self.assertRaises(check.VerificationError):
            check.json_text('{"nested":[{"time":1e999}]}')

    def test_boolean_cannot_substitute_integer(self):
        with self.assertRaises(check.VerificationError):
            check.same(True, 1)
        with self.assertRaises(check.VerificationError):
            check.same(0, False)

    def test_extra_summary_key_rejected(self):
        with self.assertRaises(check.VerificationError):
            check.same({"fields": 12, "accepted": True}, {"fields": 12})

    def test_duplicate_and_missing_cohort_rejected(self):
        for rows in ([{"field": "a"}, {"field": "a"}], [{"field": "a"}]):
            with self.assertRaises(check.VerificationError):
                check.unique_keys(rows, ("field",), [("a",), ("b",)], "fixture")

    def test_duplicate_csv_column_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("field,field\na,b\n")
            with self.assertRaises(check.VerificationError):
                check.csv_rows(path)

    def test_empty_measurement_table_still_requires_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.csv"
            path.write_text("anything\n")
            with self.assertRaises(check.VerificationError):
                check.csv_rows(path, ("field",) + check.MEASUREMENTS)

    def test_file_added_after_entry_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("original")
            evidence = check.Evidence(root)
            evidence.path("first.txt")
            (root / "extra.txt").write_text("late addition")
            with self.assertRaisesRegex(check.VerificationError, "inventory changed"):
                evidence.inventory()

    def test_file_changed_after_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.txt").write_text("original")
            evidence = check.Evidence(root)
            evidence.path("first.txt").read_text()
            (root / "first.txt").write_text("modified")
            with self.assertRaisesRegex(check.VerificationError, "bytes changed"):
                evidence.inventory()

    def test_negative_and_nonfinite_time_rejected(self):
        for value in (-1.0, float("inf"), float("nan"), True):
            with self.assertRaises(check.VerificationError):
                check.nonnegative_times({"time": value}, ("time",), "fixture")

    def test_scope_does_not_conflate_empty_incumbent_with_pass(self):
        with self.assertRaises(check.VerificationError):
            check.aggregate([])


class GeometryAndAcceptance(unittest.TestCase):
    def test_known_perfect_object_and_empty_semantics(self):
        a = np.zeros((12, 12), dtype=np.int32)
        a[3:7, 4:9] = 8
        scored = check.score(a, a)
        self.assertEqual((scored["tp"], scored["fp"], scored["fn"]), (1, 0, 0))
        self.assertEqual(scored["instance_f1"], 1.0)
        self.assertEqual(scored["foreground_dice"], 1.0)
        self.assertEqual(scored["matched_area_relative_error"], 0.0)
        empty = np.zeros_like(a)
        self.assertEqual(check.score(empty, empty)["instance_f1"], 1.0)
        self.assertEqual(check.score(empty, a)["instance_f1"], 0.0)
        self.assertEqual(check.score(empty, a)["foreground_dice"], 0.0)

    def test_iou_exact_half_is_not_a_match(self):
        truth = np.zeros((10, 10), dtype=np.int32)
        truth[3:5, 2:6] = 1
        prediction = np.zeros_like(truth)
        prediction[3:5, 2:4] = 1
        prediction[3:5, 4:6] = 2
        result = check.score(prediction, truth)
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 2, 1))
        self.assertEqual(result["foreground_dice"], 1.0)
        self.assertEqual(result["instance_f1"], 0.0)

    def test_external_boundary_does_not_count_as_internal(self):
        single = np.zeros((15, 15), dtype=np.int32)
        single[3:12, 3:12] = 1
        self.assertEqual(int(check.inner_boundary(single).sum()), 0)
        split = single.copy()
        split[3:12, 8:12] = 2
        self.assertGreater(int(check.inner_boundary(split).sum()), 0)
        scored = check.score(single, split)
        self.assertEqual(scored["internal_boundary_f1"], 0.0)
        self.assertGreater(scored["reference_internal_boundary_pixels"], 0)

    def test_mask_shape_and_noninteger_rejected(self):
        with self.assertRaises(check.VerificationError):
            check.score(np.zeros((3, 4), dtype=int), np.zeros((3, 3), dtype=int))
        with self.assertRaises(check.VerificationError):
            check.valid_labels(np.zeros((3, 3), dtype=float))
        with self.assertRaises(check.VerificationError):
            check.valid_labels(np.full((3, 3), -1, dtype=int))

    def test_same_colour_disconnected_instances_remain_distinct(self):
        colour = np.zeros((8, 9), dtype=np.uint8)
        colour[1:3, 1:3] = 120
        colour[5:7, 6:8] = 120
        labels = check.component_reference(colour)
        self.assertEqual(int(labels.max()), 2)
        self.assertEqual(labels[1, 1], 1)
        self.assertEqual(labels[5, 6], 2)

    def test_component_numbering_follows_raster_not_colour_value(self):
        colour = np.zeros((8, 9), dtype=np.uint8)
        colour[1:3, 1:3] = 200
        colour[5:7, 6:8] = 40
        labels = check.component_reference(colour)
        self.assertEqual(labels[1, 1], 1)
        self.assertEqual(labels[5, 6], 2)

    def test_boolean_outline_representation_is_lossless(self):
        outline = np.zeros((10, 10), dtype=bool)
        outline[2, 2:8] = outline[7, 2:8] = True
        outline[2:8, 2] = outline[2:8, 7] = True
        a, info = check.outline_reference(outline)
        b, _ = check.outline_reference(outline.astype(np.uint8) * 255)
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(info["decoded_instances"], 1)
        self.assertEqual(info["decoded_foreground_pixels"], 36)

    def test_open_outline_is_not_silently_closed(self):
        outline = np.zeros((10, 10), dtype=np.uint8)
        outline[2, 2:8] = outline[7, 2:8] = 255
        outline[2:8, 2] = outline[2:8, 7] = 255
        outline[2, 4] = 0
        labels, _ = check.outline_reference(outline)
        self.assertEqual(int(labels.max()), 0)

    def test_rgb_adapter_preserves_geometry_and_declares_loss(self):
        rgb = np.zeros((3, 4, 3), dtype=np.uint8)
        rgb[..., 0] = 255
        raw, receipt = check.raw_adapter(rgb, "RGB")
        self.assertTrue(np.all(raw == 76))
        self.assertEqual(raw.shape, (3, 4))
        self.assertTrue(receipt["lossy_color_projection"])
        self.assertEqual(receipt["spatial_transform"], "none")

    def test_border_rule_removes_complete_labels(self):
        a = np.zeros((8, 8), dtype=np.int32)
        a[0:3, 1:4] = 1
        a[4:6, 4:6] = 6
        result = check.remove_frame(a)
        self.assertEqual(np.count_nonzero(result), 4)
        self.assertEqual(int(result.max()), 1)

    def test_empty_boundary_fields_cannot_dilute_failed_boundary_task(self):
        criteria = check.load_json(check.BASE / "PROTOCOL-amendment-2.json")["criteria"]
        summary = dict(mean_internal_boundary_f1=.95,
                       mean_boundary_f1_on_reference_boundary_bearing_fields=.50,
                       mean_relative_count_error=.05, mean_foreground_dice=.95,
                       boundary_bearing_fields=2)
        self.assertFalse(check.qualified(summary, "cells", criteria, heldout=True))
        summary["mean_boundary_f1_on_reference_boundary_bearing_fields"] = .80
        self.assertTrue(check.qualified(summary, "cells", criteria, heldout=True))
        summary["boundary_bearing_fields"] = 1
        self.assertFalse(check.qualified(summary, "cells", criteria, heldout=True))


class SavedMaskAdversarialTests(unittest.TestCase):
    """Attack self-consistent sidecars, not just a checksum in isolation."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.directory = self.root / "cohort"
        self.names = ["field_a", "field_b"]
        self.cases, self.predictions = {}, {}
        self.manifest, rows, measurements = {}, [], []
        for index, name in enumerate(self.names):
            labels = np.zeros((14, 14), dtype=np.int32)
            labels[3:7, 3 + 4 * index:7 + 4 * index] = 1
            self.predictions[name] = labels
            source = {"dna": {"member": name + ".tif", "sha256": str(index) * 64,
                               "shape": [14, 14], "dtype": "uint8"}}
            self.cases[name] = check.ReferenceCase(name, (labels * 127).astype(np.uint8),
                                                  labels.copy(), source, {})
            relative = "masks/" + check.slug(name) + ".png"
            path = self.directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(labels.astype(np.uint16)).save(path)
            file_sha, array_sha = check.file_hash(path), check.label_hash(labels)
            self.manifest[name] = dict(path=relative, sha256=file_sha, label_array_sha256=array_sha,
                shape=[14, 14], sources=source, reference_label_array_sha256=array_sha, decoder_diagnostics={})
            rows.append(check.field_record(self.cases[name], "r00", "nuclei",
                        check.score(labels, labels), array_sha, relative, file_sha))
            measurements.extend(check.measure(labels, name))
        write_csv(self.directory / "metrics.csv", rows)
        write_csv(self.directory / "measurements.csv", measurements)
        write_json(self.directory / "MASKS.json", self.manifest)
        # A fixed tiny oracle for generation identity, not a scientific model.
        self.verifier = object.__new__(check.Verifier)
        self.verifier.saved_fields = 0
        self.verifier.generated = lambda case, recipe, task, mode: (
            check.score(self.predictions[case.name], case.truth),
            check.label_hash(self.predictions[case.name]))

    def tearDown(self):
        self.temporary.cleanup()

    def verify(self):
        evidence = check.Evidence(self.root)
        result = self.verifier.saved_cohort(evidence, "cohort", self.names,
            self.cases.__getitem__, "r00", "nuclei", replay=True)
        evidence.inventory()
        return result

    def rewrite_metrics(self, mutate):
        rows = check.csv_rows(self.directory / "metrics.csv")
        mutate(rows)
        write_csv(self.directory / "metrics.csv", rows)

    def test_valid_tiny_fixture(self):
        rows, summary, _ = self.verify()
        self.assertEqual(len(rows), 2)
        self.assertEqual(summary["mean_instance_f1"], 1.0)

    def test_fabricated_score_with_unchanged_masks_rejected(self):
        self.rewrite_metrics(lambda rows: rows[0].__setitem__("instance_f1", ".77"))
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_missing_mask_rejected(self):
        (self.directory / self.manifest[self.names[0]]["path"]).unlink()
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_missing_manifest_field_rejected(self):
        self.manifest.pop(self.names[1])
        write_json(self.directory / "MASKS.json", self.manifest)
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_duplicate_field_even_with_correct_row_count_rejected(self):
        self.rewrite_metrics(lambda rows: rows.__setitem__(1, dict(rows[0])))
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_nonfinite_csv_metric_rejected(self):
        self.rewrite_metrics(lambda rows: rows[0].__setitem__("foreground_dice", "NaN"))
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_wrong_original_source_hash_rejected(self):
        self.manifest[self.names[0]]["sources"] = {"dna": {"member": "wrong.tif", "sha256": "f" * 64,
                                                         "shape": [14, 14], "dtype": "uint8"}}
        write_json(self.directory / "MASKS.json", self.manifest)
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_self_rehashed_reused_mask_rejected_by_generation_identity(self):
        first, second = self.names
        target = self.directory / self.manifest[second]["path"]
        labels = self.predictions[first]
        Image.fromarray(labels.astype(np.uint16)).save(target)
        self.manifest[second]["sha256"] = check.file_hash(target)
        self.manifest[second]["label_array_sha256"] = check.label_hash(labels)
        write_json(self.directory / "MASKS.json", self.manifest)
        # Forge every claimed score/hash consistently with the replacement.
        rows = check.csv_rows(self.directory / "metrics.csv")
        rows[1] = check.field_record(self.cases[second], "r00", "nuclei",
            check.score(labels, self.cases[second].truth), check.label_hash(labels),
            self.manifest[second]["path"], check.file_hash(target))
        write_csv(self.directory / "metrics.csv", rows)
        write_csv(self.directory / "measurements.csv",
                  check.measure(self.predictions[first], first) + check.measure(labels, second))
        with self.assertRaisesRegex(check.VerificationError, "regenerated prediction"):
            self.verify()

    def test_measurement_fabrication_rejected(self):
        rows = check.csv_rows(self.directory / "measurements.csv")
        rows[0]["area_pixels"] = "999"
        write_csv(self.directory / "measurements.csv", rows)
        with self.assertRaises(check.VerificationError):
            self.verify()

    def test_unaccounted_extra_mask_rejected(self):
        Image.fromarray(np.zeros((14, 14), dtype=np.uint16)).save(self.directory / "masks" / "extra.png")
        with self.assertRaisesRegex(check.VerificationError, "Unaccounted evidence"):
            self.verify()

    def test_symlink_rejected(self):
        path = self.directory / "masks" / "unexpected.png"
        path.symlink_to(self.directory / self.manifest[self.names[0]]["path"])
        with self.assertRaisesRegex(check.VerificationError, "symlink"):
            self.verify()

    def test_path_escape_rejected(self):
        evidence = check.Evidence(self.root)
        with self.assertRaises(check.VerificationError):
            evidence.path("../cohort/metrics.csv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
