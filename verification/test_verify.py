import copy, importlib.util, pathlib, unittest

s=importlib.util.spec_from_file_location('verify',pathlib.Path(__file__).with_name('verify.py'))
v=importlib.util.module_from_spec(s);s.loader.exec_module(v)

def triangle():
    return {'base_mva':100.,'buses':[1,2,3],'p_mw':[60.,-30.,-30.],'branches':[{'id':i,'from_bus':a,'to_bus':b,'x':.1,'tap':1.,'shift_deg':0.,'rate_mw':100.,'status':1} for i,(a,b) in enumerate([(1,2),(2,3),(1,3)])]}

class ReferenceTests(unittest.TestCase):
    def test_analytic_triangle_outage(self):
        rows=v.reference(triangle())
        self.assertEqual(rows[1]['status'],'CONNECTED')
        self.assertAlmostEqual(rows[1]['flows_mw'][0],30.)
        self.assertAlmostEqual(rows[1]['flows_mw'][1],0.)
        self.assertAlmostEqual(rows[1]['flows_mw'][2],30.)
        self.assertAlmostEqual(rows[0]['flows_mw'][2],60.)
        self.assertAlmostEqual(rows[0]['flows_mw'][1],-30.)
    def test_bridge_unknown(self):
        model=triangle();model['branches'].pop()
        self.assertTrue(all(r['status']=='ISLANDING_UNKNOWN' and r['flows_mw'] is None for r in v.reference(model)))
    def test_single_slack_declared(self):
        a=triangle();b=triangle();b['p_mw'][0]=900.
        self.assertEqual(v.reference(a),v.reference(b))
    def test_model_fingerprint_scope(self):
        a=triangle();b=copy.deepcopy(a);b['branches'][0]['tap']=.9
        self.assertNotEqual(v.model_sha(a),v.model_sha(b))
    def test_compare_rejects_false_normal(self):
        a=triangle();a['branches'].pop()
        actual={'contingencies':[{'outage':i,'status':'CONNECTED','flows_mw':[0.,0.],'overloads':[]} for i in range(2)]}
        self.assertTrue(v.compare(a,actual))
    def test_compare_rejects_zeroed_service(self):
        a=triangle();actual={'contingencies':[{'outage':i,'status':'CONNECTED','flows_mw':[0.,0.,0.],'overloads':[]} for i in range(3)]}
        self.assertTrue(v.compare(a,actual))

if __name__=='__main__':unittest.main()
