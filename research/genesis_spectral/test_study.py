import copy, io, json, struct, tempfile, unittest, zipfile
from pathlib import Path
import numpy as np
import study

def asd(values=None,code=2,unit=1,version=b'ASD',reference=None):
    if values is None:values=np.linspace(.1,.9,1551)
    b=bytearray(484);b[:3]=version;b[186]=unit;b[199]=code
    struct.pack_into('<ff',b,191,850.,1.);struct.pack_into('<H',b,204,len(values))
    fmt='<'+('d' if code==2 else 'f')*len(values)
    out=bytes(b)+struct.pack(fmt,*values)
    if version in (b'as6',b'as7',b'as8'):
        r=bytearray(20);r[0]=reference is not None
        out+=bytes(r)
        if reference is not None:out+=struct.pack(fmt,*reference)
    return out

class ParserTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(study.label('nested/Bu5_PE_0X15_00003.asd'),('Bu5','PE',.15))
        self.assertEqual(study.label('_PET_100_00001.asd'),('','PET',100.))
        self.assertEqual(study.label('DIW__0_5.asd'),('DIW','',0.))
    def test_unknown_name(self):self.assertIsNone(study.label('anything.asd'))
    def test_double(self):
        w,y=study.decode_asd(asd());self.assertEqual(len(w),1551);np.testing.assert_allclose(y,np.linspace(.1,.9,1551))
    def test_single(self):
        w,y=study.decode_asd(asd(code=0));np.testing.assert_allclose(y,np.linspace(.1,.9,1551),rtol=1e-6)
    def test_reference_conversion(self):
        _,y=study.decode_asd(asd(unit=0,version=b'as7',reference=np.full(1551,2.)))
        np.testing.assert_allclose(y,np.linspace(.1,.9,1551)/2)
    def test_unknown_unit(self):
        with self.assertRaises(ValueError):study.decode_asd(asd(unit=8))
    def test_missing_reference(self):
        with self.assertRaises(ValueError):study.decode_asd(asd(unit=0))
    def test_zero_reference(self):
        with self.assertRaises(ValueError):study.decode_asd(asd(version=b'as7',reference=np.zeros(1551)))
    def test_truncated(self):
        with self.assertRaises(ValueError):study.decode_asd(asd()[:-10])
    def test_short(self):
        with self.assertRaises(ValueError):study.decode_asd(b'ASD')
    def test_nan(self):
        with self.assertRaises(ValueError):study.decode_asd(asd(values=[.1,float('nan')]))
    def test_nonmonotone_step(self):
        a=bytearray(asd());struct.pack_into('<f',a,195,-1.)
        with self.assertRaises(ValueError):study.decode_asd(bytes(a))
    def test_unknown_version(self):
        a=bytearray(asd());a[:3]=b'BAD'
        with self.assertRaises(ValueError):study.decode_asd(bytes(a))
    def test_bad_reference_size(self):
        with self.assertRaises(ValueError):study.decode_asd(asd(version=b'as7',reference=np.ones(1551))[:-8])

class BoundaryTests(unittest.TestCase):
    def test_band_average(self):
        wave=np.arange(850,2401);b=study.band_matrix(wave,[900],10)
        self.assertEqual(int((b[0]>0).sum()),21);self.assertAlmostEqual(float((wave@b.T)[0]),900.)
    def test_sparse_input_does_not_read_unselected(self):
        wave=np.arange(850,2401);b=study.band_matrix(wave,[900,1200],10);x=np.sin(wave);a=x@b.T
        x[(b.sum(axis=0)==0)]=1e8;np.testing.assert_array_equal(a,x@b.T)
    def test_band_rejects_outside(self):
        with self.assertRaises(ValueError):study.band_matrix(np.arange(850,900),[900],10)
    def test_band_rejects_unsorted(self):
        with self.assertRaises(ValueError):study.band_matrix([3,2,1],[2],1)
    def test_metrics_independent(self):
        m=study.metrics(['a','a','b'],['a','b','b'],['a','b']);self.assertAlmostEqual(m['balanced_accuracy'],.75)
    def test_unknown_prediction(self):
        with self.assertRaises(ValueError):study.metrics(['a'],['unknown'],['a'])
    def test_missing_class(self):
        with self.assertRaises(ValueError):study.metrics(['a'],['a'],['a','b'])
    def test_prediction_length(self):
        with self.assertRaises(ValueError):study.metrics(['a'],[],['a'])
    def test_refuses_other_download(self):
        with self.assertRaises(ValueError):study.fetch('https://example.org/foo','/tmp/no-write','x')
    def test_forward_selection_is_deterministic(self):
        x=np.array([[0,1,3],[1,0,3],[0,2,4],[1,1,4],[0,3,5],[1,2,5]],float)
        y=np.array(['a','b']*3);groups=np.array(['s1','s1','s2','s2','s3','s3'])
        a=study.forward_select(x,y,groups,2,['a','b']);b=study.forward_select(x,y,groups,2,['a','b'])
        self.assertEqual(a,b);self.assertIn(0,a[0]);self.assertEqual(a[2],15)
    def test_archive_grouping_does_not_multiply_samples(self):
        p={'train_substrates':['Bu5'],'validation_substrates':[],'test_substrates':[],'polymers':['PE'],'concentrations':[5.]}
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'r.zip'
            with zipfile.ZipFile(path,'w') as z:
                for i in range(3):z.writestr(f'Bu5_PE_5_{i}.asd',asd())
            w,x,m,info=study.load_means(path,p)
            self.assertEqual(len(m),1);self.assertEqual(m[0]['replicates'],3);self.assertEqual(info['included_replicates'],3)
    def test_missing_group_rejected(self):
        p={'train_substrates':['Bu5'],'validation_substrates':[],'test_substrates':[],'polymers':['PE'],'concentrations':[5.]}
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'r.zip'
            with zipfile.ZipFile(path,'w') as z:z.writestr('foo.txt','none')
            with self.assertRaises(ValueError):study.load_means(path,p)
    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'r.json';study.save(p,{'a':1})
            with self.assertRaises(FileExistsError):study.save(p,{'a':2})
    def test_no_nonfinite_json(self):
        with self.assertRaises(ValueError):study.digest({'x':float('nan')})

if __name__=='__main__':unittest.main()
