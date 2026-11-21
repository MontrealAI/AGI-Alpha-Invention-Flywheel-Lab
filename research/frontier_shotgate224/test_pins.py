"""Owner-source digest guard: fail rather than quietly re-score a changed instrument."""
from pathlib import Path
import hashlib
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / "research" / "frontier_qec_transfer"

EXPECTED = {
    "recovery.py": "f8638af7b2532f8c2161fefe2169bb91788c9fc3a5e3321cf7a05ec717f7c134",
    "noise_experiment.py": "6afa2b999e810e8873ee1ed9de4ca09ddb06b80cfe2c37d269ab798e7c09679b",
}

class PinnedSourceTests(unittest.TestCase):
    def test_exact_existing_recovery_and_successor(self):
        for path, expected in EXPECTED.items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((SOURCE / path).read_bytes()).hexdigest(), expected)

if __name__ == "__main__":
    unittest.main()
