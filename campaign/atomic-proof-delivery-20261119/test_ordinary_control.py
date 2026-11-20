import unittest
from ordinary_control import CASES, check, report, solve

class ConventionalControlTests(unittest.TestCase):
    def test_k3(self):
        self.assertTrue(check(CASES["K3"], solve(CASES["K3"])))
    def test_c4(self):
        self.assertTrue(check(CASES["C4"], solve(CASES["C4"])))
    def test_k4_no_three_coloring(self):
        self.assertIsNone(solve(CASES["K4"]))
    def test_wrong_edges(self):
        self.assertFalse(check([2, 0, 0], [0, 1, 2]))
    def test_self_loop(self):
        self.assertFalse(check([3, 1, 0], [0, 1, 2]))
    def test_invalid_color(self):
        self.assertFalse(check(CASES["K3"], [0, 1, 3]))
    def test_wrong_length(self):
        self.assertFalse(check(CASES["C4"], [0, 1]))
    def test_no_unearned_business_claim(self):
        self.assertEqual(report()["decision"], "HOLD_NO_DEPLOY_NO_BID")
        self.assertIsNone(report()["collected_commercial_revenue"])
    def test_all_declared_alternatives_present(self):
        self.assertEqual(len(report()["alternatives"]), 5)

if __name__ == "__main__":
    unittest.main()
