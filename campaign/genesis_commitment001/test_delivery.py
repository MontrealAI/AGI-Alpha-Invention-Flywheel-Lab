"""Source/semantic boundary regressions for actual synthetic database output."""
from __future__ import annotations

import base64
import copy
import gc
import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from .acceptance import validate_request, verify
from .delivery import default_requests, produce
from .service import _safe_path


def changed_database(artifact, sql):
    candidate = copy.deepcopy(artifact)
    with closing(sqlite3.connect(':memory:')) as db:
        db.deserialize(base64.b64decode(candidate['output_database_b64']))
        db.executescript(sql)
        db.commit()
        raw = db.serialize()
    candidate['output_database_b64'] = base64.b64encode(raw).decode()
    candidate['output_sha256'] = hashlib.sha256(raw).hexdigest()
    return candidate


class DeliveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.restore, self.migration = default_requests()

    def test_restoration_actual_database_matches_source(self):
        artifact = produce(self.restore)
        self.assertTrue(verify(self.restore, artifact)['accepted'])
        self.assertNotIn('accepted', artifact)

    def test_distinct_migration_preserves_normalized_relations(self):
        self.assertTrue(verify(self.migration, produce(self.migration))['accepted'])

    def test_competent_direct_methods_tie_on_complete_output(self):
        for request in default_requests():
            retained = produce(request)
            direct = produce(request, method='direct')
            self.assertTrue(verify(request, direct)['accepted'])
            self.assertEqual(retained['output_database_b64'], direct['output_database_b64'])

    def test_retries_are_deterministic(self):
        for request in default_requests():
            self.assertEqual(produce(request), produce(request))

    def test_concurrent_production_uses_separate_temporary_files(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(produce, [self.restore] * 8))
        self.assertTrue(all(item == results[0] for item in results))
        self.assertTrue(verify(self.restore, results[0])['accepted'])

    @unittest.skipUnless(Path('/proc/self/fd').is_dir(), 'Linux descriptor accounting')
    def test_production_does_not_accumulate_open_database_files(self):
        gc.collect()
        enabled = gc.isenabled()
        gc.disable()
        try:
            before = len(list(Path('/proc/self/fd').iterdir()))
            for _ in range(40):
                for request in default_requests():
                    produce(request)
            after = len(list(Path('/proc/self/fd').iterdir()))
            self.assertEqual(before, after)
        finally:
            if enabled:
                gc.enable()

    def test_rehashed_changed_balance_is_rejected(self):
        artifact = changed_database(produce(self.restore), 'UPDATE accounts SET balance_cents=balance_cents+1')
        self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_rehashed_missing_record_is_rejected(self):
        artifact = changed_database(produce(self.restore), "DELETE FROM accounts WHERE account_id='acct-A'")
        self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_rehashed_wrong_customer_relation_is_rejected(self):
        artifact = changed_database(produce(self.migration), "UPDATE invoices SET customer_id='buyer-R' WHERE invoice_id='inv-101'")
        self.assertFalse(verify(self.migration, artifact)['accepted'])

    def test_foreign_key_violation_is_rejected(self):
        artifact = changed_database(produce(self.migration), "DELETE FROM customers WHERE customer_id='buyer-Q'")
        self.assertFalse(verify(self.migration, artifact)['accepted'])

    def test_output_under_changed_requirement_is_rejected(self):
        artifact = produce(self.restore)
        self.restore['records'][0]['balance_cents'] += 1
        self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_fabricated_accepted_field_is_rejected(self):
        artifact = produce(self.restore)
        artifact['accepted'] = True
        self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_extra_schema_objects_are_rejected(self):
        for sql in ('CREATE TABLE extra(x TEXT)',
                    'CREATE VIEW shadow AS SELECT * FROM accounts',
                    'CREATE INDEX extra_index ON accounts(name)'):
            with self.subTest(sql=sql):
                artifact = changed_database(produce(self.restore), sql)
                self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_corrupt_database_is_rejected_even_if_rehashed(self):
        artifact = produce(self.restore)
        raw = b'not a database' * 50
        artifact['output_database_b64'] = base64.b64encode(raw).decode()
        artifact['output_sha256'] = hashlib.sha256(raw).hexdigest()
        self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_duplicate_record_ids_and_names_rejected(self):
        self.restore['records'].append(copy.deepcopy(self.restore['records'][0]))
        with self.assertRaises(ValueError):
            produce(self.restore)
        self.migration['records'][2]['customer_name'] = 'Conflicting name'
        with self.assertRaises(ValueError):
            produce(self.migration)

    def test_money_requires_exact_bounded_integer(self):
        for amount in (True, -1, 1.5, '100', 10**12 + 1):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                request = copy.deepcopy(self.restore)
                request['records'][0]['balance_cents'] = amount
                produce(request)

    def test_malformed_or_oversized_input_rejected(self):
        candidates = [None, {}, {**self.restore, 'extra': 1},
                      {**self.restore, 'records': []},
                      {**self.restore, 'records': [self.restore['records'][0]] * 1025},
                      {**self.restore, 'kind': []}]
        for request in candidates:
            with self.subTest(request_type=type(request).__name__), self.assertRaises(ValueError):
                validate_request(request)

    def test_resource_bound_and_noncanonical_encoding_rejected(self):
        for value in ('A' * 2_000_001, '===' + produce(self.restore)['output_database_b64']):
            artifact = produce(self.restore)
            artifact['output_database_b64'] = value
            self.assertFalse(verify(self.restore, artifact)['accepted'])

    def test_paths_reject_escape_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'safe').mkdir()
            (root / 'link').symlink_to(root / 'safe', target_is_directory=True)
            for relative in ('../escape', '/tmp/escape', 'safe/../escape', 'link/output.json'):
                with self.subTest(path=relative), self.assertRaises(ValueError):
                    _safe_path(root, relative)
            self.assertEqual(_safe_path(root, 'safe/output.json'), root / 'safe/output.json')


if __name__ == '__main__':
    unittest.main()
