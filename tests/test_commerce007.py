import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.commerce007 import CATEGORIES, SCOPE, frontier, run


class CompatibilityCommerce007Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'verification').mkdir()
        (self.root / 'campaign/cycle-007').mkdir(parents=True)
        self.verifier = self.root / 'verification/mock007.py'
        self.verifier.write_text('MOCK_SOURCE_ONLY = True\n')
        self.market = self.root / 'campaign/cycle-007/ECONOMICS_SOURCES.json'
        self.market.write_text('{"mock_sources":true}\n')
        self.artifact = self.root / 'ARTIFACT.json'
        self.artifact.write_text('{"mock_compatibility_report":true}\n')
        self.acceptance_path = self.root / 'ACCEPTANCE.json'
        self.contract_path = self.root / 'CONTRACT.json'
        self.binding = {'artifact_sha256': self.sha(self.artifact), 'candidate_sha256': '1' * 64,
                        'technical_contract_sha256': '2' * 64, 'verifier_sha256': self.sha(self.verifier),
                        'verifier_path': 'verification/mock007.py', 'source_manifest_sha256': '3' * 64}
        self.acceptance = {'schema': 'agi-alpha/compatibility-acceptance007/v1', 'accepted': True, 'scope': SCOPE,
                           'artifact_sha256': self.binding['artifact_sha256'], 'candidate_sha256': '1' * 64,
                           'contract_sha256': '2' * 64, 'verifier_sha256': self.binding['verifier_sha256'],
                           'source_manifest_sha256': '3' * 64,
                           'tests': {'upstream_total': 9, 'upstream_passed': 9, 'upstream_skipped': 0,
                                     'upstream_source_unchanged': True, 'protected_checks_total': 4,
                                     'protected_checks_passed': 4}}
        self.contract = {'schema': 'agi-alpha/conditional-remediation-commercial007/v1', 'scope': SCOPE,
                         'binding': self.binding, 'cohort': ['one-prospective-migration'], 'horizon': 'one prospective migration',
                         'offering': {'description': 'TEST FIXTURE ONLY; not an actual accepted migration'},
                         'cost_intervals': {key: {'lower_microUSD': 0, 'upper_microUSD': None,
                                                   'basis': 'unknown; lower bound is not actual zero cost'} for key in CATEGORIES},
                         'illustrative_price_grid_microUSD': [0, 1_000_000],
                         'buyer_parameters': {'trust': None, 'switching': None, 'procurement': None,
                                              'dispute_cost': None, 'expected_useful_value': None},
                         'outside_options': ['free self-service', 'ordinary AI-native repair', 'non-entry'],
                         'market_source_manifest': {'path': 'campaign/cycle-007/ECONOMICS_SOURCES.json', 'sha256': self.sha(self.market)},
                         'commercial_admission': False, 'fixture_price_is_not_market_evidence': True}
        self.write(self.acceptance_path, self.acceptance)
        self.write(self.contract_path, self.contract)

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value, indent=2) + '\n')

    def execute(self, name='output'):
        return run(self.artifact, self.acceptance_path, self.contract_path, self.root / name,
                   expected_contract_sha256=self.sha(self.contract_path),
                   expected_acceptance_sha256=self.sha(self.acceptance_path), root=self.root)

    def test_source_bound_release_and_reversal_never_qualify_commercial_funds(self):
        result = self.execute()
        self.assertTrue(result['technical_accepted'])
        self.assertEqual(result['snapshots']['positive_functional_fixture_before_stress']['revenue'], 4_000_000)
        self.assertEqual(result['snapshots']['final_full_reversal_or_rejection']['revenue'], 0)
        self.assertEqual(result['commercial_decision']['qualified_simulated_earned_funds_microUSD'], 0)
        self.assertTrue(all(x['passed'] for x in result['checks']))
        self.assertEqual(json.loads((self.root / 'output/DELIVERED.json').read_text()), json.loads(self.artifact.read_text()))
        ids = [x['id'] for x in result['all_fixture_inputs']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {x['id'] for x in result['all_fixture_outcomes']})
        with self.assertRaises(FileExistsError):
            self.execute()

    def test_unknown_cost_and_zero_participation_are_not_positive_profit(self):
        report = frontier(self.contract)
        self.assertIsNone(report['complete_cost_upper_bound_microUSD'])
        self.assertEqual(set(report['unknown_categories']), set(CATEGORIES))
        self.assertTrue(all(x['complete_profit_lower_microUSD'] is None for x in report['scenarios']))
        self.assertTrue(any(x['paying_count'] == 0 for x in report['scenarios']))
        self.assertTrue(any(x['paying_count'] == 1 and x['refunded_count'] == 1 for x in report['scenarios']))

    def test_skipped_or_modified_tests_refuse_delivery_and_keep_zero_earnings(self):
        for key, value in [('upstream_skipped', 1), ('upstream_source_unchanged', False)]:
            self.acceptance['tests'][key] = value
            self.write(self.acceptance_path, self.acceptance)
            report = self.execute(key)
            self.assertFalse(report['technical_accepted'])
            self.assertFalse((self.root / key / 'DELIVERED.json').exists())
            self.assertEqual(report['snapshots']['final_full_reversal_or_rejection']['collections'], 0)
            self.acceptance['tests'][key] = 0 if key == 'upstream_skipped' else True

    def test_false_acceptance_has_no_positive_clearance(self):
        self.acceptance['accepted'] = False
        self.write(self.acceptance_path, self.acceptance)
        result = self.execute()
        self.assertFalse(result['technical_accepted'])
        self.assertNotIn('positive_functional_fixture_before_stress', result['snapshots'])

    def test_stale_receipt_or_changed_sources_refuse_before_exchange_effects(self):
        for name, target in [('artifact', self.artifact), ('verifier', self.verifier), ('market', self.market)]:
            original = target.read_bytes()
            target.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'CHANGED'):
                self.execute(name)
            self.assertFalse((self.root / name).exists())
            target.write_bytes(original)
        old_sha = self.sha(self.acceptance_path)
        self.acceptance['candidate_sha256'] = '9' * 64
        self.write(self.acceptance_path, self.acceptance)
        with self.assertRaisesRegex(ValueError, 'FROZEN_ACCEPTANCE_CHANGED'):
            run(self.artifact, self.acceptance_path, self.contract_path, self.root / 'receipt',
                expected_contract_sha256=self.sha(self.contract_path), expected_acceptance_sha256=old_sha,
                root=self.root)
        self.assertFalse((self.root / 'receipt').exists())

    def test_missing_cost_category_or_permissive_scope_is_rejected(self):
        value = copy.deepcopy(self.contract)
        del value['cost_intervals']['agent_inference']
        with self.assertRaisesRegex(ValueError, 'ALL_LIFECYCLE_COST'):
            frontier(value)
        self.contract['commercial_admission'] = True
        self.write(self.contract_path, self.contract)
        with self.assertRaisesRegex(ValueError, 'UNQUALIFIED_COMMERCIAL_SCOPE'):
            self.execute()


if __name__ == '__main__':
    unittest.main()
