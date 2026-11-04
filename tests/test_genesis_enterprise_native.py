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
