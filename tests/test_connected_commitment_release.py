"""A packaged native adapter must include its executable dependency closure."""
import unittest
from pathlib import Path
from connected_enterprise.runner import source_paths
from campaign.genesis_commitment001.service import source_paths as service_paths

ROOT = Path(__file__).resolve().parents[1]


class CommitmentReleaseTest(unittest.TestCase):
    def test_entire_opt_in_service_and_tests_are_packaged(self):
        names = set(source_paths(ROOT))
        self.assertTrue(set(service_paths(ROOT)) <= names)
        for name in ('test_delivery.py', 'test_native.py', 'PROTOCOL.md', 'README.md'):
            self.assertIn('campaign/genesis_commitment001/' + name, names)
        self.assertIn('.github/workflows/genesis-commitment001.yml', names)


if __name__ == '__main__':
    unittest.main()
