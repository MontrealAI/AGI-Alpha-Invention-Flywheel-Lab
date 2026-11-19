"""EIT190 independent chest source: offline adversarial acceptance cases."""
import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import numpy as np
from scipy.io import savemat

from research.eit_independent190.inspect import (
    RECORD_ID, TARGET, Refusal, choose_exact_file, inventory_archive,
    mat_variables, safe_zip_members, write_create_only, main,
)


def mat_bytes(key="voltages_matrix"):
    f = io.BytesIO()
    savemat(f, {key: np.array([[1., 2.], [3., 4.]])})
    return f.getvalue()


def synthetic_archive(path, add_j=True):
    with ZipFile(path, "w") as z:
        base = "AgarChestPhantom/"
        if add_j:
            z.writestr(base + "Data/J_AgarChestPhantom.mat", mat_bytes("J"))
        z.writestr(base + "Data/mesh_AgarChestPhantom_2D_inverse_4.mat",
                   mat_bytes("mesh"))
        for k in range(4):
            z.writestr(base + "Data/2_" + str(k) + "_AgarChestPhantom.mat", mat_bytes())
        z.writestr(base + "ExampleCodes/Example_ChestPhantom_LinearDifferenceImaging.m",
                   "dV = V2 - V1;\n")


class Eit190OfflineTests(unittest.TestCase):
    def test_preselected_record_id_not_forgivable(self):
        with self.assertRaisesRegex(Refusal, "WRONG_ZENODO_RECORD_ID"):
            choose_exact_file({"id": "another", "files": {"entries": {}}})

    def test_archive_name_cannot_be_selected_from_other_files(self):
        with self.assertRaisesRegex(Refusal, "REQUIRED_CHEST_ARCHIVE_ABSENT"):
            choose_exact_file({"id": RECORD_ID, "files": {"entries": {
                "AgarCylinderPhantom.zip": {"size": 30, "checksum": "md5:"+"a"*32}
            }}})

    def test_manifest_current_schema_is_exact(self):
        report = {"id": int(RECORD_ID), "files": {"entries": {
            TARGET: {"key": TARGET, "size": 25, "checksum": "md5:"+("a"*32)}
        }}}
        self.assertEqual(choose_exact_file(report), (25, "a"*32))

    def test_checksum_and_size_refusal(self):
        for e in ({"size": -1, "checksum": "md5:"+("a"*32)},
                  {"size": 25, "checksum": "sha256:"+("a"*64)}):
            with self.subTest(entry=e), self.assertRaises(Refusal):
                choose_exact_file({"id": RECORD_ID, "files": {"entries": {TARGET: e}}})

    def test_duplicate_target_entries_rejected(self):
        with self.assertRaisesRegex(Refusal, "MISSING_OR_DUPLICATE"):
            choose_exact_file({"id": RECORD_ID, "files": [
                {"key": TARGET, "size": 2, "checksum": "md5:"+("a"*32)},
                {"key": TARGET, "size": 3, "checksum": "md5:"+("a"*32)}
            ]})

    def test_zip_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"unsafe.zip"
            with ZipFile(p, "w") as z:
                z.writestr("../outside.mat", b"contents")
            with ZipFile(p) as z, self.assertRaisesRegex(Refusal, "UNSAFE_MEMBER_PATH"):
                safe_zip_members(z)

    def test_duplicate_zip_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"duplicate.zip"
            with ZipFile(p, "w") as z:
                z.writestr("A/One.mat", b"x")
                z.writestr("a/one.mat", b"y")
            with ZipFile(p) as z, self.assertRaisesRegex(Refusal, "DUPLICATE_ZIP_MEMBER"):
                safe_zip_members(z)

    def test_symlink_in_zip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"link.zip"
            zi = ZipInfo("A/link.mat")
            zi.create_system = 3
            zi.external_attr = (stat.S_IFLNK | 0o777) << 16
            with ZipFile(p, "w") as z:
                z.writestr(zi, "target")
            with ZipFile(p) as z, self.assertRaisesRegex(Refusal, "SYMLINK"):
                safe_zip_members(z)

    def test_mat5_source_is_safely_inventoried(self):
        result = mat_variables(mat_bytes())
        self.assertEqual(result["format"], "MATLAB5")
        self.assertEqual(result["variables"][0]["shape"], [2, 2])
        with self.assertRaisesRegex(Refusal, "UNKNOWN_MAT"):
            mat_variables(b"not a matlab source")

    def test_all_four_synthetic_chest_states_inventoried(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"mock.zip"
            synthetic_archive(p)
            receipt = inventory_archive(p, "test-digest", p.stat().st_size, "a"*32)
            self.assertEqual(receipt["all_data_mat_members_count"], 4)
            self.assertEqual(receipt["original_jacobian_count"], 1)
            self.assertEqual(receipt["original_mesh_count"], 1)
            self.assertFalse(receipt["independent_conductivity_reconstructed"])
            self.assertIsNone(receipt["complete_cost_or_frontier_model_bill_usd"])

    def test_missing_original_jacobian_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"missing.zip"
            synthetic_archive(p, add_j=False)
            with self.assertRaisesRegex(Refusal, "REQUIRED_ORIGINAL_CHEST_COMPONENTS"):
                inventory_archive(p, "x", p.stat().st_size, "a"*32)

    def test_receipt_create_only_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/"receipt.json"
            write_create_only(target, {"decision": "HOLD_NO_DEPLOY_NO_BID"})
            original = target.read_bytes()
            with self.assertRaisesRegex(Refusal, "RECEIPT_EXISTS"):
                write_create_only(target, {"decision": "FAKE_PASS"})
            link = Path(d)/"symlink.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(Refusal, "RECEIPT_EXISTS"):
                write_create_only(link, {"decision": "FAKE_PASS"})
            self.assertEqual(target.read_bytes(), original)

    def test_no_network_with_preexisting_output(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/"existing.json"
            target.write_text("old failure")
            with patch("research.eit_independent190.inspect._read_json_source",
                       side_effect=AssertionError("network not allowed")):
                with self.assertRaisesRegex(Refusal, "RECEIPT_EXISTS"):
                    main(["--out", str(target)])
            self.assertEqual(target.read_text(), "old failure")


if __name__ == "__main__":
    unittest.main()
