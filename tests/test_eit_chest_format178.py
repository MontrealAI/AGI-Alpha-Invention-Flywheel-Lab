"""EIT178 frozen header-only classifier controls, no public network."""
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from research import eit_chest_format178 as d
from research import eit_chest177 as p

def zipped(a,b):
    out=BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('Data/Original_1.mat',a)
        z.writestr('Data/Original_2.mat',b)
    return out.getvalue()

def local_diagnose(raw):
    with patch.object(p,'SIZE',len(raw)),patch.object(p,'MD5',hashlib.md5(raw).hexdigest()):
        return d.diagnose(raw)

class Header178(unittest.TestCase):
    def test_01_matlab5_header(self):
        self.assertEqual(d.classify(b'MATLAB 5.0 MAT-file, Created...'),'MATLAB5_HEADER')

    def test_02_hdf5_at_zero(self):
        self.assertEqual(d.classify(d.HDF5+b'data'),'HDF5_SIGNATURE')

    def test_03_hdf5_at_known_userblock_offset(self):
        for at in (512,1024,2048):
            self.assertEqual(d.classify(bytes(at)+d.HDF5),'HDF5_SIGNATURE')

    def test_04_other_header_not_silently_accepted(self):
        self.assertEqual(d.classify(b'not mat data'), 'UNIDENTIFIED_HEADER')
        self.assertEqual(d.classify(bytes(256)+d.HDF5), 'UNIDENTIFIED_HEADER')

    def test_05_selected_original_pair_and_immutable_failure(self):
        raw=zipped(b'MATLAB 5.0 MAT-file',d.HDF5)
        with patch.object(p,'_mat',side_effect=AssertionError('must never inspect numeric arrays')):
            r=local_diagnose(raw)
        self.assertEqual(r['status'],'FORMAT_DIAGNOSIS_RECORDED')
        self.assertEqual(r['original_eit177_result'],'FAILED_INVALID_MAT73_MEMBER')
        self.assertEqual([x['header_class'] for x in r['members']],['MATLAB5_HEADER','HDF5_SIGNATURE'])
        self.assertFalse(r['numerical_measurements_tested'])

    def test_06_wrong_publisher_length_rejected(self):
        with self.assertRaisesRegex(p.Refused,'SIZE'): d.diagnose(b'bad')

    def test_07_publisher_md5_mismatch_rejected(self):
        raw=zipped(b'first',b'second')
        with patch.object(p,'SIZE',len(raw)):
            with self.assertRaisesRegex(p.Refused,'MD5'):d.diagnose(raw)

    def test_08_no_selected_repeat_rejected(self):
        out=BytesIO()
        with ZipFile(out,'w') as z:z.writestr('Data/Only_1.mat',b'x')
        with self.assertRaisesRegex(p.Refused,'NO_EXACT'):local_diagnose(out.getvalue())

    def test_09_no_overwrite_existing_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'out.json'
            file.write_text('preserve')
            with self.assertRaisesRegex(p.Refused,'CREATE_ONLY'):d.run(file)
            self.assertEqual(file.read_text(),'preserve')

    def test_10_one_host_one_request_preserved(self):
        self.assertEqual(p.SOURCE,'https://zenodo.org/api/records/24120439/files/AgarChestPhantom.zip/content')
        self.assertFalse(p._same_host('http://zenodo.org/anything'))
        self.assertFalse(p._same_host('https://notzenodo.org/anything'))
        class Response:
            status=200
            def geturl(self):return p.SOURCE
            def read(self,n):self.max=n;return b'bytes'
            def __enter__(self):return self
            def __exit__(self,*a):pass
        class One:
            def __init__(self):self.requests=[]
            def open(self,request,timeout):self.requests.append((request,timeout));return Response()
        o=One()
        self.assertEqual(p.download_once(o),b'bytes')
        self.assertEqual(len(o.requests),1)
        self.assertEqual(o.requests[0][0].get_header('Accept'),'*/*')
        self.assertEqual(o.requests[0][1],60)

if __name__=='__main__':unittest.main()
