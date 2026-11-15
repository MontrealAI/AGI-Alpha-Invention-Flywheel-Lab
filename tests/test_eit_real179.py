"""EIT179 prospective source-bound real-data semantics; synthetic controls only."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipInfo
import numpy as np
from research import eit_real179 as m
from research import eit_chest177 as p
from tests.test_eit_chest177 import mat, archive

def f(a='a', x=1.0, y=2.0):
    return {'AgarChestPhantom/Data/'+a+'_1.mat':mat(x),
            'AgarChestPhantom/Data/'+a+'_2.mat':mat(y)}

def parse_synthetic(contents):
    raw=archive(contents)
    with patch.object(p,'SIZE',len(raw)),patch.object(p,'MD5',hashlib.md5(raw).hexdigest()),patch.object(m,'PINNED_SHA256',hashlib.sha256(raw).hexdigest()):
        return m.parse_pinned(raw)

class TestEIT179(unittest.TestCase):
    def test_01_metadata_apple_sidecars_never_eligible(self):
        all_files={**f(), '__MACOSX/AgarChestPhantom/Data/._a_1.mat':b'junk',
                         '__MACOSX/AgarChestPhantom/Data/._a_2.mat':b'junk'}
        result=parse_synthetic(all_files)
        self.assertEqual(result['status'],'REAL_DATA_REPEAT_PARSED')
        self.assertTrue(all(x['path'].startswith('AgarChestPhantom/Data/') for x in result['pairs']))
        self.assertEqual(result['original_eit177'],'FAILED')
        self.assertFalse(result['conductivity_reconstruction_tested'])

    def test_02_fixed_lexicographic_first_real_pair(self):
        result=parse_synthetic({**f('z',5,5),**f('a',1,2)})
        self.assertEqual(result['selected_true_data_stem'],'a')
        self.assertEqual(result['observations'][1]['rms_direct_difference'],1.0)

    def test_03_only_metadata_pairs_fail(self):
        raw=archive({'__MACOSX/AgarChestPhantom/Data/._a_1.mat':b'junk',
                     '__MACOSX/AgarChestPhantom/Data/._a_2.mat':b'junk'})
        with patch.object(p,'SIZE',len(raw)),patch.object(p,'MD5',hashlib.md5(raw).hexdigest()),patch.object(m,'PINNED_SHA256',hashlib.sha256(raw).hexdigest()):
            with self.assertRaisesRegex(p.Refused,'NO_ELIGIBLE'):m.parse_pinned(raw)

    def test_04_nested_data_path_not_eligible(self):
        with self.assertRaisesRegex(p.Refused,'NO_ELIGIBLE'):
            m.true_data_first_pair([ZipInfo('AgarChestPhantom/Data/nested/a_1.mat'),ZipInfo('AgarChestPhantom/Data/nested/a_2.mat')])

    def test_05_missing_right_repeat_fails(self):
        with self.assertRaisesRegex(p.Refused,'NO_ELIGIBLE'):
            m.true_data_first_pair([ZipInfo('AgarChestPhantom/Data/only_1.mat')])

    def test_06_pinned_archive_sha_mismatch_rejected(self):
        raw=archive(f())
        with patch.object(p,'SIZE',len(raw)),patch.object(p,'MD5',hashlib.md5(raw).hexdigest()):
            with self.assertRaisesRegex(p.Refused,'SHA256_CHANGED'):m.parse_pinned(raw)

    def test_07_wrong_size_rejected(self):
        with self.assertRaisesRegex(p.Refused,'SIZE'):m.parse_pinned(b'fake')

    def test_08_wrong_publisher_md5_rejected(self):
        raw=archive(f())
        with patch.object(p,'SIZE',len(raw)):
            with self.assertRaisesRegex(p.Refused,'MD5'):m.parse_pinned(raw)

    def test_09_nonfinite_real_matrix_rejected(self):
        with self.assertRaisesRegex(p.Refused,'NONFINITE'):
            parse_synthetic({'AgarChestPhantom/Data/a_1.mat':mat(nonfinite=True),
                             'AgarChestPhantom/Data/a_2.mat':mat()})

    def test_10_real_shape_mismatch_rejected(self):
        with self.assertRaisesRegex(p.Refused,'DIMENSIONS'):
            parse_synthetic({'AgarChestPhantom/Data/a_1.mat':mat(shape=(3,2)),
                             'AgarChestPhantom/Data/a_2.mat':mat()})

    def test_11_real_mat73_fields_required(self):
        with self.assertRaisesRegex(p.Refused,'FIELDS'):
            parse_synthetic({'AgarChestPhantom/Data/a_1.mat':mat(fields=False),
                             'AgarChestPhantom/Data/a_2.mat':mat()})

    def test_12_create_only_receipt_before_fetch(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'already.json';out.write_text('same')
            with self.assertRaisesRegex(p.Refused,'CREATE_ONLY'):m.run(out)
            self.assertEqual(out.read_text(),'same')

if __name__=='__main__':unittest.main()
