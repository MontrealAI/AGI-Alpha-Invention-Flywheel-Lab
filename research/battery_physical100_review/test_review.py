"""Bounded checks for this fixed historical review, not a new scientific test."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from research.battery_physical100_review import review


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.data = review.read(review.ROOT / 'evidence.json')

    def test_committed_result_recomputes(self):
        self.assertEqual(review.analyze(self.data), review.read(review.ROOT / 'result.json'))

    def test_failed_primary_and_discrimination_gap_remain(self):
        r = review.analyze(self.data)
        self.assertFalse(r['original_acceptance'])
        self.assertEqual(r['comparison'][0]['intervals_covering_observation'], 16)
        self.assertEqual(r['cycle1000_below_threshold'], 0)
        self.assertEqual(r['always_pass_correct_on_exposed_test_cells'], 9)
        self.assertEqual({x['cell'] for x in r['primary_interval_misses']}, {'A1003'})
        self.assertLess(r['comparison'][1]['mean_absolute_error_pp'], r['comparison'][0]['mean_absolute_error_pp'])

    def test_wrong_artifact_rejected(self):
        self.data['source']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_changed_prediction_rejected(self):
        self.data['sealed']['predictions'][0]['endpoints']['500']['prediction'] += 0.01
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_missing_cell_rejected(self):
        self.data['target_capacities'].pop()
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_duplicate_cell_rejected(self):
        self.data['target_capacities'][-1] = copy.deepcopy(self.data['target_capacities'][0])
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_missing_endpoint_rejected(self):
        del self.data['target_capacities'][0]['endpoint_capacities_ah']['1000']
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_missing_reference_cycle_rejected(self):
        self.data['target_capacities'][0]['reference_first10_capacities_ah'].pop()
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_bad_numbers_rejected(self):
        for value in (True, None, math.nan, math.inf, -math.inf, 0, -1):
            with self.subTest(value=value):
                data = copy.deepcopy(self.data)
                data['target_capacities'][0]['endpoint_capacities_ah']['1000'] = value
                with self.assertRaises(ValueError): review.analyze(data)

    def test_false_pass_rejected(self):
        self.data['original_acceptance'] = True
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_false_gate_rejected(self):
        self.data['original_acceptance_conditions']['all_18_endpoint_intervals_cover'] = True
        with self.assertRaises(ValueError): review.analyze(self.data)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.json'
            p.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError): review.read(p)

    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'input.json'
            p.write_text('{"a":NaN}')
            with self.assertRaises(ValueError): review.read(p)


if __name__ == '__main__':
    unittest.main()
