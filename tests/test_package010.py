import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import package_commercial010 as package


class Commercial010PaperClosureTests(unittest.TestCase):
    def test_newly_bound_script_cannot_be_omitted_from_distribution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source'
            for name in ['campaign/commercial-010/SOURCE_FREEZE.json',
                         'campaign/commercial-010/POLICY.json', 'docs/commercial010/paper.pdf']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'unit transport fixture')
            script=root/'scripts/newly_bound_paper_input.py'
            script.parent.mkdir();script.write_bytes(b'unit_input = 1\n')
            manifest={'sources':{'scripts/newly_bound_paper_input.py':hashlib.sha256(script.read_bytes()).hexdigest()}}
            (root/'docs/commercial010/SOURCE_MANIFEST.json').write_text(json.dumps(manifest))
            output=Path(folder)/'refused.zip'
            with patch.object(package,'FILES',[]), patch.object(package,'PREFIXES',['campaign','docs']):
                with self.assertRaisesRegex(ValueError,'INCOMPLETE_COMMERCIAL_DISTRIBUTION.*newly_bound_paper_input'):
                    package.build(root,output,'a'*40)
            self.assertFalse(output.exists())
