import hashlib
import json
import unittest

from research.lean_delta import EXPERIMENT, independent_reference
from research.scheduled import SOURCES, observe_releases, proposal


class ScheduledResearchTests(unittest.TestCase):
    def test_requires_matching_primary_version_and_records_observed_delta(self):
        latest_id = [1]
        suffix_id = [None]

        def retrieve(url, hosts):
            self.assertEqual(hosts, frozenset({'api.github.com'}))
            release_id = suffix_id[0] if '/tags/' in url and suffix_id[0] else latest_id[0]
            source = json.dumps({'id': release_id, 'tag_name': f'v1.{release_id}.0',
                                 'published_at': '2026-11-20T10:00:00Z', 'draft': False, 'prerelease': False})
            return {'text': source, 'sha256': hashlib.sha256(source.encode()).hexdigest(),
                    'retrieved_at': '2026-11-22T10:00:00Z'}

        initial = observe_releases({}, retrieve)
        self.assertEqual(set(initial), set(SOURCES))
        self.assertTrue(all(item['state'] == 'first_observation' for item in initial.values()))
        self.assertTrue(all(item['state'] == 'unchanged' for item in observe_releases(initial, retrieve).values()))
        latest_id[0] = 2
        updated = observe_releases(initial, retrieve)
        for item in updated.values():
            self.assertEqual(item['state'], 'published_version_changed')
            self.assertEqual(item['preceding']['tag'], 'v1.1.0')
            self.assertEqual(item['pinned']['tag'], 'v1.2.0')
            self.assertEqual(item['opportunity']['technical_verification'], 'pending')
            self.assertEqual(item['opportunity']['payment'], 'unproven')
        suffix_id[0] = 3
        stale = observe_releases(updated, retrieve)
        self.assertTrue(all(item['state'] == 'unavailable' and 'opportunity' not in item for item in stale.values()))

    def test_observed_lean_delta_has_a_registered_workload_and_independent_witness(self):
        candidate = proposal('leanprover/lean4', 'verification', {'tag': 'v4.35.0'}, {'tag': 'v4.36.0'})
        self.assertEqual(candidate['registered_experiment'], EXPERIMENT)
        self.assertEqual(candidate['technical_verification'], 'pending')
        reference = independent_reference()
        self.assertEqual(reference['one_argument_inputs'], 81)
        self.assertEqual(reference['two_argument_inputs'], 1296)
        self.assertEqual(reference['invalid_case_witness'], {'x': 0, 'mask': 0, 'value': 0})


if __name__ == '__main__':
    unittest.main()
