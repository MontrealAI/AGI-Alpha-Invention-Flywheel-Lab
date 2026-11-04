"""Sensitivity proofs and counterfactual redesign, not measured friction."""
import copy
from fractions import Fraction
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from research.genesis_surface.model import read, construct, digest
from research.genesis_surface.check import check
from research.genesis_surface.calibration import (
    box_obstruction, construct_robust, tolerance_requirement, relative_box, diagnose)
from research.genesis_surface.build import build

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / 'campaign/genesis-surface/REQUEST.json'


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = read(REQUEST)
        cls.c = construct(cls.s)

    def test_exact_box_obstruction(self):
        r = box_obstruction(self.s)
        self.assertTrue(r['infeasible_in_declared_box'])
        self.assertEqual(len(r['witnesses']), 3)
        for w in r['witnesses']:
            a, b = Fraction(w['bound_exact']), Fraction(w['target_exact'])
            self.assertTrue(a < b if w['side'] == 'lower' else a > b)

    def test_original_box_robust_solver_agrees(self):
        c = construct_robust(self.s)
        self.assertEqual(c['status'], 'INFEASIBLE_IN_DECLARED_MODEL')
        self.assertFalse(check(self.s, c)['accepted'])

    def test_zero_error_has_no_ratio_obstruction(self):
        s = relative_box(self.s, 0.)
        self.assertFalse(box_obstruction(s)['infeasible_in_declared_box'])

    def test_zero_error_robust_build_passes(self):
        s = relative_box(self.s, 0.)
        c = construct_robust(s)
        self.assertTrue(check(s, c)['declared_box_sensitivity_pass'])

    def test_counterfactual_redesign_is_executable(self):
        s = relative_box(self.s, .0025)
        c = construct_robust(s)
        v = check(s, c)
        self.assertTrue(v['accepted']); self.assertTrue(v['declared_box_sensitivity_pass'])
        self.assertEqual(v['contacts'], 37)
        self.assertNotEqual(c['contacts'], self.c['contacts'])
        self.assertFalse(v['physical_qualified'])

    def test_larger_error_not_narrated_as_pass(self):
        s = relative_box(self.s, .003)
        self.assertEqual(construct_robust(s)['status'], 'INFEASIBLE_IN_DECLARED_MODEL')

    def test_fixed_design_requirement_calculation(self):
        r = tolerance_requirement(self.s, self.c)
        self.assertAlmostEqual(r['maximum_uniform_relative_shear_error'], .001539608204472853, places=12)
        self.assertEqual(r['limiting_constraint']['quantity'], 'dynamic_N')
        self.assertEqual(r['limiting_constraint']['state_index'], 1)

    def test_fixed_design_below_threshold(self):
        e = tolerance_requirement(self.s, self.c)['maximum_uniform_relative_shear_error']
        s = relative_box(self.s, e * .99)
        c = copy.deepcopy(self.c); c['request_sha256'] = digest(s)
        self.assertTrue(check(s, c)['declared_box_sensitivity_pass'])

    def test_fixed_design_above_threshold(self):
        e = tolerance_requirement(self.s, self.c)['maximum_uniform_relative_shear_error']
        s = relative_box(self.s, e + .0001)
        c = copy.deepcopy(self.c); c['request_sha256'] = digest(s)
        self.assertFalse(check(s, c)['declared_box_sensitivity_pass'])

    def test_requirement_has_no_sample_count_claim(self):
        r = tolerance_requirement(self.s, self.c)
        self.assertIsNone(r['sample_size_recommendation'])
        self.assertFalse(r['physical_accuracy_established'])
        self.assertIn('systematic/model discrepancy', r['next_evidence'])

    def test_relative_box_is_explicitly_hypothetical(self):
        s = relative_box(self.s, .0025)
        self.assertTrue(s['source']['counterfactual_calibration'])
        self.assertEqual(s['source']['parent_request_sha256'], digest(self.s))
        self.assertIn('HYPOTHETICAL', s['source']['scope'])
        self.assertNotIn('counterfactual_calibration', self.s['source'])

    def test_relative_box_invalid_values(self):
        for e in (True, -1, 1, float('nan'), float('inf'), '0.01'):
            with self.subTest(e=e), self.assertRaises(ValueError):
                relative_box(self.s, e)

    def test_invalid_design_cannot_get_requirement(self):
        c = copy.deepcopy(self.c); c['contacts'][0]['count'] = 0
        with self.assertRaises(ValueError): tolerance_requirement(self.s, c)

    def test_infeasible_design_cannot_get_requirement(self):
        c = construct_robust(self.s)
        with self.assertRaises(ValueError): tolerance_requirement(self.s, c)

    def test_obstruction_not_physical_impossibility(self):
        r = box_obstruction(self.s)
        self.assertIn('NOT physical impossibility', r['scope'])

    def test_all_box_vertices_confirm_robust_design(self):
        # Independent extremal enumeration with *nominal* acceptance on every vertex.
        s = relative_box(self.s, .0025); c = construct_robust(s)
        for vertex in itertools.product((0, 1), repeat=2 * len(s['families'])):
            v = copy.deepcopy(s)
            for i, f in enumerate(v['families']):
                for j, key in enumerate(('static', 'dynamic')):
                    f[key + '_MPa'] = f[key + '_range_MPa'][vertex[2*i+j]]
            cc = copy.deepcopy(c); cc['request_sha256'] = digest(v)
            self.assertTrue(check(v, cc)['accepted'])

    def test_recorded_diagnosis_keeps_original_failure(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'design'; build(REQUEST, out)
            r = diagnose(out, .0025)
            self.assertTrue(r['box_obstruction']['infeasible_in_declared_box'])
            self.assertFalse(r['robust_check']['accepted'])
            self.assertTrue(r['hypothetical_calibration_comparison']['check']['accepted'])
            self.assertEqual(r['actual_physical_measurements'], 0)
            self.assertEqual(r['decision'], 'REQUIRE_NEW_CALIBRATION_AND_PHYSICAL_TRANSFER_EVIDENCE')


if __name__ == '__main__': unittest.main()
