"""EIT175 frozen negative tests; synthetic HDF5 is a test fixture, never physical evidence."""
from io import BytesIO
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

import h5py
import numpy as np
from research import eit_measured175 as m

def mat(current=1.,voltage=2.,fields=True, nan=False,shape=(2,3)):
    sink=BytesIO()
    with h5py.File(sink,'w') as hf:
        if fields:
            hf.create_dataset('currents_matrix',data=np.full(shape,current,dtype=float))
            hf.create_dataset('voltages_matrix',data=np.full(shape,float('nan') if nan else voltage,dtype=float))
            hf.create_dataset('units_info',data=np.array([1],dtype=int))
        else:
            hf.create_dataset('not_measurements',data=[2])
    return sink.getvalue()

def archive(entries=None):
    if entries is None:
        entries=[
            ('AgarCylinderPhantom/Data/01_case_1.mat',mat()),
            ('AgarCylinderPhantom/Data/01_case_2.mat',mat(current=1.05,voltage=2.25)),
        ]
    out=BytesIO()
    with ZipFile(out,'w') as z:
        for name,data in entries:
            z.writestr(name,data)
    return out.getvalue()

def supplied(raw):
    with patch.object(m,'EXPECTED_SIZE',len(raw)), patch.object(m,'EXPECTED_MD5',hashlib.md5(raw,usedforsecurity=False).hexdigest()):
        return m.inspect_archive(raw)

class EIT175Tests(unittest.TestCase):
    def test_two_actual_hdf5_fixture_arrays_and_direct_differences(self):
        d=supplied(archive())
        self.assertTrue(d['raw_archive_bytes_verified'])
        self.assertTrue(d['some_measurement_arrays_parsed'])
        self.assertFalse(d['image_reconstruction_tested'])
        self.assertEqual(d['selected_repeat_stem'],'agarcylinderphantom/data/01_case')
        self.assertEqual([r['shape'] for r in d['direct_repeat_array_statistics']],[[2,3],[2,3]])
        self.assertAlmostEqual(d['direct_repeat_array_statistics'][1]['rms_direct_difference'],.25)

    def test_exact_publisher_hash_mismatch(self):
        raw=archive()
        with patch.object(m,'EXPECTED_SIZE',len(raw)),patch.object(m,'EXPECTED_MD5','0'*32):
            with self.assertRaisesRegex(m.SourceRefused,'PUBLISHER_MD5'):m.verify_archive_bytes(raw)

    def test_exact_publisher_size_mismatch(self):
        with self.assertRaisesRegex(m.SourceRefused,'SIZE_MISMATCH'):m.verify_archive_bytes(archive())

    def test_corrupt_archive_refused(self):
        raw=b'nonzip garbage'
        with self.assertRaisesRegex(m.SourceRefused,'INVALID_ZIP'):m.validate_archive(raw)

    def test_member_traversal_refused(self):
        raw=archive([('../escape.txt',b'bad')])
        with self.assertRaisesRegex(m.SourceRefused,'UNSAFE_ARCHIVE'):m.validate_archive(raw)

    def test_zip_symlink_refused(self):
        info=ZipInfo('AgarCylinderPhantom/Data/linked.mat')
        info.create_system=3
        info.external_attr=(stat.S_IFLNK | 0o777)<<16
        with self.assertRaisesRegex(m.SourceRefused,'SYMLINK'):
            m.validate_archive(archive([(info,b'/tmp/not-real')]))

    def test_duplicate_casefold_archive_member_refused(self):
        entries=[('AgarCylinderPhantom/Data/C.mat',b'foo'),
                 ('agarcylinderphantom/data/c.MAT',b'bar')]
        with self.assertRaisesRegex(m.SourceRefused,'DUPLICATE'):
            m.validate_archive(archive(entries))

    def test_declared_uncompressed_limit(self):
        raw=archive([('AgarCylinderPhantom/Data/a',b'big')])
        with patch.object(m,'MAX_UNCOMPRESSED',2):
            with self.assertRaisesRegex(m.SourceRefused,'UNCOMPRESSED'):
                m.validate_archive(raw)

    def test_no_repeated_pair_fails_closed(self):
        raw=archive([('Data/01_baseline.mat',mat())])
        with self.assertRaisesRegex(m.SourceRefused,'NO_REGISTERED_REPEAT'):
            supplied(raw)

    def test_missing_mat_fields_refused(self):
        raw=archive([('Data/01_case_1.mat',mat(fields=False)),
                     ('Data/01_case_2.mat',mat())])
        with self.assertRaisesRegex(m.SourceRefused,'EXPECTED_MAT73'):supplied(raw)

    def test_nonfinite_measured_array_refused(self):
        raw=archive([('Data/01_case_1.mat',mat(nan=True)),
                     ('Data/01_case_2.mat',mat())])
        with self.assertRaisesRegex(m.SourceRefused,'FINITE_BOUNDED_REAL'):supplied(raw)

    def test_mismatched_mat_array_shapes_refused(self):
        raw=archive([('Data/01_case_1.mat',mat(shape=(2,3))),
                     ('Data/01_case_2.mat',mat(shape=(3,2)))])
        with self.assertRaisesRegex(m.SourceRefused,'REPEAT_CURRENT_VOLTAGE_DIMENSIONS'):
            supplied(raw)

    def test_fixed_lexicographic_choice_not_largest_signal(self):
        raw=archive([('Data/99_later_1.mat',mat(current=100)),
                     ('Data/99_later_2.mat',mat(current=1000)),
                     ('Data/01_first_1.mat',mat()),
                     ('Data/01_first_2.mat',mat(current=1.1))])
        result=supplied(raw)
        self.assertEqual(result['selected_repeat_stem'],'data/01_first')

    def test_non_mat_files_and_unpaired_data_not_selected(self):
        raw=archive([('Data/01_first_1.mat',mat()),
                     ('Data/01_first_2.mat',mat()),
                     ('Photos/00_look_1.mat',mat()),
                     ('Photos/00_look_2.mat',mat()),
                     ('Data/notes.txt',b'none')])
        self.assertEqual(supplied(raw)['selected_repeat_stem'],'data/01_first')

    def test_encrypted_member_refused_before_decompression(self):
        info=ZipInfo('Data/01_case_1.mat')
        info.flag_bits|=1
        class FakeZip:
            def infolist(self):return [info]
            def testzip(self):return None
        with patch.object(m,'ZipFile',return_value=FakeZip()):
            with self.assertRaisesRegex(m.SourceRefused,'ENCRYPTED'):
                m.validate_archive(b'fixture')

    def test_foreign_redirect_refused(self):
        for url in ['http://zenodo.org/a','https://attacker.test/a','https://zenodo.org.attacker.test/a']:
            with self.subTest(url=url),self.assertRaisesRegex(m.SourceRefused,'UNEXPECTED_ARCHIVE_REDIRECT'):
                m.RestrictedRedirect().redirect_request(None,None,302,'redirect',{},url)

    def test_create_only_receipt_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json'
            m._write(path,{'a':1})
            with self.assertRaisesRegex(m.SourceRefused,'CREATE_ONLY'):
                m._write(path,{'a':2})

if __name__=='__main__':
    unittest.main(verbosity=2)
