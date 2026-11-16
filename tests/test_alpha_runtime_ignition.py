from __future__ import annotations
import copy
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from connected_enterprise.alpha_runtime import Engine, load, filehash, validate_request, source_identity, variant, index_sql, read_source
from connected_enterprise.alpha_demo import make_workload, request
from connected_enterprise.alpha_verify import verify


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = make_workload(self.root / 'source.sqlite', 41, 6000)
        self.engine = Engine(self.root / 'machine')
        self.req = request('job-one', 41)

    def tearDown(self):
        self.tmp.cleanup()

    def submit(self, req=None):
        self.engine.submit(self.source, req or self.req)

    def complete(self):
        self.submit()
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'DELIVERED_AWAITING_SETTLEMENT')
        return load(self.engine.root / 'outbox/job-one/receipt.json')

    def test_real_output_and_independent_verification(self):
        before = filehash(self.source)
        payload = self.complete()
        self.assertTrue(verify(self.engine.root / 'inbox/job-one/source.sqlite', payload)['verified'])
        self.assertEqual(before, filehash(self.source))
        self.assertEqual(self.engine.audit()['audit'], 'PASS')

    def test_quiescent_restart_does_not_duplicate(self):
        self.complete()
        before = self.engine.status()
        self.engine.run()
        self.assertEqual(before, self.engine.status())

    def test_successor_reuses_only_after_revalidation(self):
        first = self.complete()
        second_source = make_workload(self.root / 'fresh.sqlite', 83, 6000)
        self.engine.submit(second_source, request('job-two', 83))
        self.engine.run()
        second = load(self.engine.root / 'outbox/job-two/receipt.json')
        self.assertTrue(second['result']['accepted'])
        self.assertEqual(second['inherited_from'], 'job-one')
        self.assertLess(second['result']['search_candidates'], first['result']['search_candidates'])

    def test_already_optimized_input_is_declined(self):
        src = make_workload(self.root / 'optimized.sqlite', 41, 6000, True)
        self.engine.submit(src, self.req)
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'DECLINED')
        self.assertFalse((self.engine.root / 'outbox/job-one/apply.sql').exists())
        self.assertEqual(self.engine.status()['capabilities'], 0)

    def test_duplicate_submission_refused(self):
        self.submit()
        with self.assertRaisesRegex(ValueError, 'already submitted'):
            self.submit()

    def test_input_mutation_detected(self):
        self.submit()
        self.engine.scan()
        p = self.engine.root / 'inbox/job-one/request.json'
        r = load(p)
        r['min_gain'] = 5
        p.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.engine.run()

    def test_database_mutation_detected(self):
        self.complete()
        p = self.engine.root / 'inbox/job-one/source.sqlite'
        with sqlite3.connect(p) as c:
            c.execute('UPDATE events SET amount=amount+1 WHERE rowid=1')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.engine.audit()

    def test_wrong_result_rejected(self):
        payload = self.complete()
        payload['result']['selected']['answers'][0][0] += 1
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            verify(self.engine.root / 'inbox/job-one/source.sqlite', payload)

    def test_fake_payment_rejected(self):
        payload = self.complete()
        payload['result']['cash_collected'] = 10000
        with self.assertRaisesRegex(ValueError, 'monetary settlement'):
            verify(self.engine.root / 'inbox/job-one/source.sqlite', payload)

    def test_forged_work_metric_rejected(self):
        payload = self.complete()
        payload['result']['selected']['vm_steps'] += 1
        with self.assertRaisesRegex(ValueError, 'metric'):
            verify(self.engine.root / 'inbox/job-one/source.sqlite', payload)

    def test_sql_tampering_rejected(self):
        self.complete()
        (self.engine.root / 'outbox/job-one/apply.sql').write_text('DROP TABLE events;')
        with self.assertRaisesRegex(ValueError, 'SQL artifact'):
            self.engine.audit()

    def test_event_chain_tampering_rejected(self):
        self.complete()
        with self.engine.db() as c:
            c.execute("UPDATE events SET body='{}' WHERE seq=1")
        with self.assertRaisesRegex(ValueError, 'chain'):
            self.engine.audit()

    def test_crash_after_verification_resumes_without_recompute(self):
        self.submit()
        with patch.object(Engine, 'deliver', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'VERIFIED')
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['attempts'], 1)
        self.assertEqual(self.engine.audit()['audit'], 'PASS')

    def test_delivery_io_error_preserves_verified_state(self):
        self.submit()
        with patch.object(Engine, 'deliver', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'VERIFIED')
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['attempts'], 1)

    def test_real_process_kill_and_recovery(self):
        self.submit()
        code = "import time; from connected_enterprise import alpha_runtime as m; m.solve=lambda *a,**k:time.sleep(60); m.Engine(%r).run()" % str(self.engine.root)
        proc = subprocess.Popen([sys.executable, '-c', code])
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                jobs = self.engine.status()['jobs']
                if jobs and jobs[0]['status'] == 'RUNNING':
                    break
                time.sleep(.02)
            else:
                self.fail('Child did not claim work')
            proc.kill()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['attempts'], 2)
        with self.engine.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM events WHERE kind='INTERRUPTED_ATTEMPT'").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM events WHERE kind='DELIVERED_AWAITING_SETTLEMENT'").fetchone()[0], 1)

    def test_second_worker_cannot_acquire_lock(self):
        self.submit()
        with self.engine.lock():
            p = subprocess.run([sys.executable, '-m', 'connected_enterprise.alpha_runtime', '--root', str(self.engine.root), 'run'], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('Another worker', p.stderr)

    def test_symlink_input_refused(self):
        link = self.root / 'link.sqlite'
        link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.engine.submit(link, self.req)

    def test_unsafe_sql_identifier_refused(self):
        self.req['table'] = 'events; DROP TABLE events'
        with self.assertRaisesRegex(ValueError, 'identifier'):
            validate_request(self.req)

    def test_duplicate_json_keys_refused(self):
        p = self.root / 'duplicate.json'
        p.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            load(p)

    def test_confirmation_disjoint(self):
        self.req['confirmation'][0] = self.req['discovery'][0]
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            validate_request(self.req)

    def test_unrecognized_fields_refused(self):
        self.req['cash_collected'] = 999
        with self.assertRaisesRegex(ValueError, 'fields'):
            validate_request(self.req)

    def test_nonfinite_threshold_refused(self):
        self.req['min_gain'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            validate_request(self.req)

    def test_zero_storage_declines_without_capability(self):
        self.req['max_index_bytes'] = 0
        self.submit()
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'DECLINED')
        self.assertEqual(self.engine.status()['capabilities'], 0)

    def test_null_data_refused(self):
        with sqlite3.connect(self.source) as c:
            c.execute('UPDATE events SET amount=NULL WHERE rowid=1')
        with self.assertRaisesRegex(ValueError, 'noninteger'):
            self.submit()

    def test_source_code_identity_is_bound(self):
        payload = self.complete()
        payload['source_identity']['alpha_runtime.py'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'code changed'):
            verify(self.engine.root / 'inbox/job-one/source.sqlite', payload)

    def test_full_size_metric_resolution_regression(self):
        source = make_workload(self.root / 'large.sqlite', 41, 80000)
        self.engine.submit(source, self.req)
        self.engine.run()
        receipt = load(self.engine.root / 'outbox/job-one/receipt.json')
        self.assertTrue(receipt['result']['accepted'])
        self.assertEqual(receipt['result']['ordinary_work_ratio'], 1.0)

    def test_loaded_code_change_refused(self):
        with patch('connected_enterprise.alpha_runtime.LOADED_RUNTIME_HASH', '0'*64):
            with self.assertRaisesRegex(ValueError, 'differs from disk'):
                source_identity()


    def test_freelist_pages_count_against_zero_storage_allowance(self):
        # One fixed example and a real free-page pool; no post-hoc seeds.
        with sqlite3.connect(self.source) as c:
            c.execute('CREATE TABLE scratch(payload BLOB)')
            c.execute('INSERT INTO scratch VALUES(zeroblob(1048576))')
            c.execute('DROP TABLE scratch')
            c.commit()
            self.assertGreater(c.execute('PRAGMA freelist_count').fetchone()[0], 0)
        self.req['max_index_bytes'] = 0
        with contextlib.closing(read_source(self.source)) as source:
            with variant(source, self.req, self.req['equals'] + [self.req['range'], self.req['measure']]) as (c, size, _):
                self.assertGreater(size, 0, 'Existing freelist pages still consume real index storage')
                try:
                    allocated = c.execute("SELECT SUM(pgsize) FROM dbstat WHERE name LIKE 'alpha_%'").fetchone()[0]
                except sqlite3.OperationalError:
                    allocated = None
                if allocated is not None:
                    self.assertGreaterEqual(size, allocated)
        self.submit()
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'DECLINED')
        self.assertEqual(self.engine.status()['capabilities'], 0)

    def test_already_applied_deterministic_index_declines_not_fails(self):
        apply_sql, _ = index_sql(self.req, self.req['equals'] + [self.req['range'], self.req['measure']])
        with sqlite3.connect(self.source) as c:
            c.execute(apply_sql)
            c.commit()
        self.submit()
        self.engine.run()
        self.assertEqual(self.engine.status()['jobs'][0]['status'], 'DECLINED')
        self.assertEqual(self.engine.audit()['audit'], 'PASS')

    def test_delivered_event_cannot_be_reset_to_queued(self):
        self.complete()
        with self.engine.db() as c:
            c.execute("UPDATE jobs SET status='QUEUED' WHERE id='job-one'")
        before = self.engine.status()['events']
        with self.assertRaisesRegex(ValueError, '[Hh]istory|[Ss]tate'):
            self.engine.audit()
        with self.assertRaisesRegex(ValueError, '[Hh]istory|[Ss]tate'):
            self.engine.run()
        self.assertEqual(before, self.engine.status()['events'],
                         'A corrupt status must not trigger a duplicate processing/delivery')

if __name__ == '__main__':
    unittest.main()
