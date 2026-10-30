import unittest
from fractions import Fraction
from research.next009.successor import derive_drift_program,drift_relations,compile_drift,DriftInterpreter
from research.next009.commerce.test_commerce import CommerceTests

class ReferenceExtensionTests(unittest.TestCase):
    def parent(self):
        return {'expression':{'op':'subtract','left':{'op':'read','sensor':'$sensor','time':'$time'},'right':{'op':'zero_reference','sensor':'$sensor'}},'noise_bound_pp':'1','max_sensor_erasures':1}
    def corpus(self):
        return {'nodes':['a','b','c','d'],'sources':['left','right'],'times_seconds':[0,1],'signal':[[[0,0,0,0],[0,0,0,0]],[[5,5,10,10],[5,5,10,10]]],'network':'authored-arithmetic-regression'}
    def test_drift_forces_different_information_without_weakening_bound(self):
        c,p=self.corpus(),self.parent()
        old,_=drift_relations(c,derive_drift_program(p,'0'));new,_=drift_relations(c,derive_drift_program(p,'1'))
        self.assertEqual(old.tolist(),[[1,1,1,1]]);self.assertEqual(new.tolist(),[[0,0,1,1]])
        plan=compile_drift(c,p,'1','exhaustive');self.assertEqual(plan['sensors'],['c','d'])
        obs={'known_zero_valid':True,'drift_bound_qualified':True,'drift_bound_pp':'1','outages':['c'],'reference':{'d':'8'},'trace':{'d':['11','7']}}
        self.assertEqual(DriftInterpreter(c,plan).diagnose(obs)['sources'],['left'])
        obs['known_zero_valid']=False
        self.assertEqual(DriftInterpreter(c,plan).diagnose(obs)['status'],'ASSUMPTIONS_UNQUALIFIED')
    def test_common_reference_is_not_independent_noise_per_timestamp(self):
        c=self.corpus();c['signal'][1]=[[-3,-3,-3,-3],[3,3,3,3]]
        m,_=drift_relations(c,derive_drift_program(self.parent(),'0'))
        self.assertEqual(m.tolist(),[[1,1,1,1]])
    def test_closed_error_bounds_preserve_exact_boundary_ambiguity(self):
        c=self.corpus();c['signal'][1]=[[4,4,4,4],[4,4,4,4]]
        m,_=drift_relations(c,derive_drift_program(self.parent(),'0'))
        self.assertEqual(m.tolist(),[[0,0,0,0]])
        self.assertEqual(compile_drift(c,self.parent(),'0','exhaustive')['status'],'INFEASIBLE')

if __name__=='__main__':unittest.main()
