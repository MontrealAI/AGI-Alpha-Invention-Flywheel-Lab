import unittest
import numpy as np

from experiments.norman006 import controls


class QualifiedControlsTests(unittest.TestCase):
    def data(self):
        values = np.arange(8000, dtype=float).reshape(8, 1000) / 10000
        return {'A': values, 'B': values[::-1] + 0.1, 'ctrl': np.ones_like(values) * 0.2,
                'AB': values * 0.3 + values[::-1] * 0.7,
                'pairs': np.asarray(['p%d' % i for i in range(8)]), 'genes': np.asarray(['g%d' % i for i in range(1000)]),
                'fit_indices': np.arange(6), 'calibration_indices': np.arange(6, 8)}

    def test_known_constant_features_reduce_to_correct_target_intercept(self):
        data = self.data()
        inputs = {key: data[key] for key in ('A', 'B', 'ctrl', 'pairs', 'genes')}
        for residual in (False, True):
            artifact = controls.fit_ridge(data, 1, residual)
            prediction = controls.predict_ridge(artifact, inputs)
            base = data['A'] + data['B'] - data['ctrl'] if residual else data['ctrl']
            expected = base + np.mean(data['AB'] - base, axis=0)
            np.testing.assert_allclose(prediction, expected, atol=1e-12)
            np.testing.assert_allclose(controls.predict_ridge(artifact, dict(inputs, A=inputs['B'], B=inputs['A'])), prediction, atol=1e-12)

    def test_matching_mean_and_residual_mean_have_distinct_registered_semantics(self):
        data = self.data()
        qualified = controls.qualify(data)
        inputs = {key: data[key] for key in ('A', 'B', 'ctrl', 'pairs', 'genes')}
        values = controls.predict_all(qualified, inputs)
        np.testing.assert_array_equal(values['matching_mean'], (data['A'] + data['B']) / 2)
        expected = data['A'] + data['B'] - data['ctrl'] + np.mean(data['AB']-(data['A']+data['B']-data['ctrl']), axis=0)
        np.testing.assert_allclose(values['residual_mean'], expected)
        self.assertEqual(len(qualified['qualification']['ridge_trials']), 18)
        with self.assertRaises(ValueError):
            controls.predict_all(qualified, data)


if __name__ == '__main__':
    unittest.main()
