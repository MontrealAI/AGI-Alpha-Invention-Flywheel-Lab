"""Mandatory isolated physics coverage without changing historical numerical pins."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

def validate(text):
    start = text.index('      - name: Mandatory isolated battery physics and native qualification')
    end = text.index('      - name: Source-matched tests and actual connected replay')
    isolated = text[start:end]
    required = (
        "BATTERY_QUALIFICATION_REQUIRED: '1'",
        'python -m venv "$RUNNER_TEMP/battery040-venv"',
        '-r requirements-battery040.txt -r requirements-commercial010.txt',
        "assert importlib.metadata.version(name) == version",
        "('test_battery_service040.py', 'test_pending_battery_native.py')",
        "assert suite.countTestCases() == 14",
        'result.wasSuccessful() and not result.skipped',
    )
    if not all(item in isolated for item in required) or 'continue-on-error' in isolated:
        raise ValueError('MANDATORY_ISOLATED_BATTERY_COVERAGE_REQUIRED')
    if 'python -m unittest discover -s tests -v' not in text[end:]:
        raise ValueError('FULL_GENERIC_DISCOVERY_REQUIRED')
    if '-r requirements-perturb006.txt -r requirements-battery040.txt' in text:
        raise ValueError('CONFLICTING_NUMERICAL_PINS')
    return True

class BatteryCIContract(unittest.TestCase):
    def setUp(self): self.text=(ROOT/'.github/workflows/campaign.yml').read_text()
    def test_required_isolated_coverage(self): self.assertTrue(validate(self.text))
    def test_missing_dependency_fails(self):
        with self.assertRaises(ValueError): validate(self.text.replace('-r requirements-battery040.txt',''))
    def test_skips_cannot_pass_mandatory_step(self):
        with self.assertRaises(ValueError): validate(self.text.replace(' and not result.skipped',''))
    def test_missing_inventory_fails(self):
        with self.assertRaises(ValueError): validate(self.text.replace('assert suite.countTestCases() == 14','assert True'))
    def test_generic_discovery_retained(self):
        with self.assertRaises(ValueError): validate(self.text.replace('python -m unittest discover -s tests -v','echo omitted'))
