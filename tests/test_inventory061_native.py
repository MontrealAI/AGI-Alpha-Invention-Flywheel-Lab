"""Fresh funded engineering produces a real policy, then checks and releases it."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import canonical
from connected_enterprise.finance import SOURCE_PATHS
from inventory061 import service
from inventory061.native import audit_export
from inventory061.operate import operate, reopen

ROOT = Path(__file__).resolve().parents[1]


class Inventory061NativeTests(unittest.TestCase):
    def test_funded_actual_construction_acceptance_release_reopen_and_tamper(self):
        with tempfile.TemporaryDirectory(prefix='inventory061-qualified-') as tmp:
            root, state = Path(tmp)/'source', Path(tmp)/'private-state'
            for name in sorted(set(SOURCE_PATHS) | set(service.SOURCES)):
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, target)
            self.assertFalse((root/'inventory061/deliveries/conditional').exists())
            report = operate(root, state)
            self.assertEqual(report['economics']['fixed_price_usd'], 5000)
            self.assertIsNone(report['economics']['actual_total_AI_billing_usd'])
            self.assertEqual(report['production']['exit_code'], 0)
            self.assertTrue(report['acceptance']['accepted'])
            self.assertTrue(report['acceptance']['additional_quality95']['accepted'])
            self.assertTrue(report['native_audit']['accepted'])
            self.assertLess(report['summary']['profit'], 0)
            export = json.loads((state/'public-native-export.json').read_text())
            self.assertEqual(export['ledger']['summary']['revenue'], 5_000_000_000)
            started = json.loads((state/'production.started.json').read_text())
            self.assertTrue(started['funded_before_start'])
            self.assertTrue(started['delivery_directory_absent_before_start'])
            actions = export['ledger']['actions']
            prepares = [i for i,a in enumerate(actions) if a['op']=='event' and a['args']['action']=='prepare']
            self.assertEqual(len(prepares), 1)
            self.assertGreaterEqual(prepares[0], started['native_action_count_before_start'])
            manifest = json.loads((state/'manifest.json').read_text())
            path = root/manifest['jobs'][0]['delivery_path']
            artifact = json.loads(path.read_text())
            self.assertEqual(len(artifact['inventory_policy']),54)
            self.assertEqual(len(artifact['cdc_service_time']),6)
            self.assertTrue(reopen(root,state)['same_export_bytes'])
            self.assertTrue(audit_export(export,root=root,manifest=manifest)['accepted'])
            before = path.read_bytes()
            changed = copy.deepcopy(artifact)
            changed['inventory_policy'][0]['parameters'][next(iter(changed['inventory_policy'][0]['parameters']))] += 1
            try:
                path.write_bytes(canonical(changed))
                with self.assertRaisesRegex(ValueError,'ACTUAL_DELIVERY_HASH_CHANGED'):
                    audit_export(export,root=root,manifest=manifest)
            finally:
                path.write_bytes(before)
            self.assertTrue(audit_export(export,root=root,manifest=manifest)['accepted'])


if __name__=='__main__':
    unittest.main()
