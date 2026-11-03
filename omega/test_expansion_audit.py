"""Independent market/native binding and operating-observation tamper tests."""
from __future__ import annotations
import copy
from pathlib import Path
import tempfile
import unittest

from omega.expansion_audit import RecordingBridge, audit_market
from omega.expansion_market import MarketRunner, config, worlds
from omega.expansion_native import NativeBridge, default_config


class OperatingAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.world = worlds()['capability_gap']
        cls.world.update(need_bps=10000, reach_bps=10000, activation_bps=10000,
                         budget_cents=[100000], payment_bps=10000,
                         delivery_bps=10000, refund_bps=0, collection_delay_hours=0)
        cls.settings = config(horizon_days=3, cadence_days=2, initial_contacts=2)
        cfg = default_config(); cfg.update(operating_hours=72, claim_hours=1, engineering_fixture=True)
        with NativeBridge(Path(cls.temp.name) / 'account', config=cfg) as native:
            runner = MarketRunner(cls.world, mode='joint', seed=17, settings=cls.settings)
            recorder = RecordingBridge(native)
            recorder.begin_segment(runner.state)
            runner.run(recorder)
            recorder.end_segment(runner.export())
            cls.state, cls.trace = runner.export(), recorder.export()
            native.finish()
            cls.record = native.account.export()
            cls.root, cls.manifest = native.source, native.manifest

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def audit(self, trace=None, state=None, world=None):
        return audit_market(world or self.world, 'joint', 17, self.settings,
                            state or self.state, trace or self.trace, self.record,
                            root=self.root, manifest=self.manifest)

    def test_native_prefixes_and_complete_market_replay_accept(self):
        result = self.audit()
        self.assertTrue(result['accepted'])
        self.assertGreater(result['order_requests'], 0)
        self.assertGreater(result['funded_work'], 0)

    def test_fabricated_available_cash_cannot_change_policy(self):
        trace = copy.deepcopy(self.trace)
        row = next(r for r in trace['calls'] if r[0] == 'snapshot')
        trace['values'][row[3]]['available_cents'] += 1
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_OBSERVATION_NOT_NATIVE_PREFIX'):
            self.audit(trace=trace)

    def test_changed_private_buyer_world_cannot_keep_accepted_orders(self):
        world = copy.deepcopy(self.world); world['need_bps'] = 0
        with self.assertRaises(ValueError):
            self.audit(world=world)

    def test_native_spend_cannot_be_removed_from_operating_history(self):
        trace = copy.deepcopy(self.trace)
        row = next(r for r in trace['calls'] if r[0] == 'spend')
        trace['values'].append(False); row[3] = len(trace['values']) - 1
        with self.assertRaisesRegex(ValueError, 'COMMITTED_COST_REPORTED_UNFUNDED'):
            self.audit(trace=trace)

    def test_recorded_collections_cannot_be_observed_before_native_release(self):
        trace = copy.deepcopy(self.trace)
        row = next(r for r in trace['calls'] if r[0] == 'deliver')
        receipt = copy.deepcopy(trace['values'][row[3]])
        receipt['collected_cents'] += 1
        trace['values'].append(receipt); row[3] = len(trace['values']) - 1
        with self.assertRaisesRegex(ValueError, 'FUTURE_OR_FICTITIOUS_COLLECTION_OBSERVED'):
            self.audit(trace=trace)

    def test_invented_prebuilt_initial_state_is_rejected(self):
        trace = copy.deepcopy(self.trace)
        trace['segments'][0]['initial_state']['built'] = True
        with self.assertRaisesRegex(ValueError, 'UNAUTHORED_INITIAL_OR_RECOVERY_STATE'):
            self.audit(trace=trace)

    def test_available_native_cash_cannot_be_falsely_called_unfunded(self):
        trace = copy.deepcopy(self.trace)
        first = len(trace['values'])
        trace['values'].extend([['artificially-disabled', 1, 0, 'build'], {}, False])
        trace['calls'].insert(0, ['spend', first, first + 1, first + 2, 0, 0, 0, 0])
        trace['segments'][0]['end_call'] += 1
        with self.assertRaisesRegex(ValueError, 'AVAILABLE_FUNDING_FALSELY_REJECTED'):
            self.audit(trace=trace)

    def test_affordable_voluntary_order_cannot_be_falsely_deferred(self):
        trace = copy.deepcopy(self.trace)
        request = {'id': 'artificial-deferral', 'buyer': 'new-buyer', 'budget_cents': 100000,
                   'price_cents': 29900, 'hour': 0, 'collection_delay_hours': 0,
                   'choice': True, 'acquired': True, 'pay': True, 'accept': True,
                   'delivery_ok': True}
        returned = {'request': request, 'status': 'liquidity_deferred', 'collected': False,
                    'collected_cents': 0, 'contribution_cents': 0}
        first = len(trace['values'])
        trace['values'].extend([[request], {}, returned])
        trace['calls'].insert(0, ['deliver', first, first + 1, first + 2, 0, 0, 0, 0])
        trace['segments'][0]['end_call'] += 1
        with self.assertRaisesRegex(ValueError, 'AFFORDABLE_ORDER_FALSELY_DEFERRED'):
            self.audit(trace=trace)

    def test_interrupted_segment_replays_with_same_native_account(self):
        class Interrupted(RuntimeError):
            pass
        saved = {}
        cfg = default_config(); cfg.update(operating_hours=72, claim_hours=1, engineering_fixture=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'same-account'
            def checkpoint(state):
                saved['state'] = copy.deepcopy(state)
            def persist(trace):
                saved['trace'] = copy.deepcopy(trace)
                if (not saved.get('interrupted') and trace['pending'] is None
                        and trace['calls'] and trace['calls'][-1][0] == 'deliver'):
                    saved['interrupted'] = True
                    raise Interrupted('after native delivery, before market checkpoint')
            with NativeBridge(path, config=cfg) as native:
                runner = MarketRunner(self.world, mode='joint', seed=17, settings=self.settings)
                recording = RecordingBridge(native, persist=persist)
                recording.begin_segment(runner.state)
                with self.assertRaises(Interrupted):
                    runner.run(recording, checkpoint)
                prefix = native.account.export()['ledger']['actions']
            with NativeBridge(path, resume=True) as native:
                runner = MarketRunner(self.world, mode='joint', seed=17,
                                      settings=self.settings, state=saved['state'])
                recording = RecordingBridge(native, trace=saved['trace'], persist=persist)
                recording.begin_segment(runner.state)
                runner.run(recording, checkpoint)
                recording.end_segment(runner.export())
                native.finish()
                record = native.account.export()
                self.assertEqual(record['ledger']['actions'][:len(prefix)], prefix)
                result = audit_market(self.world, 'joint', 17, self.settings, runner.export(),
                                      recording.export(), record, root=native.source,
                                      manifest=native.manifest)
                self.assertTrue(result['accepted'])
                self.assertEqual(result['segments'], 2)


if __name__ == '__main__':
    unittest.main()
