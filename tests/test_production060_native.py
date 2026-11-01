"""Real public plans pass through funded native execution and public replay."""
import copy
from dataclasses import asdict
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import canonical, digest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import SOURCE_PATHS, _audit_journal
from production060 import service
from production060.dispatch import DispatchConfig, solve
from production060.native import BusinessAccount, OPENING, audit_export

ROOT = Path(__file__).resolve().parents[1]
DAYS = ('cdp_o5_01s', 'cdp_o5_02s')


class Production060NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='production060-native-')
        self.root = Path(self.temp.name) / 'source'
        names = set(SOURCE_PATHS) | set(service.source_paths(ROOT))
        names.add('production060/data/resources.json')
        names.update('production060/data/days/' + day + '.json' for day in DAYS)
        for name in sorted(names):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.config = DispatchConfig(time_limit_s=0)
        self.manifest = service.prepare_manifest(self.root, [
            {'id': day, 'instance_path': 'production060/data/days/' + day + '.json',
             'resources_path': 'production060/data/resources.json',
             'delivery_path': 'production060/deliveries/native-test/' + day + '.json',
             'mode': 'nearest', 'config': asdict(self.config)} for day in DAYS])
        self.path = Path(self.temp.name) / 'native.sqlite'
        self.account = BusinessAccount(self.root, self.manifest, self.path)

    def tearDown(self):
        self.account.close()
        self.temp.cleanup()

    def produce(self, index=0):
        return solve(service.read_json(self.root, 'production060/data/resources.json'),
                     service.read_json(self.root, 'production060/data/days/' + DAYS[index] + '.json'),
                     mode='nearest', config=self.config)

    def fund(self, index=0, day=1):
        order = 'native-test-' + str(index)
        terms = prospective_terms(order, 200_000_000, day + 9, day + 2,
                                  residual=2_000_000, fee=200_000)
        self.account.begin_order(DAYS[index], order, 'one-conditional-operator',
                                 200_000_000, 500_000_000, day, day + 5, terms)
        return order

    def test_funded_actual_output_and_two_distinct_requests_replay(self):
        self.assertEqual(self.account.snapshot()['summary']['cash'], OPENING)
        setup = self.account.spend('native-test-setup', 'instrument_setup', 100_000_000,
                                   0, {'purpose': 'native funded public benchmark test'},
                                   allow_seed=True)
        self.assertEqual(setup['funding'], 'SEED')
        for index in range(2):
            day = 1 + index * 12
            order = self.fund(index, day)
            cost = self.account.spend('native-test-production-' + str(index), 'production',
                                      2_000_000, day,
                                      {'public_request': DAYS[index]},
                                      expected_net=198_000_000, allow_seed=True)
            self.assertIsNotNone(cost)
            artifact = self.produce(index)  # Construct after native payment.
            receipt = self.account.complete_order(order, DAYS[index], artifact, day + 1)
            self.assertTrue(receipt['accepted'], receipt['errors'])
            self.account.release(order, day + 2)
            self.account.advance(day + 10)
        record = self.account.export()
        self.assertEqual(record['ledger']['summary']['revenue'], 400_000_000)
        self.assertEqual(record['ledger']['summary']['expenses'], 104_400_000)
        self.assertEqual(record['ledger']['summary']['profit'], 295_600_000)
        self.assertEqual(sum(a['op'] == 'wallet' for a in record['ledger']['actions']), 1)
        self.assertEqual(len(record['ledger']['orders']), 2)
        prepares = [a for a in record['ledger']['actions']
                    if a['op'] == 'event' and a['args']['action'] == 'prepare']
        for index, action in enumerate(prepares):
            delivered = service.delivery(self.root, self.manifest, DAYS[index])
            self.assertEqual(action['args']['artifact_sha256'], digest(delivered))
        self.assertTrue(audit_export(record, root=self.root, manifest=self.manifest)['accepted'])
        self.account.close()
        self.account = BusinessAccount(self.root, self.manifest, self.path)
        self.assertEqual(self.account.export(), record)

    def test_missing_terms_and_output_before_funding_have_no_effect(self):
        before = self.account.export()
        with self.assertRaisesRegex(ValueError, 'EXPLICIT_BUYER_CHOSEN_TERMS'):
            self.account.begin_order(DAYS[0], 'unfunded', 'one-conditional-operator',
                                     200_000_000, 500_000_000, 0, 5)
        self.assertEqual(self.account.export(), before)
        with self.assertRaisesRegex(ValueError, 'OUTPUT_REQUIRES_FUNDED_ORDER'):
            self.account.complete_order('unfunded', DAYS[0], self.produce(), 1)
        output = service.safe_path(self.root, self.manifest['jobs'][0]['delivery_path'])
        self.assertFalse(output.exists())
        self.assertEqual(self.account.export(), before)

    def test_independent_rejection_and_changed_delivery_fail_closed(self):
        order = self.fund()
        artifact = self.produce()
        corrupt = copy.deepcopy(artifact)
        corrupt['source_binding']['instance_sha256'] = '0' * 64
        receipt = service.verify_delivery(self.root, self.manifest, DAYS[0], corrupt)
        self.assertFalse(receipt['accepted'])
        receipt = self.account.complete_order(order, DAYS[0], artifact, 2)
        self.assertTrue(receipt['accepted'])
        self.account.release(order, 3)
        record = self.account.export()
        output = service.safe_path(self.root, self.manifest['jobs'][0]['delivery_path'])
        original = output.read_bytes()
        try:
            output.write_bytes(canonical(corrupt))
            with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
                audit_export(record, root=self.root, manifest=self.manifest)
        finally:
            output.write_bytes(original)
        self.assertTrue(audit_export(record, root=self.root, manifest=self.manifest)['accepted'])

    def test_cached_financial_prefix_rebinds_refunded_outputs_and_drift(self):
        order = self.fund()
        artifact = self.produce()
        self.assertTrue(self.account.complete_order(order, DAYS[0], artifact, 2)['accepted'])
        self.account.refund(order, 3)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        record = self.account.export()
        output = service.safe_path(self.root, self.manifest['jobs'][0]['delivery_path'])
        original = output.read_bytes()
        alternate = copy.deepcopy(artifact)
        alternate['additional_review_note'] = 'Still feasible; different historical delivery.'
        self.assertTrue(service.verify_delivery(self.root, self.manifest, DAYS[0], alternate)['accepted'])
        try:
            output.write_bytes(canonical(alternate))
            with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
                self.account.account._audit_incremental()
            with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
                audit_export(record, root=self.root, manifest=self.manifest)
        finally:
            output.write_bytes(original)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        input_path = self.root / self.manifest['jobs'][1]['request']['instance_path']
        input_bytes = input_path.read_bytes()
        try:
            input_path.write_bytes(input_bytes + b'\n')
            with self.assertRaisesRegex(ValueError, 'INPUT_BYTES_CHANGED'):
                self.account.account._audit_incremental()
        finally:
            input_path.write_bytes(input_bytes)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        source_path = self.root / 'production060/dispatch.py'
        source_bytes = source_path.read_bytes()
        try:
            source_path.write_bytes(source_bytes + b'\n')
            with self.assertRaisesRegex(ValueError, 'CONNECTED_FINANCE_SOURCE_CHANGED'):
                self.account.account._audit_incremental()
        finally:
            source_path.write_bytes(source_bytes)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        altered = copy.deepcopy(record)
        altered['ledger']['actions'][0]['args']['amount'] -= 1
        altered['ledger']['actions_sha256'] = digest(altered['ledger']['actions'])
        with self.assertRaises(ValueError):
            _audit_journal(altered, root=self.root, manifest=self.manifest,
                           _native_session=self.account.account._native_prefix)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        self.assertTrue(audit_export(record, root=self.root, manifest=self.manifest)['accepted'])

    def test_cached_prefix_detects_delivery_change_during_audit(self):
        order = self.fund()
        artifact = self.produce()
        self.assertTrue(self.account.complete_order(order, DAYS[0], artifact, 2)['accepted'])
        self.account.release(order, 3)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])
        output = service.safe_path(self.root, self.manifest['jobs'][0]['delivery_path'])
        original = output.read_bytes()
        alternate = copy.deepcopy(artifact)
        alternate['additional_review_note'] = 'Changed between prefix and final guard.'
        calls = 0
        rebind = service.rebind_prepared
        def interfere(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = rebind(*args, **kwargs)
            if calls == 1:
                output.write_bytes(canonical(alternate))
            return result
        try:
            with patch.object(service, 'rebind_prepared', side_effect=interfere):
                with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
                    self.account.account._audit_incremental()
        finally:
            output.write_bytes(original)
        self.assertGreaterEqual(calls, 2)
        self.assertTrue(self.account.account._audit_incremental()['accepted'])


if __name__ == '__main__':
    unittest.main()
