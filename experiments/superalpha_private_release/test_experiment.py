from fractions import Fraction
import unittest

from .experiment import exact_bound, ordinary_channel, split_channel, synthesize, verify


class ReleaseTests(unittest.TestCase):
    def test_single_family_changes_complete_output(self):
        # No attacker data or adaptive query is required for this witness.
        for n in (2, 4):
            exact = [[int(i == j) for j in range(n)] + [0] for i in range(n)]
            self.assertFalse(verify(exact, 57)['privacy_accepted'])
            self.assertEqual(verify(exact, 57)['worst_complete_accuracy'], 1)

    def test_lp_matches_separate_rational_bound_and_incumbent(self):
        for n in (2, 4):
            for ratio in (Fraction(11, 10), 2, 10, 19, 57):
                with self.subTest(n=n, ratio=ratio):
                    result = verify(synthesize(n, ratio), ratio)
                    self.assertTrue(result['privacy_accepted'])
                    self.assertAlmostEqual(result['worst_complete_accuracy'], float(exact_bound(n, ratio)))
                    self.assertAlmostEqual(result['worst_complete_accuracy'],
                                           verify(ordinary_channel(n, ratio), ratio)['worst_complete_accuracy'])

    def test_whole_package_changes_required_privacy_bound(self):
        self.assertEqual(exact_bound(2, 19), Fraction(19, 20))
        self.assertEqual(exact_bound(4, 57), Fraction(19, 20))
        self.assertLess(exact_bound(4, 19), Fraction(19, 20))

    def test_ordinary_joint_beats_factorized_but_not_a_discovery_gain(self):
        split = verify(split_channel(2), 2)
        joint = verify(ordinary_channel(4, 2), 2)
        self.assertTrue(split['privacy_accepted'])
        self.assertGreater(joint['worst_complete_accuracy'], split['worst_complete_accuracy'])

    def test_refusal_does_not_create_useful_output(self):
        result = verify([[0, 0, 1], [0, 0, 1]], 2)
        self.assertTrue(result['privacy_accepted'])
        self.assertEqual(result['worst_complete_accuracy'], 0)

    def test_checker_rejects_invalid_probabilities_and_normalization(self):
        for bad in ([[1, 0, 0], [0, float('nan'), 0]],
                    [[0.5, 0, 0], [0, 1, 0]],
                    [[2, -1, 0], [0, 1, 0]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                verify(bad, 2)

    def test_identity_is_not_a_private_channel(self):
        result = verify([[1, 0, 0], [0, 1, 0]], 2)
        self.assertEqual(result['max_privacy_violation'], 1)


if __name__ == '__main__':
    unittest.main()
