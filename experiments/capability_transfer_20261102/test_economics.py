import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, audit_journal
from experiments.capability_transfer_20261102 import economics


class ResearchCostAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='capability-economics-tests-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.artifact = cls.directory / 'artifact.json'
        cls.artifact.write_text('{"scope":"EXPOSED_ACCOUNTING_TEST_ONLY","science_accepted":false}\n')
        envelope = {'schema': economics.SCHEMA, 'campaign_id': 'exposed-accounting-test',
                    'scope': 'SIMULATED_COST_ONLY', 'clock_start_utc': '2026-11-02T00:00:00Z',
                    'observation_end_hour': 8760, 'capital_levels_microUSD': [100_000*10**6, 10**9*10**6],
                    'working_reserve_microUSD': 1000*10**6,
                    'cost_items': [
                        {'id': 'first-cost', 'category': 'accounting_test', 'amount_microUSD': 1200*10**6,
                         'at_hour': 0, 'basis': 'Authored test amount, not a measured project cost.'},
                        {'id': 'refusal-cost', 'category': 'accounting_test', 'amount_microUSD': 120000*10**6,
                         'at_hour': 24, 'basis': 'Authored amount tests refusal in the 100k case.'}],
                    'unpriced_resources': ['Included assistant and scientific resources remain unmeasured.']}
        cls.envelope = cls.directory / 'envelope.json'
        cls.envelope.write_text(json.dumps(envelope) + '\n')
        registration = cls.directory / 'registration.json'
        commitment = economics.register(cls.artifact, cls.envelope, registration)
        cls.registration_sha256 = commitment['registration_sha256']
        reg = json.loads(registration.read_text())
        fixture = economics.ROOT / '_native_cost_fixtures' / digest(reg)
        if fixture.exists():
            raise AssertionError('Test fixture namespace unexpectedly already exists')
        cls.addClassCleanup(shutil.rmtree, fixture, True)
        result = economics.run(cls.artifact, registration, cls.registration_sha256, cls.directory / 'run')
        cls.public_path = Path(result['public_path'])
        cls.public = json.loads(cls.public_path.read_text())

    def assert_rejected(self, mutation, error):
        public = copy.deepcopy(self.public)
        mutation(public)
        path = self.directory / (self._testMethodName + '.json')
        path.write_text(json.dumps(public))
        with self.assertRaisesRegex(ValueError, error):
            economics.audit_public(self.artifact, path, self.registration_sha256)

    def test_positive_replay_and_reserve_refusal(self):
        result = economics.audit_public(self.artifact, self.public_path, self.registration_sha256)
        self.assertTrue(result['accepted'])
        low, high = self.public['cases']
        self.assertTrue(low['funding_refused'])
        self.assertEqual(low['snapshot']['cash'], 98800*10**6)
        self.assertEqual(low['snapshot']['workingCapital'], 1000*10**6)
        self.assertFalse(high['funding_refused'])
        self.assertEqual(high['incurred_cost_microUSD'], 121200*10**6)
        self.assertTrue(all(c['snapshot']['revenue'] == 0 for c in self.public['cases']))

    def test_profit_tamper(self):
        self.assert_rejected(lambda x: x['cases'][0]['snapshot'].update(profit=999999), 'RESEARCH_REPORT_RECONCILIATION_FAILED')

    def test_false_refusal(self):
        self.assert_rejected(lambda x: x['cases'][0].update(funding_refused=False), 'RESEARCH_COST_OR_REFUSAL_REPORT_CHANGED')

    def test_capital_pooling(self):
        self.assert_rejected(lambda x: x['cases'].append(copy.deepcopy(x['cases'][0])), 'CAPITAL_CASES_CHANGED_OR_POOLED')

    def test_unsupported_scientific_claim(self):
        self.assert_rejected(lambda x: x['claims'].update(qualified_scientific_capability=True), 'COST_ACCOUNTING_CANNOT_CERTIFY_SCIENCE_OR_COMMERCE')

    def test_unearned_expansion_claim(self):
        self.assert_rejected(lambda x: x['claims'].update(earned_funded_expansion=True), 'COST_ACCOUNTING_CANNOT_CERTIFY_SCIENCE_OR_COMMERCE')

    def test_false_case_identity(self):
        self.assert_rejected(lambda x: x['cases'][1].update(case_id=x['cases'][0]['case_id']), 'EXPLICIT_INDEPENDENT_CAPITAL_CASE_ID_REQUIRED')

    def test_unknown_model_cost_is_not_zero(self):
        self.assert_rejected(lambda x: x['execution_resources'].update(actual_inference_cost_usd=0), 'UNMEASURED_ENGINEERING_COSTS_CANNOT_BECOME_ZERO')

    def test_substituted_registration(self):
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_REGISTRATION_COMMITMENT_CHANGED'):
            economics.audit_public(self.artifact, self.public_path, '0'*64)

    def test_substituted_artifact(self):
        with self.assertRaisesRegex(ValueError, 'REGISTERED_RESEARCH_ARTIFACT_CHANGED'):
            economics.audit_public(self.envelope, self.public_path, self.registration_sha256)

    def test_genuine_native_account_with_lowered_reserve_is_rejected(self):
        public = copy.deepcopy(self.public)
        case = public['cases'][0]
        reg, manifest = public['registration'], public['manifest']
        env = reg['envelope']
        item = env['cost_items'][0]
        with JournalAccount(economics.ROOT, manifest, self.directory / 'alternate-private' / 'account.sqlite',
                            opening=case['opening_equity_microUSD'], working=0,
                            contract=env['campaign_id'] + '-' + case['case_id']) as account:
            work = {'registration_sha256': self.registration_sha256, 'artifact_sha256': reg['artifact_sha256'],
                    'economics_sha256': reg['economics_sha256'], 'item': item,
                    'scope': 'COSTED_RESEARCH_ONLY_NO_SERVICE_SALE'}
            account.spend(item['id'], 'research', item['amount_microUSD'], item['at_hour'], work, 0, allow_seed=True)
            case['record'] = account.export()
            case['snapshot'] = case['record']['snapshot']['summary']
            case['native_audit'] = audit_journal(case['record'], root=economics.ROOT, manifest=manifest)
            self.assertTrue(case['native_audit']['accepted'])
        path = self.directory / 'alternate-public.json'
        path.write_text(json.dumps(public))
        with self.assertRaisesRegex(ValueError, 'RESEARCH_REPORT_RECONCILIATION_FAILED'):
            economics.audit_public(self.artifact, path, self.registration_sha256)


if __name__ == '__main__':
    unittest.main()
