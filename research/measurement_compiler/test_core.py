import unittest
import numpy as np
from scipy import linalg
from .core import compile_plan, decode, geometry


def fixture(symmetric=True):
    rng=np.random.default_rng(20261105)
    n=7
    I=np.zeros((n,n*(n-1)//2))
    p=0
    for a in range(n):
        for b in range(a+1,n):
            I[a,p]=1; I[b,p]=-1; p+=1
    M=np.zeros((n,n-1))
    for i in range(n-1): M[i,i]=1; M[i+1,i]=-1
    Q=linalg.helmert(n,full=False).T
    S=rng.normal(size=(n-1,n-1))
    if symmetric: S=S@S.T
    V=M.T@Q@S@Q.T@I
    return I,M,V


class BoundaryTests(unittest.TestCase):
    def test_reciprocal_physics_reproduces_unobserved_patterns(self):
        I,M,V=fixture()
        for mode in ['linear','reciprocal']:
            plan=compile_plan(I,M,6,mode)
            np.testing.assert_allclose(plan.predict(I,M,V[:,plan.selected]),V,atol=1e-11)

    def test_independent_potential_oracle(self):
        I,M,V=fixture()
        plan=compile_plan(I,M,6)
        Q=linalg.helmert(7,full=False).T
        # Independently solve for electrode potentials, then the current map.
        potentials=linalg.solve(M.T@Q,V[:,plan.selected])
        S=linalg.solve((Q.T@I[:,plan.selected]).T,potentials.T).T
        oracle=M.T@Q@S@Q.T@I
        np.testing.assert_allclose(plan.predict(I,M,V[:,plan.selected]),oracle,atol=1e-11)

    def test_wrong_reciprocity_can_fail_while_linear_succeeds(self):
        I,M,V=fixture(False)
        a=compile_plan(I,M,6,'linear'); b=compile_plan(I,M,6)
        np.testing.assert_allclose(a.predict(I,M,V[:,a.selected]),V,atol=1e-11)
        self.assertGreater(np.linalg.norm(b.predict(I,M,V[:,b.selected])-V),1)

    def test_geometry_change_invalidates_inheritance(self):
        I,M,V=fixture(); p=compile_plan(I,M,6)
        altered=I.copy(); altered[:,0]*=2
        with self.assertRaises(ValueError): p.predict(altered,M,V[:,p.selected])

    def test_unchanged_dimensions_do_not_bind_electrode_identity(self):
        I,M,V=fixture(); p=compile_plan(I,M,6)
        with self.assertRaises(ValueError): p.predict(I[::-1],M,V[:,p.selected])

    def test_rank_deficient_current_set_is_refused(self):
        I,M,V=fixture()
        with self.assertRaises(ValueError):
            compile_plan(I,M,6,order=[0,1,2,6,7,11])

    def test_partial_excitation_scope_does_not_claim_full_operator(self):
        I,M,V=fixture()
        # Only three independent sources; arbitrary additional electrode currents
        # remain outside the plan's contract even if physically available.
        ids=[0,1,2,6,7,11]
        restricted=I[:,ids]; values=V[:,ids]
        plan=compile_plan(restricted,M,3)
        np.testing.assert_allclose(plan.predict(restricted,M,values[:,plan.selected]),values,atol=1e-11)
        with self.assertRaises(ValueError): plan.predict(I,M,values[:,plan.selected])

    def test_unacquired_columns_cannot_be_passed_as_acquired(self):
        I,M,V=fixture(); p=compile_plan(I,M,6)
        with self.assertRaises(ValueError): p.predict(I,M,V)

    def test_vector_order_matches_explicit_pattern_concatenation(self):
        _,_,V=fixture()
        vector=np.concatenate([V[:,j] for j in range(V.shape[1])])
        np.testing.assert_array_equal(decode(vector,*V.shape),V)

    def test_invalid_geometry_and_voltage_fail_closed(self):
        I,M,V=fixture()
        bad=I.copy(); bad[0,0]=float('nan')
        with self.assertRaises(ValueError): geometry(bad,M)
        with self.assertRaises(ValueError): compile_plan(I,M,5)
        with self.assertRaises(ValueError): compile_plan(I,M,6,order=[0]*6)
        p=compile_plan(I,M,6)
        acquired=V[:,p.selected].copy(); acquired[0,0]=float('nan')
        with self.assertRaises(ValueError): p.predict(I,M,acquired)

if __name__=='__main__': unittest.main()
