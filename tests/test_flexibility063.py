import copy
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flexibility063.kernel import Infeasible,solve
from flexibility063.verify import digest,validate_request,verify
from flexibility063.service import prepare_manifest,load_contracts,write_delivery,delivery,rebind_prepared

ROOT=Path(__file__).resolve().parents[1]


class FlexibilityKernelTests(unittest.TestCase):
    def setUp(self):
        self.profiles=json.loads((ROOT/'flexibility063/profiles.json').read_text())

    def test_all_frozen_profiles_accepted_and_individual_threshold_fails(self):
        for request in self.profiles:
            with self.subTest(request=request['id']):
                with self.assertRaises(Infeasible):solve(request,'individual')
                pooled=solve(request)
                checked=verify(request,pooled)
                self.assertTrue(checked['accepted'],checked['errors'])
                self.assertEqual(sum(pooled['payments_microUSD'].values()),sum(solve(request,'conventional')['payments_microUSD'].values()))
                self.assertTrue(all(pooled['delivered_wh'][i]>=target for i,target in enumerate(request['target_wh'])))

    def test_exact_objective_matches_independent_finite_enumeration(self):
        request=copy.deepcopy(self.profiles[0]);request.update(target_wh=[5,0,0,0],derating_ppm=0,participant_margin_microUSD=1)
        request['devices']=request['devices'][:3]
        for i,device in enumerate(request['devices']):
            device.update(power_wh=[4]*4,baseline_wh=[4,4,0,0],required_wh=8,disutility_microUSD_per_wh=[1,2,4][i])
        oracle=min(sum(r*[1,2,4][i]+(1 if r else 0) for i,r in enumerate(reductions)) for reductions in itertools.product(range(5),repeat=3) if sum(reductions)>=5)
        artifact=solve(request)
        self.assertTrue(verify(request,artifact)['accepted'])
        self.assertEqual(sum(artifact['payments_microUSD'].values()),oracle)

    def test_wrong_energy_payment_derating_and_source_rejected(self):
        request=self.profiles[0];artifact=solve(request)
        cases=[]
        changed=copy.deepcopy(artifact);changed['dispatch_wh']['load-1'][2]+=1;cases.append(changed)
        changed=copy.deepcopy(artifact);changed['payments_microUSD']['load-1']=0;cases.append(changed)
        changed=copy.deepcopy(artifact);changed['delivered_wh'][0]+=1;cases.append(changed)
        changed=copy.deepcopy(artifact);changed['input_sha256']='0'*64;cases.append(changed)
        for changed in cases:self.assertFalse(verify(request,changed)['accepted'])

    def test_refusal_is_possible_for_low_budget_or_unavailable_shift(self):
        request=copy.deepcopy(self.profiles[0]);request['buyer_budget_microUSD']=1
        with self.assertRaises(Infeasible):solve(request)
        request=copy.deepcopy(self.profiles[0])
        for device in request['devices']:device['available']=[True,True,False,False]
        with self.assertRaises(Infeasible):solve(request)

    def test_successor_control_may_build_the_same_ordinary_solver(self):
        request=self.profiles[-1]
        inherited=solve(request);ordinary=solve(request,'conventional')
        self.assertTrue(verify(request,inherited)['accepted'])
        self.assertTrue(verify(request,ordinary)['accepted'])
        self.assertEqual(sum(inherited['payments_microUSD'].values()),sum(ordinary['payments_microUSD'].values()))

    def test_sparse_constraint_matrix_and_large_numeric_rejection(self):
        import flexibility063.kernel as kernel
        real=kernel.milp
        def inspect(*args,**kwargs):
            from scipy.sparse import issparse
            self.assertTrue(issparse(kwargs['constraints'].A))
            return real(*args,**kwargs)
        with patch.object(kernel,'milp',side_effect=inspect):solve(self.profiles[0])
        request=copy.deepcopy(self.profiles[0]);request['devices'][0]['power_wh'][0]=2**63
        with self.assertRaisesRegex(ValueError,'NUMERIC_RANGE'):solve(request)
        request=copy.deepcopy(self.profiles[0]);request['devices'][0]['disutility_microUSD_per_wh']=2**50
        with self.assertRaisesRegex(ValueError,'AGGREGATE_RANGE'):solve(request)

    def test_malformed_request_and_boolean_quantities_fail_closed(self):
        request=copy.deepcopy(self.profiles[0]);request['target_wh'][0]=True
        with self.assertRaises(ValueError):validate_request(request)
        self.assertFalse(verify({'bad':set()},None)['accepted'])

    def test_manifest_binds_frozen_request_and_actual_delivered_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'flexibility063') as directory:
            rel=Path(directory).relative_to(ROOT).as_posix()
            # Native delivery namespace is explicit; test files are removed.
            path='flexibility063/deliveries/kernel-test-'+Path(directory).name+'.json'
            target=ROOT/path
            try:
                manifest=prepare_manifest(ROOT,[{'id':'cycle-1','delivery_path':path}])
                self.assertIn('cycle-1',load_contracts(ROOT,manifest))
                artifact=solve(self.profiles[0]);receipt=write_delivery(ROOT,manifest,'cycle-1',artifact)
                self.assertTrue(receipt['accepted'])
                actions=[{'op':'offer','args':{'id':'order','job_id':'cycle-1'}},{'op':'event','args':{'id':'order','action':'prepare','artifact_sha256':digest(artifact)}}]
                rebind_prepared(ROOT,manifest,actions)
                changed=copy.deepcopy(artifact);changed['delivered_wh'][0]+=1
                target.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError,'ACTUAL_DELIVERY_HASH_CHANGED'):rebind_prepared(ROOT,manifest,actions)
                altered=copy.deepcopy(manifest);altered['jobs'][0]['request']['target_wh'][0]-=1
                with self.assertRaisesRegex(ValueError,'FROZEN_PROFILE_CHANGED'):load_contracts(ROOT,altered)
            finally:target.unlink(missing_ok=True)


if __name__=='__main__':unittest.main()
