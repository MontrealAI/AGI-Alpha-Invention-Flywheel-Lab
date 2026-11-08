#!/usr/bin/env python3
"""Focused partition, byte-integrity and filesystem-boundary tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import projection


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ltb-projection-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.evidence = self.base / "evidence"
        canonical = {"RESULTS.json": b'{"cost": 7}', "successor/mask.png": b"synthetic mask bytes"}
        residual = "attempts/successor-001/mask.png"
        for name, contents in canonical.items():
            path = self.evidence / "classical" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        path = self.evidence / "classical-residuals" / residual
        path.parent.mkdir(parents=True)
        path.write_bytes(canonical["successor/mask.png"])
        canonical_ids = {name: projection.content_identity(data) for name, data in canonical.items()}
        raw = dict(canonical_ids, **{residual: canonical_ids["successor/mask.png"]})
        self.map = {
            "schema": "learning-to-build/observed-evidence-projection/v1",
            "status": "COMPLETE_BYTE_PRESERVING_PROJECTION",
            "numerical_edits": False, "cost_exclusions": False,
            "source_bytes_unchanged_during_projection": True,
            "observed_raw_files": raw, "post_copy_raw_files": copy.deepcopy(raw),
            "inclusion_mapping": [{"raw_path": n, "projected_path": n, **v} for n, v in canonical_ids.items()],
            "residual_mapping": [{"raw_path": residual, "preserved_path": residual,
                                  "canonical_counterpart": "successor/mask.png", **raw[residual]}],
            "raw_file_count": 3, "projected_file_count": 2, "residual_file_count": 1,
            "raw_content_tree_sha256": projection.tree_hash(raw),
            "projection_content_tree_sha256": projection.tree_hash(canonical_ids),
        }
        self.map_path = self.evidence / "classical-residuals/PROJECTION.json"
        self.save_map()

    def save_map(self):
        self.map_path.write_text(json.dumps(self.map))

    def test_reconstructs_all_original_bytes_without_mutating_sources(self):
        before = projection.inventory(self.evidence)
        target = self.base / "raw"
        result = projection.verify(self.evidence, target)
        self.assertEqual(projection.inventory(target), self.map["observed_raw_files"])
        self.assertEqual(projection.inventory(self.evidence), before)
        self.assertEqual((result["raw_files"], result["canonical_files"], result["retained_residual_files"]), (3, 2, 1))
        self.assertFalse(result["scientific_acceptance_checked"])
        self.assertFalse(result["cost_completeness_verified"])
        self.assertFalse(result["raw_strict_inventory_acceptance_checked"])

    def test_duplicate_or_missing_partition_rejected_before_writing(self):
        original = copy.deepcopy(self.map)
        for action in ("duplicate", "missing"):
            with self.subTest(action=action):
                self.map = copy.deepcopy(original)
                rows = self.map["inclusion_mapping"]
                rows.append(rows[0]) if action == "duplicate" else rows.pop()
                self.save_map()
                target = self.base / ("raw-" + action)
                with self.assertRaises(ValueError):
                    projection.verify(self.evidence, target)
                self.assertFalse(target.exists())

    def test_traversal_absolute_and_noncanonical_mapping_paths_rejected(self):
        original = copy.deepcopy(self.map)
        for field in ("raw_path", "preserved_path", "canonical_counterpart"):
            for name in ("../escape", "/absolute", "a/../escape", "a//b", "a\\b", "C:escape", "."):
                with self.subTest(field=field, name=name):
                    self.map = copy.deepcopy(original)
                    self.map["residual_mapping"][0][field] = name
                    self.save_map()
                    with self.assertRaises(ValueError):
                        projection.verify(self.evidence)

    def test_duplicate_json_keys_rejected(self):
        contents = self.map_path.read_text()
        self.map_path.write_text('{"raw_file_count": 3,' + contents[1:])
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            projection.verify(self.evidence)

    def test_unmapped_files_and_changed_residual_bytes_rejected(self):
        extra = self.evidence / "classical/unmapped"
        extra.write_bytes(b"unaccounted")
        with self.assertRaisesRegex(ValueError, "inventory"):
            projection.verify(self.evidence)
        extra.unlink()
        residual = self.evidence / "classical-residuals" / self.map["residual_mapping"][0]["preserved_path"]
        residual.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "byte identity"):
            projection.verify(self.evidence)

    def test_wrong_counterpart_is_rejected_even_if_present(self):
        self.map["residual_mapping"][0]["canonical_counterpart"] = "RESULTS.json"
        self.save_map()
        with self.assertRaisesRegex(ValueError, "counterpart byte identity"):
            projection.verify(self.evidence)

    def test_original_inventory_drift_and_digest_drift_rejected(self):
        original = copy.deepcopy(self.map)
        for location in ("post_copy_raw_files", "raw_content_tree_sha256", "raw_file_count"):
            with self.subTest(location=location):
                self.map = copy.deepcopy(original)
                if location == "post_copy_raw_files":
                    self.map[location]["RESULTS.json"]["bytes"] += 1
                else:
                    self.map[location] = "0" * 64 if "sha256" in location else True
                self.save_map()
                with self.assertRaises(ValueError):
                    projection.verify(self.evidence)

    def test_existing_or_inside_evidence_destination_preserved(self):
        target = self.base / "existing"
        target.mkdir()
        marker = target / "marker"
        marker.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "new destination"):
            projection.verify(self.evidence, target)
        self.assertEqual(marker.read_text(), "preserve")
        with self.assertRaisesRegex(ValueError, "outside extracted evidence"):
            projection.verify(self.evidence, self.evidence / "raw")
        self.assertFalse((self.evidence / "raw").exists())

    def test_symlinked_source_file_directory_root_and_destination_parent_rejected(self):
        mask = self.evidence / "classical/successor/mask.png"
        real = self.base / "same-bytes"
        real.write_bytes(mask.read_bytes())
        mask.unlink()
        mask.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            projection.verify(self.evidence)
        mask.unlink()
        mask.write_bytes(real.read_bytes())
        linked_dir = self.evidence / "classical/unused-link"
        linked_dir.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            projection.verify(self.evidence)
        linked_dir.unlink()
        alias = self.base / "alias"
        alias.symlink_to(self.evidence, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            projection.verify(alias)
        outside = self.base / "outside"
        outside.mkdir()
        alias.unlink()
        alias.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            projection.verify(self.evidence, alias / "raw")
        self.assertFalse((outside / "raw").exists())

    def test_file_directory_collision_rejected_before_writing(self):
        residual = self.map["residual_mapping"][0]
        previous, changed = residual["raw_path"], "RESULTS.json/child"
        residual["raw_path"] = changed
        for key in ("observed_raw_files", "post_copy_raw_files"):
            self.map[key][changed] = self.map[key].pop(previous)
        self.save_map()
        with self.assertRaisesRegex(ValueError, "collision"):
            projection.verify(self.evidence, self.base / "raw")
        self.assertFalse((self.base / "raw").exists())


if __name__ == "__main__":
    unittest.main()
