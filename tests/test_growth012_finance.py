import copy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest

from commercial.ledger import audit, digest
from commercial.single_writer import SingleWriterExchange
from enterprise.finance012 import AuditedAllocation

ROOT = Path(__file__).resolve().parents[1]


class AuditedAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'campaign/commercial-010/service/executed-002/manifest.json').read_bytes())
        cls.job = next(row for row in cls.manifest['jobs'] if row['accepted'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'account.sqlite'
        self.exchange = self.open()

    def tearDown(self):
        self.exchange.close()
        self.tmp.cleanup()

    def open(self):
        return SingleWriterExchange(self.path, root=ROOT, manifest=self.manifest,
                                    opening=1_000_000_000, working=0, contract='growth012-allocation-test')

    def earn(self):
        ex = self.exchange
        ex.execute('cost', {'id': 'production', 'amount': 10_000_000}, 0)
        ex.execute('wallet', {'buyer': 'buyer', 'amount': 100_000_000}, 0)
        ex.execute('offer', {'id': 'order', 'buyer': 'buyer', 'price': 100_000_000,
                            'job_id': self.job['id'], 'deadline': 20}, 0)
        for day, action in enumerate(['consent', 'fund', 'prepare', 'release']):
            ex.execute('event', {'id': 'order', 'action': action, 'event_id': action}, day)

    def allocator(self, cap=90_000_000):
        return AuditedAllocation(self.exchange, root=ROOT, manifest=self.manifest,
                                 allocation_id='bounded012', cap=cap)

    def test_future_return_and_seed_cannot_substitute_for_earned_cash(self):
        gate = self.allocator()
        plan = gate.plan('first', 1, 99_000_000, intent={'delivery': True})
        before = self.exchange.export()
        with self.assertRaisesRegex(ValueError, 'ELIGIBLE_FUNDS'):
            gate.reserve(plan, 0)
        self.assertEqual(self.exchange.export(), before)

    def test_stale_plan_refused_after_actual_cost(self):
        self.earn(); gate = self.allocator()
        plan = gate.plan('first', 60_000_000, 10_000_000, intent={'delivery': True})
        self.exchange.execute('cost', {'id': 'support', 'amount': 1}, 4)
        before = self.exchange.export()
        with self.assertRaisesRegex(ValueError, 'STALE_ALLOCATION_PLAN'):
            gate.reserve(plan, 4)
        self.assertEqual(self.exchange.export(), before)

    def test_bound_plan_reserves_once_and_recovery_preserves_commitment(self):
        self.earn(); gate = self.allocator()
        plan = gate.plan('first', 60_000_000, 10_000_000, intent={'delivery': True})
        gate.reserve(plan, 4)
        with self.assertRaisesRegex(ValueError, 'STALE_ALLOCATION_PLAN'):
            gate.reserve(plan, 4)
        self.exchange.close(); self.exchange = self.open(); restored = self.allocator()
        observation = restored.observe()
        self.assertEqual(observation['summary']['reservedInvestment'], 60_000_000)
        self.assertEqual(observation['summary']['unrestrictedEarned'], 30_000_000)
        self.assertEqual(observation['allocation_remaining'], 30_000_000)
        impossible = restored.plan('second', 40_000_000, 10_000_000, intent={'delivery': True})
        with self.assertRaisesRegex(ValueError, 'ELIGIBLE_FUNDS'):
            restored.reserve(impossible, 5)
        restored.finish(plan, 40_000_000, digest({'accepted': 'new delivery'}), 5)
        before = self.exchange.export()
        with self.assertRaisesRegex(ValueError, 'construction budget/state'):
            restored.finish(plan, 40_000_000, digest({'accepted': 'new delivery'}), 5)
        self.assertEqual(self.exchange.export(), before)
        self.assertTrue(audit(before, root=ROOT, manifest=self.manifest)['accepted'])
        self.assertEqual(before['summary']['profit'], 50_000_000)

    def test_later_reversal_stops_new_investment_and_stales_old_plan(self):
        self.earn(); gate = self.allocator()
        plan = gate.plan('first', 60_000_000, 10_000_000, intent={'delivery': True})
        self.exchange.execute('event', {'id': 'order', 'action': 'late_reversal', 'event_id': 'adverse'}, 4)
        with self.assertRaisesRegex(ValueError, 'STALE_ALLOCATION_PLAN'):
            gate.reserve(plan, 4)
        self.assertEqual(gate.observe()['summary']['unrestrictedEarned'], 0)
        self.assertEqual(gate.observe()['summary']['profit'], -10_000_000)

    def test_allocation_ceiling_survives_reopen_and_unused_cap_is_not_new_authority(self):
        self.earn(); gate = self.allocator(cap=60_000_000)
        plan = gate.plan('first', 60_000_000, 10_000_000, intent={'delivery': True})
        gate.reserve(plan, 4); gate.finish(plan, 30_000_000, digest({'accepted': True}), 4)
        self.assertEqual(gate.observe()['allocation_remaining'], 0)
        follow = gate.plan('second', 1, 10, intent={'delivery': True})
        with self.assertRaisesRegex(ValueError, 'ELIGIBLE_FUNDS_OR_ALLOCATION'):
            gate.reserve(follow, 4)

    def test_cancel_releases_unspent_cap_without_changing_profit(self):
        self.earn(); gate = self.allocator()
        plan = gate.plan('first', 60_000_000, 10_000_000, intent={'delivery': True})
        gate.reserve(plan, 4); gate.cancel(plan, 4)
        self.assertEqual(gate.observe()['summary']['profit'], 90_000_000)
        self.assertEqual(gate.observe()['allocation_remaining'], 90_000_000)

    def test_incremental_replay_refuses_rehashed_prior_prefix_and_derived_state(self):
        self.earn(); gate = self.allocator(); gate.observe()
        original = self.exchange.export
        forged = copy.deepcopy(original())
        forged['actions'][0]['args']['amount'] += 1
        forged['actions_sha256'] = digest(forged['actions'])
        self.exchange.export = lambda: forged
        try:
            with self.assertRaisesRegex(ValueError, 'PREVIOUSLY_AUDITED_PREFIX_CHANGED'):
                gate.observe()
        finally:
            self.exchange.export = original
        forged = copy.deepcopy(original()); forged['summary']['unrestrictedEarned'] += 1
        self.exchange.export = lambda: forged
        try:
            with self.assertRaisesRegex(ValueError, 'DERIVED_SUMMARY_MISMATCH'):
                gate.observe()
        finally:
            self.exchange.export = original
        self.assertTrue(gate.observe()['independent_native_replay'])

    def test_incremental_replay_rejects_configuration_substitution(self):
        self.earn(); gate = self.allocator(); gate.observe()
        original = self.exchange.export; forged = copy.deepcopy(original())
        forged['config']['working'] = 1
        self.exchange.export = lambda: forged
        try:
            with self.assertRaisesRegex(ValueError, 'CONFIG_CHANGED'):
                gate.observe()
        finally:
            self.exchange.export = original

    def test_duplicate_collection_does_not_change_money(self):
        self.earn(); gate = self.allocator(); before = gate.observe()['summary']
        self.exchange.execute('event', {'id': 'order', 'action': 'release', 'event_id': 'release'}, 3)
        self.assertEqual(gate.observe()['summary'], before)
        self.assertTrue(audit(self.exchange.export(), root=ROOT, manifest=self.manifest)['accepted'])

    @unittest.skipUnless(os.name == 'posix', 'Declared POSIX account ownership')
    def test_abrupt_full_exchange_owner_death_recovers_acknowledged_native_action(self):
        self.exchange.close()
        code = """import json,sys,time
from pathlib import Path
from commercial.single_writer import SingleWriterExchange
root=Path(sys.argv[2]); manifest=json.loads((root/'campaign/commercial-010/service/executed-002/manifest.json').read_bytes())
ex=SingleWriterExchange(Path(sys.argv[1]),root=root,manifest=manifest,opening=1000000000,working=0,contract='growth012-allocation-test')
ex.execute('cost',{'id':'survives-process-death','amount':123},0)
print('ACKNOWLEDGED',flush=True)
time.sleep(30)
"""
        process = subprocess.Popen([sys.executable, '-c', code, str(self.path), str(ROOT)],
                                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 8)[0])
            self.assertEqual(process.stdout.readline().strip(), 'ACKNOWLEDGED')
            with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'):
                self.open()
            process.kill(); process.wait(timeout=5)
            self.exchange = self.open()
            self.assertEqual(self.exchange.snapshot()['expenses'], 123)
            self.assertTrue(self.allocator().observe()['independent_native_replay'])
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
            process.stdout.close(); process.stderr.close()


if __name__ == '__main__':
    unittest.main()
