import importlib.util,tempfile,unittest
from fractions import Fraction
from pathlib import Path

spec=importlib.util.spec_from_file_location('independent_successor_verifier',Path(__file__).with_name('verify_successor.py'));v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class SuccessorTests(unittest.TestCase):
    def data(self):return [[[Fraction(0),Fraction(0),Fraction(0),Fraction(0)] for _ in range(24)],[[Fraction(10),Fraction(10),Fraction(30),Fraction(30)] for _ in range(24)]]
    def test_drift_changes_measurement_need_and_conventional_matches(self):
        data=self.data();old=v.relations(data,Fraction(1),Fraction(0));new=v.relations(data,Fraction(1),Fraction(5))
        self.assertTrue(v.check_plan([0,1],old,['a','b'],1)['accepted']);self.assertFalse(v.check_plan([0,1],new,['a','b'],1)['accepted']);self.assertTrue(v.check_plan([2,3],new,['a','b'],1)['accepted'])
        control=v.conventional(new,4,2);self.assertEqual(control['objective'],2);self.assertEqual(control['selected'],[2,3])
    def test_old_plan_identical_observation_witness(self):
        data=self.data();pairs=v.relations(data,Fraction(1),Fraction(5));failed=v.check_plan([0,1],pairs,['a','b'],1)['failed_pairs'][0]
        witness=v.ambiguity_witness(data,failed,[0,1],Fraction(1),Fraction(5),['s0','s1','s2','s3'],['a','b'])
        self.assertTrue(witness['exact_identical_raw_observations']);self.assertEqual(witness['remaining_sensor_count'],2)
    def test_exact_boundary_includes_compatible_equality(self):
        self.assertEqual(v.shift_interval([Fraction(14)],Fraction(1),Fraction(5)),(Fraction(2),Fraction(2)))
        low,high=v.shift_interval([Fraction(14)+Fraction(1,10**20)],Fraction(1),Fraction(5));self.assertGreater(low,high)
    def test_shared_reference_and_time_varying_drift(self):
        low,high=v.shift_interval([Fraction(-13),Fraction(13)],Fraction(1),Fraction(5));self.assertGreater(low,high)
    def test_fresh_observations_have_correct_source_with_revised_plan(self):
        data=self.data();worlds=v.worlds(data,Fraction(1),Fraction(5),4,'EXPOSED-TEST')
        for world in worlds:
            observations,choices=v.select_world(world,[2,3],Fraction(1),Fraction(5),data,['s0','s1','s2','s3']);self.assertEqual(choices,[world['source']]);self.assertLessEqual(len(observations['outages']),1)

    def test_source_binding_rejects_omitted_junction_and_simulator_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);network=root/'network.inp';raw=root/'raw.json';receipt=root/'receipt.json'
            network.write_bytes(b'[JUNCTIONS]\na 0\nb 0 ; retained junction\n[PIPES]\n')
            corpus={'nodes':['a','b'],'sources':['a','b'],'upstream_commit':'11eec7d5bf0a9367ffe04d75707918f0c0a890a1','simulator_sha256':'frozen-simulator','network_sha256':v.sha(network.read_bytes())}
            raw.write_bytes(v.canonical(corpus));simulation={'corpus_sha256':v.sha(v.canonical(corpus)),'warnings':[],'source_cases':2,'sensors':2,'times':24};receipt.write_bytes(v.canonical(simulation))
            freeze={'files':{'inventions/measurement009/inputs/libepanet22.so':'frozen-simulator'}}
            self.assertEqual(v.verify_source_binding(corpus,raw,network,receipt,freeze)['all_acquired_junctions'],['a','b'])
            omitted={**corpus,'nodes':['a'],'sources':['a']}
            with self.assertRaisesRegex(ValueError,'FULL_ACQUIRED_JUNCTION_COHORT'):v.verify_source_binding(omitted,raw,network,receipt,freeze)
            simulation['warnings']=[{'code':1}];receipt.write_bytes(v.canonical(simulation))
            with self.assertRaisesRegex(ValueError,'SIMULATION_RECEIPT_IDENTITY_OR_WARNINGS'):v.verify_source_binding(corpus,raw,network,receipt,freeze)

    def test_numerical_edition_rounds_exact_half_ties_to_even(self):
        spec=importlib.util.spec_from_file_location('numeric_checker_test',Path(__file__).with_name('numeric_edition_checker.py'));numeric=importlib.util.module_from_spec(spec);spec.loader.exec_module(numeric)
        for original,expected in [('0.0000000000005','0'),('0.0000000000015','0.000000000002'),('-0.0000000000015','-0.000000000002'),('100.00000000000006','100')]:
            self.assertEqual(numeric.rounded(original),Fraction(expected))

    def test_replay_seed_is_explicitly_exposed_and_domain_checked(self):
        self.assertEqual(v.case_seed('ab'*32),('ab'*32,'EXPOSED_REPRODUCTION_NO_NEW_CONFIRMATION'))
        with self.assertRaisesRegex(ValueError,'REPLAY_SEED_REQUIRES_64_LOWERCASE_HEX_CHARACTERS'):v.case_seed('EXPOSED-TEST')

if __name__=='__main__':unittest.main()
