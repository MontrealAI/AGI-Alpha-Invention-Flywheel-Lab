import json
import tempfile
import unittest
from pathlib import Path
import lab


class LabTests(unittest.TestCase):
    def test_shortest_matches_oracle(self):
        for jobs in lab.DEVELOPMENT + lab.SUCCESSOR:
            self.assertEqual(lab.execute('shortest_first', jobs)['total_completion_time'], lab.oracle(jobs))

    def test_decisive_counterexample(self):
        row = lab.evaluate('longest_first', [(8, 1, 3)])[0]
        self.assertTrue(row['counterexample'])
        self.assertGreater(row['candidate'], row['exhaustive_optimum'])

    def test_reject_code(self):
        with self.assertRaises(ValueError):
            lab.execute('__import__("os")', [1])

    def test_bounds_and_types(self):
        for jobs in ([], [1]*8, [0], [101], [True], [1.2], ['3']):
            with self.assertRaises(ValueError):
                lab.execute('input_order', jobs)
        with self.assertRaises(ValueError):
            lab.evaluate('input_order', [[1]]*17)

    def test_unknown_not_zero(self):
        result = lab.economics(dict.fromkeys(lab.COST_NAMES))
        self.assertIsNone(result['complete_cost'])
        self.assertIsNone(result['profit'])
        self.assertEqual(result['verdict'], 'UNKNOWN')

    def test_invalid_costs(self):
        for value in (-1, float('nan'), True, 'free'):
            costs = dict.fromkeys(lab.COST_NAMES, 0)
            costs['discovery'] = value
            with self.assertRaises(ValueError):
                lab.economics(costs)
        with self.assertRaises(ValueError):
            lab.economics({})

    def test_retains_both_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'run'
            summary = lab.demo(directory)
            failed = json.loads((directory / 'longest_first.json').read_text())
            passed = json.loads((directory / 'shortest_first.json').read_text())
            self.assertEqual(failed['retention'], 'FAILED_TRANSFER')
            self.assertTrue(failed['counterexamples'])
            self.assertEqual(passed['successor']['observed_gain_over_strongest_control'], 0)
            self.assertEqual(summary['causally_helps_fresh_successor'], 'NOT_ESTABLISHED')
            self.assertEqual(summary['blue_sky_admission'], 'NOT_ADMITTED')
            self.assertEqual(summary['protocol_sha256'], lab.digest(json.loads((directory / 'protocol.json').read_text())))

    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'run'
            lab.demo(directory)
            original = (directory / 'longest_first.json').read_bytes()
            with self.assertRaises(FileExistsError):
                lab.demo(directory)
            self.assertEqual(original, (directory / 'longest_first.json').read_bytes())

    def test_input_size_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'large.json'
            path.write_bytes(b' ' * (lab.MAX_INPUT_BYTES + 1))
            with self.assertRaises(ValueError):
                lab.read_opportunity(path)

    def test_screen_not_admission(self):
        record = json.loads(Path('examples/opportunity.json').read_text())
        self.assertEqual(lab.screen(record)['admission'], 'NOT_ADMITTED')
        del record['evidence_gaps']
        with self.assertRaises(ValueError):
            lab.screen(record)


if __name__ == '__main__':
    unittest.main()
