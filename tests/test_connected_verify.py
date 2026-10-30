import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from commercial.ledger import digest
from connected_enterprise.verify import check_budgets, check_channels, check_events, check_source
from connected_enterprise.channels import ChannelBook, default_contracts


class ConnectedEvidenceChecks(unittest.TestCase):
    def test_event_identity_time_and_causal_reordering(self):
        events = [{'id': 'consent', 'time': 1, 'kind': 'QUALIFIED'}, {'id': 'production', 'time': 2, 'kind': 'PRODUCTION'}]
        self.assertEqual(len(check_events(events)), 2)
        for broken in [[events[0], events[0]], list(reversed(events))]:
            with self.assertRaises(ValueError):
                check_events(broken)

    def test_cross_service_budget_conservation(self):
        orders = [{'id': 'invoice', 'customer_id': 'buyer', 'price': 20, 'outcome': 'SETTLED'},
                  {'id': 'kpi', 'customer_id': 'buyer', 'price': 30, 'outcome': 'PENDING'}]
        buyers = [{'id': 'buyer', 'initial_budget': 100, 'remaining_budget': 50, 'pending_commitments': {'kpi': 30}, 'outside_spend': 0, 'our_settled_spend': 20}]
        self.assertEqual(check_budgets(buyers, orders)['buyers_checked'], 1)
        for field, value in [('remaining_budget', 80), ('pending_commitments', {}), ('our_settled_spend', 0)]:
            changed = copy.deepcopy(buyers)
            changed[0][field] = value
            with self.assertRaises(ValueError):
                check_budgets(changed, orders)

    def test_source_bytes_and_path_boundaries(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'engine.py').write_text('executed source\n')
            files = {'engine.py': hashlib.sha256((root / 'engine.py').read_bytes()).hexdigest()}
            source = {'files': files, 'sha256': digest(files)}
            self.assertEqual(check_source(root, source)['source_files_checked'], 1)
            (root / 'engine.py').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                check_source(root, source)
            escaped = {'../engine.py': files['engine.py']}
            with self.assertRaisesRegex(ValueError, 'PATH_ESCAPE'):
                check_source(root, {'files': escaped, 'sha256': digest(escaped)})

    def test_channel_audit_detects_expired_or_duplicate_reach(self):
        terms = default_contracts()
        terms['pilot'].update(activation_reliability_bps=10000, realization_bps=10000)
        book = ChannelBook(314, terms)
        purchase = book.purchase('pilot', 0, 'earned-plan')
        buyers = [{'id': 'customer-' + str(i).zfill(2)} for i in range(12)]
        for day in range(24):
            book.expose(day, buyers)
        investments = [{'plan_id': 'earned-plan', 'kind': 'acquisition', 'cost': purchase['invoice_microUSD'],
                        'purchased_time': 0, 'activation_time': 48, 'expiry_time': 552}]
        state = book.export()
        self.assertGreater(check_channels(state, investments, buyers)['paid_exposures_checked'], 0)
        changed = copy.deepcopy(state)
        day = next(k for k, v in changed['exposures_by_day'].items() if v['exposures'])
        changed['exposures_by_day'][day]['exposures'].append(changed['exposures_by_day'][day]['exposures'][0])
        with self.assertRaisesRegex(ValueError, 'DOUBLE_COUNT'):
            check_channels(changed, investments, buyers)
        changed = copy.deepcopy(state)
        changed['instances']['earned-plan']['expiry_day'] = 2
        with self.assertRaisesRegex(ValueError, 'LEAD_OR_DURATION'):
            check_channels(changed, investments, buyers)


class ConnectedEndToEndVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from adaptive_enterprise.runner import source_paths
        from adaptive_enterprise.instruments import prepare_services
        from connected_enterprise.finance import SOURCE_PATHS
        from connected_enterprise.engine import default_config, run_world
        cls.temporary = tempfile.TemporaryDirectory(prefix='connected014-independent-test-')
        cls.root = Path(cls.temporary.name) / 'source'
        repo = Path(__file__).resolve().parents[1]
        names = set(source_paths(repo)) | set(SOURCE_PATHS) | {str(path.relative_to(repo)) for path in (repo / 'connected_enterprise').glob('*.py')}
        for name in names:
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / name, target)
        files = {name: hashlib.sha256((cls.root / name).read_bytes()).hexdigest() for name in sorted(names)}
        cls.manifest = prepare_services(cls.root, 'service-inputs', cohort_seed=14003)
        config = default_config()
        config['horizon_days'] = 12
        cls.result = run_world(cls.root, cls.manifest, config, 14003, 'baseline', Path(cls.temporary.name) / 'world',
                               source={'files': files, 'sha256': digest(files)})

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_native_finance_and_actual_useful_output_replay(self):
        from connected_enterprise.verify import audit
        checked = audit(self.root, self.manifest, self.result)
        self.assertTrue(checked['accepted'])
        self.assertTrue(checked['verifier_matches_world_source_snapshot'])
        self.assertGreater(checked['orders_reexecuted'], 0)
        self.assertEqual(checked['collections_microUSD'], self.result['summary']['collections'])

    def test_complete_public_receipt_survives_json_roundtrip_exactly(self):
        from connected_enterprise.verify import audit
        receipt = audit(self.root, self.manifest, self.result)
        self.assertEqual(receipt, json.loads(json.dumps(receipt, sort_keys=True)))
        self.assertTrue(receipt['daily_outreach_units_recomputed'])
        self.assertTrue(all(type(key) is str for key in receipt['daily_outreach_units_recomputed']))

    def test_lifecycle_or_producer_flag_cannot_replace_independent_acceptance(self):
        from connected_enterprise.verify import audit
        mutations = [lambda row: row.update(production_time=row['qualified_time'] - 1),
                     lambda row: row['service_receipt'].update(accepted=False),
                     lambda row: row['service_receipt']['artifact'].update(useful_outcome={}),
                     lambda row: row.update(collection_time=row['acceptance_time'] - 1)]
        for mutation in mutations:
            changed = copy.deepcopy(self.result)
            mutation(changed['orders'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                audit(self.root, self.manifest, changed)

    def test_missing_shared_cost_and_counterfeit_earned_funding_are_rejected(self):
        from connected_enterprise.verify import audit
        changed = copy.deepcopy(self.result)
        changed['costs'] = changed['costs'][1:]
        with self.assertRaisesRegex(ValueError, 'FULL_ENTERPRISE_COSTS'):
            audit(self.root, self.manifest, changed)
        changed = copy.deepcopy(self.result)
        changed['orders'][0]['funding_receipt']['funding'] = 'EARNED'
        with self.assertRaisesRegex(ValueError, 'FUNDING_RECEIPT_NOT_SOURCE_BOUND'):
            audit(self.root, self.manifest, changed)

    def test_commercial_counters_and_expansion_are_derived(self):
        from connected_enterprise.verify import audit
        for key, value in [('paid_jobs', self.result['paid_jobs'] + 1),
                           ('conditional_simulated_commercial_success', not self.result['conditional_simulated_commercial_success'])]:
            changed = copy.deepcopy(self.result)
            changed[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'COUNTERS_OR_SUCCESS'):
                audit(self.root, self.manifest, changed)
        changed = copy.deepcopy(self.result)
        changed['productive_expansion'] = [{'plan_id': 'invented', 'scoped_collections': 1}]
        with self.assertRaisesRegex(ValueError, 'EXPANSION_ATTRIBUTION'):
            audit(self.root, self.manifest, changed)

    def test_private_buyer_choice_and_operating_cost_contracts_are_recomputed(self):
        from connected_enterprise.verify import audit
        changed = copy.deepcopy(self.result)
        decision = next(row for row in changed['decisions'] if row.get('kind') == 'offer' and row['chosen'])
        decision.update(buyer_choice='decline', chosen=False)
        with self.assertRaisesRegex(ValueError, 'BUYER_CHOICE'):
            audit(self.root, self.manifest, changed)
        changed = copy.deepcopy(self.result)
        changed['costs'][0]['category'] = 'unpriced_resource'
        with self.assertRaisesRegex(ValueError, 'FROZEN_OPERATING_SEMANTICS'):
            audit(self.root, self.manifest, changed)


if __name__ == '__main__':
    unittest.main()
