"""Frozen offline ZIP-path and selection controls (not evidence of measured physics)."""
from importlib.util import module_from_spec, spec_from_file_location
import io
from pathlib import Path
import stat
import unittest
from zipfile import ZipFile, ZipInfo

SOURCE = Path(__file__).resolve().parents[1] / "research/eit_public182/physical_intake.py"
spec = spec_from_file_location("eit_physical182", SOURCE)
module = module_from_spec(spec)
spec.loader.exec_module(module)


def makezip(names):
    memory = io.BytesIO()
    with ZipFile(memory, "w") as z:
        for name in names:
            z.writestr(name, b"pretend-mat-bytes")
    memory.seek(0)
    return ZipFile(memory)


class PhysicalZipGateTests(unittest.TestCase):
    def test_all_registered_data_cases_selected_without_best_of_subset(self):
        z = makezip(["AgarCylinderPhantom/Data/03_b.mat", "AgarCylinderPhantom/Data/01_a.mat",
                     "AgarCylinderPhantom/mesh_x.mat", "AgarCylinderPhantom/Data/J_control.mat",
                     "AgarCylinderPhantom/Photos/image.jpg"])
        self.assertEqual([i.filename for i in module.check_names(z)],
                         ["AgarCylinderPhantom/Data/01_a.mat", "AgarCylinderPhantom/Data/03_b.mat"])

    def test_real_measurement_cases_remain_while_appledouble_is_excluded(self):
        z = makezip(["__MACOSX/AgarCylinderPhantom/Data/._1o0_NoInc.mat",
                     "AgarCylinderPhantom/Data/1o0_NoInc.mat",
                     "AgarCylinderPhantom/Data/2o0_WithInc.mat"])
        self.assertTrue(module.is_appledouble_member("__MACOSX/AgarCylinderPhantom/Data/._1o0_NoInc.mat"))
        self.assertEqual([i.filename for i in module.check_names(z)],
                         ["AgarCylinderPhantom/Data/1o0_NoInc.mat", "AgarCylinderPhantom/Data/2o0_WithInc.mat"])

    def test_duplicate_casefold_zip_name_refused(self):
        z = makezip(["AgarCylinderPhantom/Data/A.mat", "agarcylinderphantom/Data/a.MAT"])
        with self.assertRaisesRegex(module.PhysicalIntakeRefusal, "DUPLICATE_ZIP_MEMBER"):
            module.check_names(z)

    def test_relative_traversal_refused(self):
        z = makezip(["AgarCylinderPhantom/Data/../A.mat", "AgarCylinderPhantom/Data/B.mat"])
        with self.assertRaisesRegex(module.PhysicalIntakeRefusal, "UNSAFE_ZIP_MEMBER"):
            module.check_names(z)

    def test_backslash_member_refused(self):
        z = makezip(["AgarCylinderPhantom\\Data\\A.mat", "AgarCylinderPhantom/Data/B.mat"])
        with self.assertRaisesRegex(module.PhysicalIntakeRefusal, "UNSAFE_ZIP_MEMBER"):
            module.check_names(z)

    def test_less_than_two_cases_refused(self):
        z = makezip(["AgarCylinderPhantom/Data/A.mat", "AgarCylinderPhantom/J_matrix.mat"])
        with self.assertRaisesRegex(module.PhysicalIntakeRefusal, "INSUFFICIENT_REGISTERED"):
            module.check_names(z)

    def test_symlink_refused_before_read(self):
        mem = io.BytesIO()
        with ZipFile(mem, "w") as z:
            item = ZipInfo("AgarCylinderPhantom/Data/A.mat")
            item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(item, b"danger")
            z.writestr("AgarCylinderPhantom/Data/B.mat", b"ok")
        mem.seek(0)
        with ZipFile(mem) as z, self.assertRaisesRegex(module.PhysicalIntakeRefusal, "LINK_OR_ENCRYPTED"):
            module.check_names(z)

    def test_public_source_id_and_declared_archive_bound_before_download(self):
        self.assertEqual(module.ARCHIVE_NAME, "AgarCylinderPhantom.zip")
        self.assertEqual(module.EXPECTED_SIZE, 12482688)
        self.assertEqual(module.EXPECTED_MD5, "658694f69f64075b6fefec2e2c597131")
        self.assertEqual(module.URL, "https://zenodo.org/api/records/24120439/files/AgarCylinderPhantom.zip/content")


if __name__ == "__main__":
    unittest.main()
