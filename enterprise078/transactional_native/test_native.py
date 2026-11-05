import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from .stage import stage


class NativeSQLTests(unittest.TestCase):
    def test_fresh_native_sql(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            source=stage(root,Path(tmp)/'prospective')
            p=subprocess.run([sys.executable,'-m','enterprise078.transactional_native.fixture'],cwd=source,
                env=dict(os.environ,PYTHONPATH=str(source)),text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            result=json.loads(p.stdout);self.assertEqual(len(result['checks']),4)
            self.assertTrue(result['accepted']);self.assertFalse(result['original_catalog_transition'])

if __name__=='__main__':unittest.main()
