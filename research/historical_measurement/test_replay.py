"""Offline regressions. No downloads, model calls, or financial operations."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def read(relative):
    return json.loads((ROOT / relative).read_text())


class ReplayTests(unittest.TestCase):
    def test_clean_replay_exact_four_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'instrument'
            shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('images', '*.jpg', '__pycache__'))
            expected = read('expected_output_hashes.json')
            expected['v3_canopy/selected_measurements.csv'] = read('expected_selected_hash.json')['sha256']
            for relative in expected:
                (target / relative).unlink(missing_ok=True)
            subprocess.run([sys.executable, str(target / 'replay.py')], check=True, capture_output=True)
            for relative, digest in expected.items():
                self.assertEqual(hashlib.sha256((target / relative).read_bytes()).hexdigest(), digest)
            rows = list(csv.DictReader((target / 'v2/production_measurements_zoned.csv').read_text().splitlines()))
            self.assertEqual(len(rows), 676)
            for query, expected_counts in [('road', (71, 251, 16)), ('sidewalk', (71, 261, 6))]:
                self.assertEqual(tuple(sum(r['query'] == query and r['state'] == state for r in rows)
                                       for state in ['water_contact', 'no_water_contact', 'unknown']), expected_counts)
            canopy = list(csv.DictReader((target / 'v3_canopy/selected_measurements.csv').read_text().splitlines()))
            self.assertEqual(len(canopy), 61)
            self.assertEqual(sum(r['quality_flag'] == 'native_uncertain' for r in canopy), 11)
            self.assertEqual(sum(r['quality_flag'] == 'method_disagreement' for r in canopy), 6)

    def test_manifest_public_sources_unique(self):
        for name, count in [('manifest.json', 338), ('v3_canopy/manifest.json', 61)]:
            rows = read(name)
            self.assertEqual(len(rows), count)
            self.assertEqual(len({r['filename'] for r in rows}), count)
            for row in rows:
                self.assertTrue(row['url'].startswith('https://usgs-nims-images.s3.amazonaws.com/overlay/'))
                self.assertEqual(len(row['sha256']), 64)
                self.assertEqual(Path(row['filename']).name, row['filename'])

    def test_production_route_complete_not_duplicate(self):
        sys.path.insert(0, str(ROOT / 'v2'))
        from hybrid import route
        compiled = list(csv.DictReader((ROOT / 'v2/production_compiled.csv').read_text().splitlines()))
        responses = read('v2/production_native_responses.json')
        key = lambda row: (row['filename'], row['query'])
        self.assertEqual(len(responses), 372)
        self.assertEqual(len({key(r) for r in responses}), 372)
        self.assertEqual({key(r) for r in compiled if route(r) == 'semantic'}, {key(r) for r in responses})
        self.assertEqual(sum(route(r) == 'compiled' for r in compiled), 304)

    def test_canopy_native_abstentions_preserved(self):
        predictions = read('v3_canopy/native_predictions.json')
        self.assertEqual(len(predictions), 61)
        self.assertEqual(sum(r['state'] == 'unknown' for r in predictions), 11)
        self.assertEqual({r['filename'] for r in predictions}, {r['filename'] for r in read('v3_canopy/manifest.json')})

    def test_v1_failure_not_relabelled(self):
        result = read('independent_visual_validation/comparison.json')['results']
        self.assertFalse(result['road']['passes_predeclared_thresholds'])
        self.assertTrue(result['sidewalk']['passes_predeclared_thresholds'])
        self.assertFalse(all(r['passes_predeclared_thresholds'] for r in result.values()))

    def test_canopy_exclusions_and_confirmation_denominator(self):
        report = read('v3_canopy/independent_validation/confirmation/scoring_report.json')
        self.assertEqual((report['n_initial_manifest'], report['n_prediction_exposed_excluded'], report['n_strict_blind']), (35, 2, 33))
        self.assertEqual((report['n_joint_decisive'], report['correct']), (29, 28))

    def test_download_rejects_unapproved_host_without_network(self):
        import fetch_sources
        with patch.object(fetch_sources, 'urlopen') as network:
            with self.assertRaises(ValueError):
                fetch_sources.download('https://example.com/image.jpg', '0' * 64, ROOT / 'images/example.jpg')
            network.assert_not_called()

    def test_download_rejects_destination_escape(self):
        import fetch_sources
        with patch.object(fetch_sources, 'urlopen') as network:
            with self.assertRaises(ValueError):
                fetch_sources.download('https://usgs-nims-images.s3.amazonaws.com/a.jpg', '0' * 64, ROOT.parent / 'escape.jpg')
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
