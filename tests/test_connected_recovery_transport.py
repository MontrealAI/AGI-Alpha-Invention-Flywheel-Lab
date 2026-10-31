import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from connected_enterprise.runner import package

class PublicRecoveryTransportTests(unittest.TestCase):
    def test_rejected_intents_keep_exact_bytes_without_private_archive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'world';out.mkdir();p=out/'worlds/one/account.sqlite.rejected-operating-intents/intent.json';p.parent.mkdir(parents=True);p.write_bytes(b'{"preserved":"signed public intent"}\n')
            (out/'worlds/one/account.sqlite').write_bytes(b'private database')
            (out/'worlds/one/account.sqlite.adaptive-simulation-key').write_bytes(b'private key')
            archive=root/'public.zip'
            with patch('connected_enterprise.runner.read_freeze'),patch('connected_enterprise.runner.audit_output',return_value={'accepted':True}):package(out,archive)
            with zipfile.ZipFile(archive) as z:
                self.assertFalse(any('.sqlite' in n or n.endswith('.adaptive-simulation-key') for n in z.namelist()))
                name='worlds/one/public-rejected-operating-intents/intent.json';self.assertEqual(z.read(name),p.read_bytes())
                record=json.loads(z.read('PUBLIC_RECOVERY_INDEX.json'))['files'][name]
                self.assertEqual(record['original_path'],p.relative_to(out).as_posix());self.assertEqual(record['bytes'],len(p.read_bytes()))
            self.assertEqual(p.read_bytes(),b'{"preserved":"signed public intent"}\n')

if __name__=='__main__':unittest.main()
