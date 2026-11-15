"""EIT181 frozen synthetic controls; actual publisher data is a separate one-shot test."""
from io import BytesIO
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import h5py
import numpy as np
from research import eit_chest177 as src
from research import eit_real179 as parent
from research import eit_transfer181 as m


def toy():
    x = np.arange(36, dtype=float).reshape(12, 3) / 7. + 1.
    y = x * 1.4
    drive = np.ones_like(x)
    return drive, x, y


def archive_with(pairs, sidecars=True, incomplete=False):
    """Build two explicit source-stem repeats; no live data or customer inputs."""
    out = BytesIO()

    def mat(drive, volt):
        b = BytesIO()
        with h5py.File(b, "w") as f:
            f.create_dataset("currents_matrix", data=drive)
            f.create_dataset("voltages_matrix", data=volt)
            f.create_dataset("units_info", data=np.asarray([1]))
        return b.getvalue()

    with ZipFile(out, "w") as z:
        if sidecars:
            z.writestr("__MACOSX/AgarChestPhantom/Data/._00_1.mat", b"Mac OS X")
            z.writestr("__MACOSX/AgarChestPhantom/Data/._00_2.mat", b"Mac OS X")
        for stem, (drive, x, y) in pairs.items():
            z.writestr("AgarChestPhantom/Data/" + stem + "_1.mat", mat(drive, x))
            z.writestr("AgarChestPhantom/Data/" + stem + "_2.mat", mat(drive, y))
        if incomplete:
            z.writestr("AgarChestPhantom/Data/000_1.mat", b"incomplete")
    return out.getvalue()


