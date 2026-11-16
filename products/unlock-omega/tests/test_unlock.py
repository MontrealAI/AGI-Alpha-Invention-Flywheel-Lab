"""Adversarial local tests use only audited checked-in sample programs."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from make_demo import make_demo
from unlock import read_project, verify


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = make_demo(Path(self.temp.name))
        # Keep most unit tests quick; separate full performance test below.
        cases = json.loads((self.project / 'heldout.json').read_text())
        for case in cases:
            if case['kind'] == 'performance':
                case['input']['values'] = case['input']['values'][:100]
            if case['kind'] == 'frontier':
                case['input']['values'] = case['input']['values'][:100]
                case['expected'] = 100 * 99 // 2
        (self.project / 'heldout.json').write_text(json.dumps(cases))
        (self.project / 'acceptance.json').write_text(json.dumps({'min_speedup': 1.01}))

    def test_bounded_compatibility(self):
        result = verify(self.project, self.project / 'candidate.py', 'local')
        self.assertEqual(result['status'], 'PASS', result)
        self.assertFalse(result['correctness']['mismatches'])

    def test_wrong_answer_rejected_even_when_fast(self):
        (self.project / 'candidate.py').write_text('def solve(payload):\n    return 0\n')
        result = verify(self.project, self.project / 'candidate.py', 'local')
        self.assertEqual(result['status'], 'HOLD')
        self.assertTrue(result['correctness']['mismatches'])

    def test_same_algorithm_rejected_on_speedup(self):
        shutil.copy2(self.project / 'reference.py', self.project / 'candidate.py')
        (self.project / 'acceptance.json').write_text(json.dumps({'min_speedup': 10.0}))
        result = verify(self.project, self.project / 'candidate.py', 'local')
        self.assertEqual(result['status'], 'HOLD')

    def test_forged_case_id_rejected(self):
        cases = json.loads((self.project / 'heldout.json').read_text())
        cases[1]['id'] = cases[0]['id']
        (self.project / 'heldout.json').write_text(json.dumps(cases))
        with self.assertRaises(ValueError):
            read_project(self.project)

    def test_frontier_oracle_is_mandatory(self):
        cases = json.loads((self.project / 'heldout.json').read_text())
        item = next(c for c in cases if c['kind'] == 'frontier')
        item['expected'] += 1
        (self.project / 'heldout.json').write_text(json.dumps(cases))
        result = verify(self.project, self.project / 'candidate.py', 'local')
        self.assertEqual(result['status'], 'HOLD')
        self.assertFalse(result['frontier']['passed'])

    def test_missed_frontier_deadline_is_hold(self):
        cases = json.loads((self.project / 'heldout.json').read_text())
        next(c for c in cases if c['kind'] == 'frontier')['max_ms'] = 0.00001
        (self.project / 'heldout.json').write_text(json.dumps(cases))
        result = verify(self.project, self.project / 'candidate.py', 'local')
        self.assertEqual(result['status'], 'HOLD')
        self.assertFalse(result['frontier']['passed'])

    def test_docker_absence_fails_closed(self):
        with patch('unlock.shutil.which', return_value=None):
            result = verify(self.project, self.project / 'candidate.py', 'docker')
        self.assertEqual(result['status'], 'HOLD')
        self.assertIn('Docker', result['execution_error'])


if __name__ == '__main__':
    unittest.main()

