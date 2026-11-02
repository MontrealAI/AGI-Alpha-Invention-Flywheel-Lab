"""Independent boundary tests; fixtures are not benchmark production receipts."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
from business_productivity065 import service
from business_productivity065.acceptance import verify, check_additional_quality95
from commercial.ledger import digest, load_jobs

ROOT=Path(__file__).resolve().parents[1]


def full_stock(instance):
    policies=[]; times=[]
    for product in instance['products']:
        name=product['product']; central=product['source_central_warehouse']
        total=sum(sum(p[name]) for p in instance['demand'].values())
        policies.append({'node':central,'product':name,'policy_type':'base_stock','parameters':{'base_stock_level':total}})
        times.append({'node':central,'product':name,'days':0})
        for regional in instance['regional_centers']:
            policies.append({'node':regional['node'],'product':name,'policy_type':'base_stock','parameters':{'base_stock_level':total}})
    return {'inventory_policy':policies,'cdc_service_time':times}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='test065-',dir=ROOT/'business_productivity065')
        self.folder=Path(self.temp.name); self.rows=[]
        for scenario in ('original','demand_plus20pct_ceil'):
            path=self.folder/(scenario+'.json')
            path.write_text(json.dumps(service.scenario_instance(ROOT,scenario)))
            self.rows.append({'id':scenario,'scenario':scenario,'instance_path':path.relative_to(ROOT).as_posix(),
                              'delivery_path':'business_productivity065/deliveries/test-'+scenario+'.json'})
        self.manifest=service.prepare_manifest(ROOT,self.rows)
    def tearDown(self):self.temp.cleanup()
    def test_two_distinct_precommitted_requests_reach_native_dispatch(self):
        jobs=load_jobs(ROOT,self.manifest)
        self.assertEqual(len(jobs),2)
        self.assertNotEqual(*[j['job']['artifact_sha256'] for j in jobs.values()])
    def test_scenario_only_changes_demand_with_exact_rounding(self):
        a=service.scenario_instance(ROOT,'original'); b=service.scenario_instance(ROOT,'demand_plus20pct_ceil')
        for node, products in a['demand'].items():
            for product, values in products.items():
                self.assertEqual(b['demand'][node][product],[(6*x+4)//5 for x in values])
        a.pop('demand');b.pop('demand');self.assertEqual(a,b)
    def test_both_independently_checked_and_wrong_request_refused(self):
        for scenario in ('original','demand_plus20pct_ceil'):
            instance=service.scenario_instance(ROOT,scenario); artifact=full_stock(instance)
            result=service.verify_delivery(ROOT,self.manifest,scenario,artifact)
            self.assertTrue(result['accepted'],result['errors'])
            result=verify(instance,artifact,expected_input_sha256='0'*64)
            self.assertFalse(result['accepted'])
    def test_mutations_refused(self):
        for mutate in ('scenario','hash','path','duplicate'):
            bad=copy.deepcopy(self.manifest)
            if mutate=='scenario':bad['jobs'][1]['request']['scenario']='original'
            elif mutate=='hash':bad['jobs'][0]['request']['instance_sha256']='0'*64
            elif mutate=='path':bad['jobs'][1]['delivery_path']='../unsafe.json'
            else:bad['jobs'].append(copy.deepcopy(bad['jobs'][0]))
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):service.load_contracts(ROOT,bad)
    def test_bad_delivery_rejected_without_write(self):
        instance=service.scenario_instance(ROOT,'original'); artifact=full_stock(instance)
        artifact['inventory_policy'].pop()
        result=service.verify_delivery(ROOT,self.manifest,'original',artifact)
        self.assertFalse(result['accepted'])
    def test_quality_floor_and_pair_count_are_decisive(self):
        counts={str(i):347 for i in range(48)}
        receipt={'accepted':True,'metrics':{'successful_anchor_counts_by_pair':counts}}
        self.assertTrue(check_additional_quality95(receipt)['accepted'])
        counts['0']=346
        self.assertFalse(check_additional_quality95(receipt)['accepted'])
        counts.pop('0')
        self.assertFalse(check_additional_quality95(receipt)['accepted'])
    def test_zero_stock_and_changed_source_refused(self):
        instance=service.scenario_instance(ROOT,'original');artifact=full_stock(instance)
        for row in artifact['inventory_policy']:row['parameters']['base_stock_level']=0
        self.assertFalse(service.verify_delivery(ROOT,self.manifest,'original',artifact)['accepted'])
        changed=copy.deepcopy(self.manifest);changed['source_hashes']['business_productivity065/acceptance.py']='0'*64
        with self.assertRaises(ValueError):service.load_contracts(ROOT,changed)
    def test_original_contract_rejects_modeled_input(self):
        from inventory061.independent_acceptance import verify as original_verify
        instance=service.scenario_instance(ROOT,'demand_plus20pct_ceil')
        self.assertFalse(original_verify(instance,full_stock(instance))['accepted'])

if __name__=='__main__':unittest.main()
