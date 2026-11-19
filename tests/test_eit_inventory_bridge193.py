"""EIT193 preregistered offline refusing tests, no source downloads."""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

from tools.eit_inventory_bridge193 import (
    BridgeRefusal, analyze_genuine_members, git_blob_sha1,
    verify_source_bytes, get_pinned_source, is_utf8,
    SOURCE_ARCHIVE_SHA256, PINNED_MODULES,
)


def fixture_archive(path, *, malformed=False):
    with ZipFile(path, "w") as archive:
        archive.writestr("AgarChestPhantom/Data/J_AgarChestPhantom.mat", b"mat-j")
        archive.writestr("AgarChestPhantom/Data/mesh_AgarChestPhantom_2D.mat", b"mat-mesh")
        archive.writestr("AgarChestPhantom/Data/2o2_AgarChestPhantom_Inc_missingPiece_1.mat",
                         b"malformed" if malformed else b"mat-data")
        archive.writestr("AgarChestPhantom/ExampleCodes/Example_ChestPhantom_LinearDifferenceImaging.m",
                         b"x=1;\n")
        archive.writestr("__MACOSX/AgarChestPhantom/Data/._2o2_AgarChestPhantom_Inc_missingPiece_1.mat",
                         b"resource")


def typed_list():
    names = [
        "AgarChestPhantom/Data/J_AgarChestPhantom.mat",
        "AgarChestPhantom/Data/mesh_AgarChestPhantom_2D.mat",
        "AgarChestPhantom/Data/2o2_AgarChestPhantom_Inc_missingPiece_1.mat",
        "AgarChestPhantom/ExampleCodes/Example_ChestPhantom_LinearDifferenceImaging.m"
    ]
    return {"genuine_members": sorted(names),
            "genuine_matlab_candidates": sorted(names),
            "sidecars": [{
                "member": "__MACOSX/AgarChestPhantom/Data/._2o2_AgarChestPhantom_Inc_missingPiece_1.mat"
            }]}


class Eit193Offline(unittest.TestCase):
    def test_git_blob_identity_matches_canonical_git_object(self):
        data = b"ordinary verified Python source\n"
        expected = hashlib.sha1(b"blob 32\0" + data).hexdigest()
        self.assertEqual(len(data), 32)
        self.assertEqual(git_blob_sha1(data), expected)
        verify_source_bytes(data, expected)
        with self.assertRaisesRegex(BridgeRefusal, "BLOB_CHANGED"):
            verify_source_bytes(data + b"x", expected)
        with self.assertRaisesRegex(BridgeRefusal, "SIZE_REJECTED"):
            verify_source_bytes(b"", expected)

    def test_declared_source_blobs_are_three_distinct_fixed_sources(self):
        self.assertEqual(len(PINNED_MODULES), 3)
        self.assertEqual(len(set(row[3] for row in PINNED_MODULES)), 3)
        self.assertEqual(len(SOURCE_ARCHIVE_SHA256), 64)

    def test_no_network_if_raw_host_changes(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def geturl(self): return "http://example.com/evil"
            def read(self, *_): return b"not pinned"
        with mock.patch("tools.eit_inventory_bridge193.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(BridgeRefusal, "HOST_CHANGED"):
                get_pinned_source("a"*40, "p.py", "b"*40)

    def test_exact_matlab_candidates_and_no_sidecar_read(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.zip"
            fixture_archive(source)
            seen = []
            def parser(raw):
                seen.append(raw)
                return {"format": "MATLAB5", "variables": [{"name": "M", "shape": [1, 1],
                                                              "type": "double"}]}
            report = analyze_genuine_members(source, typed_list(), parser)
            self.assertEqual(len(seen), 3)
            self.assertNotIn(b"resource", seen)
            self.assertEqual(report["jacobians"], 1)
            self.assertEqual(report["meshes"], 1)
            self.assertEqual(report["scripts"], 1)
            self.assertEqual(report["data_matrices"], 1)
            self.assertEqual(len(report["matlab_members"]), 4)
            self.assertEqual(report["matlab_members"][-1]["sha256"],
                             hashlib.sha256(b"mat-mesh").hexdigest())

    def test_original_parser_failure_must_not_silently_discard_genuine_mat(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.zip"
            fixture_archive(source, malformed=True)
            def parser(raw):
                if raw == b"malformed":
                    raise ValueError("genuine MAT corrupt")
                return {"format": "MATLAB5", "variables": []}
            with self.assertRaisesRegex(BridgeRefusal, "ORIGINAL_MAT_PARSER_REJECTED"):
                analyze_genuine_members(source, typed_list(), parser)

    def test_missing_real_mat_or_injected_sidecar_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.zip"
            fixture_archive(source)
            good = typed_list()
            missing = {"genuine_members": good["genuine_members"],
                       "genuine_matlab_candidates": good["genuine_matlab_candidates"][:-1]}
            with self.assertRaisesRegex(BridgeRefusal, "CANDIDATE_SET_CHANGED"):
                analyze_genuine_members(source, missing, lambda _: {"variables": []})
            evil = {**good, "genuine_members": sorted(
                good["genuine_members"] + ["__MACOSX/A/._file.mat"]),
                "genuine_matlab_candidates": sorted(
                    good["genuine_matlab_candidates"] + ["__MACOSX/A/._file.mat"])}
            with self.assertRaisesRegex(BridgeRefusal, "SIDECAR_CANDIDATE_LEAK"):
                analyze_genuine_members(source, evil, lambda _: {"variables": []})

    def test_missing_chest_components_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.zip"
            fixture_archive(source)
            typed = typed_list()
            names = [x for x in typed["genuine_members"] if "J_AgarChestPhantom" not in x]
            typed["genuine_members"] = names
            typed["genuine_matlab_candidates"] = names
            with self.assertRaisesRegex(BridgeRefusal, "REQUIRED_ORIGINAL_CHEST"):
                analyze_genuine_members(source, typed, lambda _: {"variables": []})

    def test_script_encoding_only_not_execution(self):
        self.assertTrue(is_utf8(b"x=1;\n"))
        self.assertFalse(is_utf8(b"\xff"))

if __name__ == "__main__":
    unittest.main()
