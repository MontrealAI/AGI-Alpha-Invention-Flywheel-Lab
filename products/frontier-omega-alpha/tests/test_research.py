from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from research.__main__ import BridgeError, observe, rank, read_logs, run_experiment, verify_experiment


class ResearchTests(unittest.TestCase):
    def test_observer_deduplicates_and_preserves_predecessor_after_outage(self):
        source = {'url': 'https://example.test/record', 'published': '2026-11-21', 'title': 'Synthetic fixture'}
        plan = {'sources': {'test': source}}
        sequence = iter(['a', 'a', 'b', None, 'a'])

        def fetch(url, hosts):
            self.assertEqual(url, source['url'])
            self.assertEqual(hosts, {'example.test'})
            value = next(sequence)
            if value is None:
                raise BridgeError('SOURCE_FAILURE', 'Synthetic failure')
            return {'sha256': sha256(value.encode()).hexdigest(), 'retrieved_at': '2026-11-22T17:00:00Z'}

        with TemporaryDirectory() as path:
            state = Path(path) / 'radar.sqlite'
            observations = [observe(plan, state, fetch)['test'] for _ in range(5)]
            with sqlite3.connect(state) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM observations').fetchone()[0], 3)
        self.assertEqual([item['status'] for item in observations],
                         ['first-observed', 'unchanged', 'bytes-changed', 'unavailable', 'bytes-changed'])
        self.assertEqual(observations[2]['sha256'], observations[4]['previous_sha256'])
        self.assertEqual(observations[2]['sha256'], observations[3]['previous_sha256'])

    def test_rank_uses_registered_weights_and_preserves_source_status(self):
        plan = {
            'settings': {'impact': 1, 'verification': 3},
            'opportunities': [
                {'id': 'larger', 'scores': {'impact': 5, 'verification': 1}, 'sources': ['a']},
                {'id': 'verified', 'scores': {'impact': 2, 'verification': 4}, 'sources': ['b']}
            ]
        }
        ranked = rank(plan, {'b': {'status': 'first-observed'}})
        self.assertEqual([item['id'] for item in ranked], ['verified', 'larger'])
        self.assertEqual(ranked[0]['rank_score'], 14)
        self.assertEqual(ranked[1]['source_status'], {'a': 'unobserved'})

    def test_stage_reuse_and_independent_replay_fail_closed_on_modified_input_or_report(self):
        negatives = ['missing_statement_match', 'failed_checker', 'disallowed_axiom',
                     'unregistered_theorem', 'duplicate_witness', 'wrong_declaration_count']
        allowed = ['propext', 'Classical.choice', 'Quot.sound']
        plan = {'allowed_axioms': allowed, 'negative_cases': negatives, 'stages': []}
        with TemporaryDirectory() as path:
            root = Path(path)
            for i, theorem in enumerate(['first_theorem', 'second_theorem']):
                entries = {
                    'audit': f"'{theorem}' depends on axioms: [propext, Classical.choice, Quot.sound]",
                    'statement': f'theorem {theorem} : True := True.intro',
                }
                for key in ('con-leche', 'con-ron'):
                    entries[key] = (f'{key}: accepted 15 declarations, 1 axioms justified by the solution '
                                    f'solution.ndjson (200 declarations accepted) (--verified)\n'
                                    f'{key}: theorem {theorem} justified by the solution\n\tExit status: 0\n')
                stage = {'id': f'test-{i}', 'theorems': [theorem], 'challenge_declarations': 15,
                         'solution_declarations': 200, 'files': {}}
                for kind, content in entries.items():
                    body = content.encode()
                    file = f'fixture-{i}-{kind}.txt'
                    (root / file).write_bytes(body)
                    stage['files'][kind] = {'file': file, 'bytes': len(body), 'sha256': sha256(body).hexdigest()}
                plan['stages'].append(stage)
            protocol = sha256(json.dumps(plan).encode()).hexdigest()
            report = run_experiment(plan, protocol, root, root / 'output')
            self.assertEqual(report['technical_verdict'], 'receipt-agreement')
            self.assertEqual(report['economic']['payment'], None)
            self.assertTrue((root / 'output' / 'retained-profile.json').is_file())
            self.assertTrue(verify_experiment(plan, protocol, root, report))
            report['stages'][0]['cases'][0]['reusable_index'] = False
            self.assertFalse(verify_experiment(plan, protocol, root, report))
            (root / 'fixture-1-con-ron.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'registered digest'):
                read_logs(plan['stages'][1], root)


if __name__ == '__main__':
    unittest.main()
