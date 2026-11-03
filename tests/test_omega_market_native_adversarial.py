"""Reproduced public-result and plan-to-delivery binding failures.

Uses one disposable development/nonentry account; no evaluation seeds or
historical primary recovery material are touched.
"""
import copy
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import canonical, digest, strict_json
from omega import market, market_native, product
from tests.test_omega_market_product import receipts


ROOT = Path(__file__).resolve().parents[1]


class NativeReportAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='omega-native-report-development-')
        cls.output = Path(cls.tmp.name)/'run'
        market_native.register(cls.output, development=True, modes=('nonentry',),
            cases=(market.registered_cases(development=True)[0],))
        market_native.operate(cls.output)
        cls.registration_path = cls.output/'registration.json'
        cls.result_path = cls.output/'result.json'
        cls.registration_raw = cls.registration_path.read_bytes()
        cls.result_raw = cls.result_path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.registration_path.write_bytes(self.registration_raw)
        self.result_path.write_bytes(self.result_raw)

    def tearDown(self):
        self.registration_path.write_bytes(self.registration_raw)
        self.result_path.write_bytes(self.result_raw)

    def reject_report(self):
        with self.assertRaises(ValueError) as caught:
            market_native.audit(self.output)
        self.assertNotEqual(str(caught.exception), 'EXACT_REGISTERED_MARKET_SOURCE_REQUIRED')

    def test_unchanged_development_reference_replays(self):
        result = market_native.audit(self.output)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['accounts_replayed'], 1)
        self.assertFalse(result['original_primary_account_continued'])

    def test_top_level_cannot_claim_primary_objective_actual_profit_or_pooled_accounts(self):
        for field, wrong in [('primary_objective_established', True),
                             ('actual_complete_profit', 3_000_000_000),
                             ('pooled_profit', 3_000_000_000), ('account_count', 999)]:
            with self.subTest(field=field):
                report = strict_json(self.result_raw)
                report[field] = wrong
                self.result_path.write_bytes(canonical(report))
                self.reject_report()

    def test_removing_registered_arm_cannot_become_successful_zero_account_audit(self):
        registration = strict_json(self.registration_raw)
        registration['arms'] = []
        self.registration_path.write_bytes(canonical(registration))
        report = strict_json(self.result_raw)
        report.update(accounts=[], account_count=0, registration_sha256=digest(registration))
        self.result_path.write_bytes(canonical(report))
        self.reject_report()

    def test_duplicate_arm_is_not_a_second_independent_execution(self):
        registration = strict_json(self.registration_raw)
        registration['arms'].append(copy.deepcopy(registration['arms'][0]))
        self.registration_path.write_bytes(canonical(registration))
        report = strict_json(self.result_raw)
        report['accounts'].append(copy.deepcopy(report['accounts'][0]))
        report.update(account_count=2, registration_sha256=digest(registration))
        self.result_path.write_bytes(canonical(report))
        self.reject_report()


class PlanDeliveryBindingTests(unittest.TestCase):
    def test_process_promise_cannot_accept_water_request_in_native_mapping(self):
        # Isolate the plan->manifest boundary; policy replay has its own tests.
        choice = receipts()[0]
        item = {'product':'self_hosted', 'price_cents':14900, 'choice':choice,
                'costs_cents':{'delivery':100}, 'workflow':'process'}
        plan = {'trace':[{'quarter':0, 'bundles':[{'buyer_id':'authored-one-decision',
                'accepted':True, 'paid':True, 'items':[item]}]}]}
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='omega-plan-binding-') as td:
            manifest = product.prepare_manifest(ROOT, Path(td)/'products', hypothetical_rights=True,
                prices=[149_000_000], choices=[choice], job_costs=[{'delivery':1_000_000}],
                outcomes=[{'accepted':True, 'paid':True}])
            with self.assertRaisesRegex(ValueError, 'MISMATCH|BINDING|WORKFLOW|REQUEST'):
                market_native._check_manifest(ROOT, manifest, plan)


if __name__ == '__main__':
    unittest.main()
