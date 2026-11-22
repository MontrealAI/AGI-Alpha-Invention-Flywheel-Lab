import unittest
import numpy as np
from .test_core import fixture
from .core import geometry
from .calibrated import compile_calibrated


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.I,self.M,self.V=fixture()
        rng=np.random.default_rng(27)
        _,_,C,_=geometry(self.I,self.M)
        r=rng.normal(size=C.shape[1]); r-=r@np.linalg.pinv(C)@C
        self.extra=r/np.linalg.norm(r)
        self.ref=self.V+np.outer(rng.normal(size=6),self.extra)
        # New specimen has fresh coefficients for both physical and extra modes.
        self.target=rng.normal(size=(6,6))@C+np.outer(rng.normal(size=6),self.extra)

    def test_new_specimen_coefficients_are_not_inherited(self):
        p=compile_calibrated(self.I,self.M,self.ref,7)
        recovered=p.predict(self.I,self.M,self.ref,self.target[:,p.selected])
        np.testing.assert_allclose(recovered,self.target,atol=1e-10)

    def test_current_only_ablation_misses_extra_mode(self):
        p=compile_calibrated(self.I,self.M,self.ref,7)
        b=compile_calibrated(self.I,self.M,self.ref,7,'current_only',p.selected)
        self.assertGreater(np.linalg.norm(b.predict(self.I,self.M,self.ref,self.target[:,b.selected])-self.target),.1)

    def test_calibration_bytes_bind_reuse(self):
        p=compile_calibrated(self.I,self.M,self.ref,7)
        changed=self.ref.copy(); changed[0,0]+=1e-10
        with self.assertRaises(ValueError):
            p.predict(self.I,self.M,changed,self.target[:,p.selected])

    def test_acquired_data_is_preserved_despite_model_error(self):
        p=compile_calibrated(self.I,self.M,self.ref,7)
        noise=np.random.default_rng(33).normal(size=(6,7))
        result=p.predict(self.I,self.M,self.ref,noise)
        np.testing.assert_array_equal(result[:,p.selected],noise)

    def test_no_extra_mode_is_not_manufactured(self):
        with self.assertRaises(ValueError): compile_calibrated(self.I,self.M,self.V,7)

    def test_target_specific_extra_mode_is_not_guaranteed(self):
        p=compile_calibrated(self.I,self.M,self.ref,7)
        novel=np.zeros_like(self.target); novel[0,-1]=10
        recovered=p.predict(self.I,self.M,self.ref,novel[:,p.selected])
        self.assertGreater(np.linalg.norm(recovered-novel),.1)

if __name__=='__main__': unittest.main()
