"""Scope-aware metamorphic and adversarial tests for Ω Reality Probe 001."""
import copy
import unittest
from research.singularity_direction001 import experiment as engine, verify as checker


class RealityProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases={}
        cls.evidence={'schema':'montreal-ai/reality-probe-001/v2', 'stress':engine.STRESS, 'cases':[]}
        # Local/CI tests use the exact repository PGLIB sources.
        for n in ('14','30'):
            case=engine.parse_case(n)
            cls.cases[n]=case
            cls.evidence['cases'].append(engine.probe_case(case))

    def test_source_bound_and_scenarios_are_declared(self):
        for name,case in self.cases.items():
            self.assertEqual(case['source_git_blob_sha1'],engine.SOURCE[name][1])
            self.assertEqual(len(case['lines']),20 if name=='14' else 41)
        self.assertEqual(engine.STRESS,{'demand_multiplier':1.2,'thermal_rating_multiplier':0.75})
        self.assertEqual(engine.OUTAGES,{'14':4,'30':18})

    def test_independent_primal_dual_proof(self):
        report=checker.verify(self.evidence)
        self.assertEqual(report['status'],'PASS_SCOPED_DC_PROOF')
        a,b=report['results']
        self.assertAlmostEqual(a['gain_mw'],11.55573817,places=5)
        self.assertAlmostEqual(b['gain_mw'],28.68939554,places=5)
        self.assertLess(a['new_topology_primal_mw'],1e-5)
        self.assertGreater(b['new_topology_primal_mw'],40)

    def test_all_extra_openings_are_compared(self):
        for r in self.evidence['cases']:
            self.assertEqual(len(r['responses']),r['line_count']-1)
            self.assertEqual(r['selected_additional_switch'],min(r['responses'],key=lambda row:(row['unserved_mw'],row['switch']))['switch'])
            self.assertLess(r['switched']['unserved_mw'],r['baseline']['unserved_mw'])
            self.assertGreaterEqual(min(q['unserved_mw'] for q in r['responses']),-1e-5)
            self.assertEqual(len(r['responses']),19 if r['case']=='14' else 40)
            for q in r['responses']:
                self.assertIn('primal',q['witness'])
                self.assertIn('dual',q['witness'])

    def test_adversarial_tampering_is_rejected(self):
        edits=(lambda x:x['cases'][0]['switched']['primal'].__setitem__(0,9999),
               lambda x:x['cases'][0]['baseline']['dual']['equalities'].__setitem__(1,999),
               lambda x:x['cases'][1]['source'].__setitem__('sha256','invented'),
               lambda x:x['cases'][0]['responses'].pop(),
               lambda x:x['cases'][0].__setitem__('modeled_gain_mw',100000))
        for edit in edits:
            altered=copy.deepcopy(self.evidence);edit(altered)
            with self.subTest(edit=repr(edit)):
                with self.assertRaises((ValueError,KeyError,AssertionError)):
                    checker.verify(altered)

    def test_full_ranking_receipts_are_independently_certified(self):
        report=checker.verify(self.evidence)
        self.assertEqual([r['certified_alternative_switches'] for r in report['results']],
                         [19,40])
        for r in report['results']:
            self.assertEqual(r['ranking_certificate'],
                             'ALL_ONE_EXTRA_SWITCH_LP_OPTIMA_VERIFIED')
            self.assertLessEqual(r['maximum_candidate_objective_dual_gap_mw'],
                                 checker.TOL)

    def test_tampered_nonwinning_scalar_cannot_fake_best_choice(self):
        # Previously this forged inflation could pass: the other candidates'
        # scalar costs were trusted without their independent LP certificates.
        corrupted=copy.deepcopy(self.evidence)
        case=corrupted['cases'][0]
        row=next(x for x in case['responses']
                 if x['switch']!=case['selected_additional_switch'])
        row['unserved_mw'] += 10000.0
        with self.assertRaisesRegex(ValueError,'RESPONSE_WITNESS_MISMATCH'):
            checker.verify(corrupted)

    def test_tampered_nonwinning_primal_cannot_fake_global_ranking(self):
        corrupted=copy.deepcopy(self.evidence)
        case=corrupted['cases'][1]
        row=next(x for x in case['responses']
                 if x['switch']!=case['selected_additional_switch'])
        row['witness']['primal'][0] += 10.0
        with self.assertRaises(ValueError):
            checker.verify(corrupted)

    def test_tampered_nonwinning_dual_cannot_fake_global_ranking(self):
        corrupted=copy.deepcopy(self.evidence)
        case=corrupted['cases'][1]
        row=next(x for x in case['responses']
                 if x['switch']!=case['selected_additional_switch'])
        row['witness']['dual']['equalities'][1] += 10.0
        with self.assertRaises(ValueError):
            checker.verify(corrupted)

    def test_candidate_order_does_not_influence_certification(self):
        original=checker.verify(self.evidence)
        reordered=copy.deepcopy(self.evidence)
        reordered['cases'].reverse()
        for case in reordered['cases']:
            case['responses'].reverse()
        second=checker.verify(reordered)
        by_case=lambda results:{r['case']:r for r in results}
        self.assertEqual(by_case(original['results']),by_case(second['results']))

    def test_case_substitution_is_rejected(self):
        corrupted=copy.deepcopy(self.evidence)
        corrupted['cases'][1]=copy.deepcopy(corrupted['cases'][0])
        with self.assertRaisesRegex(ValueError,'CASE_COVERAGE'):
            checker.verify(corrupted)

    def test_negative_control_not_all_switches_help(self):
        case=self.cases['14']
        unchanged=engine.solve(case,{engine.OUTAGES['14']})['unserved_mw']
        bad_switch=next((r for r in self.evidence['cases'][0]['responses'] if r['unserved_mw']>=unchanged),None)
        self.assertIsNotNone(bad_switch)


if __name__=='__main__':unittest.main()
