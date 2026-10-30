import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def checker(name):
    spec = importlib.util.spec_from_file_location('summary_test_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COHORT = checker('cohort_check')
REFERENCE = checker('reference_check')


class CompleteSummaryIntegrityTests(unittest.TestCase):
    def evaluate(self, reference=False, changes=None, top_level=None):
        name = 'reference-r1' if reference else 'analog-r3'
        protocol_name = 'REFERENCE_PROTOCOL.json' if reference else 'PROTOCOL.json'
        module = REFERENCE if reference else COHORT
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence/consequential009/verifier', prefix='summary-negative-') as temporary:
            base = Path(temporary)
            directory = base / 'artifacts'
            shutil.copytree(ROOT / 'evidence/consequential009/resources' / name / 'artifacts', directory)
            path = directory / 'REPORT.json'
            report = json.loads(path.read_text())
            if changes:
                report['primary'].update(changes)
            if top_level:
                report.update(top_level)
            if changes or top_level:
                path.write_text(json.dumps(report, indent=2) + '\n')
            result = module.run(ROOT, directory, hashlib.sha256((ROOT / 'research/consequential009/analog' / protocol_name).read_bytes()).hexdigest(),
                                hashlib.sha256(path.read_bytes()).hexdigest(), base / 'ACCEPTANCE.json')
            if changes or top_level:
                self.assertFalse(result['accepted'])
            else:
                self.assertTrue(result['accepted'])
            return [c['name'] for c in result['checks'] if not c['passed']]

    def test_untouched_complete_native_cohort_summary_passes(self):
        self.assertEqual(self.evaluate(), [])

    def test_constructed_zero_count_and_boolean_count_rejected(self):
        for forged in [0, True]:
            with self.subTest(value=forged):
                failures = self.evaluate(changes={'constructed_actions': forged})
                self.assertIn('primary: report summary constructed_actions', failures)

    def test_constructed_zero_cost_rejected(self):
        self.assertIn('primary: report summary constructed_relative_acquisition_units', self.evaluate(changes={'constructed_relative_acquisition_units': 0}))

    def test_ordinary_zero_action_count_rejected(self):
        self.assertIn('primary: report summary ordinary_actions', self.evaluate(changes={'ordinary_actions': 0}))

    def test_false_complete_acceptance_rejected(self):
        self.assertIn('primary: report summary constructed_complete_acceptance', self.evaluate(changes={'constructed_complete_acceptance': False}))

    def test_old_greedy_zero_counts_and_costs_rejected(self):
        for field in ['old_greedy_actions', 'old_greedy_relative_acquisition_units']:
            with self.subTest(field=field):
                self.assertIn('primary: report summary ' + field, self.evaluate(changes={field: 0}))

    def test_physical_or_financial_claim_substitution_rejected(self):
        for field, value in [('physical_capability', 'VALIDATED'), ('monetary_cost', 'zero'), ('commerce', 'earned revenue')]:
            with self.subTest(field=field):
                self.assertIn('report preserves evidence scope ' + field, self.evaluate(top_level={field: value}))

    def test_untouched_complete_native_reference_summary_passes(self):
        self.assertEqual(self.evaluate(reference=True), [])

    def test_reference_zero_action_counts_and_false_completion_rejected(self):
        for field, value in [('selected_frequency_count', 0), ('ordinary_frequency_count', 0), ('conditional_complete_acceptance', False)]:
            with self.subTest(field=field):
                self.assertIn('primary: report summary ' + field, self.evaluate(reference=True, changes={field: value}))

    def test_reference_forged_drift_and_high_noise_acceptance_rejected(self):
        for field, value in [('gain_drift_decision', 'ACCEPT'), ('high_noise_decision', 'ACCEPT'), ('gain_drift_witnesses_identical', [False] * 4)]:
            with self.subTest(field=field):
                self.assertIn('primary: report summary ' + field, self.evaluate(reference=True, changes={field: value}))

    def test_reference_physical_and_commercial_claim_substitution_rejected(self):
        for field, value in [('physical_calibration', 'performed'), ('buyer_participation', 'established'), ('complete_monetary_cost', '0')]:
            with self.subTest(field=field):
                self.assertIn('report preserves evidence scope ' + field, self.evaluate(reference=True, top_level={field: value}))


if __name__ == '__main__':
    unittest.main()
