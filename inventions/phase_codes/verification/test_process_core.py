import unittest
import numpy as np
import process_core as P


class Tests(unittest.TestCase):
    def test_ideal_and_global_phase_pass(self):
        for phase in [1,np.exp(.713j)]:
            def channel(v):
                w=phase*(P.U@v);return np.outer(w,w.conj())
            self.assertTrue(P.analyze(channel)['passed'])

    def test_wrong_phase_and_basis_preserving_dephasing_fail(self):
        self.assertFalse(P.analyze(lambda v:np.outer(v,v.conj()))['passed'])
        def dephase(v):
            w=P.U@v;return np.diag(np.abs(w)**2)
        r=P.analyze(dephase);self.assertFalse(r['passed'])
        self.assertAlmostEqual(r['entanglement_fidelity'],.25)

    def test_lossy_projection_and_hidden_renormalization_fail(self):
        a=np.diag([1,1,1,.1])@P.U
        def lossy(v):
            w=a@v;return np.outer(w,w.conj())
        self.assertFalse(P.analyze(lossy)['passed'])
        def postselected(v):
            w=a@v;w/=np.linalg.norm(w);return np.outer(w,w.conj())
        r=P.analyze(postselected);self.assertFalse(r['passed'])
        self.assertGreater(max(x['tomographic_linearity_error'] for x in r['extra_probes']),.01)

    def test_uncorrected_amplitude_damping_fails(self):
        gamma=.2;k0=np.kron(np.eye(2),np.diag([1,np.sqrt(1-gamma)]))
        k1=np.kron(np.eye(2),np.array([[0,np.sqrt(gamma)],[0,0]]))
        def channel(v):
            w=P.U@v;return sum(np.outer(k@w,(k@w).conj()) for k in [k0,k1])
        r=P.analyze(channel);self.assertFalse(r['passed'])
        self.assertLess(r['trace_preservation_error'],1e-12)


if __name__=='__main__':unittest.main(verbosity=2)
