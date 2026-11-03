"""Read coalescing must preserve the original recorder and native operation."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from omega.expansion_audit import RecordingBridge, audit_market
from omega.expansion_market import MarketRunner, config, worlds
from omega.expansion_native import NativeBridge, default_config
from omega.recording_cache import make_recording_bridge
from omega.test_expansion_native import order


def fixture():
    world = worlds()['capability_gap']
    world.update(need_bps=10000, reach_bps=10000, activation_bps=10000,
                 budget_cents=[100000], payment_bps=10000, delivery_bps=10000,
                 refund_bps=0, collection_delay_hours=0)
    settings = config(horizon_days=4, cadence_days=2, initial_contacts=2)
    cfg = default_config()
    cfg.update(operating_hours=96, claim_hours=1, engineering_fixture=True)
    return world, settings, cfg


class RecordingCacheTests(unittest.TestCase):
    def test_same_native_actions_decisions_and_exact_public_trace_as_reference(self):
        world, settings, cfg = fixture()
        results, counts = [], []
        with tempfile.TemporaryDirectory() as directory:
            for name, coalesced in [('reference', False), ('coalesced', True)]:
                with NativeBridge(Path(directory) / name, config=cfg) as native:
                    runner = MarketRunner(world, mode='joint', seed=17, settings=settings)
                    with patch.object(native, 'snapshot', wraps=native.snapshot) as observed:
                        recorder = make_recording_bridge(RecordingBridge, native) if coalesced else RecordingBridge(native)
                        recorder.begin_segment(runner.export())
                        runner.run(recorder)
                        recorder.end_segment(runner.export())
                        counts.append(observed.call_count)
                    native.finish()
                    record, trace = native.account.export(), recorder.export()
                    checked = audit_market(world, 'joint', 17, settings, runner.export(), trace,
                                           record, root=native.source, manifest=native.manifest)
                    self.assertTrue(checked['accepted'])
                    results.append((runner.export(), trace, record['ledger']['actions'], record['ledger']['summary']))
            self.assertEqual(results[0], results[1])
            self.assertLess(counts[1], counts[0])

    def test_repeated_reads_private_copies_and_mutations_invalidate(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as native:
                recorder = make_recording_bridge(RecordingBridge, native)
                with patch.object(native, 'snapshot', wraps=native.snapshot) as observed:
                    first = recorder.snapshot()
                    first['available_cents'] = -1
                    second = recorder.snapshot()
                    self.assertGreater(second['available_cents'], 0)
                    self.assertEqual(observed.call_count, 1)
                    self.assertTrue(recorder.spend('cost', 1, 0, 'research'))
                    after_spend = recorder.snapshot()
                    self.assertLess(after_spend['cash_cents'], second['cash_cents'])
                    recorder.deliver(order('delayed', hour=1, collection_delay_hours=2))
                    self.assertFalse(recorder.order_receipt('delayed')['collected'])
                    recorder.advance(3)
                    self.assertTrue(recorder.order_receipt('delayed')['collected'])
                    before_reads = observed.call_count
                    for _ in range(20):
                        recorder.order_receipt('delayed')
                        recorder.snapshot()
                    self.assertEqual(observed.call_count, before_reads)

    def test_unrouted_mutation_is_refused_and_does_not_become_cached_funding(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as native:
                recorder = make_recording_bridge(RecordingBridge, native)
                recorder.snapshot()
                native.account.cost('unsupported-direct-cost', 10000, 0)
                with self.assertRaisesRegex(ValueError, 'UNROUTED_NATIVE_MUTATION'):
                    recorder.snapshot()
                # A second read must not silently reset the same poisoned proxy.
                with self.assertRaisesRegex(ValueError, 'UNROUTED_NATIVE_MUTATION'):
                    recorder.native.snapshot()
                fresh = make_recording_bridge(RecordingBridge, native)
                self.assertEqual(fresh.snapshot(), native.snapshot())

    def test_ownership_source_and_rejected_mutation_checks_remain_live(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as native:
                recorder = make_recording_bridge(RecordingBridge, native)
                expected = recorder.snapshot()
                with patch.object(native.account, '_assert_current', side_effect=ValueError('SOURCE_CHANGED')):
                    with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                        recorder.snapshot()
                # New recorder: the old one has an unfinished read after error,
                # exactly as the original recorder's recovery contract requires.
                recorder = make_recording_bridge(RecordingBridge, native)
                self.assertFalse(recorder.spend('not-funded', expected['available_cents'] + 1, 0, 'research'))
                self.assertEqual(recorder.snapshot(), native.snapshot())

    def test_pending_call_recovers_fresh_against_same_native_authority(self):
        class Interrupted(RuntimeError):
            pass
        world, settings, cfg = fixture()
        saved = {}
        def checkpoint(state):
            saved['state'] = copy.deepcopy(state)
        def persist(trace):
            saved['trace'] = copy.deepcopy(trace)
            if (not saved.get('interrupted') and trace['pending'] is not None
                    and trace['pending']['method'] == 'deliver'):
                saved['interrupted'] = True
                raise Interrupted('durable delivery intent before native mutation')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'same-account'
            with NativeBridge(path, config=cfg) as native:
                runner = MarketRunner(world, mode='joint', seed=17, settings=settings)
                recorder = make_recording_bridge(RecordingBridge, native, persist=persist)
                recorder.begin_segment(runner.export())
                with self.assertRaises(Interrupted):
                    runner.run(recorder, checkpoint)
                prefix = copy.deepcopy(native.account.export()['ledger']['actions'])
            with NativeBridge(path, resume=True) as native:
                runner = MarketRunner(world, mode='joint', seed=17, settings=settings, state=saved['state'])
                with patch.object(native, 'snapshot', wraps=native.snapshot) as observed:
                    recorder = make_recording_bridge(RecordingBridge, native, trace=saved['trace'], persist=persist)
                    self.assertGreater(observed.call_count, 0)
                recorder.begin_segment(runner.export())
                runner.run(recorder, checkpoint)
                recorder.end_segment(runner.export())
                native.finish()
                record = native.account.export()
                self.assertEqual(record['ledger']['actions'][:len(prefix)], prefix)
                checked = audit_market(world, 'joint', 17, settings, runner.export(), recorder.export(),
                                       record, root=native.source, manifest=native.manifest)
                self.assertTrue(checked['accepted'])
                self.assertEqual(checked['segments'], 2)


if __name__ == '__main__':
    unittest.main()
