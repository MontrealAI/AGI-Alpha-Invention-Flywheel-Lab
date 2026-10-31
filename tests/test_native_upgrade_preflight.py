import json
from pathlib import Path
import tempfile
import unittest

from connected_enterprise.upgrades import MAX_TICKET_BYTES,preflight_ticket_size


class NativeUpgradePreflightTests(unittest.TestCase):
    def test_oversized_history_is_rejected_without_changing_authority_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);journal=root/'account.sqlite.connected-journal.json'
            journal.write_text(json.dumps({'body':{'source_history':[{'preserved':'x'*(MAX_TICKET_BYTES//2)}]},'signature':'0'*64}))
            operator=root/'OPERATOR.json';operator.write_bytes(b'original operator bytes\n')
            before={p.name:p.read_bytes() for p in root.iterdir()}
            with self.assertRaisesRegex(ValueError,'SOURCE_UPGRADE_EXCEEDS_EXISTING_TICKET_BOUND'):preflight_ticket_size(root)
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})

    def test_small_payload_is_only_a_size_preflight_and_cannot_confer_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);journal=root/'account.sqlite.connected-journal.json'
            journal.write_text(json.dumps({'body':{'source_history':[]},'signature':'invalid'}))
            size=preflight_ticket_size(root)
            self.assertLess(size,MAX_TICKET_BYTES)
            self.assertEqual(MAX_TICKET_BYTES,16_000_000)
            self.assertFalse((root/'MIGRATION_INTENT.json').exists())


if __name__=='__main__':unittest.main()
