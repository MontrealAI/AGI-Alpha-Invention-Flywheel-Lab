import unittest,copy,json,tempfile
import numpy as np
from science import response,design_response,construct_process,produce,EXPANDED_GRAPHS,DESIGNS
from reference import measure_exact,process_exact,observer

class ScientificChecks(unittest.TestCase):
    def test_two_implementations(self):
        for r in ([.5,.1,0,0],[.6,0,.1,0],[.9,.1,.05,.2],[.2,.2,.2,.2]):
            for t in (.02,.2,2,20):
                for q in (0,.4,1):
                    np.testing.assert_allclose(response(r,t,q),measure_exact(r,'combined',t,q),rtol=1e-8,atol=1e-10)
    def test_conservation_and_nonnegative(self):
        for t in (0,.1,1,10,100):
            r=response([.8,.1,.2,.1],t,.3)
            self.assertAlmostEqual(float(sum(r)),1,places=12);self.assertGreaterEqual(min(r),-1e-12)
    def test_analytic_zero_rates(self):
        np.testing.assert_allclose(response([0,0,0,0],10,.2),[.8,.2,0],atol=1e-15)
    def test_process_two_implementations(self):
        for d in DESIGNS[::13]:
            y,s,_=design_response([.6,.1,.05,.03],d);ry,rs=process_exact([.6,.1,.05,.03],'combined',d)
            self.assertAlmostEqual(y,ry,8);self.assertAlmostEqual(s,rs,8)
    def test_graph_grammar(self):
        self.assertEqual(len(EXPANDED_GRAPHS),8);self.assertTrue(all(g[0] for g in EXPANDED_GRAPHS))
    def test_invalid_rates(self):
        with self.assertRaises(ValueError):response([-1,1,1,1],2)
    def test_high_noise_stops_without_costly_query(self):
        def forbidden(*args):raise AssertionError('No query permitted')
        r=produce(forbidden,arm='retained',retained={'prefix':[]},noise_bound=.1,budget=8)
        self.assertEqual(r['queries'],0);self.assertEqual(construct_process(r)['status'],'NO_DEPLOY')
    def test_budget_stop(self):
        obs,_=observer(922001,'combined',.001)
        r=produce(obs,arm='retained',retained={'prefix':[]},noise_bound=.001,budget=1)
        self.assertEqual(r['queries'],1);self.assertEqual(construct_process(r)['status'],'NO_DEPLOY')
    def test_bad_calibration(self):
        obs,_=observer(922002,'gain',.001)
        r=produce(obs,arm='ordinary',retained={'prefix':[]},noise_bound=.001,budget=8)
        self.assertEqual(r['status'],'UNRESOLVED_CALIBRATION')
    def test_no_result_without_k1(self):
        self.assertEqual(construct_process({'status':'UNRESOLVED','models':[]})['status'],'NO_DEPLOY')

if __name__=='__main__':unittest.main()
