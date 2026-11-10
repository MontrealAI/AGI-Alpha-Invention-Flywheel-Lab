# SPDX-License-Identifier: Apache-2.0
"""Schema dependency drift must invalidate source-bound engineering proof."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import genesis_next, output_schema, strategy_demo, upgrade_foundry, workflow_schemas
from bridge.adapters import BridgeError
from scripts import probe_frontier_monitor, qualify_genesis_successor


class SchemaSourceClosureTests(unittest.TestCase):
    def test_loaded_schema_drift_invalidates_genesis_and_foundry_authority(self):
        for module in (workflow_schemas, output_schema):
            with self.subTest(module=module.__name__):
                name = Path(module.__file__).name
                expected = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                self.assertEqual(genesis_next.source_identity()[name], expected)
                self.assertEqual(upgrade_foundry._authority_manifest(None)['sources'][name], expected)
                with patch.object(module, 'LOADED_SOURCE_SHA256', '0' * 64):
                    with self.assertRaises(BridgeError) as error:
                        genesis_next.require_current_source()
                    self.assertEqual(error.exception.code, 'GENESIS_SOURCE_DRIFT')
                    with self.assertRaises(BridgeError) as error:
                        upgrade_foundry._authority_manifest(None)
                    self.assertEqual(error.exception.code, 'FOUNDRY_SOURCE_DRIFT')

    def test_changed_schema_bytes_invalidate_genesis_and_foundry_authority(self):
        for module in (workflow_schemas, output_schema):
            selected = Path(module.__file__)
            for owner, call, code in (
                (genesis_next, genesis_next.require_current_source, 'GENESIS_SOURCE_DRIFT'),
                (upgrade_foundry, lambda: upgrade_foundry._authority_manifest(None), 'FOUNDRY_SOURCE_DRIFT'),
            ):
                regular = owner._regular
                def changed(path, *args):
                    raw = regular(path, *args)
                    return raw + b'\n# simulated changed dependency\n' if Path(path) == selected else raw
                with self.subTest(module=module.__name__, owner=owner.__name__), patch.object(owner, '_regular', side_effect=changed):
                    with self.assertRaises(BridgeError) as error:
                        call()
                    self.assertEqual(error.exception.code, code)

    def test_changed_schema_bytes_invalidate_frozen_successor_before_evaluation(self):
        read_bytes = Path.read_bytes
        for label in ('workflow_schemas', 'output_schema'):
            selected = qualify_genesis_successor.PATHS[label]
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                freeze = Path(temporary) / 'freeze.json'
                output = Path(temporary) / 'result.json'
                qualify_genesis_successor.freeze(freeze)
                def changed(path):
                    raw = read_bytes(path)
                    return raw + b'\n# simulated changed dependency\n' if path == selected else raw
                with patch.object(Path, 'read_bytes', changed), patch.object(qualify_genesis_successor, 'generate') as generate:
                    with self.assertRaisesRegex(ValueError, 'changed after the source freeze'):
                        qualify_genesis_successor.qualify(freeze, output)
                generate.assert_not_called()
                self.assertFalse(output.exists())

    def test_fixture_and_frontier_receipts_bind_both_schema_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            paired = strategy_demo.demonstrate(Path(temporary) / 'paired')
            genesis = genesis_next.demonstrate(Path(temporary) / 'genesis')
        frontier = probe_frontier_monitor.source_identities()
        snapshot = upgrade_foundry._manifest(upgrade_foundry._snapshot(ROOT))
        for module in (workflow_schemas, output_schema):
            path = Path(module.__file__)
            key = path.relative_to(ROOT).as_posix()
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(paired['source_sha256'][key], expected)
            self.assertEqual(genesis['source']['dependency_sha256'][path.name], expected)
            self.assertEqual(frontier[key], expected)
            self.assertEqual(snapshot[key], expected)


if __name__ == '__main__':
    unittest.main()
