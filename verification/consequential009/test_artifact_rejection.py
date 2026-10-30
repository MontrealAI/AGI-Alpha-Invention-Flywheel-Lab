import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('frozen_complete_r2', Path(__file__).with_name('cohort_check_r2_preserved.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'evidence/consequential009/resources/analog-r2/artifacts'
PROTOCOL = '9a28e4202fecbe46769f82a20a8aeedb92020cdd2701a6d941b6694d5363d7ad'


class CompleteArtifactRejectionTests(unittest.TestCase):
    def corrupted(self, filename=None, edit=None):
        temporary = tempfile.TemporaryDirectory(dir=ROOT / 'evidence/consequential009/verifier', prefix='negative-artifact-')
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name)
        staged = output / 'source-root'
        shutil.copytree(ROOT / 'research/consequential009/analog', staged / 'research/consequential009/analog')
        target = staged / 'inventions/consequential009'
        target.mkdir(parents=True)
        for source in ['circuit.py', 'experiment.py']:
            shutil.copy2(ROOT / 'evidence/consequential009/source-r2' / source, target / source)
        directory = staged / 'artifacts'
        shutil.copytree(SOURCE, directory)
        if filename is not None:
            path = directory / filename
            value = json.loads(path.read_text())
            edit(value)
            path.write_text(json.dumps(value, indent=2) + '\n')
        report_sha = hashlib.sha256((directory / 'REPORT.json').read_bytes()).hexdigest()
        result = checker.run(staged, directory, PROTOCOL, report_sha, output / 'RECEIPT.json')
        self.assertEqual(result['accepted'], filename is None)
        return [c['name'] for c in result['checks'] if not c['passed']]

    def test_exact_archived_source_positive_control(self):
        self.assertEqual(self.corrupted(), [])

    def test_false_pruning_consequence_rejected(self):
        def edit(value):
            value['pruning_trace'][0]['removed'] = not value['pruning_trace'][0]['removed']
        failures = self.corrupted('primary-constructed.json', edit)
        self.assertTrue(any('reverse-delete consequence' in name for name in failures))

    def test_fabricated_pair_count_rejected(self):
        def edit(value):
            value['separated_pairs'] += 1
        failures = self.corrupted('primary-constructed.json', edit)
        self.assertTrue(any('coverage and abstentions' in name for name in failures))

    def test_modified_exact_response_rejected(self):
        def edit(value):
            first = next(iter(value['exact_responses']))
            value['exact_responses'][first][0][0] = '123456789'
        failures = self.corrupted('primary-constructed.json', edit)
        self.assertTrue(any('every exact response' in name for name in failures))

    def test_dropped_cohort_unit_rejected(self):
        failures = self.corrupted('primary-COHORT.json', lambda value: value['hypotheses'].pop())
        self.assertTrue(any('complete frozen cohort' in name for name in failures))

    def test_favorable_sensor_policy_substitution_rejected(self):
        def edit(value):
            value['policies']['input_admittance']['absolute_coordinate_error'] = '0'
        failures = self.corrupted('primary-constructed.json', edit)
        self.assertTrue(any('exact frozen uncertainty' in name for name in failures))


if __name__ == '__main__':
    unittest.main()