class EIT181FrozenControls(unittest.TestCase):

    def test_01_selects_first_two_distinct_complete_stems_and_ignores_sidecars(self):
        raw = archive_with({"z": (toy()), "a": (toy()), "b": (toy())}, incomplete=True)
        with ZipFile(BytesIO(raw)) as z:
            count, choices = m.first_two_data_pairs(z.infolist())
        self.assertEqual(count, 3)
        self.assertEqual([x[0] for x in choices], ["a", "b"])
        self.assertEqual(choices[0][1].filename, "AgarChestPhantom/Data/a_1.mat")

    def test_02_fewer_than_two_complete_stems_is_failure_not_skip(self):
        raw = archive_with({"only": toy()}, sidecars=True)
        with ZipFile(BytesIO(raw)) as z:
            with self.assertRaisesRegex(src.Refused, "INSUFFICIENT"):
                m.first_two_data_pairs(z.infolist())

    def test_03_duplicate_slot_is_not_silently_overwritten(self):
        choices = [
            ZipInfo("AgarChestPhantom/Data/a_1.mat"),
            ZipInfo("AgarChestPhantom/Data/a_1.MAT"),
            ZipInfo("AgarChestPhantom/Data/a_2.mat"),
            ZipInfo("AgarChestPhantom/Data/b_1.mat"),
            ZipInfo("AgarChestPhantom/Data/b_2.mat"),
        ]
        with self.assertRaisesRegex(src.Refused, "DUPLICATE"):
            m.first_two_data_pairs(choices)

    def test_04_transferred_global_gain_is_the_ordinary_positive_control(self):
        c, x, y = toy()
        bx = 1.15 * x
        alternating = (np.arange(bx.shape[0]) % 2)[:, None] * 0.0001
        by = 1.4 * bx + alternating
        result = m.compare_stems(c, c, x, y, c, c, bx, by)
        self.assertGreater(result["gain_relative_rms_reduction_vs_identity"], 0.95)
        self.assertEqual(result["decision"], "TRANSFERRED_ORDINARY_GAIN_PLAUSIBLE_WITHIN_ARCHIVE")
        self.assertFalse(result["no_commercial_or_financial_result"])

    def test_05_different_gain_in_second_stem_falsifies_transfer(self):
        c, x, y = toy()
        z = m.compare_stems(c, c, x, y, c, c, x, x * 0.8 + 0.0001)
        self.assertEqual(z["decision"], "TRANSFER_NOT_ESTABLISHED")

    def test_06_per_channel_affine_is_ordinary_not_an_instrument(self):
        c, x, y = toy()
        gain = np.asarray([0.9, 1.2, 1.6])
        offsets = np.asarray([0.3, -0.2, 0.4])
        a = m.compare_stems(c, c, x, x * gain + offsets,
                            c, c, x * 0.85, x * 0.85 * gain + offsets)
        self.assertLess(a["model_heldout_second_stem"]["R3_transferred_per_column_affine"]["rms"], 1e-12)
        self.assertTrue(a["per_channel_improves_at_least_ten_percent"])
        self.assertTrue(a["no_physical_property_ground_truth"])

    def test_07_fitting_A_ignores_all_B_outcomes(self):
        c, x, y = toy()
        first = m.compare_stems(c, c, x, y, c, c, x, y)
        after = m.compare_stems(c, c, x, y, c, c, x, 7 * x)
        self.assertEqual(first["source_stem_a_fitted_parameters"],
                         after["source_stem_a_fitted_parameters"])
        self.assertNotEqual(first["model_heldout_second_stem"],
                            after["model_heldout_second_stem"])

    def test_08_both_stems_require_unchanged_within_stem_current_patterns(self):
        c, x, y = toy()
        different = c.copy()
        different[-1, 0] += 0.01
        with self.assertRaisesRegex(src.Refused, "CURRENT_PATTERNS_DIFFER"):
            m.compare_stems(c, c, x, y, c, different, x, y)

    def test_09_mismatched_stem_shape_rejected_not_transposed(self):
        c, x, y = toy()
        cb = np.ones((12, 4), dtype=float)
        xb = np.ones_like(cb) + np.arange(12)[:, None]
        with self.assertRaisesRegex(src.Refused, "CROSS_STEM"):
            m.compare_stems(c, c, x, y, cb, cb, xb, 2 * xb)

    def test_10_nonfinite_second_stem_is_not_discarded(self):
        c, x, y = toy()
        contaminated = y.copy()
        contaminated[1, 1] = float("nan")
        with self.assertRaisesRegex(src.Refused, "NONFINITE"):
            m.compare_stems(c, c, x, y, c, c, x, contaminated)

    def test_11_training_rank_deficiency_is_fail_closed(self):
        c, x, y = toy()
        x[:, 1] = 4.
        with self.assertRaisesRegex(src.Refused, "RANK_DEFICIENT"):
            m.compare_stems(c, c, x, y, c, c, x, y)

    def test_12_pinned_source_and_exact_first_two_pair_proofs(self):
        c, x, y = toy()
        raw = archive_with({"b": (c, x, y + 0.002), "a": (c, x, y), "c": (c, x, y)})
        md5 = hashlib.md5(raw).hexdigest()
        sha = hashlib.sha256(raw).hexdigest()
        with patch.object(src, "SIZE", len(raw)), patch.object(src, "MD5", md5), patch.object(parent, "PINNED_SHA256", sha):
            result = m.analyze_source(raw)
            self.assertEqual(result["selected_stem_names"], ["a", "b"])
            self.assertEqual(result["distinct_complete_data_stem_count"], 3)
            self.assertEqual(result["original_eit177_result"], "FAILED")
            self.assertEqual(len(result["selected_stem_member_proofs"]), 2)
        with patch.object(src, "SIZE", len(raw)), patch.object(src, "MD5", md5):
            with self.assertRaisesRegex(src.Refused, "SHA256_CHANGED"):
                m.analyze_source(raw)

    def test_13_corrupt_selected_stem_must_fail_instead_of_skipping_to_third(self):
        c, x, y = toy()
        raw = BytesIO()
        def mat(data):
            mem = BytesIO()
            with h5py.File(mem, "w") as f:
                f.create_dataset("currents_matrix", data=c)
                f.create_dataset("voltages_matrix", data=data)
                f.create_dataset("units_info", data=np.asarray([1]))
            return mem.getvalue()
        with ZipFile(raw, "w") as z:
            for name in ("a", "c"):
                for i in (1, 2):
                    z.writestr(f"AgarChestPhantom/Data/{name}_{i}.mat", mat(x if i == 1 else y))
            z.writestr("AgarChestPhantom/Data/b_1.mat", b"Mac OS X")
            z.writestr("AgarChestPhantom/Data/b_2.mat", b"Mac OS X")
        data = raw.getvalue()
        with patch.object(src, "SIZE", len(data)), patch.object(src, "MD5", hashlib.md5(data).hexdigest()), patch.object(parent, "PINNED_SHA256", hashlib.sha256(data).hexdigest()):
            with self.assertRaisesRegex(src.Refused, "INVALID_MAT73_MEMBER"):
                m.analyze_source(data)

    def test_14_create_only_refuses_before_any_source_request(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "receipt.json"
            p.write_text("unaltered")
            with patch.object(src, "download_once", side_effect=AssertionError("should never GET")):
                with self.assertRaisesRegex(src.Refused, "CREATE_ONLY"):
                    m.run(p)
            self.assertEqual(p.read_text(), "unaltered")

    def test_15_predecessor_failure_labels_and_commerce_refusal_are_explicit(self):
        self.assertEqual(m.SCHEMA, "agi-alpha/eit181-first-two-stem-transfer/v1")
        c, x, y = toy()
        raw = archive_with({"a": (c, x, y), "b": (c, x, y)})
        with patch.object(src, "SIZE", len(raw)), patch.object(src, "MD5", hashlib.md5(raw).hexdigest()), patch.object(parent, "PINNED_SHA256", hashlib.sha256(raw).hexdigest()):
            result = m.analyze_source(raw)
            self.assertEqual(result["original_eit177_result"], "FAILED")
            self.assertTrue(result["no_commercial_or_financial_result"])
            self.assertTrue(result["no_independent_session_claim"])


if __name__ == "__main__":
    unittest.main()
