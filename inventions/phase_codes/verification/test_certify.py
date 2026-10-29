"""Independent exact reference and adversarial input checks; no builder candidate used."""
import copy,hashlib,itertools,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
import certify


def steane_pair():
    dual={0}
    for g in [0b1111000,0b1100110,0b1010101]:dual|={x^g for x in list(dual)}
    supports=[dual,{x^127 for x in dual}]
    states=[{(a<<7)|b for a in supports[i] for b in supports[j]} for i,j in itertools.product(range(2),repeat=2)]
    obj=dict(n=14,physical_weights=[0]*14,global_phase_exponent=0,
             logical_order=certify.LABELS,
             codewords=[dict(logical=label,probabilities={format(x,'014b'):'1/64' for x in sorted(s)}) for label,s in zip(certify.LABELS,states)])
    return obj,states


def direct_uniform_KL(states,n):
    """Independent signed overlap sum for every explicit Pauli; no moment/distance reduction."""
    ops=[(0,0,0)]
    for weight in [1,2]:
        for sites in itertools.combinations(range(n),weight):
            for letters in itertools.product('XYZ',repeat=weight):
                flip=zmask=ny=0
                for j,p in zip(sites,letters):
                    bit=1<<(n-1-j)
                    if p in 'XY':flip|=bit
                    if p in 'YZ':zmask|=bit
                    if p=='Y':ny+=1
                ops.append((flip,zmask,ny))
    for flip,zmask,ny in ops:
        matrix=[]
        for left in states:
            row=[]
            for right in states:
                total=sum((-1 if (x&zmask).bit_count()%2 else 1) for x in right if (x^flip) in left)
                row.append(total*(1j**ny))
            matrix.append(row)
        scalar=matrix[0][0]
        assert all(matrix[i][j]==(scalar if i==j else 0) for i in range(4) for j in range(4)), (flip,zmask,ny,matrix)
    return len(ops)


class Tests(unittest.TestCase):
    def test_known_distance3_control_and_direct_all_paulis(self):
        obj,states=steane_pair();r=certify.certify(json.dumps(obj))
        self.assertEqual(direct_uniform_KL(states,14),862)
        for key in ['unit_normalization','disjoint_supports','union_support_distance_at_least3','common_exact_Z_and_ZZ_moments']:
            self.assertTrue(r['checks'][key])
        self.assertFalse(r['checks']['physical_phase_is_fixed_logical_controlled_S'])
        self.assertEqual(r['status'],'NOT_CERTIFIED')
        self.assertFalse(r['non_Pauli_stabilizer_certified'])

    def test_unbalanced_but_normalized_distribution(self):
        obj,_=steane_pair();p=obj['codewords'][0]['probabilities'];a,b=list(p)[:2]
        p[a]='3/128';p[b]='1/128'
        r=certify.certify(json.dumps(obj))
        self.assertTrue(r['checks']['unit_normalization'])
        self.assertFalse(r['checks']['common_exact_Z_and_ZZ_moments'])

    def test_support_neighbour_is_not_certified(self):
        obj,_=steane_pair();p=obj['codewords'][0]['probabilities'];x=next(iter(p));v=p.pop(x)
        p[format(int(x,2)^1,'014b')]=v
        r=certify.certify(json.dumps(obj))
        self.assertFalse(r['checks']['union_support_distance_at_least3'])

    def test_overlap_and_norm_do_not_slip_through(self):
        obj,_=steane_pair();obj['codewords'][1]['probabilities']=copy.deepcopy(obj['codewords'][0]['probabilities'])
        self.assertFalse(certify.certify(json.dumps(obj))['checks']['disjoint_supports'])
        obj,_=steane_pair();p=obj['codewords'][0]['probabilities'];p[next(iter(p))]='1/32'
        self.assertFalse(certify.certify(json.dumps(obj))['checks']['unit_normalization'])

    def test_float_boolean_duplicate_and_target_overrides_rejected(self):
        obj,_=steane_pair();p=obj['codewords'][0]['probabilities'];p[next(iter(p))]=.015625
        with self.assertRaises(ValueError):certify.certify(json.dumps(obj))
        obj,_=steane_pair();obj['physical_weights'][0]=True
        with self.assertRaises(ValueError):certify.certify(json.dumps(obj))
        with self.assertRaises(ValueError):certify.load_candidate('{"n":14,"n":15}')
        obj,_=steane_pair();obj['logical_phase_exponents']=[0,0,0,0]
        with self.assertRaises(ValueError):certify.certify(json.dumps(obj))

    def test_input_identity_and_output_reuse(self):
        obj,_=steane_pair();raw=json.dumps(obj).encode();script=Path(certify.__file__)
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);c=d/'known_control.json';c.write_bytes(raw);o=d/'result.json'
            base=[sys.executable,str(script),str(c),'--output',str(o),'--expected-sha256']
            r=subprocess.run(base+['0'*64],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse(o.exists())
            r=subprocess.run(base+[hashlib.sha256(raw).hexdigest()],capture_output=True,text=True)
            self.assertEqual(r.returncode,1);saved=o.read_bytes()
            self.assertEqual(json.loads(saved)['status'],'NOT_CERTIFIED')
            r=subprocess.run(base+[hashlib.sha256(raw).hexdigest()],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertEqual(o.read_bytes(),saved)


if __name__=='__main__':unittest.main(verbosity=2)
