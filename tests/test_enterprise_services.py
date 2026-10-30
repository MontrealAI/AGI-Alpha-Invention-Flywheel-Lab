import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import TapeExchange, audit, load_jobs as routed_load_jobs
from enterprise.checkers import audit_delivery
from enterprise.services import (SOURCE_PATHS, SERVICE_IDS, canonical, check_job, execute_job,
                                 load_jobs, prepare_services, produce, sha, synthetic_order)

ROOT = Path(__file__).resolve().parents[1]


class EnterpriseServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='enterprise011-service-test-')
        cls.root = Path(cls.temp.name)
        for source in SOURCE_PATHS:
            target = cls.root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target)
        cls.manifest = prepare_services(cls.root, 'services')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def first_job(self, service_id):
        return next(job for job in self.manifest['jobs'] if job['service_id'] == service_id)

    def test_actual_three_service_cohort_and_rejected_probes(self):
        self.assertEqual(len(self.manifest['jobs']), 96)
        self.assertEqual({job['service_id'] for job in self.manifest['jobs']}, set(SERVICE_IDS))
        self.assertTrue(all(job['accepted'] for job in self.manifest['jobs']))
        self.assertEqual(len({job['artifact_sha256'] for job in self.manifest['jobs']}), 96)
        self.assertEqual(len(self.manifest['attempts']), 3)
        self.assertTrue(all(job['accepted'] is False for job in self.manifest['attempts']))
        self.assertEqual(len(routed_load_jobs(self.root, self.manifest)), 96)

    def test_kpi_arithmetic_zero_base_and_negative_delta(self):
        order = synthetic_order('kpi_variance', 0)
        artifact = produce('kpi_variance', order)
        self.assertTrue(audit_delivery('kpi_variance', order, artifact)['accepted'])
        self.assertIsNone(artifact['rows'][0]['change_ratio'])
        self.assertTrue(any(row['delta_cents'] < 0 for row in artifact['rows']))
        self.assertEqual(artifact['totals']['delta_cents'], artifact['totals']['current_cents'] - artifact['totals']['prior_cents'])

    def test_kpi_missing_duplicate_and_invented_metric_rejected(self):
        order = synthetic_order('kpi_variance', 0)
        for mode in ['missing', 'duplicate', 'invented']:
            artifact = produce('kpi_variance', order)
            if mode == 'missing':
                artifact['rows'].pop()
            elif mode == 'duplicate':
                artifact['rows'].append(copy.deepcopy(artifact['rows'][0]))
            else:
                artifact['rows'][0]['metric'] = 'invented-source-metric'
            with self.subTest(mode=mode):
                self.assertFalse(audit_delivery('kpi_variance', order, artifact)['accepted'])

    def test_kpi_total_ratio_direction_tampering_rejected(self):
        order = synthetic_order('kpi_variance', 1)
        artifact = produce('kpi_variance', order)
        for field, value in [('delta_cents', 999), ('direction', 'INVALID'), ('change_ratio', [1, 1])]:
            changed = copy.deepcopy(artifact)
            changed['rows'][0][field] = value
            with self.subTest(field=field):
                self.assertFalse(audit_delivery('kpi_variance', order, changed)['accepted'])
        artifact['totals']['prior_cents'] += 1
        self.assertFalse(audit_delivery('kpi_variance', order, artifact)['accepted'])

    def test_malformed_kpi_currency_units_numbers_and_duplicates_rejected(self):
        for field, value in [('currency', 'CAD'), ('currency', 'USD/hour'), ('scope', 'PRIVATE_CUSTOMER')]:
            order = synthetic_order('kpi_variance', 0)
            order[field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(audit_delivery('kpi_variance', order, {})['accepted'])
        for value in [True, -1, 10**14 + 1, float('nan'), 1.5, '100']:
            order = synthetic_order('kpi_variance', 0)
            order['metrics'][0]['prior_cents'] = value
            with self.subTest(value=value):
                self.assertFalse(audit_delivery('kpi_variance', order, {})['accepted'])
        order = synthetic_order('kpi_variance', 0)
        order['metrics'].append(copy.deepcopy(order['metrics'][0]))
        self.assertFalse(audit_delivery('kpi_variance', order, {})['accepted'])

    def test_evidence_missing_and_conflict_are_useful_disclosed_results(self):
        order = synthetic_order('evidence_matrix', 0)
        artifact = produce('evidence_matrix', order)
        self.assertTrue(audit_delivery('evidence_matrix', order, artifact)['accepted'])
        statuses = {row['status'] for row in artifact['rows']}
        self.assertEqual(statuses, {'SUPPORTED', 'MISSING', 'CONFLICT'})
        self.assertTrue(all(row['value'] is None for row in artifact['rows'] if row['status'] != 'SUPPORTED'))

    def test_evidence_unsupported_claim_and_fabricated_citation_rejected(self):
        order = synthetic_order('evidence_matrix', 0)
        for mode in ['value', 'source', 'missing', 'conflict']:
            artifact = produce('evidence_matrix', order)
            if mode == 'value':
                artifact['rows'][0]['value'] = 'Certified for a claim absent from the source'
            elif mode == 'source':
                artifact['rows'][0]['citations'][0]['source_id'] = 'UNKNOWN'
            elif mode == 'missing':
                artifact['rows'].pop()
            else:
                row = next(row for row in artifact['rows'] if row['status'] == 'CONFLICT')
                row['status'] = 'SUPPORTED'
            with self.subTest(mode=mode):
                self.assertFalse(audit_delivery('evidence_matrix', order, artifact)['accepted'])

    def test_duplicate_sources_requirements_and_unscoped_inputs_rejected(self):
        for mode in ['source', 'requirement', 'extra']:
            order = synthetic_order('evidence_matrix', 0)
            if mode == 'source':
                order['sources'].append(copy.deepcopy(order['sources'][0]))
            elif mode == 'requirement':
                order['requirements'].append(copy.deepcopy(order['requirements'][0]))
            else:
                order['authority'] = 'Invented permission'
            with self.subTest(mode=mode):
                self.assertFalse(audit_delivery('evidence_matrix', order, {})['accepted'])

    def test_reconciliation_exception_and_conservation_contract(self):
        order = synthetic_order('reconciliation', 0)
        artifact = produce('reconciliation', order)
        self.assertTrue(audit_delivery('reconciliation', order, artifact)['accepted'])
        self.assertEqual(artifact['unmatched_invoices'], ['I11'])
        artifact['totals']['matched_payment_cents'] += 1
        self.assertFalse(audit_delivery('reconciliation', order, artifact)['accepted'])

    def test_reconciliation_unsupported_extra_claim_is_rejected(self):
        order = synthetic_order('reconciliation', 0)
        artifact = produce('reconciliation', order)
        artifact['customer_credential'] = 'Unsupported claim outside source data'
        self.assertFalse(audit_delivery('reconciliation', order, artifact)['accepted'])

    def test_checker_has_no_producer_import(self):
        source = (ROOT / 'enterprise/checkers.py').read_text()
        self.assertNotIn('from enterprise.services', source)
        self.assertNotIn('import enterprise.services', source)
        self.assertNotIn('from commercial.service import', source)

    def test_reexecution_is_actual_and_matches_all_three_saved_outputs(self):
        for service_id in SERVICE_IDS:
            with self.subTest(service_id=service_id):
                receipt = execute_job(self.root, self.first_job(service_id))
                self.assertTrue(receipt['accepted'])
                self.assertTrue(receipt['reexecuted'])
                self.assertGreaterEqual(receipt['process_cpu_seconds'], 0)
                self.assertEqual(receipt['model_calls'], 0)

    def test_output_overwrite_absolute_and_parent_traversal_refused(self):
        with self.assertRaises(FileExistsError):
            prepare_services(self.root, 'services')
        for path in ['/tmp/forbidden-enterprise-output', '../forbidden']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                prepare_services(self.root, path)

    def test_job_identity_currency_schema_and_hash_tampering_refused(self):
        for mode in ['currency', 'scope', 'unknown', 'duplicate', 'hash', 'source']:
            manifest = copy.deepcopy(self.manifest)
            if mode == 'currency':
                manifest['currency'] = 'CAD'
            elif mode == 'scope':
                manifest['scope'] = 'OBSERVED'
            elif mode == 'unknown':
                manifest['accepted_count'] = 999
            elif mode == 'duplicate':
                manifest['jobs'].append(copy.deepcopy(manifest['jobs'][0]))
            elif mode == 'hash':
                manifest['jobs'][0]['artifact_sha256'] = '0' * 64
            else:
                manifest['source_hashes']['enterprise/checkers.py'] = '0' * 64
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                load_jobs(self.root, manifest)

    def test_manifest_rejected_probe_cannot_be_silently_promoted(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['attempts'][0]['accepted'] = True
        with self.assertRaises(ValueError):
            load_jobs(self.root, manifest)

    def test_malformed_rejected_probe_fails_typed_validation(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['attempts'][0].pop('id')
        with self.assertRaises(ValueError):
            load_jobs(self.root, manifest)

    def test_rehashed_copied_source_cannot_impersonate_executing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(self.root, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('linked-artifact.json'))
            manifest = copy.deepcopy(self.manifest)
            path = root / 'enterprise/checkers.py'
            path.write_bytes(path.read_bytes() + b'\nINVENTED = True\n')
            manifest['source_hashes']['enterprise/checkers.py'] = sha(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'EXECUTING_SOURCE_IDENTITY_MISMATCH'):
                load_jobs(root, manifest)

    def test_relative_bound_path_and_symlink_rejected(self):
        for path in ['/etc/passwd', '../escape.json']:
            job = copy.deepcopy(self.manifest['jobs'][0])
            job['artifact'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                check_job(self.root, self.manifest, job)
        link = self.root / 'linked-artifact.json'
        link.symlink_to(self.root / self.manifest['jobs'][0]['artifact'])
        job = copy.deepcopy(self.manifest['jobs'][0])
        job['artifact'] = 'linked-artifact.json'
        with self.assertRaises(ValueError):
            check_job(self.root, self.manifest, job)

    def test_forged_acceptance_and_rehashed_unsupported_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(self.root, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns('linked-artifact.json'))
            manifest = copy.deepcopy(self.manifest)
            job = next(job for job in manifest['jobs'] if job['service_id'] == 'evidence_matrix')
            artifact = json.loads((root / job['artifact']).read_text())
            artifact['rows'][0]['value'] = 'Unsupported capability'
            raw = canonical(artifact)
            (root / job['artifact']).write_bytes(raw)
            job['artifact_sha256'] = sha(raw)
            receipt = json.loads((root / job['receipt']).read_text())
            receipt['artifact_sha256'] = job['artifact_sha256']
            receipt['artifact_content_sha256'] = __import__('enterprise.checkers', fromlist=['identity']).identity(artifact)
            raw = canonical(receipt)
            (root / job['receipt']).write_bytes(raw)
            job['receipt_sha256'] = sha(raw)
            with self.assertRaises(ValueError):
                load_jobs(root, manifest)

    def test_three_services_settle_through_same_native_ledger_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = TapeExchange(Path(tmp) / 'exchange.sqlite', root=self.root, manifest=self.manifest,
                              opening=5_000_000_000, working=100_000_000, contract='enterprise-service-test', durable=False)
            try:
                ex.execute('wallet', {'buyer': 'synthetic-buyer', 'amount': 1_000_000_000}, 0)
                for index, service_id in enumerate(SERVICE_IDS):
                    job = self.first_job(service_id)
                    order_id = 'order-' + str(index)
                    ex.execute('offer', {'id': order_id, 'buyer': 'synthetic-buyer', 'price': 200_000_000, 'job_id': job['id'], 'deadline': 100}, index)
                    for action in ['consent', 'fund', 'prepare', 'release']:
                        ex.execute('event', {'id': order_id, 'action': action, 'event_id': order_id + '-' + action}, index)
                tape = ex.export()
                self.assertEqual(tape['summary']['collections'], 600_000_000)
                self.assertEqual(len([order for order in tape['orders'] if order['state'] == 'released']), 3)
                self.assertTrue(audit(tape, root=self.root, manifest=self.manifest)['accepted'])
                mutated = copy.deepcopy(tape)
                mutated['summary']['profit'] += 1
                with self.assertRaises(ValueError):
                    audit(mutated, root=self.root, manifest=self.manifest)
            finally:
                ex.close()


if __name__ == '__main__':
    unittest.main()
