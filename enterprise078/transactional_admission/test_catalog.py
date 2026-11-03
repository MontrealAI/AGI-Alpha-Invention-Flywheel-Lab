import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from enterprise078.runtime import materialize


class CatalogPreparationTests(unittest.TestCase):
    def test_fresh_native_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=materialize(Path(__file__).resolve().parents[2],Path(tmp)/'science')
            r=subprocess.run([sys.executable,str(Path(__file__).with_name('catalog_fixture.py'))],
                             cwd=source,env=dict(os.environ,PYTHONPATH=str(source)),
                             capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            result=json.loads(r.stdout)
            self.assertTrue(result['accepted']);self.assertEqual(len(result['checks']),9)
            self.assertFalse(result['native_catalog_admitted'])


if __name__=='__main__':unittest.main()
