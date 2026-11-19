"""EIT185 frozen source-mapping tests: synthetic input, never physical confirmation."""
import hashlib
import io
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import h5py
import numpy as np

from research.eit_physical_control183.control import MEMBERS, Refusal, SHAPE
from research.eit_jacobian185 import original_source as src


def make_mat(**arrays):
    buf = io.BytesIO()
    with h5py.File(buf, "w") as h:
        for name, array in arrays.items():
            h.create_dataset(name, data=array)
    return buf.getvalue()


def make_archive(jacobian=None, script=True, bad_currents=False, include_j=True):
    paths = list(MEMBERS)
    i0 = np.ones(SHAPE, dtype=np.float64)
    i1 = i0.copy()
    if bad_currents:
        i1[1, 1] = 2
    a0 = make_mat(currents_matrix=i0, voltages_matrix=np.ones(SHAPE, dtype=np.float64))
    a1 = make_mat(currents_matrix=i1, voltages_matrix=np.ones(SHAPE, dtype=np.float64) * 1.2)
    with io.BytesIO() as stream:
        with ZipFile(stream, "w") as z:
            z.writestr(paths[0], a0)
            z.writestr(paths[1], a1)
            if include_j:
                z.writestr("AgarCylinderPhantom/Data/J_source.mat",
                           jacobian if jacobian is not None else make_mat(J=np.ones((1264, 2))))
            if script:
                z.writestr("AgarCylinderPhantom/ExampleCodes/Original.m", "x = 1;")
        data = stream.getvalue()
    return data, {paths[0]: hashlib.sha256(a0).hexdigest(),
                  paths[1]: hashlib.sha256(a1).hexdigest()}


class TestEIT185(unittest.TestCase):
    def inspect(self, archive, hashes):
        with patch.object(src, "MEMBERS", hashes):
            with ZipFile(io.BytesIO(archive)) as z:
                return src.inspect_zip(z)

    def test_complete_source_inventory_and_no_reconstruction(self):
        archive, hashes = make_archive()
        out = self.inspect(archive, hashes)
        self.assertEqual(out["original_jacobian_candidate_count"], 1)
        self.assertEqual(out["original_example_script_count"], 1)
        self.assertEqual(out["all_original_jacobian_candidates"][0]["datasets"][0]["shape"], [1264, 2])
        self.assertFalse(out["measurement_to_J_mapping_authenticated"])
        self.assertFalse(out["reconstruction_performed"])
        self.assertIsNone(out["real_commercial_collections_usd"])

    def test_no_jacobian_refused(self):
        archive, hashes = make_archive(include_j=False)
        with self.assertRaisesRegex(Refusal, "ORIGINAL_JACOBIAN_OR_EXAMPLE_SCRIPT_MISSING"):
            self.inspect(archive, hashes)

    def test_no_original_script_refused(self):
        archive, hashes = make_archive(script=False)
        with self.assertRaisesRegex(Refusal, "ORIGINAL_JACOBIAN_OR_EXAMPLE_SCRIPT_MISSING"):
            self.inspect(archive, hashes)

    def test_protect_original_measured_member_hash(self):
        archive, hashes = make_archive()
        hashes[list(hashes)[0]] = "0" * 64
        with self.assertRaisesRegex(Refusal, "ORIGINAL_MEASUREMENT_HASH_CHANGED"):
            self.inspect(archive, hashes)

    def test_mismatched_currents_refused(self):
        archive, hashes = make_archive(bad_currents=True)
        with self.assertRaisesRegex(Refusal, "ORIGINAL_EXCITATIONS_UNMATCHED"):
            self.inspect(archive, hashes)

    def test_nonfinite_jacobian_refused(self):
        j = np.ones((1264, 2))
        j[0, 0] = np.nan
        archive, hashes = make_archive(jacobian=make_mat(J=j))
        with self.assertRaisesRegex(Refusal, "NONFINITE_JACOBIAN_DATASET"):
            self.inspect(archive, hashes)

    def test_non_HDF5_original_jacobian_refused(self):
        archive, hashes = make_archive(jacobian=b"not HDF5")
        with self.assertRaisesRegex(Refusal, "ORIGINAL_JACOBIAN_NOT_HDF5"):
            self.inspect(archive, hashes)

    def test_no_actual_dataset_refused(self):
        archive, hashes = make_archive(jacobian=make_mat())
        with self.assertRaisesRegex(Refusal, "ORIGINAL_JACOBIAN_HAS_NO_DATASETS"):
            self.inspect(archive, hashes)

    def test_all_jacobian_candidates_counted_not_cherry_picked(self):
        archive, hashes = make_archive()
        with ZipFile(io.BytesIO(archive)) as z:
            entries = [(i.filename, z.read(i)) for i in z.infolist()]
        s = io.BytesIO()
        with ZipFile(s, "w") as z:
            for name, raw in entries:
                z.writestr(name, raw)
            z.writestr("AgarCylinderPhantom/Data/J_second.mat", make_mat(second=np.ones((12, 9))))
        out = self.inspect(s.getvalue(), hashes)
        self.assertEqual(out["original_jacobian_candidate_count"], 2)
        self.assertEqual([x["member"] for x in out["all_original_jacobian_candidates"]],
                         ["AgarCylinderPhantom/Data/J_second.mat",
                          "AgarCylinderPhantom/Data/J_source.mat"])


if __name__ == "__main__":
    unittest.main()
