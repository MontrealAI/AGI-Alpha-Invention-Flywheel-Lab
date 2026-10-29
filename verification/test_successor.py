import copy,importlib.util,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from campaign.successor import construct
from grid_screen import screen, exact_screen
import verify

def triangle(source=0.):
    return {'base_mva':100.,'buses':[1,2,3],'p_mw':[source,0.,-source],'branches':[{'id':i,'from_bus':a,'to_bus':b,'x':.1,'tap':1.,'shift_deg':0.,'rate_mw':100.,'status':1} for i,(a,b) in enumerate([(1,2),(2,3),(1,3)])]}

def independent(model):return {'contingencies':verify.reference(model)}

class SuccessorTests(unittest.TestCase):
    def assert_interval(self,actual,expected):
        self.assertIsNotNone(actual)
        for a,e in zip(actual,expected):self.assertAlmostEqual(a,e,places=6)
    def test_analytic_positive_triangle(self):
        for method in [screen,exact_screen,independent]:
            result=construct(triangle(),method)
            self.assert_interval(result['interval_mw'],[0.,100.])
            self.assertEqual(result['unknown_outages'],[])
            self.assertFalse(result['operationally_admissible'])
    def test_analytic_existing_transfer_headroom(self):
        for method in [screen,exact_screen,independent]:
            self.assert_interval(construct(triangle(60.),method)['interval_mw'],[0.,40.])
    def test_worsening_infeasible_transfer(self):
        for method in [screen,exact_screen,independent]:
            self.assertIsNone(construct(triangle(120.),method)['interval_mw'])
    def test_declared_upper_bound(self):
        self.assert_interval(construct(triangle(),independent,maximum_mw=25.)['interval_mw'],[0.,25.])
    def test_bridge_remains_unknown(self):
        model=triangle();model['branches'].pop()
        result=construct(model,independent)
        self.assertEqual(result['unknown_outages'],[0,1])
        self.assertFalse(result['operationally_admissible'])

if __name__=='__main__':unittest.main()
