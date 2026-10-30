import copy, importlib.util, itertools, random, unittest
from fractions import Fraction
from pathlib import Path

spec=importlib.util.spec_from_file_location('next009_independent',Path(__file__).with_name('verify.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class VerificationTests(unittest.TestCase):
    def test_exact_common_reference_boundary(self):
        eps=Fraction(1)
        self.assertEqual(module.interval([Fraction(4)],eps,True),(Fraction(2),Fraction(2)))
        low,high=module.interval([Fraction(4)+Fraction(1,2**40)],eps,True)
        self.assertGreater(low,high)
        self.assertEqual(module.interval([Fraction(-2),Fraction(2)],eps,True),(Fraction(0),Fraction(0)))

    def test_common_reference_correlation_cannot_be_ignored(self):
        differences=[Fraction(-3),Fraction(3)]
        self.assertLessEqual(max(abs(v) for v in differences),4)
        low,high=module.interval(differences,Fraction(1),True)
        self.assertGreater(low,high)

    def test_unknown_offset_ambiguity_has_exact_witness(self):
        data=[[[Fraction(0),Fraction(5)],[Fraction(1),Fraction(6)]],[[Fraction(10),Fraction(25)],[Fraction(11),Fraction(26)]]]
        pair=module.pair_channels(data,Fraction(1))[0]
        self.assertEqual(pair['uncalibrated'],[False,False])
        self.assertEqual(pair['calibrated'],[True,True])
        witness=module.ambiguity_witness(data,pair,Fraction(1),['a','b'],['h1','h2'])
        self.assertTrue(witness['checked_equal'])

    def test_bitmask_control_matches_direct_enumeration(self):
        rng=random.Random(919)
        for count,outages in itertools.product(range(2,9),range(3)):
            pairs=[{'calibrated':[bool(rng.randrange(2)) for _ in range(count)]} for _ in range(13)]
            expected=None
            for size in range(outages+1,count+1):
                if any(module.viable(selected,pairs,outages) for selected in itertools.combinations(range(count),size)):
                    expected=size;break
            self.assertEqual(module.exact_minimum(pairs,count,outages)['size'],expected)

    def test_known_erasure_is_required_for_redundancy(self):
        pairs=[{'a':0,'b':1,'calibrated':[True,False,False]}]
        self.assertFalse(module.viable([0,1],pairs,1))
        checks=module.outage_checks([0,1],pairs,['a','b'],1)
        self.assertEqual(sum(not c['passed'] for c in checks),1)

    def test_true_source_with_exact_reference_errors(self):
        data=[[[Fraction(0),Fraction(0)],[Fraction(1),Fraction(1)]],[[Fraction(12),Fraction(12)],[Fraction(13),Fraction(13)]]]
        cases=module.protected_cases(data,['a','b'],['h1','h2'],[0,1],Fraction(1),1,8,'development-only-seed')
        self.assertEqual(len(cases),16)
        self.assertTrue(all(c['passed'] for c in cases))

if __name__=='__main__': unittest.main()
