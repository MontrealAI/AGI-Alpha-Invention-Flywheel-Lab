"""Real canonical-account integration tests. No mocks of money or acceptance."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from genesis_enterprise import native
from genesis_enterprise.policy import canonical, digest

ROOT = Path(__file__).resolve().parents[1]
NATIVE_AVAILABLE = (ROOT / 'commercial/ledger.py').is_file()


@unittest.skipUnless(NATIVE_AVAILABLE, 'Full repository/native source required; no fake ledger fallback')
class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = self.base / 'operation'
        self.p = json.loads((ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json').read_text())

    def tearDown(self): self.tmp.cleanup()

    def register(self):
        path = self.base / 'protocol.json'
        path.write_bytes(canonical(self.p))
        return native.register(ROOT, self.workspace, path)

    def test_complete_earned_funded_episode_and_key_free_export(self):
        self.register()
        r = native.operate(self.workspace)
        self.assertTrue(r['complete'])
        self.assertTrue(r['conditional_self_funding'])
        self.assertGreater(r['earned_funded_deliveries'], 0)
        self.assertEqual(r['actual_revenue'], 0)
        (self.workspace / 'source/private-notes.txt').write_text('private-local-note')
        (self.workspace / 'public/access-token.txt').write_text('not-a-real-token')
        public = self.base / 'public-copy'
        native.export_public(self.workspace, public)
        self.assertFalse((public / 'private').exists())
        self.assertFalse((public / 'source/private-notes.txt').exists())
        self.assertFalse((public / 'public/access-token.txt').exists())
        self.assertEqual(native.audit(public), r)

    def test_checkpoint_resume_and_no_duplicate_settlement(self):
        self.register()
        r = native.operate(self.workspace, max_steps=3)
        self.assertFalse(r['complete'])
        complete = native.operate(self.workspace)
        before = (self.workspace / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.workspace), complete)
        self.assertEqual(before, (self.workspace / 'public/native-export.json').read_bytes())

    def test_interruption_after_release_recovers_same_native_event(self):
        self.register()
        fired = []
        def crash(phase, i):
            if phase == 'release' and not fired:
                fired.append(True)
                raise RuntimeError('INJECTED_INTERRUPTION_AFTER_COMMIT')
        with self.assertRaises(RuntimeError): native.operate(self.workspace, fault=crash)
        result = native.operate(self.workspace)
        tape = json.loads((self.workspace / 'public/native-export.json').read_text())['ledger']
        releases = [a for a in tape['actions'] if a['op'] == 'event' and a['args']['action'] == 'release']
        self.assertEqual(len(releases), len({a['args']['id'] for a in releases}))
        self.assertTrue(result['complete'])

    def test_registered_maturities_apply_before_each_successor_choice(self):
        self.register()
        r = native.operate(self.workspace)
        self.assertTrue(r['complete'])
        manifest = json.loads((self.workspace / 'MANIFEST.json').read_text())
        execution = json.loads((self.workspace / 'public/execution.json').read_text())
        tape = json.loads((self.workspace / 'public/native-export.json').read_text())['ledger']
        maturities = [a for a in tape['actions'] if a['op'] == 'mature']
        self.assertEqual([a['day'] for a in maturities], [24 * (i + 2) for i in range(len(manifest['jobs']))])
        self.assertEqual(len(maturities), len({a['args']['event_id'] for a in maturities}))
        self.assertEqual([row['decision']['selected']['price'] for row in execution['rows']],
                         [60000000] * len(manifest['jobs']))
        terms = {t['id']: json.loads(t['terms']) for t in tape['prospective_terms']}
        for row in tape['prospective_orders']:
            self.assertGreater(row['matured_at'], terms[row['terms_id']]['maturity_day'])

    def test_zero_overhead_maturity_snapshot_audits_and_resumes(self):
        self.p['acquisition'] = self.p['maintenance'] = 0
        self.register()
        fired = []
        def crash(phase, i):
            if phase == 'overhead' and i == 1 and not fired:
                fired.append(True)
                raise RuntimeError('INTERRUPTED_AFTER_DATED_MATURITY')
        with self.assertRaisesRegex(RuntimeError, 'INTERRUPTED_AFTER_DATED_MATURITY'):
            native.operate(self.workspace, fault=crash)
        r = native.operate(self.workspace)
        self.assertTrue(r['complete'])
        self.assertEqual(native.audit(self.workspace), r)
        before = (self.workspace / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.workspace), r)
        self.assertEqual((self.workspace / 'public/native-export.json').read_bytes(), before)
        tape = json.loads(before)['ledger']
        maturities = [a['args']['event_id'] for a in tape['actions'] if a['op'] == 'mature']
        self.assertEqual(len(maturities), len(set(maturities)))

    def test_exact_native_collateral_fee_and_production_boundary(self):
        self.p['offer']['prices'] = [30000000]
        self.p['opening'] = self.p['development'] + self.p['acquisition'] + self.p['maintenance'] + 35200000
        self.register()
        result = native.operate(self.workspace)
        self.assertTrue(result['complete'])
        execution = json.loads((self.workspace / 'public/execution.json').read_text())
        first = execution['rows'][0]
        self.assertEqual(first['decision_state']['available'], 35200000)
        self.assertEqual(first['decision']['selected']['price'], 30000000)
        self.assertTrue(first['accepted'])
        self.assertEqual(first['resource_receipt']['funding'], 'SEED')
        self.assertEqual(native.audit(self.workspace), result)

    def test_insufficient_order_collateral_declines_without_order(self):
        self.p['opening'] = self.p['development'] + self.p['acquisition'] + self.p['maintenance'] + 35199999
        self.register()
        result = native.operate(self.workspace)
        self.assertTrue(result['complete'])
        tape = json.loads((self.workspace / 'public/native-export.json').read_text())['ledger']
        self.assertFalse([a for a in tape['actions'] if a['op'] in ('offer', 'wallet')])
        self.assertEqual(result['accepted_collected_deliveries'], 0)
        self.assertEqual(result['actual_revenue'], 0)

    def test_refusal_is_zero_sales_and_a_real_modeled_loss(self):
        self.p['offer']['value'] = 0
        self.register()
        r = native.operate(self.workspace)
        self.assertEqual(r['accepted_collected_deliveries'], 0)
        self.assertLess(r['simulated_profit_microUSD'], 0)
        self.assertFalse(r['conditional_self_funding'])

    def test_copycat_outside_option_wins(self):
        self.p['offer']['rival'] = min(self.p['offer']['prices'])
        self.register()
        r = native.operate(self.workspace)
        self.assertEqual(r['accepted_collected_deliveries'], 0)

    def test_stop_before_any_paid_action(self):
        self.register()
        (self.workspace / 'STOP').touch()
        r = native.operate(self.workspace)
        self.assertFalse(r['complete'])
        self.assertEqual(r['simulated_profit_microUSD'], 0)
        (self.workspace / 'STOP').unlink()
        self.assertTrue(native.operate(self.workspace)['complete'])

    def test_frozen_source_change_rejected(self):
        self.register()
        with (self.workspace / 'source/genesis_enterprise/policy.py').open('a') as f: f.write('\n# changed\n')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'): native.operate(self.workspace)

    def test_changed_decision_report_rejected(self):
        self.register(); native.operate(self.workspace)
        path = self.workspace / 'public/execution.json'
        r = json.loads(path.read_text()); r['rows'][0]['decision']['selected']['price'] += 1
        path.write_bytes(canonical(r))
        with self.assertRaises(ValueError): native.audit(self.workspace)

    def test_changed_delivery_rejected(self):
        self.register(); native.operate(self.workspace)
        manifest = json.loads((self.workspace / 'MANIFEST.json').read_text())
        path = self.workspace / 'source' / manifest['jobs'][0]['delivery_path']
        path.write_text('{}')
        with self.assertRaises(ValueError): native.audit(self.workspace)

    def test_missing_operating_checkpoint_does_not_reseed(self):
        self.register(); native.operate(self.workspace, max_steps=3)
        path = self.workspace / 'private/STATE.json'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'CHECKPOINT_MISSING'): native.operate(self.workspace)

    def test_modified_protocol_cannot_resume(self):
        self.register(); native.operate(self.workspace, max_steps=3)
        p = self.p.copy(); p['opening'] += 1000000
        (self.workspace / 'PROTOCOL.json').write_bytes(canonical(p))
        with self.assertRaisesRegex(ValueError, 'REGISTRATION_CHANGED'): native.operate(self.workspace)


if __name__ == '__main__': unittest.main()
