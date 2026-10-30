import importlib.util
from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('independent_analog_check', Path(__file__).with_name('analog_check.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ExactCheckerTests(unittest.TestCase):
    def circuit(self, text):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'case.sp'
        path.write_text(text)
        return path

    def test_rc_exact_closed_form(self):
        path = self.circuit('Closed form RC\nvin in 0 dc 0 ac 1\nr1 in out 2\nc1 out 0 3\n.end\n')
        parts, source = check.parse(path)
        volts, y = check.solve(parts, source, F(5))
        self.assertEqual(volts['out'], (F(1, 901), F(-30, 901)))
        self.assertEqual(y, (F(450, 901), F(15, 901)))

    def test_rl_exact_closed_form(self):
        path = self.circuit('Closed form RL\nvin in 0 dc 0 ac 1\nr1 in out 3\nl1 out 0 2\n.end\n')
        parts, source = check.parse(path)
        volts, y = check.solve(parts, source, F(5))
        self.assertEqual(volts['out'], (F(100, 109), F(30, 109)))
        self.assertEqual(y, (F(3, 109), F(-10, 109)))

    def test_source_amplitude_cannot_be_mistaken_for_input_admittance(self):
        a = self.circuit('A\nvin in 0 dc 0 ac 1\nr1 in out 2\nc1 out 0 3\n.end\n')
        b = self.circuit('B\nvin in 0 dc 0 ac 2\nr1 in out 2\nc1 out 0 3\n.end\n')
        va, ya = check.solve(*check.parse(a), 5)
        vb, yb = check.solve(*check.parse(b), 5)
        self.assertEqual(ya, yb)
        self.assertEqual(vb['out'], check.times((F(2), F(0)), va['out']))

    def test_unknown_gain_exactly_confounds_impedance_scale(self):
        path = self.circuit('RC\nvin in 0 dc 0 ac 1\nr1 in out 2\nc1 out 0 3\n.end\n')
        result = check.inspect(path, ['1/2', '1', '2'], ['5', '500'], '0')
        self.assertTrue(result['all_calibrated_pairwise_satisfiable'])
        self.assertTrue(all(c['exact_gain_times_changed_current_equal'] for c in result['unknown_gain_counterexamples']))

    def test_rectangular_threshold_does_not_accept_touching_bounds(self):
        self.assertFalse(check.rectangles_disjoint((F(0), F(0)), (F(2), F(2)), '1'))
        self.assertTrue(check.rectangles_disjoint((F(0), F(0)), (F(201, 100), F(0)), '1'))

    def test_large_uncertainty_abstains_instead_of_faking_precision(self):
        path = self.circuit('RC\nvin in 0 dc 0 ac 1\nr1 in out 2\nc1 out 0 3\n.end\n')
        result = check.inspect(path, ['1', '2'], ['5'], '100')
        self.assertFalse(result['all_calibrated_pairwise_satisfiable'])

    def test_spice_M_and_MEG_units_differ(self):
        self.assertEqual(check.value('1M'), F(1, 1000))
        self.assertEqual(check.value('1MEG'), F(1000000))
        self.assertEqual(check.value('500p'), F(1, 2000000000))

    def test_active_elements_and_parameter_expressions_refuse(self):
        for element in ['d1 in 0 diode', 'r1 in 0 {rval}', '.param rval=1000', 'q1 in out 0 model']:
            path = self.circuit('Unsupported\nvin in 0 dc 0 ac 1\n' + element + '\n.end\n')
            with self.assertRaises(ValueError):
                check.parse(path)

    def test_singular_float_subnetwork_refuses(self):
        path = self.circuit('Floating RC\nvin in 0 dc 0 ac 1\nr1 a b 2\nc1 a b 3\n.end\n')
        with self.assertRaisesRegex(ValueError, 'SINGULAR_NODAL_MATRIX'):
            check.solve(*check.parse(path), 5)

    def test_protocol_cannot_have_duplicate_or_nonpositive_scale(self):
        path = self.circuit('RC\nvin in 0 dc 0 ac 1\nr1 in out 2\nc1 out 0 3\n.end\n')
        for scales in [['1', '1'], ['0', '1'], ['-1', '2']]:
            with self.assertRaises(ValueError):
                check.inspect(path, scales, ['5'], '0')


if __name__ == '__main__':
    unittest.main()
