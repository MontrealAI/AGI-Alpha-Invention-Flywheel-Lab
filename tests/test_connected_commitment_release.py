"""A packaged native adapter must include its executable dependency closure."""
import unittest
import importlib.util
from pathlib import Path
from fnmatch import fnmatchcase
from connected_enterprise.finance import source_paths_for_manifest
from connected_enterprise.runner import source_paths
from campaign.genesis_commitment001.service import source_paths as service_paths

ROOT = Path(__file__).resolve().parents[1]


class CommitmentReleaseTest(unittest.TestCase):
    def test_release_gate_requires_dependency_and_test_only_changes(self):
        spec = importlib.util.spec_from_file_location('commitment_release', ROOT / 'scripts/release_connected014.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        workflow = 'genesis-commitment001.yml'
        paths = set(source_paths_for_manifest({'schema': 'genesis-commitment001/native-services/v1'}))
        paths.update(('requirements-commercial010.txt',
                      'tests/test_connected_commitment_release.py',
                      'tests/test_connected_commitment_independent.py',
                      'tests/test_connected_commitment_public_receipts.py',
                      'tests/test_connected_commitment_startup.py',
                      'tests/test_connected_commitment_registration.py'))
        triggers = [line.strip()[3:-1] for line in
                    (ROOT / '.github/workflows/genesis-commitment001.yml').read_text().splitlines()
                    if line.strip().startswith("- '")]
        for path in sorted(paths):
            with self.subTest(path=path):
                self.assertIn(workflow, release.applicable_workflows([path]))
                self.assertTrue(any(fnmatchcase(path, pattern) for pattern in triggers),
                                "Bound dependency would not trigger qualification: " + path)

    def test_push_and_pull_request_trigger_the_same_qualification_paths(self):
        workflow = (ROOT / '.github/workflows/genesis-commitment001.yml').read_text()
        pr, push = workflow.split('  push:', 1)
        push = push.split('  workflow_dispatch:', 1)[0]
        paths = lambda section: {line.strip() for line in section.splitlines()
                                 if line.strip().startswith('- ')}
        self.assertEqual(paths(pr), paths(push))

    def test_entire_opt_in_service_and_tests_are_packaged(self):
        names = set(source_paths(ROOT))
        self.assertTrue(set(service_paths(ROOT)) <= names)
        for name in ('test_delivery.py', 'test_native.py', 'PROTOCOL.md', 'README.md', 'RESULTS.md'):
            self.assertIn('campaign/genesis_commitment001/' + name, names)
        self.assertIn('.github/workflows/genesis-commitment001.yml', names)


if __name__ == '__main__':
    unittest.main()
