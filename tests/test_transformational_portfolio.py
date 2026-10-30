"""Include scoped portfolio assertions in the repository's real test discovery."""
import unittest
from portfolio_scale import test_scale, test_transformational


def load_tests(loader, standard_tests, pattern):
    return unittest.TestSuite((loader.loadTestsFromModule(test_scale),
                               loader.loadTestsFromModule(test_transformational)))
