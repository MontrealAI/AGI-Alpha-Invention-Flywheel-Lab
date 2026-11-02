import json, unittest
import numpy as np
from experiments.capability_transfer_20261102.instrument import Cell,Ladder,minimum_separating_probe

class InstrumentBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.cell=Cell(2,.02,.01,30,(0.,1.),(2.5,4.2)); self.pack=Ladder([self.cell]*4,[.002]*3)
    def test_invalid_state_rejected(self):
        for z,p,i in [(np.ones(5),np.zeros(4),8),(np.ones(4),np.zeros(3),8),(np.ones(4),np.zeros(4),float('nan')),(np.ones(4)*1.1,np.zeros(4),8)]:
            with self.subTest(z=z,p=p,i=i),self.assertRaises(ValueError): self.pack.currents(z,p,i)
    def test_ideal_identical_cells_share_current(self):
        pack=Ladder([self.cell]*4,[0,0,0]); current,voltage=pack.currents(np.ones(4),np.zeros(4),8)
        np.testing.assert_allclose(current,[2]*4,atol=1e-12); self.assertAlmostEqual(voltage,4.16)
    def test_no_load_ocv_difference_drives_balancing(self):
        current,_=self.pack.currents([1,.9,.9,.9],np.zeros(4),0)
        self.assertGreater(current[0],0); self.assertAlmostEqual(sum(current),0,places=12)
    def test_invalid_physical_parameters_rejected(self):
        for q,r,t in [(0,.02,30),(2,-.02,30),(2,.02,0)]:
            with self.assertRaises(ValueError): Cell(q,r,.01,t,(0.,1.),(2.5,4.2))
        with self.assertRaises(ValueError): Ladder([self.cell]*4,[-.1]*3)
    def test_probe_evidence_serializes_without_numpy_scalar_coercion(self):
        result=minimum_separating_probe([self.cell,self.cell]); json.dumps(result,allow_nan=False)
        self.assertIsNone(result['selected']); self.assertEqual(result['evaluated_probes'],21)

if __name__=='__main__': unittest.main()
