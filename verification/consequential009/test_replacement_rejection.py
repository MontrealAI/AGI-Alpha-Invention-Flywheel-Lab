import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('frozen_complete_r3', Path(__file__).with_name('cohort_check.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'evidence/consequential009/resources/analog-r3/artifacts'
PROTOCOL = '9a28e4202fecbe46769f82a20a8aeedb92020cdd2701a6d941b6694d5363d7ad'


class ReplacementRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = []

    @classmethod
    def tearDownClass(cls):
        destination = os.environ.get('AGI009_TEST_RECEIPT_PATH')
        if not destination:
            return
        report = {'schema': 'agi-alpha/consequential009-replacement-negative-controls/v1',
                  'source_report_sha256': hashlib.sha256((SOURCE / 'REPORT.json').read_bytes()).hexdigest(),
                  'checker_sha256': hashlib.sha256(Path(__file__).with_name('cohort_check.py').read_bytes()).hexdigest(),
                  'test_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'cases': cls.cases,
                  'scope': 'Unchanged frozen checker on exact r3 copies plus explicitly generated forgeries; not fresh scientific samples.'}
        output = Path(destination)
        with output.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')

    def corrupted(self, label, edit=None):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence/consequential009/verifier', prefix='replacement-negative-') as temporary:
            directory = Path(temporary) / 'artifacts'
            shutil.copytree(SOURCE, directory)
            path = directory / 'primary-constructed.json'
            original = json.loads(path.read_text())
            value = json.loads(path.read_text())
            if edit is not None:
                edit(value)
                path.write_text(json.dumps(value, indent=2) + '\n')
            report_sha = hashlib.sha256((directory / 'REPORT.json').read_bytes()).hexdigest()
            result = checker.run(ROOT, directory, PROTOCOL, report_sha, Path(temporary) / 'RECEIPT.json')
            failures = [c['name'] for c in result['checks'] if not c['passed']]
            self.cases.append({'label': label, 'accepted': result['accepted'], 'failed_checks': failures,
                               'original_replacement_trace': original['replacement_trace'],
                               'tested_replacement_trace': value['replacement_trace']})
            self.assertEqual(result['accepted'], edit is None)
            return failures

    def test_untouched_positive_control(self):
        self.assertEqual(self.corrupted('unmodified r3'), [])

    def test_false_replacement_coverage_rejected(self):
        def edit(value):
            value['replacement_trace']['evaluations'][0]['covers_prior_coverage'] = True
        self.assertTrue(any('every replacement coverage' in x for x in self.corrupted('false voltage fullcoverage', edit)))

    def test_missing_replacement_witness_rejected(self):
        def edit(value):
            value['replacement_trace']['evaluations'][0]['first_missing_pair'] = None
        self.assertTrue(any('every replacement coverage' in x for x in self.corrupted('suppressed unresolved pair', edit)))

    def test_unevaluated_selected_replacement_rejected(self):
        def edit(value):
            value['replacement_trace']['selected_action_id'] = 'v:mid1:100000'
        self.assertTrue(any('deterministic lower-cost replacement' in x for x in self.corrupted('selected unqualified voltageaction', edit)))


if __name__ == '__main__':
    unittest.main()
