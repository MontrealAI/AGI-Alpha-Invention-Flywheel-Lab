"""EIT177 preregistered fail-closed controls, entirely synthetic offline fixtures."""
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo
import numpy as np
import h5py
from research import eit_chest177 as m

def mat(voltage=1.0, fields=True, nonfinite=False, shape=(2,2)):
    io = BytesIO()
    with h5py.File(io,'w') as f:
        f.create_dataset('currents_matrix', data=np.ones((2,2)))
        v=np.full(shape,voltage)
        if nonfinite:v.flat[0]=np.nan
        f.create_dataset('voltages_matrix', data=v)
        if fields:f.create_dataset('units_info',data=np.array([1]))
    return io.getvalue()

def archive(files=None):
    if files is None:
        files={'Data/Z_Set_1.mat':mat(1),'Data/Z_Set_2.mat':mat(1.5)}
    io=BytesIO()
    with ZipFile(io,'w') as z:
        for n,b in files.items():z.writestr(n,b)
    return io.getvalue()

def inspect_synthetic(raw):
    with patch.object(m,'SIZE',len(raw)),patch.object(m,'MD5',hashlib.md5(raw).hexdigest()):
        return m.inspect(raw)

class TestChest177(unittest.TestCase):
    def test_01_two_exact_repeat_real_arrays(self):
        r=inspect_synthetic(archive())
        self.assertEqual(r['status'],'REPEAT_FIELDS_ACCESSIBLE')
        self.assertEqual(r['selected_repeat_stem'],'data/z_set')
        self.assertEqual(r['measurements'][1]['rms_direct_difference'],0.5)
        self.assertFalse(r['new_observability_demonstrated'])

    def test_02_wrong_size_refused(self):
        with self.assertRaisesRegex(m.Refused,'SIZE'):m.verify_source(b'no')

    def test_03_publisher_md5_mismatch_refused(self):
        raw=archive()
        with patch.object(m,'SIZE',len(raw)):
            with self.assertRaisesRegex(m.Refused,'MD5'):m.verify_source(raw)

    def test_04_corrupt_zip_refused(self):
        with patch.object(m,'SIZE',3), patch.object(m,'MD5',hashlib.md5(b'abc').hexdigest()):
            with self.assertRaisesRegex(m.Refused,'INVALID_ZIP'):m.inspect(b'abc')

    def test_05_archive_traversal_refused(self):
        with self.assertRaisesRegex(m.Refused,'UNSAFE'):inspect_synthetic(archive({'../Data/a_1.mat':b'x'}))

    def test_06_archive_symlink_refused(self):
        z=BytesIO()
        with ZipFile(z,'w') as f:
            i=ZipInfo('Data/x_1.mat'); i.create_system=3; i.external_attr=(0o120777<<16)
            f.writestr(i,b'x')
        with self.assertRaisesRegex(m.Refused,'UNSAFE'):inspect_synthetic(z.getvalue())

    def test_07_duplicate_casefold_refused(self):
        z=BytesIO()
        with ZipFile(z,'w') as f:
            f.writestr('Data/a_1.mat',b'x'); f.writestr('data/A_1.mat',b'x')
        with self.assertRaisesRegex(m.Refused,'DUPLICATE'):inspect_synthetic(z.getvalue())

    def test_08_encrypted_member_flag_refused(self):
        i=ZipInfo('Data/a_1.mat'); i.flag_bits=1
        class FakeZip:
            def infolist(self):return [i]
        with self.assertRaisesRegex(m.Refused,'ENCRYPTED'):m._members(FakeZip())

    def test_09_uncompressed_guard_refused(self):
        i=ZipInfo('Data/a_1.mat');i.file_size=m.MAX_TOTAL+1
        class FakeZip:
            def infolist(self):return [i]
        with self.assertRaisesRegex(m.Refused,'RESOURCE_BOUND'):m._members(FakeZip())

    def test_10_no_exact_pair_refused(self):
        with self.assertRaisesRegex(m.Refused,'NO_EXACT'):inspect_synthetic(archive({'Data/only_1.mat':mat()}))

    def test_11_lexicographic_fixed_pair_not_best(self):
        r=inspect_synthetic(archive({'Data/B_1.mat':mat(3),'Data/B_2.mat':mat(3),
                                     'Data/A_1.mat':mat(1),'Data/A_2.mat':mat(2)}))
        self.assertEqual(r['selected_repeat_stem'],'data/a')
        self.assertEqual(r['measurements'][1]['rms_direct_difference'],1.)

    def test_12_required_mat73_fields(self):
        with self.assertRaisesRegex(m.Refused,'FIELDS'):inspect_synthetic(archive({'Data/a_1.mat':mat(fields=False),'Data/a_2.mat':mat()}))

    def test_13_nonfinite_rejected(self):
        with self.assertRaisesRegex(m.Refused,'NONFINITE'):inspect_synthetic(archive({'Data/a_1.mat':mat(nonfinite=True),'Data/a_2.mat':mat()}))

    def test_14_shape_mismatch_rejected(self):
        with self.assertRaisesRegex(m.Refused,'DIMENSIONS'):inspect_synthetic(archive({'Data/a_1.mat':mat(shape=(3,2)),'Data/a_2.mat':mat()}))

    def test_15_request_single_expected_zenodo_host(self):
        class R:
            status=200
            def geturl(self):return m.SOURCE
            def read(self,n):self.limit=n;return b'ab'
            def __enter__(self):return self
            def __exit__(self,*a):pass
        class O:
            def __init__(self):self.calls=[]
            def open(self,req,timeout):self.calls.append((req,timeout));return R()
        o=O();self.assertEqual(m.download_once(o),b'ab')
        self.assertEqual(len(o.calls),1)
        self.assertEqual(o.calls[0][0].get_header('Accept'),'*/*')
        self.assertEqual(o.calls[0][0].full_url,m.SOURCE)
        self.assertEqual(o.calls[0][1],60)
        self.assertFalse(m._same_host('https://evil.example/'))

    def test_16_create_only_receipt_even_before_download(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'receipt.json';p.write_text('existing')
            with self.assertRaisesRegex(m.Refused,'CREATE_ONLY'):
                m.run(p)
            self.assertEqual(p.read_text(),'existing')

if __name__=='__main__':unittest.main()
